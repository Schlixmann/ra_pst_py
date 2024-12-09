import gurobipy as gp
from gurobipy import GRB
import json


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
                    "branchCost": 0
                }
                first_job = True
                for job in branch["jobs"]:
                    newJob = {
                        "branch": len(result["branches"]),
                        "resource": job[0],
                        "cost": float(job[1]),
                        "after": []
                    }
                    if first_job:
                        first_job = False
                    else:
                        newJob["after"].append(len(result["jobs"])-1)
                    newBranch["branchCost"] += float(job[1])
                    newBranch["jobs"].append(len(result["jobs"]))
                    result["jobs"].append(newJob)
                result["branches"].append(newBranch)

        return result




def configuration_ilp(ra_pst_json):
    """
    Construct the ILP fromulation from a JSON object to the Gurobi model
    """
    ra_pst = transform_json(ra_pst_json)

    model = gp.Model('RA-PST configuration')

    # Variables:
    # Define branches
    x = model.addVars(len(ra_pst["branches"]), vtype=(GRB.BINARY), name='x')
    # Define tasks
    y = model.addVars(len(ra_pst["tasks"]), vtype=(GRB.BINARY), name='y')

    # Objective:
    # Minimize the cost of the chosen branches
    model.setObjective(gp.quicksum(ra_pst["branches"]["branchCost"] * x[i] for i in range(len(ra_pst["branches"]))), GRB.MINIMIZE)

    # Constraints:
    # Set the number of chosen branches equal to 1 if the task is not deleted
    model.addConstrs(gp.quicksum(x[i] for i in range(len(ra_pst["branches"])) if ra_pst["tasks"][t] == ra_pst["branches"][i]["task"]) == 1 - y[t] for t in range(len(ra_pst["tasks"])))

    # If a branch is selected that deletes a task, the task is not chosen
    for t in range(len(ra_pst["tasks"])):
        model.addConstrs(y[t] >= x[i] for i in range(len(ra_pst["branches"])) if ra_pst["tasks"][t] in ra_pst["branches"][i]["deletes"])

    # If none of the branches that deletes the task is chosen, the task can not be set to deleted
    model.addConstrs(gp.quicksum(x[i] for i in range(len(ra_pst["branches"])) if ra_pst["tasks"][t] in ra_pst["branches"][i]["deletes"]) >= y[t] for t in range(len(ra_pst["tasks"])))

    model.optimize()

    for b in range(len(ra_pst["branches"])):
        print(f'branch {b} ({ra_pst["branches"][b]["task"]}, {ra_pst["branches"][b]["branchCost"]}): {x[b].x}')
    for t in range(len(ra_pst["tasks"])):
        print(f'task {t} deleted: {y[t].x}')

def scheduling_ilp(ra_pst_json):
    """
    Construct the ILP fromulation from a JSON object to the Gurobi model
    """
    ra_pst = transform_json(ra_pst_json)

    model = gp.Model('RA-PST scheduling')

    # Add variables
    c_max = model.addVar(vtype=(GRB.CONTINUOUS), name='c_max')
    t = model.addVars(len(ra_pst["jobs"]), vtype=(GRB.CONTINUOUS), name='t') # starting times of the jobs
    e = {}
    for i in range(len(ra_pst["jobs"])):
        for j in range(i+1, len(ra_pst["jobs"])):
            e[(i,j)] = model.addVar(vtype=(GRB.BINARY), name=f'e_{i}_{j}')
    w = sum(job["cost"] for job in ra_pst["jobs"])

    # Objective
    model.setObjective(c_max, GRB.MINIMIZE)

    # Constraints
    # set $C_{max}$ to be at least the starting time of each job plus the processing time of the job
    model.addConstrs(t[i] + ra_pst["jobs"][i]["cost"] <= c_max for i in range(len(ra_pst["jobs"])))

    # For two jobs on the same resource, no overlap can occur
    model.addConstrs((t[i] - t[j] <= -ra_pst["jobs"][i]["cost"] + w*(1-e[i,j]) for i in range(len(ra_pst["jobs"])) for j in range(i+1, len(ra_pst["jobs"])) if ra_pst["jobs"][i]["resource"] == ra_pst["jobs"][j]["resource"]))
    model.addConstrs((t[j] - t[i] <= -ra_pst["jobs"][j]["cost"] + w*e[i,j] for i in range(len(ra_pst["jobs"])) for j in range(i+1, len(ra_pst["jobs"])) if ra_pst["jobs"][i]["resource"] == ra_pst["jobs"][j]["resource"]) )

    # Precedence constraints between individual jobs
    model.addConstrs((t[i] + ra_pst["jobs"][i]["cost"] <= t[j] for j in range(len(ra_pst["jobs"])) for i in ra_pst["jobs"][j]["after"]) )

    # Optimize
    model.optimize()

    print(f'c_max: {c_max.x}')

    for job in range(len(ra_pst["jobs"])):
        print(f'job {job} ({ra_pst["jobs"][job]["resource"]}, {ra_pst["jobs"][job]["cost"]}): {t[job].x}')


def combined_ilp(ra_pst_json):
    """
    Construct the ILP fromulation from a JSON object to the Gurobi model
    """
    ra_pst = transform_json(ra_pst_json)

    model = gp.Model('RA-PST optimization')

    # Add variables
    c_max = model.addVar(vtype=(GRB.CONTINUOUS), name='c_max')
    t = model.addVars(len(ra_pst["jobs"]), vtype=(GRB.CONTINUOUS), name='t') # starting times of the jobs
    e = {}
    for i in range(len(ra_pst["jobs"])):
        for j in range(i+1, len(ra_pst["jobs"])):
            e[(i,j)] = model.addVar(vtype=(GRB.BINARY), name=f'e_{i}_{j}')
    w = sum(job["cost"] for job in ra_pst["jobs"])
    x = model.addVars(len(ra_pst["branches"]), vtype=(GRB.BINARY), name='x')
    y = model.addVars(len(ra_pst["tasks"]), vtype=(GRB.BINARY), name='y')

    # Objective
    model.setObjective(c_max, GRB.MINIMIZE)
    
    # Configuration constraints
    # Set the number of chosen branches equal to 1 if the task is not deleted
    model.addConstrs(gp.quicksum(x[i] for i in range(len(ra_pst["branches"])) if ra_pst["tasks"][t] == ra_pst["branches"][i]["task"]) == 1 - y[t] for t in range(len(ra_pst["tasks"])))

    # If a branch is selected that deletes a task, the task is not chosen
    for task in range(len(ra_pst["tasks"])):
        model.addConstrs(y[task] >= x[i] for i in range(len(ra_pst["branches"])) if ra_pst["tasks"][task] in ra_pst["branches"][i]["deletes"])

    # If none of the branches that deletes the task is chosen, the task can not be set to deleted
    model.addConstrs(gp.quicksum(x[i] for i in range(len(ra_pst["branches"])) if ra_pst["tasks"][t] in ra_pst["branches"][i]["deletes"]) >= y[t] for t in range(len(ra_pst["tasks"])))

    # Scheduling constraints
    # set $C_{max}$ to be at least the starting time of each job plus the processing time of the job
    model.addConstrs(t[i] + ra_pst["jobs"][i]["cost"]*x[ra_pst["jobs"][i]["branch"]] <= c_max for i in range(len(ra_pst["jobs"])))

    # For two jobs on the same resource, no overlap can occur
    model.addConstrs((t[i] - t[j] <= -ra_pst["jobs"][i]["cost"]*x[ra_pst["jobs"][i]["branch"]] + w*(1-e[i,j]) for i in range(len(ra_pst["jobs"])) for j in range(i+1, len(ra_pst["jobs"])) if ra_pst["jobs"][i]["resource"] == ra_pst["jobs"][j]["resource"]))
    model.addConstrs((t[j] - t[i] <= -ra_pst["jobs"][j]["cost"]*x[ra_pst["jobs"][j]["branch"]] + w*e[i,j] for i in range(len(ra_pst["jobs"])) for j in range(i+1, len(ra_pst["jobs"])) if ra_pst["jobs"][i]["resource"] == ra_pst["jobs"][j]["resource"]) )

    # Precedence constraints between individual jobs
    model.addConstrs((t[i] + ra_pst["jobs"][i]["cost"]*x[ra_pst["jobs"][i]["branch"]] <= t[j] for j in range(len(ra_pst["jobs"])) for i in ra_pst["jobs"][j]["after"]) )

    # Optimize
    model.optimize()

    # Store result in a result dict
    result = {
        "objective": c_max.x,
        "jobs": [],
        "branches": [],
        "tasks": []
    }

    for job in range(len(ra_pst["jobs"])):
        result["jobs"].append({
            "resource": ra_pst["jobs"][job]["resource"],
            "cost": ra_pst["jobs"][job]["cost"] * x[ra_pst["jobs"][job]["branch"]].x,
            "selected": x[ra_pst["jobs"][job]["branch"]].x,
            "start": t[job].x,
            "branch": ra_pst["jobs"][job]["branch"]
        })
    for b in range(len(ra_pst["branches"])):
        result["branches"].append({
            "id": b,
            "selected": x[b].x,
            "task": ra_pst["branches"][b]["task"]
        })
    for task in range(len(ra_pst["tasks"])):
        result["tasks"].append({
            "id": ra_pst["tasks"][task],
            "deleted": y[task].x
        })
    
    return result