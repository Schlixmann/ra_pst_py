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
    
    # create branch variables for each task and set number of chosen branches == 1 if task is not deleted
    branch_vars = {}
    for task, taskId in enumerate(ra_pst["tasks"]):
        branch_vars[taskId] = [model.NewBoolVar(f"{ra_pst['tasks'][task]}_branch{i}") for i in range(len(task_branch_list[taskId]))]
        # Set the number of chosen branches equal to 1 if the task is not deleted
        model.Add(sum(branch_vars[taskId]) == 1 - task_vars[task])

    flat_branch_vars = sum(list(branch_vars.values()), [])
    # If a branch is selected that deletes a task, the task is not chosen
    for t in range(len(ra_pst["tasks"])):
        for i,var in enumerate(flat_branch_vars):
            if ra_pst["tasks"][t] in ra_pst["branches"][i]["deletes"]:
                model.Add(task_vars[t] >= flat_branch_vars[i])
    
    # If none of the branches that deletes the task is chosen, the task can not be set to deleted                 
    for t in range(len(ra_pst["tasks"])):
        model.Add(sum([flat_branch_vars[i] for i in range(len(ra_pst["branches"])) if ra_pst["tasks"][t] in ra_pst["branches"][i]["deletes"]]) >= task_vars[t])

    total_cost = sum(
        flat_branch_vars[j] * sum(task_branch_list.values(), [])[j]["branchCost"]
        for j in range(len(flat_branch_vars))
        )
    model.Minimize(total_cost)
    # Solve the model
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        # Extract the solution
        print(solver.ObjectiveValue())
        solution = {
            task: [branch_vars[task].index(var) for var in branch_vars[task]
                   if solver.value(var) == 1] for task in ra_pst["tasks"]}
        return result_to_dict(solver, ra_pst, flat_branch_vars, task_vars)
        
    else:
        raise ValueError({'error': 'No solution found'})
    
def result_to_dict(solver, ra_pst, flat_branch_vars, task_vars  ):
    # Store result in a result dict
    result = {
        "objective": solver.ObjectiveValue(),
        "jobs": [],
        "branches": [],
        "tasks": []
    }

    for job in range(len(ra_pst["jobs"])):
        result["jobs"].append({
            "resource": ra_pst["jobs"][job]["resource"],
            "cost": ra_pst["jobs"][job]["cost"] * solver.value(flat_branch_vars[ra_pst["jobs"][job]["branch"]]),
            "selected": solver.value(flat_branch_vars[ra_pst["jobs"][job]["branch"]]),
            #"start": t[job].x,
            "branch": ra_pst["jobs"][job]["branch"]
        })
    for b in range(len(ra_pst["branches"])):
        result["branches"].append({
            "id": b,
            "selected": solver.value(flat_branch_vars[b]),
            "task": ra_pst["branches"][b]["task"],
            "branch_no": ra_pst["branches"][b]["branch_no"]
        })
    for task in range(len(ra_pst["tasks"])):
        result["tasks"].append({
            "id": ra_pst["tasks"][task],
            "deleted": solver.value(task_vars[task])
        })
    return result
    
def conf_cp_scheduling(ra_pst_json):
    # create multiple sequences:
    sequences = {}
    for i in range(5):
        ra_pst = transform_json(ra_pst_json)
        sequences[i] = ra_pst
    model = cp_model.CpModel()

    task_num = len(ra_pst["tasks"])
    task_branch_list = {defaultdict(list)}
    task_vars ={}
    branch_vars = {}

    for sequence, ra_pst in sequence.items():
        task_branch_list[sequence] = [task_branch_list[sequence][branch["task"]].append(branch) for branch in ra_pst["branches"]]
        
        # create task_vars
        task_vars[sequence] = [model.NewBoolVar(f"{task}_task") for task in ra_pst["tasks"]]
    
    # create branch variables for each task and set number of chosen branches == 1 if task is not deleted
    for sequence, ra_pst in sequences.items():
        for task, taskId in enumerate(ra_pst["tasks"]):
            branch_vars[sequence][taskId] = [model.NewBoolVar(f"{ra_pst["tasks"][task]}_branch{i}") for i in range(len(task_branch_list[taskId]))]
            # Set the number of chosen branches equal to 1 if the task is not deleted
            model.Add(sum(branch_vars[sequence][taskId]) == 1 - task_vars[sequence][task])
            # TODO needs intervals?!

        flat_branch_vars = sum(list(branch_vars[sequence].values()), [])
        # If a branch is selected that deletes a task, the task is not chosen
        for t in range(len(ra_pst["tasks"])):
            for i,var in enumerate(flat_branch_vars):
                if ra_pst["tasks"][t] in ra_pst["branches"][i]["deletes"]:
                    model.Add(task_vars[sequence][t] >= flat_branch_vars[i])
                    # TODO chosen or not chosen with task
        # If none of the branches that deletes the task is chosen, the task can not be set to deleted                 
        for t in range(len(ra_pst["tasks"])):
            model.Add(sum([flat_branch_vars[i] for i in range(len(ra_pst["branches"])) if ra_pst["tasks"][t] in ra_pst["branches"][i]["deletes"]]) >= task_vars[sequence][t])

    # Scheduling constraints

    # Makespan variable
    horizon = 5000 #TODO calc. actually useful horizon
    obj_var = model.NewIntVar(0, 500, "makespan")
    model.add_max_equality(
        obj_var,
        # TODO highest value of all interval variables
    )
    model.Minimize(obj_var)
    
    # Solve the model
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        # Extract the solution
        print(solver.ObjectiveValue())
        solution = {
            task: [branch_vars[task].index(var) for var in branch_vars[task]
                   if solver.value(var) == 1] for task in ra_pst["tasks"]}
        return result_to_dict(solver, ra_pst, flat_branch_vars, task_vars)
        
    else:
        raise ValueError({'error': 'No solution found'})