from ortools.sat.python import cp_model
from collections import defaultdict
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
                    "branch_no":branch["branch_no"],
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
    
def conf_cp(ra_pst_json):
    ra_pst = transform_json(ra_pst_json)
    model = cp_model.CpModel()

    task_num = len(ra_pst["tasks"])
    
    task_branch_list = defaultdict(list)
    [task_branch_list[branch["task"]].append(branch) for branch in ra_pst["branches"]]

    task_vars = [model.NewBoolVar(f"{task}_task") for task in ra_pst["tasks"]]
    branch_vars = {}
    for task, taskId in enumerate(ra_pst["tasks"]):
        branch_vars[taskId] = [model.NewBoolVar(f"{ra_pst["tasks"][task]}_branch{i}") for i in range(len(task_branch_list[taskId]))]
        model.Add(sum(branch_vars[taskId]) == 1 - task_vars[task])

    for t in range(len(ra_pst["tasks"])):
        for i,var in enumerate(sum(list(branch_vars.values()), [])):
            if ra_pst["tasks"][t] in ra_pst["branches"][i]["deletes"]:
                model.Add(task_vars[t] >= branch_vars[i])
    for t in range(len(ra_pst["tasks"])):
        model.Add(sum([branch_vars[i] for i in range(len(ra_pst["branches"])) if ra_pst["tasks"][t] in ra_pst["branches"][i]["deletes"]]) >= task_vars[t])
        
    

    total_cost = sum(
        task_vars[j] * task_branch_list[ra_pst["tasks"][j]][i]["branchCost"]
        for j in range(len(ra_pst["tasks"])) 
        for i in range(len(task_branch_list[ra_pst["tasks"][j]]))
    )
    model.Minimize(total_cost)
    # Solve the model
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        # Extract the solution
        print([branch for task,branch in branch_vars.items()])
        print(solver.ObjectiveValue())
        solution = {
            task: next(
                i for i, var in enumerate(branch_vars[task]) if solver.BooleanValue(var)
            )
            for task in ra_pst["tasks"]
        }
        return {
            'selected_branches': solution,
            'total_cost': solver.ObjectiveValue()
        }
    else:
        return {'error': 'No solution found'}