from docplex.cp.model import *
import json
import gurobipy as gp
from gurobipy import GRB


context.solver.local.execfile = '/opt/ibm/ILOG/CPLEX_Studio2211/cpoptimizer/bin/x86-64_linux/cpoptimizer'


def cp_solver(ra_pst_json, warm_start_json=None, log_file = "cpo_solver.log", timeout=100, break_symmetries:bool=False, sigma:int=0):
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
    
    if warm_start_json:
        with open(warm_start_json, "r") as f:
            warm_start_ra_psts = json.load(f)
    
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

    model = CpoModel()
    job_intervals = []
    fixed_intervals = 0

    for ra_pst in ra_psts["instances"]:
        min_time = 0
        if ra_pst["fixed"]:
            # Create fixed intervals for selected jobs:
            for jobId, job in ra_pst["jobs"].items():
                if job["selected"]:
                    job["interval"] = model.interval_var(name=jobId, optional=False, size=int(job["cost"]))
                    # print(f'Add job {jobId}')
                    
                    # Fix intervals of Jobs scheduled in previous jobs:
                    if job["start"] is not None:
                        start_hr = int(job["start"])
                        end_hr = int(job["start"]) + int(job["cost"])
                        job["interval"].set_start_min(start_hr)
                        job["interval"].set_start_max(start_hr + sigma) 
                        job["interval"].set_end_min(end_hr)
                        job["interval"].set_end_max(end_hr + sigma)
                    fixed_intervals += 1
                    
                    # TODO figure out if this should be part of the objective or not
                    job_intervals.append(job["interval"])

        else:
            # Create optional interval variables for each job
            for jobId, job in ra_pst["jobs"].items():
                job["interval"] = model.interval_var(name=jobId, optional=True, size=int(job["cost"]))

                # Start time must be > than release time if a release time for instance is given
                if job["release_time"]:
                    min_time = job["release_time"]
                job["interval"].set_start_min(min_time)
                job_intervals.append(job["interval"])

        # Precedence constraints
        for jobId, job in ra_pst["jobs"].items():
            for jobId2 in job["after"]:
                if ra_pst["fixed"]:
                    if ra_pst["jobs"][jobId]["selected"] & ra_pst["jobs"][jobId2]["selected"]:
                        model.add(end_before_start(ra_pst["jobs"][jobId2]["interval"], ra_pst["jobs"][jobId]["interval"]))
                else:    
                    model.add(end_before_start(ra_pst["jobs"][jobId2]["interval"], ra_pst["jobs"][jobId]["interval"]))
                    
     # No overlap between jobs on the same resource   
    for r in ra_psts["resources"]:
        resource_intervals = []
        for ra_pst in ra_psts["instances"]:
            if ra_pst["fixed"]:
                resource_intervals.extend([job["interval"] for job in ra_pst["jobs"].values() if (job["resource"] == r and job["selected"])])
            else:
                resource_intervals.extend([job["interval"] for job in ra_pst["jobs"].values() if job["resource"] == r])
        if len(resource_intervals) > 0:
            model.add(no_overlap(resource_intervals))
    

    model.add(minimize(max([end_of(interval) for interval in job_intervals])))

    # Configuration constraints
    # Select exactly one branch from each non-deleted task
    #for ra_pst in ra_psts["instances"]:
    #    if not ra_pst["fixed"]:
    #        for taskId, task in ra_pst["tasks"].items():
    #            task_jobs = []
    #            branch_jobs = []
    #            for branchId in task["branches"]:
    #                for jobId in ra_pst["branches"][branchId]["jobs"]:
    #                    if len(branch_jobs) > 0:
    #                        model.add(equal(presence_of(ra_pst["jobs"][jobId]["interval"]), presence_of(ra_pst["jobs"][branch_jobs[-1]]["interval"])))
    #                    for jobId2 in task_jobs:
    #                        model.add(if_then(presence_of(ra_pst["jobs"][jobId]["interval"]), logical_not(presence_of(ra_pst["jobs"][jobId2]["interval"]))))
    #                    branch_jobs.append(jobId)
    #                task_jobs.extend(branch_jobs)
    #                branch_jobs = []
    #            deletes_task = [presence_of(ra_pst["jobs"][branch["jobs"][0]]["interval"]) for branch in ra_pst["branches"].values() if taskId in branch["deletes"]]
    #            deletes_task.append(0)
    #            model.add(sum([presence_of(ra_pst["jobs"][ra_pst["branches"][branchId]["jobs"][0]]["interval"]) for branchId in task["branches"]]) == 1-max(deletes_task))

    for ra_pst in ra_psts["instances"]:
        if ra_pst["fixed"]: continue
        for branchId, branch in ra_pst["branches"].items():
            independent_branches = []
            for branch_2_id, branch_2 in ra_pst["branches"].items():
                if branch_2["task"] == branch["task"] or branch["task"] in branch_2["deletes"]:
                    independent_branches.append(branch_2_id)
            # master_model.add(sum([ra_pst["branches"][b_id]["selected"] for b_id in independent_branches]) == 1)
            model.add(sum([presence_of(ra_pst["jobs"][ra_pst["branches"][b_id]["jobs"][0]]["interval"]) for b_id in independent_branches]) == 1)
            branch_jobs = []
            for jobId in branch["jobs"]:
                if len(branch_jobs) > 0:
                    model.add(equal(presence_of(ra_pst["jobs"][jobId]["interval"]), presence_of(ra_pst["jobs"][branch_jobs[-1]]["interval"])))
                branch_jobs.append(jobId)

    if warm_start_json:
        starting_solution = CpoModelSolution()
        for i, ra_pst in enumerate(ra_psts["instances"]):
            if not ra_pst["fixed"]:
                for jobId, job in ra_pst["jobs"].items():
                    interval_var = job["interval"]
                    warm_start_job = warm_start_ra_psts["instances"][i]["jobs"][jobId]
                    if warm_start_job["selected"]:
                        starting_solution.add_interval_var_solution(interval_var, start=warm_start_job["start"], end= warm_start_job["start"] + warm_start_job["cost"], size=warm_start_job["cost"], presence= warm_start_job["selected"])
                    else:
                        starting_solution.add_interval_var_solution(interval_var, start=warm_start_job["start"], end=None, size=warm_start_job["cost"], presence= warm_start_job["selected"])
        if len(starting_solution.get_all_var_solutions()) != len(model.get_all_variables())-fixed_intervals:
            raise ValueError(f"Solution size <{len(starting_solution.get_all_var_solutions())}> does not match model size <{len(model.get_all_variables())-fixed_intervals}>")
        model.set_starting_point(starting_solution)

    with open(log_file, "w") as f:
        result = model.solve(TimeLimit=timeout, log_output=f)
    # result.print_solution()
    if result.get_solve_status() == "Infeasible":
        raise ValueError("Infeasible model")
    intervals = []
    for ra_pst in ra_psts["instances"]:
        if not ra_pst["fixed"]:
            for jobId, job in ra_pst["jobs"].items():
                itv = result.get_var_solution(ra_pst["jobs"][jobId]["interval"])
                job["selected"] = itv.is_present()
                job["start"] = itv.get_start()
                del job["interval"]

        else:
            for jobId, job in ra_pst["jobs"].items():
                if "interval" in job.keys():
                    itv = result.get_var_solution(ra_pst["jobs"][jobId]["interval"])
                    job["selected"] = itv.is_present()
                    job["start"] = itv.get_start()
                    del job["interval"]
        ra_pst["fixed"] = True
    
        for jobId, job in ra_pst["jobs"].items():
            if job["selected"]:
                intervals.append(job)
    
    solve_details = result.get_solver_infos()
    total_interval_length = sum([element["cost"] for element in intervals])

    # Metadata per instance:
    ra_psts["instances"][-1]["solution"] = {
            "objective": result.get_objective_value(),
            "optimality gap": solve_details.get('RelativeOptimalityGap', 'N/A'),
            "computing time": solve_details.get('TotalTime', 'N/A'),
            "solver status": result.get_solve_status(),
            "branches": solve_details.get('NumberOfBranches', 'N/A'),
            "propagations": solve_details.get('NumberOfPropagations','N/A'),
            "total interval length": total_interval_length,
            "lower_bound" : result.get_objective_bound()
        }


    if "solution" in ra_psts.keys():
        computing_time = ra_psts["solution"]["computing time"] + solve_details.get('TotalTime', 'N/A')
    else:
        computing_time = solve_details.get('TotalTime', 'N/A')
    ra_psts["solution"] = {
        "objective": result.get_objective_value(),
        "optimality gap": solve_details.get('RelativeOptimalityGap', 'N/A'),
        "lower_bound" : result.get_objective_bound(),
        "computing time": computing_time,
        "solver status": result.get_solve_status(),
        "branches": solve_details.get('NumberOfBranches', 'N/A'),
        "propagations": solve_details.get('NumberOfPropagations','N/A'),
        "total interval length": total_interval_length
        #"objective_no_symmetry_breaking": result.get_objective_value() - alpha * sum([interval.get_size()[0] * presence_of(interval) for interval in job_intervals])
    }
    # TODO maybe add resource usage
    return ra_psts


def cp_solver_alternative_new(ra_pst_json, warm_start_json=None, log_file = "cpo_solver_new.log", timeout = 100, replan = False, release_time:int=0, break_symmetries:bool=False, sigma = 0):
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
    
        # create bucketing
        all_deletes = set()
        for key, branch in instance["branches"].items():
            all_deletes.update(branch["deletes"])
            branch["finish_time"] = branch["release_time"] + branch["branchCost"]

        all_tasks = list(instance["tasks"].keys())
        for taskId, task in instance["tasks"].items():
            task_index = all_tasks.index(taskId)
            if task_index == 0:
                for branchId, branch in instance["branches"].items():
                    if branch["task"] == taskId:
                        branch["finish_time"] = branch["release_time"] + branch["branchCost"]
                        if taskId in all_deletes:
                            branch["finish_time"] = branch["release_time"]
            else:
                previous_task = all_tasks[task_index-1]
                earliest_possible_finish = min([instance["branches"][branchId]["finish_time"] for branchId in instance["tasks"][previous_task]["branches"]])
                # set release time for all branches to finish time of previous task
                for branchId, branch in instance["branches"].items():
                    if branch["task"] == taskId:
                        branch["release_time"] = earliest_possible_finish
                        if taskId in all_deletes:
                            branch["finish_time"] = branch["release_time"]
                        else:
                            branch["finish_time"] = branch["release_time"] + branch["branchCost"]

        for jobId, job in instance["jobs"].items():
            job["release_time"] = instance["branches"][job["branch"]]["release_time"]

    #-----------------------------------------------------------------------------
    # Build the model
    #-----------------------------------------------------------------------------

    model = CpoModel()
    job_intervals = []
    fixed_intervals = 0

    for ra_pst in ra_psts["instances"]:
        min_time = 0
        # Create optional interval variables for each job
        for jobId, job in ra_pst["jobs"].items():
            min_time = job["release_time"]
            if job["release_time"] >= int(release_time):
                job["interval"] = model.interval_var(name=jobId, optional=True, size=int(job["cost"]))
                job["interval"].set_start_min(int(min_time))
            else:
                job["interval"] = model.interval_var(name=jobId, optional=False, size=int(job["cost"])) #model.interval_var(name=jobId, optional=False, size=int(job["cost"]))
                # Fix intervals of Jobs scheduled in previous jobs:
                if job["start"] is not None:
                    start_hr = int(job["start"])
                    end_hr = int(job["start"]) + int(job["cost"])
                    job["interval"].set_start_min(start_hr)
                    job["interval"].set_start_max(start_hr + sigma)
                    job["interval"].set_end_min(start_hr)
                    job["interval"].set_end_min(start_hr + sigma)

                #job_intervals.append(job["interval"])
                fixed_intervals += 1
                job["fixed"] = True
                branchId = ra_pst["branches"][job["branch"]]
                taskId = branchId["task"]
                ra_pst["tasks"][taskId]["fixed"] = True
            job_intervals.append(job["interval"])

        # Precedence constraints
        for jobId, job in ra_pst["jobs"].items():
            if "fixed" not in job.keys():
                for jobId2 in job["after"]:
                    model.add(end_before_start(ra_pst["jobs"][jobId2]["interval"], ra_pst["jobs"][jobId]["interval"]))


    print(len(job_intervals), len(model.get_all_variables()), len(model.get_all_expressions()))

    # No overlap between jobs on the same resource   
    for r in ra_psts["resources"]:
        resource_intervals = []
        for ra_pst in ra_psts["instances"]:
            resource_intervals.extend([job["interval"] for job in ra_pst["jobs"].values() if (job["resource"] == r and job["selected"] and "fixed" in job.keys())])
            resource_intervals.extend([job["interval"] for job in ra_pst["jobs"].values() if (job["resource"] == r and "fixed" not in job.keys())])
        if len(resource_intervals) > 0:
            model.add(no_overlap(resource_intervals))
    
    # model.add(no_overlap(job["interval"] for job in ra_pst["jobs"].values() if job["resource"] == r) for r in ra_pst["resources"])

    # Objective
    if break_symmetries:
        alpha = 0.01
    else:
        alpha = 0
    model.add(minimize(max([end_of(interval) for interval in job_intervals]) + alpha * sum([interval.get_size()[0] * presence_of(interval) for interval in job_intervals])))


    # Configuration constraints
    # Select exactly one branch from each non-deleted task
    for ra_pst in ra_psts["instances"]:
        if not ra_pst["fixed"]:
            for taskId, task in ra_pst["tasks"].items():
                if not "fixed" in task.keys():
                    dummy_task = model.interval_var(optional=True, name=f"Dummy_{taskId}")
                    alternatives = [ra_pst["jobs"][ra_pst["branches"][branchId]["jobs"][0]]["interval"] for branchId in task["branches"]]               
                    
                    
                    for branchId in task["branches"]:
                        # Add First job of each branch as alternative
                        # TODO check how model.alternative works!
                        for jobId in ra_pst["branches"][branchId]["jobs"]:
                            # TODO presence of each job in branch equals presence of first job
                            # TODO ensure only one alternative is chosen
                            #if len(branch_jobs) > 0:
                            model.add(equal(presence_of(ra_pst["jobs"][jobId]["interval"]), presence_of(ra_pst["jobs"][ra_pst["branches"][branchId]["jobs"][0]]["interval"])))
                    
                    # TODO ensure deletes are added correctly to this
                    deleted_by_tracker = [branch["jobs"][0] for branch in ra_pst["branches"].values() if taskId in branch["deletes"]]
                    deleted_by = model.sum(presence_of(ra_pst["jobs"][branch["jobs"][0]]["interval"]) for branch in ra_pst["branches"].values() if taskId in branch["deletes"])
                    #deletes_task = [presence_of(ra_pst["jobs"][branch["jobs"][0]]["interval"]) for branch in ra_pst["branches"].values() if taskId in branch["deletes"]] # Deprecated
                    #deletes_task.append(0) # Deprecated
                    
                    # branch that 
                    deletion_tracker = [ra_pst["branches"][branchId]["jobs"][0] for branchId in task["branches"]]
                    model.add(model.sum(presence_of(ra_pst["jobs"][ra_pst["branches"][branchId]["jobs"][0]]["interval"]) for branchId in task["branches"]) + deleted_by == 1)
                    #model.add(sum([presence_of(ra_pst["jobs"][ra_pst["branches"][branchId]["jobs"][0]]["interval"]) for branchId in task["branches"]]) == 1-max(deletes_task))
                    model.add(model.alternative(dummy_task, alternatives))
                    model.add(sum(presence_of(alt) for alt in alternatives) + deleted_by == 1)

    #result = model.solve()
    # Solve and write log to file
    with open(log_file, "w") as f:
        result = model.solve(FailLimit=100000000, TimeLimit=timeout, log_output=f)
    # result.print_solution()
    if result.get_solve_status() == "Infeasible":
        raise ValueError("Infeasible model")
    intervals = []

    for ra_pst in ra_psts["instances"]:
        if not ra_pst["fixed"]:
            for jobId, job in ra_pst["jobs"].items():
                if "fixed" not in job.keys():
                    itv = result.get_var_solution(ra_pst["jobs"][jobId]["interval"])
                    job["selected"] = itv.is_present()
                    job["start"] = itv.get_start()
                    del job["interval"]
    
        for jobId, job in ra_pst["jobs"].items():
            if "interval" in job.keys():
                itv = result.get_var_solution(ra_pst["jobs"][jobId]["interval"])
                job["start"] = itv.get_start()
                del job["interval"]
            if job["selected"]:
                intervals.append(job)
    
    solve_details = result.get_solver_infos()
    total_interval_length = sum([element["cost"] for element in intervals])

    # Metadata per instance:
    ra_psts["instances"][-1]["solution"] = {
            "objective": result.get_objective_value(),
            "optimality gap": solve_details.get('RelativeOptimalityGap', 'N/A'),
            "computing time": solve_details.get('TotalTime', 'N/A'),
            "solver status": result.get_solve_status(),
            "branches": solve_details.get('NumberOfBranches', 'N/A'),
            "propagations": solve_details.get('NumberOfPropagations','N/A'),
            "total interval length": total_interval_length,
            "lower_bound" : result.get_objective_bound()
        }


    if "solution" in ra_psts.keys():
        computing_time = ra_psts["solution"]["computing time"] + solve_details.get('TotalTime', 'N/A')
    else:
        computing_time = solve_details.get('TotalTime', 'N/A')
    ra_psts["solution"] = {
        "objective": result.get_objective_value(),
        "optimality gap": solve_details.get('RelativeOptimalityGap', 'N/A'),
        "computing time": computing_time,
        "solver status": result.get_solve_status(),
        "branches": solve_details.get('NumberOfBranches', 'N/A'),
        "propagations": solve_details.get('NumberOfPropagations','N/A'),
        "total interval length": total_interval_length,
        "lower_bound" : result.get_objective_bound(),
    }
    # TODO maybe add resource usage
    return ra_psts

def cp_solver_decomposed(ra_pst_json):
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

    master_model = gp.Model('master')
    master_model.setParam('OutputFlag', False)
    z = master_model.addVar()
    # Branch variables
    for ra_pst in ra_psts["instances"]:
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
    # Get the maximum bin size of the selected branches
    master_model.addConstrs(z >= gp.quicksum(branch["selected"] * branch["branch_jobs"][r] for ra_pst in ra_psts["instances"] for branch in ra_pst["branches"].values()) for r in ra_psts["resources"])
    # Objective
    master_model.setObjective(z, GRB.MINIMIZE)

    lower_bound = 0
    big_number = 0
    all_jobs = []
    for ra_pst in ra_psts["instances"]:
        for branch in ra_pst["branches"].values():
            big_number += branch["branchCost"]
    upper_bound = big_number
    best_schedule = None
    while (upper_bound - lower_bound)/upper_bound > 0.10: # Gap of .1
        print(f"Lower bound: {lower_bound}, upper bound: {upper_bound}. Gap {100*(upper_bound-lower_bound)/upper_bound:.2f}%")
        # Solve master problem
        master_model.optimize()
        lower_bound = master_model.objVal
        if lower_bound < upper_bound:
            # Solve sub-problem
            schedule, all_jobs = cp_subproblem(ra_psts)
            # Solved subproblem: Add cuts
            if schedule.get_objective_value() < upper_bound:
                upper_bound = schedule.get_objective_value()
                best_schedule = schedule # TODO add selected jobs + start times to original ILP description
                print(f'Upper bound: {upper_bound}')
            # for ra_pst in ra_psts["instances"]:
            #     for branchId, branch in ra_pst["branches"].items():
            #         if int(branch["selected"].x):
            #             print(f'Add cut for branch {branchId} ({branch["branchCost"]})')
            master_model.addConstr(z >= schedule.get_objective_value() - big_number * gp.quicksum(1-branch["selected"] for ra_pst in ra_psts["instances"] for branchId, branch in ra_pst["branches"].items() if int(branch["selected"].x)))
            master_model.addConstr(z >= lower_bound)
            # Output the current schedule
    for ra_pst in ra_psts["instances"]:
        for jobId, job in ra_pst["jobs"].items():
            job["selected"] = 0
            job["start"] = 0
            for interval in all_jobs:
                itv = schedule.get_var_solution(interval)
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

def cp_subproblem(ra_psts):
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
            if not int(branch["selected"].x): continue
            for jobId in branch["jobs"]:
                interval_var = subproblem_model.interval_var(name=jobId, optional=False, size=int(ra_pst["jobs"][jobId]["cost"]))
                if previous_branch_job is not None:
                    subproblem_model.add(end_before_start(previous_branch_job, interval_var))
                resource_jobs[ra_pst["jobs"][jobId]["resource"]].append(interval_var)
                resource_costs[ra_pst["jobs"][jobId]["resource"]] += int(ra_pst["jobs"][jobId]["cost"])
                previous_branch_job = interval_var
                all_jobs.append(interval_var)
    
    # No overlap between jobs on the same resource
    subproblem_model.add(no_overlap(resource_jobs[resource]) for resource in ra_psts["resources"] if len(resource_jobs[resource]) > 1)
    # Objective
    subproblem_model.add(minimize(max(end_of(interval) for interval in all_jobs )))
    schedule = subproblem_model.solve(TimeLimit=100)
    return schedule, all_jobs

    
def cp_solver_scheduling_only(ra_pst_json, warm_start_json=None, log_file = "cpo_solver.log", timeout=100, break_symmetries:bool=False, sigma:int=0):
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
    
    if warm_start_json:
        with open(warm_start_json, "r") as f:
            warm_start_ra_psts = json.load(f)
    
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

    model = CpoModel()
    job_intervals = []
    selected_jobs = []
    fixed_intervals = 0
    active_intervals = 0

    for ra_pst in ra_psts["instances"]:
        min_time = 0
        if ra_pst["fixed"]:
            # Create fixed intervals for selected jobs:
            for jobId, job in ra_pst["jobs"].items():
                if job["selected"]:
                    job["interval"] = model.interval_var(name=jobId, optional=False, size=int(job["cost"]))
                    # print(f'Add job {jobId}')
                    
                    # Fix intervals of Jobs scheduled in previous jobs:
                    if job["start"] is not None:
                        start_hr = int(job["start"])
                        end_hr = int(job["start"]) + int(job["cost"])
                        job["interval"].set_start_min(start_hr)
                        job["interval"].set_start_max(start_hr + sigma) 
                        job["interval"].set_end_min(end_hr)
                        job["interval"].set_end_max(end_hr + sigma)
                    #job_intervals.append(job["interval"])
                    fixed_intervals += 1
                    
                    # TODO figure out if this should be part of the objective or not
                    job_intervals.append(job["interval"])

        else:
            # Create optional interval variables for each job
            for jobId, job in ra_pst["jobs"].items():
                if job["selected"] == True:
                    job["interval"] = model.interval_var(name=jobId, optional=False, size=int(job["cost"]))
                    # Start time must be > than release time if a release time for instance is given
                    if job["release_time"]:
                        min_time = job["release_time"]
                    job["interval"].set_start_min(min_time)
                    active_intervals += 1
                    job_intervals.append(job["interval"])
                    selected_jobs.append(jobId)

                #else:
                #    job["interval"] = model.interval_var(name=jobId, optional=True, size=int(0))
                #    model.add(presence_of(job["interval"]) == 0)
                    

        # Precedence constraints
        precedence_counter = 0
        for jobId, job in ra_pst["jobs"].items():
            if not "interval" in job.keys(): continue
            for jobId2 in job["after"]:
                if jobId2 in selected_jobs:
                    if ra_pst["fixed"]:
                        if ra_pst["jobs"][jobId]["selected"] & ra_pst["jobs"][jobId2]["selected"]:
                            model.add(end_before_start(ra_pst["jobs"][jobId2]["interval"], ra_pst["jobs"][jobId]["interval"]))
                    else:    
                        model.add(end_before_start(ra_pst["jobs"][jobId2]["interval"], ra_pst["jobs"][jobId]["interval"]))
                        precedence_counter +=1
                        
     # No overlap between jobs on the same resource   
    for r in ra_psts["resources"]:
        resource_intervals = []
        for ra_pst in ra_psts["instances"]:
            if ra_pst["fixed"]:
                resource_intervals.extend([job["interval"] for job in ra_pst["jobs"].values() if (job["resource"] == r and job["selected"])])
            else:
                resource_intervals.extend([job["interval"] for job in ra_pst["jobs"].values() if job["resource"] == r if "interval" in job.keys()])
        if len(resource_intervals) > 0:
            model.add(no_overlap(resource_intervals))
    
    
    # model.add(no_overlap(job["interval"] for job in ra_pst["jobs"].values() if job["resource"] == r) for r in ra_pst["resources"])
    alpha = 0
    # Objective
    model.add(minimize(max([end_of(interval) for interval in job_intervals]) + alpha * sum([interval.get_size()[0] * presence_of(interval) for interval in job_intervals])))

    with open(log_file, "w") as f:
        result = model.solve(FailLimit=100000000, TimeLimit=timeout, log_output=f)
    # result.print_solution()
    if result.get_solve_status() == "Infeasible":
        raise ValueError("Infeasible model")
    intervals = []
    for ra_pst in ra_psts["instances"]:
        if not ra_pst["fixed"]:
            for jobId, job in ra_pst["jobs"].items():
                if not "interval" in job.keys(): continue
                itv = result.get_var_solution(ra_pst["jobs"][jobId]["interval"])
                job["selected"] = itv.is_present()
                job["start"] = itv.get_start()
                del job["interval"]

        else:
            for jobId, job in ra_pst["jobs"].items():
                if "interval" in job.keys():
                    itv = result.get_var_solution(ra_pst["jobs"][jobId]["interval"])
                    job["start"] = itv.get_start()
                    del job["interval"]
        ra_pst["fixed"] = True
    
        for jobId, job in ra_pst["jobs"].items():
            if job["selected"]:
                intervals.append(job)
    
    solve_details = result.get_solver_infos()
    total_interval_length = sum([element["cost"] for element in intervals])

    # Metadata per instance:
    ra_psts["instances"][-1]["solution"] = {
            "objective": result.get_objective_value(),
            "optimality gap": solve_details.get('RelativeOptimalityGap', 'N/A'),
            "computing time": solve_details.get('TotalTime', 'N/A'),
            "solver status": result.get_solve_status(),
            "branches": solve_details.get('NumberOfBranches', 'N/A'),
            "propagations": solve_details.get('NumberOfPropagations','N/A'),
            "total interval length": total_interval_length,
            "lower_bound" : result.get_objective_bound()
        }


    if "solution" in ra_psts.keys():
        computing_time = ra_psts["solution"]["computing time"] + solve_details.get('TotalTime', 'N/A')
    else:
        computing_time = solve_details.get('TotalTime', 'N/A')
    ra_psts["solution"] = {
        "objective": result.get_objective_value(),
        "optimality gap": solve_details.get('RelativeOptimalityGap', 'N/A'),
        "lower_bound" : result.get_objective_bound(),
        "computing time": computing_time,
        "solver status": result.get_solve_status(),
        "branches": solve_details.get('NumberOfBranches', 'N/A'),
        "propagations": solve_details.get('NumberOfPropagations','N/A'),
        "total interval length": total_interval_length
        #"objective_no_symmetry_breaking": result.get_objective_value() - alpha * sum([interval.get_size()[0] * presence_of(interval) for interval in job_intervals])
    }
    # TODO maybe add resource usage
    return ra_psts


if __name__ == "__main__":
    file = "cp_rep_test.json"    
    print("Start")
    #result = cp_solver_decomposed(file)
    #x = cp_solver_alternative(file, warm_start_json=None)
    #with open("alterna_out.json", "w") as f:
    #    json.dump(x, f)
    print("================= \n comparison \n=================")
    x = cp_solver(file)
    with open("alterna_out.json", "w") as f:
        json.dump(x, f, indent=2)