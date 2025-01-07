import gurobipy as gp
from gurobipy import GRB
import json


<<<<<<< HEAD
def transform_json(ra_pst_json):
    """
    Transform the JSON object from the shape:
    {
      tasks: list of tasks,
      resources: list of resources,
      branches: {
        task : [
          {
            "jobs": [[resource, cost], ...],
            "deletes": [task]
          }
        ]
      }
    }
    to: 
    {
        "tasks": [taskId],
        "resources": [resourceId],
        "branches": [{
            "task": taskId,
            "jobs": [jobId],
            "deletes": [taskId],
            "branchCost": cost
        }],
        "jobs": [{
            "branch": branchId,
            "resource": resourceId,
            "cost": cost,
            "after": [jobId]
        }]
    }
    """
    with open(ra_pst_json, "r") as f:
        ra_pst = json.load(f)
        result = {
            "tasks": ra_pst["tasks"],
            "resources": ra_pst["resources"],
            "branches": [],
            "jobs": []
        }
        for task in result["tasks"]:
            for branch in ra_pst["branches"][task]:
                newBranch = {
                    "task": task,
                    "jobs": [],
                    "deletes": branch["deletes"],
                    "branch_no":branch["branch_no"],
                    "branchCost": 0
                }
                # first_job = True
                for job in branch["jobs"]:
                    newJob = {
                        "branch": len(result["branches"]),
                        "resource": job[0],
                        "cost": float(job[1]),
                        "after": []
                    }
                    # if first_job:
                    #     first_job = False
                    # else:
                    #     newJob["after"].append(len(result["jobs"])-1)
                    if len(result["jobs"]) > 0:
                        newJob["after"].append(len(result["jobs"])-1)
                    newBranch["branchCost"] += float(job[1])
                    newBranch["jobs"].append(len(result["jobs"]))
                    result["jobs"].append(newJob)
                result["branches"].append(newBranch)

        return result

=======
>>>>>>> ilp
def configuration_ilp(ra_pst_json):
    """
    Construct the ILP fromulation from a JSON object to the Gurobi model
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
    with open(ra_pst_json) as f:
        ra_pst = json.load(f)

    model = gp.Model('RA-PST configuration')

    # Variables:
    # Define branches
    for branchId, branch in ra_pst["branches"].items():
        branch["selected"] = model.addVar(vtype=(GRB.BINARY), name=f'x_{branchId}')
    # Define tasks
    for taskId, task in ra_pst["tasks"].items():
        task["deleted"] = model.addVar(vtype=(GRB.BINARY), name=f'y_{taskId}')

    # Objective:
    # Minimize the cost of the chosen branches
    model.setObjective(gp.quicksum(branch["branchCost"] * branch["selected"] for branch in ra_pst["branches"].values()), GRB.MINIMIZE)

    # Constraints:
    # Set the number of chosen branches equal to 1 if the task is not deleted
    for taskId, task in ra_pst["tasks"].items():
        model.addConstr(gp.quicksum(branch["selected"] for branch in ra_pst["branches"].values() if taskId == branch["task"]) == 1 - task["deleted"])

    # If a branch is selected that deletes a task, the task is not chosen
    for taskId, task in ra_pst["tasks"].items():
        if taskId in branch["deletes"]:
            model.addConstr(task["deleted"] >= branch["selected"] for branch in ra_pst["branches"].values())

    # If none of the branches that deletes the task is chosen, the task can not be set to deleted
    for taskId, task in ra_pst["tasks"].items():
        model.addConstr(gp.quicksum(branch["selected"] for branch in ra_pst["branches"].values() if taskId in branch["deletes"]) >= task["deleted"])

    model.optimize()
    ra_pst["objective"] = model.objVal

    for task in ra_pst["tasks"].values():
        task["deleted"] = task["deleted"].x
    for branch in ra_pst["branches"].values():
        branch["selected"] = branch["selected"].x

    return ra_pst


def scheduling_ilp(ra_pst_json):
    """
    Construct the ILP fromulation from a JSON object to the Gurobi model
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
    with open(ra_pst_json) as f:
        ra_pst = json.load(f)

    model = gp.Model('RA-PST scheduling')

    # Add variables
    c_max = model.addVar(vtype=(GRB.CONTINUOUS), name='c_max')
    e = {}
    for id1 in ra_pst["jobs"]:
        for id2 in ra_pst["jobs"]:
            if (id1, id2) not in e and id1 != id2:
                e[(id1, id2)] = model.addVar(vtype=(GRB.BINARY), name=f'e_{id1}_{id2}')
    w = sum(job["cost"] for job in ra_pst["jobs"].values())
    for jobId, job in ra_pst["jobs"].items():
        job["start"] = model.addVar(vtype=(GRB.CONTINUOUS), name=f't_{jobId}')

    # Objective
    model.setObjective(c_max, GRB.MINIMIZE)

    # Constraints
    # set $C_{max}$ to be at least the starting time of each job plus the processing time of the job
    for job in ra_pst["jobs"].values():
        model.addConstr(job["start"] + job["cost"] <= c_max)

    # For two jobs on the same resource, no overlap can occur
    for jobId1, jobId2 in e:
        if ra_pst["jobs"][jobId1]["resource"] == ra_pst["jobs"][jobId2]["resource"]:
            model.addConstr(ra_pst["jobs"][jobId1]["start"] - ra_pst["jobs"][jobId2]["start"] <= -ra_pst["jobs"][jobId1]["cost"] + w*(1-e[(jobId1, jobId2)]))
            model.addConstr(ra_pst["jobs"][jobId2]["start"] - ra_pst["jobs"][jobId1]["start"] <= -ra_pst["jobs"][jobId2]["cost"] + w*e[(jobId1, jobId2)])

    # Precedence constraints between individual jobs
    for jobId1, job in ra_pst["jobs"].items():
        for jobId2 in job["after"]:
            model.addConstr(ra_pst["jobs"][jobId2]["start"] + ra_pst["jobs"][jobId2]["cost"] <= ra_pst["jobs"][jobId1]["start"])

    # Optimize
    model.optimize()

    print(f'c_max: {c_max.x}')
    
    ra_pst["objective"] = c_max.x
    for jobId, job in ra_pst["jobs"].items():
        job["start"] = job["start"].x
    
    return ra_pst


def combined_ilp(ra_pst_json):
    """
    Construct the ILP fromulation from a JSON object to the Gurobi model
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
    with open(ra_pst_json) as f:
        ra_pst = json.load(f)

    model = gp.Model('RA-PST optimization')

    # Add variables
    c_max = model.addVar(vtype=(GRB.CONTINUOUS), name='c_max')
    e = {}
    for id1 in ra_pst["jobs"]:
        for id2 in ra_pst["jobs"]:
            if (id1, id2) not in e and id1 != id2:
                e[(id1, id2)] = model.addVar(vtype=(GRB.BINARY), name=f'e_{id1}_{id2}')
    w = sum(job["cost"] for job in ra_pst["jobs"].values())
    for jobId, job in ra_pst["jobs"].items():
        job["start"] = model.addVar(vtype=(GRB.CONTINUOUS), name=f't_{jobId}')
    # Define branches
    for branchId, branch in ra_pst["branches"].items():
        branch["selected"] = model.addVar(vtype=(GRB.BINARY), name=f'x_{branchId}')
    # Define tasks
    for taskId, task in ra_pst["tasks"].items():
        task["deleted"] = model.addVar(vtype=(GRB.BINARY), name=f'y_{taskId}')

    # Objective
    model.setObjective(c_max, GRB.MINIMIZE)
    
    # Configuration constraints
    # Set the number of chosen branches equal to 1 if the task is not deleted
    for taskId, task in ra_pst["tasks"].items():
        model.addConstr(gp.quicksum(branch["selected"] for branch in ra_pst["branches"].values() if taskId == branch["task"]) == 1 - task["deleted"])

    # If a branch is selected that deletes a task, the task is not chosen
    for taskId, task in ra_pst["tasks"].items():
        if taskId in branch["deletes"]:
            model.addConstr(task["deleted"] >= branch["selected"] for branch in ra_pst["branches"].values())

    # If none of the branches that deletes the task is chosen, the task can not be set to deleted
    for taskId, task in ra_pst["tasks"].items():
        model.addConstr(gp.quicksum(branch["selected"] for branch in ra_pst["branches"].values() if taskId in branch["deletes"]) >= task["deleted"])

    # Scheduling constraints
    # set $C_{max}$ to be at least the starting time of each job plus the processing time of the job
    for jobId, job in ra_pst["jobs"].items():
        model.addConstr(job["start"] + job["cost"]*ra_pst["branches"][job["branch"]]["selected"] <= c_max)

    # For two jobs on the same resource, no overlap can occur
    for jobId1, jobId2 in e:
        if ra_pst["jobs"][jobId1]["resource"] == ra_pst["jobs"][jobId2]["resource"]:
            model.addConstr(ra_pst["jobs"][jobId1]["start"] - ra_pst["jobs"][jobId2]["start"] <= -ra_pst["jobs"][jobId1]["cost"]*ra_pst["branches"][ra_pst["jobs"][jobId1]["branch"]]["selected"] + w*(1-e[(jobId1, jobId2)]))
            model.addConstr(ra_pst["jobs"][jobId2]["start"] - ra_pst["jobs"][jobId1]["start"] <= -ra_pst["jobs"][jobId2]["cost"]*ra_pst["branches"][ra_pst["jobs"][jobId2]["branch"]]["selected"] + w*e[(jobId1, jobId2)])

    # Precedence constraints between individual jobs
<<<<<<< HEAD
    model.addConstrs((t[i] + ra_pst["jobs"][i]["cost"]*x[ra_pst["jobs"][i]["branch"]] <= t[j] for j in range(len(ra_pst["jobs"])) for i in ra_pst["jobs"][j]["after"]) )
    
=======
    for jobId1, job in ra_pst["jobs"].items():
        for jobId2 in job["after"]:
            model.addConstr(ra_pst["jobs"][jobId2]["start"] + ra_pst["jobs"][jobId2]["cost"]*ra_pst["branches"][ra_pst["jobs"][jobId2]["branch"]]["selected"] <= ra_pst["jobs"][jobId1]["start"])
>>>>>>> ilp

    # Optimize
    model.optimize()

    for task in ra_pst["tasks"].values():
        task["deleted"] = task["deleted"].x
    for job in ra_pst["jobs"].values():
        job["start"] = job["start"].x
        job["selected"] = ra_pst["branches"][job["branch"]]["selected"].x
    for branch in ra_pst["branches"].values():
        branch["selected"] = branch["selected"].x
    ra_pst["objective"] = c_max.x
    
    return ra_pst