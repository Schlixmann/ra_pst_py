from docplex.cp.model import *
import json

context.solver.local.execfile = '/opt/ibm/ILOG/CPLEX_Studio2211/cpoptimizer/bin/x86-64_linux/cpoptimizer'


def cp_solver(ra_pst_json):
    """
    ra_pst_json input format:
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
                "instance": instanceId
            }
        }
    }
    """
    with open(ra_pst_json, "r") as f:
        ra_pst = json.load(f)
    
    #-----------------------------------------------------------------------------
    # Build the model
    #-----------------------------------------------------------------------------

    model = CpoModel()

    # Create optional interval variables for each job
    for jobId, job in ra_pst["jobs"].items():
        job["interval"] = model.interval_var(name=jobId, optional=True, size=int(job["cost"]))

    # Precedence constraints
    for jobId, job in ra_pst["jobs"].items():
        for jobId2 in job["after"]:
            model.add(end_before_start(ra_pst["jobs"][jobId2]["interval"], ra_pst["jobs"][jobId]["interval"]))
    
    # No overlap between jobs on the same resource
    for r in ra_pst["resources"]:
        resource_intervals = [job["interval"] for job in ra_pst["jobs"].values() if job["resource"] == r]
        if len(resource_intervals) > 0:
            model.add(no_overlap(resource_intervals))
    
    # model.add(no_overlap(job["interval"] for job in ra_pst["jobs"].values() if job["resource"] == r) for r in ra_pst["resources"])

    # Objective
    model.add(minimize(max([end_of(job["interval"]) for job in ra_pst["jobs"].values()])))

    # Configuration constraints
    # Select exactly one branch from each non-deleted task
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


    result = model.solve(FailLimit=1000, TimeLimit=10)
    # result.print_solution()

    for jobId, job in ra_pst["jobs"].items():
        itv = result.get_var_solution(ra_pst["jobs"][jobId]["interval"])
        job["selected"] = itv.is_present()
        job["start"] = itv.get_start()
        del job["interval"]
        del job["after"]
    ra_pst["objective"] = result.get_objective_value()

    return ra_pst

    

