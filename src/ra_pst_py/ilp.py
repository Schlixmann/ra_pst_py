import gurobipy as gp
from gurobipy import GRB
import json


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
        "tasks": [taskId],
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
    for jobId1, job in ra_pst["jobs"].items():
        for jobId2 in job["after"]:
            model.addConstr(ra_pst["jobs"][jobId2]["start"] + ra_pst["jobs"][jobId2]["cost"]*ra_pst["branches"][ra_pst["jobs"][jobId2]["branch"]]["selected"] <= ra_pst["jobs"][jobId1]["start"])

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