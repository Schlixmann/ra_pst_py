from docplex.cp.model import *
import json
import random
from math import comb

import gurobipy as gp
from gurobipy import GRB


def cp_solver_decomposed_monotone_cuts(ra_pst_json, TimeLimit = None):
    """
    ra_pst_json input format:
    {
        "resources": [resourceId],
        "instances": [
            {
                "tasks": { 
                    taskId: {
                        "branches": [branchId]
                    }
                },
                "resources": [resourceId],
                "branches": {
                    branchId: {
                        "task": taskId,
                        "jobs": [jobId],
                        "deletes": [taskId],
                        "branchCost": cost
                    }
                },
                "jobs": {
                    jobId: {
                        "branch": branchId,
                        "resource": resourceId,
                        "cost": cost,
                        "after": [jobId],
                        "instance": instanceId,
                        "min_start_time": int
                    }
                }
            }
        ]
    }
    """
    with open(ra_pst_json, "r") as f:
        ra_psts = json.load(f)

    # Fix taskIds for deletes: 
    for i, instance in enumerate(ra_psts["instances"]):
        if "fixed" not in instance.keys():
            instance["fixed"] = False
        inst_prefix = str(list(instance["tasks"].keys())[0]).split("-")[0]
        for key, value in instance["branches"].items():
            value["deletes"] = [str(inst_prefix) + f"-{element}"for element in value["deletes"]]
    
    #-----------------------------------------------------------------------------
    # Build the model
    #-----------------------------------------------------------------------------
    lower_bound = 0
    big_number = 0
    all_jobs = []
    for ra_pst in ra_psts["instances"]:
        for branch in ra_pst["branches"].values():
            big_number += branch["branchCost"]
    upper_bound = big_number

    master_model, z, E, Q, Y = ilp_masterproblem(ra_psts, upper_bound)

    start_time = time.time()

    best_schedule = None
    best_jobs = None

    counter = 0
    # Solve decomposed problem
    while (upper_bound - lower_bound)/upper_bound > 0.001: # Gap of .1
        print(f"{counter:4.0f}: Lower bound: {lower_bound}, upper bound: {upper_bound}. Gap {100*(upper_bound-lower_bound)/upper_bound:.2f}%")
        # Solve master problem
        master_model.optimize()
        lower_bound = master_model.objVal
        if lower_bound < upper_bound:
            # Iterate through instances to include 
            selected_branches_extended = []
            for ra_pst in ra_psts["instances"]:
                selected_branches_extended.extend([branchId for branchId, branch in ra_pst["branches"].items() if branch["selected"].x])
            schedule, all_jobs = cp_subproblem(ra_psts, selected_branches_extended)
            # Solved subproblem: Set new upper bound
            if schedule.get_objective_value() < upper_bound:
                upper_bound = schedule.get_objective_value()
                # Set new best solution
                best_schedule = schedule
                best_jobs = all_jobs
            # Add monotone cut
            master_model.addConstr(z >= schedule.get_objective_value() - (schedule.get_objective_value() - lower_bound) * gp.quicksum(1-branch["selected"] for ra_pst in ra_psts["instances"] for branchId, branch in ra_pst["branches"].items() if int(branch["selected"].x)))

        counter += 1
        if TimeLimit is not None and time.time() - start_time > TimeLimit:
            break

    # Output the current schedule
    for ra_pst in ra_psts["instances"]:
        for jobId, job in ra_pst["jobs"].items():
            job["selected"] = 0
            job["start"] = 0
            for interval in best_jobs:
                itv = best_schedule.get_var_solution(interval)
                if jobId == itv.get_name():
                    job["selected"] = 1
                    job["start"] = itv.get_start()
                    break
    for ra_pst in ra_psts["instances"]:
        for branchId, branch in ra_pst["branches"].items():
            del branch["selected"]

    # solve_details = result.get_solver_infos()
    ra_psts["solution"] = {
        "objective": upper_bound,
        "solver status": '?',
    }
                
    print(f"Lower bound: {lower_bound}, upper bound: {upper_bound}. Gap {100*(upper_bound-lower_bound)/upper_bound:.2f}%")

    return ra_psts


def cp_solver_decomposed_strengthened_cuts(ra_pst_json, warm_start_json=None, log_file = "cpo_solver.log", TimeLimit=100, break_symmetries:bool=False, sigma:int=0):
    """
    ra_pst_json input format:
    {
        "resources": [resourceId],
        "instances": [
            {
                "tasks": { 
                    taskId: {
                        "branches": [branchId]
                    }
                },
                "resources": [resourceId],
                "branches": {
                    branchId: {
                        "task": taskId,
                        "jobs": [jobId],
                        "deletes": [taskId],
                        "branchCost": cost
                    }
                },
                "jobs": {
                    jobId: {
                        "branch": branchId,
                        "resource": resourceId,
                        "cost": cost,
                        "after": [jobId],
                        "instance": instanceId,
                        "min_start_time": int
                    }
                }
            }
        ]
    }
    """
    with open(ra_pst_json, "r") as f:
        ra_psts = json.load(f)

    # Fix taskIds for deletes: 
    for i, instance in enumerate(ra_psts["instances"]):
        if "fixed" not in instance.keys():
            instance["fixed"] = False
        #inst_prefix = str(list(instance["tasks"].keys())[0]).split("-")[0]
        #for key, value in instance["branches"].items():
        #    value["deletes"] = [str(inst_prefix) + f"-{element}"for element in value["deletes"]]
    
    #-----------------------------------------------------------------------------
    # Build the model
    #-----------------------------------------------------------------------------
    lower_bound = 0
    big_number = 0
    for ra_pst in ra_psts["instances"]:
        for branch in ra_pst["branches"].values():
            big_number += branch["branchCost"]
    upper_bound = big_number

    master_model, z, E, Q, Y = ilp_masterproblem(ra_psts, upper_bound)

    best_schedule = None
    best_jobs = None
    best_branches = None

    starting_time = time.time()

    counter = 0
    # Solve decomposed problem
    while (upper_bound - lower_bound)/upper_bound > 0.001: # Gap of .1
        if counter > 0:
            print("\033[A\033[K", end="")  # Move up one line and clear it
        print(f"{counter:4.0f}: Lower bound: {lower_bound:.0f}, upper bound: {upper_bound:.0f}. Gap {100*(upper_bound-lower_bound)/upper_bound:.2f}%")
        # Solve master problem
        master_model.optimize()
        lower_bound = master_model.objVal
        if lower_bound < upper_bound:
            # Iterate through instances to include 
            configuration_branches = []
            selected_branches_extended = []
            for i, ra_pst in enumerate(ra_psts["instances"]):
                for branchId, branch in ra_pst["branches"].items():
                    if type(branch["selected"]) is int:
                        if branch["selected"]:
                            selected_branches_extended.append(branchId)
                    elif branch["selected"].x:
                        selected_branches_extended.append(branchId)
                # selected_branches_extended.extend([branchId for branchId, branch in ra_pst["branches"].items() if (not type(branch["selected"]) is int and branch["selected"].x or branch["selected"])] )
                instance_resource_list = []
                for branchId, branch in ra_pst["branches"].items():
                    if type(branch["selected"]) is int:
                        if branch["selected"]:
                            instance_resource_list.extend([ra_pst["jobs"][jobId]["resource"] for jobId in branch["jobs"] for _ in range(int(ra_pst["jobs"][jobId]["cost"]))])
                    elif branch["selected"].x:
                        instance_resource_list.extend([ra_pst["jobs"][jobId]["resource"] for jobId in branch["jobs"] for _ in range(int(ra_pst["jobs"][jobId]["cost"]))])
                # instance_resource_list = [ra_pst["jobs"][jobId]["resource"] for branchId, branch in ra_pst["branches"].items() if (not type(branch["selected"]) is int and branch["selected"].x or branch["selected"]) for jobId in branch["jobs"] for _ in range(int(ra_pst["jobs"][jobId]["cost"]))]
                config_branches = []
                for branchId, branch in ra_pst["branches"].items():
                    if type(branch["selected"]) is int:
                        if branch["selected"]:
                            config_branches.append(branchId)
                    elif branch["selected"].x:
                        config_branches.append(branchId)
                configuration_branches.append({
                    "instance": i,
                    "branches": config_branches,
                    "resources": [{resource: instance_resource_list[t:].count(resource) for resource in ra_psts["resources"]} for t in range(len(instance_resource_list)+1)]
                    })
            full_resource_lb = 0
            for r in range(len(ra_psts["instances"]), 1, -1):
                added_cut = False
                for combination in itertools.combinations(configuration_branches, r):
                    max_length = max(len(c["resources"]) for c in combination)
                    resource_lb = [max([t + sum(c["resources"][t][resource] for c in combination if t < len(c["resources"])) for t in range(max_length)]) for resource in ra_psts["resources"]]

                    subproblem_lb = max(resource_lb)

                    if subproblem_lb > lower_bound:
                        # Add strengthened cuts
                        master_model.addConstr(z >= subproblem_lb - (subproblem_lb - lower_bound) * gp.quicksum(1 - ra_psts["instances"][c["instance"]]["branches"][branchId]["selected"] for c in combination for branchId in c["branches"]))
                        added_cut = True
                        if r == len(ra_psts["instances"]):
                            full_resource_lb = subproblem_lb
                if not added_cut: break

            schedule, all_jobs = cp_subproblem(ra_psts, selected_branches_extended, lower_bound=full_resource_lb, sigma=sigma)
            # Solved subproblem: Set new upper bound
            if schedule.get_objective_value() <= upper_bound:
                upper_bound = schedule.get_objective_value()
                best_schedule = schedule
                best_jobs = all_jobs
                best_branches = selected_branches_extended
            master_model.addConstr(z >= schedule.get_objective_value() - (schedule.get_objective_value() - lower_bound) * gp.quicksum(1-branch["selected"] for ra_pst in ra_psts["instances"] for branchId, branch in ra_pst["branches"].items() if not ra_pst["fixed"] and int(branch["selected"].x)))

        counter += 1
        if TimeLimit is not None and time.time() - starting_time > TimeLimit:
            print(f'Time limit reached...')
            break
        # for resourceId, e in E.items():
        #     print(f'E_{resourceId}: {e.X}')

    for ra_pst in ra_psts["instances"]:
        if ra_pst["fixed"]: continue
        for jobId, job in ra_pst["jobs"].items():
            job["selected"] = 0
            job["start"] = 0
            if best_jobs is None: 
                continue
            for interval in best_jobs:
                itv = best_schedule.get_var_solution(interval)
                if jobId == itv.get_name():
                    job["selected"] = 1
                    job["start"] = itv.get_start()
                    # print(f'Job {jobId} on resource {job["resource"]} selected at {job["start"]} to {job["start"] + job["cost"]}')
                    break
    
    for ra_pst in ra_psts["instances"]:
        if ra_pst["fixed"]: continue
        for branchId, branch in ra_pst["branches"].items():
            if branchId in best_branches:
                branch["selected"] = 1
                continue
            branch["selected"] = 0
        ra_pst["fixed"] = True

    # solve_details = result.get_solver_infos()
    ra_psts["solution"] = {
        "objective": upper_bound,
        "solver status": '?',
        "lower_bound": lower_bound
    }
                
    print(f"Lower bound: {lower_bound}, upper bound: {upper_bound}. Gap {100*(upper_bound-lower_bound)/upper_bound:.2f}%")

    return ra_psts


def ilp_masterproblem(ra_psts, upper_bound):
    master_model = gp.Model('master')
    master_model.setParam('OutputFlag', False)
    z = master_model.addVar()
    # Branch variables
    for ra_pst in ra_psts["instances"]:
        if ra_pst["fixed"]: continue
        for branchId, branch in ra_pst["branches"].items():
            branch["selected"] = master_model.addVar(vtype=(GRB.BINARY), name=branchId)
    # Add constraints
    for ra_pst in ra_psts["instances"]:
        for branchId, branch in ra_pst["branches"].items():
            independent_branches = []
            for branch_2_id, branch_2 in ra_pst["branches"].items():
                if branch_2["task"] == branch["task"] or branch["task"] in branch_2["deletes"]:
                    independent_branches.append(branch_2_id)
            # master_model.add(sum([ra_pst["branches"][b_id]["selected"] for b_id in independent_branches]) == 1)
            master_model.addConstr(gp.quicksum([ra_pst["branches"][b_id]["selected"] for b_id in independent_branches]) == 1)
            branch_jobs = {}
            for resource in ra_psts["resources"]:
                branch_jobs[resource] = 0
            for jobId in branch["jobs"]:
                branch_jobs[ra_pst["jobs"][jobId]["resource"]] += ra_pst["jobs"][jobId]["cost"]
            branch["branch_jobs"] = branch_jobs
        master_model.addConstr(z >= gp.quicksum(branch["branchCost"] * branch["selected"] for branch in ra_pst["branches"].values()))
    # Find the minimum release time of any selected job on resource r. 
    Y = {}
    E = {}
    Q = {}
    for resource in ra_psts["resources"]:
        Y[resource] = master_model.addVar(vtype=(GRB.BINARY), name=f'Y_{resource}')
        E[resource] = master_model.addVar(vtype=(GRB.CONTINUOUS), name=f'E_{resource}')
        Q[resource] = {}
    for ra_pst in ra_psts["instances"]:
        for branchId, branch in ra_pst["branches"].items():
            past_resources = []
            branch_cost = 0
            release_times = {resource: 0 for resource in ra_psts["resources"]}
            for jobId in branch["jobs"]:
                if ra_pst["jobs"][jobId]["resource"] in past_resources: continue
                past_resources.append(ra_pst["jobs"][jobId]["resource"])
                release_times[ra_pst["jobs"][jobId]["resource"]] = branch_cost
                branch_cost += ra_pst["jobs"][jobId]["cost"]
            branch["resources"] = past_resources
            branch["release_times"] = release_times
            for resource in ra_psts["resources"]:
                Q[resource][branchId] = master_model.addVar(vtype=(GRB.CONTINUOUS), name=f'Q_{resource}_{branchId}')
    # Constraints
    for ra_pst in ra_psts["instances"]:
        for branchId, branch in ra_pst["branches"].items():
            for jobId in branch["jobs"]:
                master_model.addConstr(Y[ra_pst["jobs"][jobId]["resource"]] >= branch["selected"])
                master_model.addConstr(Q[ra_pst["jobs"][jobId]["resource"]][branchId] <= branch["selected"])
    for resource in ra_psts["resources"]:
        master_model.addConstr(gp.quicksum(Q[resource][branchId] for ra_pst in ra_psts["instances"] for branchId, branch in ra_pst["branches"].items() if resource in branch["resources"]) == Y[resource])
        for ra_pst in ra_psts["instances"]:
            for i, branch in enumerate(ra_pst["branches"].values()):
                master_model.addConstr(E[resource] >= gp.quicksum(branchPred["branchCost"] * branchPred["selected"] for b, branchPred in enumerate(ra_pst["branches"].values()) if b < i) + branch["release_times"][resource]*branch["selected"] - upper_bound*(1 - Q[resource][branchId]))
    # Get the maximum bin size of the selected branches
    master_model.addConstrs(z >= E[r] + gp.quicksum(branch["selected"] * branch["branch_jobs"][r] for ra_pst in ra_psts["instances"] for branch in ra_pst["branches"].values()) for r in ra_psts["resources"])
    # Objective
    master_model.setObjective(z, GRB.MINIMIZE)
    return master_model, z, E, Q, Y


def cp_subproblem(ra_psts, branches, lower_bound=0, sigma:int=0):
    # Solve sub-problem
    resource_jobs = {}
    resource_costs = {}
    all_jobs = []
    for resource in ra_psts["resources"]:
        resource_jobs[resource] = []
        resource_costs[resource] = 0
    subproblem_model = CpoModel(name="subproblem")
    for ra_pst in ra_psts["instances"]:
        previous_branch_job = None
        for branchId, branch in ra_pst["branches"].items():
            # print(f'branch {branchId}: {int(branch["selected"].x)}')
            if not branchId in branches: continue
            for jobId in branch["jobs"]:
                interval_var = subproblem_model.interval_var(name=jobId, optional=False, size=int(ra_pst["jobs"][jobId]["cost"]))
                if "release_time" in ra_pst["jobs"][jobId].keys():
                    interval_var.set_start_min(ra_pst["jobs"][jobId]["release_time"])
                if ra_pst["fixed"]:
                    job = ra_pst["jobs"][jobId]
                    if job["start"] is not None:
                        start_hr = int(job["start"])
                        end_hr = int(job["start"]) + int(job["cost"])
                        interval_var.set_start_min(start_hr)
                        interval_var.set_start_max(start_hr + sigma)
                        interval_var.set_end_min(end_hr)
                        interval_var.set_end_max(end_hr + sigma)
                else:
                    if previous_branch_job is not None:
                        subproblem_model.add(end_before_start(previous_branch_job, interval_var))
                resource_jobs[ra_pst["jobs"][jobId]["resource"]].append(interval_var)
                resource_costs[ra_pst["jobs"][jobId]["resource"]] += int(ra_pst["jobs"][jobId]["cost"])
                previous_branch_job = interval_var
                all_jobs.append(interval_var)
    
    # No overlap between jobs on the same resource
    subproblem_model.add(no_overlap(resource_jobs[resource]) for resource in ra_psts["resources"] if len(resource_jobs[resource]) > 1)
    # Objective
    makespan = max(end_of(interval) for interval in all_jobs)
    subproblem_model.add(makespan >= lower_bound)
    subproblem_model.add(minimize(makespan))
    # Solve model
    # print(f'Solving CP subproblem...')
    start_time = time.time()
    schedule = subproblem_model.solve(
        LogVerbosity='Quiet', 
        TimeLimit=100,
        SearchType='IterativeDiving'
        )
    # print(f'Solved CP subproblem in {time.time() - start_time} seconds')
    return schedule, all_jobs

def create_schedule(ra_psts, result, all_jobs):
    all_job_names = {job.get_name():job for job in all_jobs}
    intervals = []
    for ra_pst in ra_psts["instances"]:
        if not ra_pst["fixed"]:
            for jobId, job in ra_pst["jobs"].items():
                if jobId not in all_job_names: continue
                itv = result.get_var_solution(all_job_names[jobId])
                job["selected"] = itv.is_present()
                job["start"] = itv.get_start()
                #del job["interval"]

        else:
            for jobId, job in ra_pst["jobs"].items():
                if "interval" in job.keys():
                    itv = result.get_var_solution(ra_pst["jobs"][jobId]["interval"])
                    job["start"] = itv.get_start()
                    del job["interval"]
        for branchId, branch in ra_pst["branches"].items():
            if "selected" in branch.keys():
                del branch["selected"]
        ra_pst["fixed"] = True
    
        for jobId, job in ra_pst["jobs"].items():
            if job["selected"]:
                intervals.append(job)
    
    return ra_psts
    