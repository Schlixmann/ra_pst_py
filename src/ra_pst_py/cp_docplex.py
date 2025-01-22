from docplex.cp.model import *
import json

context.solver.local.execfile = '/opt/ibm/ILOG/CPLEX_Studio2211/cpoptimizer/bin/x86-64_linux/cpoptimizer'


def cp_solver(ra_pst_json, warm_start_json=None):
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
        inst_prefix = str(list(instance["tasks"].keys())[0]).split("-")[0]
        for key, value in instance["branches"].items():
            value["deletes"] = [str(inst_prefix) + f"-{element}"for element in value["deletes"]]
    
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
                        job["interval"].set_start_max(start_hr)
                        job["interval"].set_end_min(end_hr)
                        job["interval"].set_end_max(end_hr)
                    #job_intervals.append(job["interval"])
                    fixed_intervals += 1

        else:
            # Create optional interval variables for each job
            for jobId, job in ra_pst["jobs"].items():
                job["interval"] = model.interval_var(name=jobId, optional=True, size=int(job["cost"]))
                # print(f'Add job {jobId}')

                # Start time must be > than release time if a release time for instance is given
                if job["release_time"]:
                    min_time = job["release_time"]
                job["interval"].set_start_min(min_time)
                job_intervals.append(job["interval"])

            # Precedence constraints
            for jobId, job in ra_pst["jobs"].items():
                for jobId2 in job["after"]:
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
    
    
    # model.add(no_overlap(job["interval"] for job in ra_pst["jobs"].values() if job["resource"] == r) for r in ra_pst["resources"])

    # Objective
    model.add(minimize(max([end_of(interval) for interval in job_intervals])))

    # Configuration constraints
    # Select exactly one branch from each non-deleted task
    for ra_pst in ra_psts["instances"]:
        if not ra_pst["fixed"]:
            for taskId, task in ra_pst["tasks"].items():
                task_jobs = []
                branch_jobs = []
                for branchId in task["branches"]:
                    for jobId in ra_pst["branches"][branchId]["jobs"]:
                        if len(branch_jobs) > 0:
                            model.add(equal(presence_of(ra_pst["jobs"][jobId]["interval"]), presence_of(ra_pst["jobs"][branch_jobs[-1]]["interval"])))
                        for jobId2 in task_jobs:
                            model.add(if_then(presence_of(ra_pst["jobs"][jobId]["interval"]), logical_not(presence_of(ra_pst["jobs"][jobId2]["interval"]))))
                        branch_jobs.append(jobId)
                    task_jobs.extend(branch_jobs)
                    branch_jobs = []
                deletes_task = [presence_of(ra_pst["jobs"][branch["jobs"][0]]["interval"]) for branch in ra_pst["branches"].values() if taskId in branch["deletes"]]
                deletes_task.append(0)
                model.add(sum([presence_of(ra_pst["jobs"][ra_pst["branches"][branchId]["jobs"][0]]["interval"]) for branchId in task["branches"]]) == 1-max(deletes_task))


    if warm_start_json:
        starting_solution = CpoModelSolution()
        #TODO make sure warm_start instances are the same as to optimize ones
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

    result = model.solve(FailLimit=1000000, TimeLimit=10000)
    # result.print_solution()
    intervals = []
    for ra_pst in ra_psts["instances"]:
        if not ra_pst["fixed"]:
            for jobId, job in ra_pst["jobs"].items():
                itv = result.get_var_solution(ra_pst["jobs"][jobId]["interval"])
                # if itv is None:
                #     continue
                job["selected"] = itv.is_present()
                job["start"] = itv.get_start()
                #if itv.is_present():
                #    intervals.append({
                #        "jobID": jobId, 
                #        "start": itv.get_start(),
                #        "cost" : itv.get_length()
                #    })
                del job["interval"]
                #del job["after"]
        else:
            for jobId, job in ra_pst["jobs"].items():
                if "interval" in job.keys():
                    del job["interval"]
        ra_pst["fixed"] = True
    
        for jobId, job in ra_pst["jobs"].items():
            if job["selected"]:
                intervals.append(job)
    
    solve_details = result.get_solver_infos()
    total_interval_length = sum([element["cost"] for element in intervals])
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
        "total interval length": total_interval_length
    }
    # TODO maybe add resource usage
    return ra_psts

    

