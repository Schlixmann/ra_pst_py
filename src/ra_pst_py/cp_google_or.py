from ortools.sat.python import cp_model
from collections import defaultdict, namedtuple
import json

    
def conf_cp(ra_pst_json):
    """
    Input ra_pst_json format:
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
    # ra_pst = transform_json(ra_pst_json)
    with open(ra_pst_json) as f:
        ra_pst = json.load(f)
    # TODO: refactor with the new JSON format

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
    
def result_to_dict(solver, ra_pst, flat_branch_vars, task_vars):
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
    task_branch_list = {}
    task_vars ={}
    branch_vars = {}
    # Named tuple to store information about created variables.
    task_type = namedtuple("task_type", "start end interval duration presence task_id sequence")
    # Named tuple to manipulate solution information.
    assigned_task_type = namedtuple(
        "assigned_task_type", "start job index duration presence"
    )
    task_resource_type = namedtuple(
        "task_resource_type", "interval presence task_id sequence branch"
    )

    for sequence, ra_pst in sequences.items():
        task_branch_list[sequence] = defaultdict(list)
        [task_branch_list[sequence][branch["task"]].append(branch) for branch in ra_pst["branches"]]
        
        # create task_vars
        task_vars[sequence] = [model.NewBoolVar(f"{task}_task") for task in ra_pst["tasks"]]
    
    # create branch variables for each task and set number of chosen branches == 1 if task is not deleted
    flat_branch_vars = {}
    for sequence, ra_pst in sequences.items():
        branch_vars[sequence] = defaultdict(list)
        for task, taskId in enumerate(ra_pst["tasks"]):
            branch_vars[sequence][taskId] = [model.NewBoolVar(f"{ra_pst["tasks"][task]}_branch{i}") for i in range(len(task_branch_list[sequence][taskId]))]
            # Set the number of chosen branches equal to 1 if the task is not deleted
            model.Add(sum(branch_vars[sequence][taskId]) == 1 - task_vars[sequence][task])
            # TODO needs intervals?!

        flat_branch_vars[sequence] = sum(list(branch_vars[sequence].values()), [])
        # If a branch is selected that deletes a task, the task is not chosen
        for t in range(len(ra_pst["tasks"])):
            for i,var in enumerate(flat_branch_vars[sequence]):
                if ra_pst["tasks"][t] in ra_pst["branches"][i]["deletes"]:
                    model.Add(task_vars[sequence][t] >= flat_branch_vars[sequence][i])
                    # TODO chosen or not chosen with task
        # If none of the branches that deletes the task is chosen, the task can not be set to deleted                 
        for t in range(len(ra_pst["tasks"])):
            model.Add(sum([flat_branch_vars[sequence][i] for i in range(len(ra_pst["branches"])) if ra_pst["tasks"][t] in ra_pst["branches"][i]["deletes"]]) >= task_vars[sequence][t])

    # Scheduling constraints
    horizon = 5000 #TODO calc. actually useful horizon
    machine_to_intervals = defaultdict(dict)
    all_tasks = {}
    for sequence, ra_pst in sequences.items():
        for task_id, task in enumerate(ra_pst["tasks"]):
            for branch_id, branch in enumerate(ra_pst["branches"]):
                if task == branch["task"]:
                    suffix = f"_{sequence}_{task}"
                    resource, duration = branch["jobs_detailed"][0]
                    presence = model.NewBoolVar(f"pres_{sequence}_{task}_{branch_id}")

                    not_task_var = model.NewBoolVar(f"not_task_{task_id}")
                    model.Add(not_task_var == 1 - task_vars[sequence][task_id])
                    model.AddBoolAnd([not_task_var, flat_branch_vars[sequence][branch_id]]).only_enforce_if(presence)
                    model.AddBoolOr([not_task_var.Not(), flat_branch_vars[sequence][branch_id].Not()]).only_enforce_if(presence.Not())

                    start_var = model.NewIntVar(0, horizon, "start" + suffix)
                    end_var = model.NewIntVar(0, horizon, "end" + suffix)
                    task_interval = model.NewOptionalIntervalVar(start_var, int(duration), end_var, presence ,"interval" + suffix)
                    all_tasks[sequence, task, branch_id] = task_type(
                        start = start_var, end=end_var, interval=task_interval, duration=int(duration), presence=presence, task_id=task, sequence=sequence
                    )
                    machine_to_intervals[resource][sequence, task, branch_id] = task_resource_type(interval=task_interval, presence=presence, task_id=task, sequence=sequence, branch=branch_id)

    for resource in ra_pst["resources"]:
        machine_intervals = [interval.interval for interval in machine_to_intervals[resource].values()]
        model.add_no_overlap(machine_intervals)

    # Precedence inside a sequence:
    # TODO bring on branch level
    #for sequence, ra_pst in sequences.items():
    #    for task_id, task in enumerate(ra_pst["tasks"]):
    #        if task_id < len(ra_pst["tasks"])-1:
    #            model.add(all_tasks[sequence, ra_pst["tasks"][task_id +1]].start >= all_tasks[sequence, ra_pst["tasks"][task_id]].end)

    # TODO Group by sequ, task and branches
    groups = {}
    for sequence in sequences.keys():
        groups[sequence] = defaultdict(list)
    for (sequence, task, branch), values in all_tasks.items():
        groups[sequence][task].append(branch)
    
    for sequence, group in groups.items():
        for task, branches in list(group.items())[:-1]:
            for branch1 in branches:
                task_id = list(group.keys()).index(task)
                if task_id + 1 < len(list(group.keys())):
                    next_task, next_branches = list(group.keys())[task_id + 1], list(group.values())[task_id + 1]
                    for branch2 in next_branches:
                        model.add(all_tasks[sequence, next_task, branch2].start >= all_tasks[sequence,task,branch1].end)


    # Makespan variable
    obj_var = model.NewIntVar(0, horizon, "makespan")
    model.add_max_equality(
        obj_var,
        [task.end for task in all_tasks.values()],
    )
    model.Minimize(obj_var)
    
    # Solve the model
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        if status == cp_model.OPTIMAL:
            status = "Optimal"
        elif status == cp_model.FEASIBLE:
            status = "Feasible"
        print(f"Solution: {status}")
        # Create one list of assigned tasks per machine.
        assigned_jobs = defaultdict(list)
        for sequence, ra_pst in sequences.items(): 
            for resource, values in machine_to_intervals.items():
                for key, task_resource in values.items():
                    if solver.value(task_resource.presence):
                        machine = resource
                        task_tuple = (task_resource.sequence, task_resource.task_id, task_resource.branch)
                        assigned_jobs[machine].append(
                            assigned_task_type(
                                start=solver.value(all_tasks[task_tuple].start),
                                job=sequence,
                                index=task_tuple,
                                duration=solver.value(all_tasks[task_tuple].end) - solver.value(all_tasks[task_tuple].start),
                                presence = solver.value(all_tasks[task_tuple].presence)
                            )
                        )
        

        # Create per machine output lines.
        output = ""
        for machine in ra_pst["resources"]:
            # Sort by starting time.
            assigned_jobs[machine].sort()
            sol_line_tasks = "Machine " + str(machine) + ": "
            sol_line = "           "

            for assigned_task in assigned_jobs[machine]:
                name = f"job_{assigned_task.job}_task_{assigned_task.index}"
                # add spaces to output to align columns.
                sol_line_tasks += f"{name:15}"

                start = assigned_task.start
                duration = assigned_task.duration
                sol_tmp = f"[{start},{start + int(duration)}]"
                # add spaces to output to align columns.
                sol_line += f"{sol_tmp:15}"

            sol_line += "\n"
            sol_line_tasks += "\n"
            output += sol_line_tasks
            output += sol_line

        # Finally print the solution found.
        print(f"{status} Schedule Length: {solver.objective_value}")
        #print(output)
        for sequence, flat_branch_var in flat_branch_vars.items():
            print([solver.value(branch) for branch in flat_branch_var])
        sol = [{(solver.value(all_tasks[task].start), solver.value(all_tasks[task].end), solver.value(all_tasks[task].presence))} for task in all_tasks if solver.value(all_tasks[task].presence) == 1]
        print([{(solver.value(all_tasks[task].start), solver.value(all_tasks[task].end), solver.value(all_tasks[task].presence))} for task in all_tasks])
        print(len(sol))
        result = result_to_dict_sched(solver, sequences, flat_branch_vars, task_vars, list(branch_vars.keys()), all_tasks, machine_to_intervals)
        return result
    else:
        print("No solution found.")


def result_to_dict_sched(solver, ra_pst, flat_branch_vars, task_vars, sequences, all_tasks, machine_to_intervals):
    # Store result in a result dict
    result = {}
    for sequence in sequences:
        result[sequence] = {
            "objective": solver.ObjectiveValue(),
            "jobs": [],
            "branches": [],
            "tasks": []
        }
    for key, job in all_tasks.items():
        sequence, task_id, branch = key
        result[sequence]["jobs"].append({
            "task" : task_id,
            "resource": [resource for resource in machine_to_intervals if key in machine_to_intervals[resource].keys()],
            "cost": solver.value(all_tasks[(sequence, task_id, branch)].duration) * solver.value(all_tasks[(sequence, task_id, branch)].presence),
            "selected": solver.value(all_tasks[(sequence, task_id, branch)].presence),
            "start": solver.value(all_tasks[(sequence, task_id, branch)].start),
            "branch": branch
        })
    
    for sequence in sequences:       
        for b in range(len(ra_pst[sequence]["branches"])):
            result[sequence]["branches"].append({
                "id": b,
                "selected": solver.value(flat_branch_vars[sequence][b]),
                "task": ra_pst[sequence]["branches"][b]["task"],
                "branch_no": ra_pst[sequence]["branches"][b]["branch_no"]
            })
        for task in range(len(ra_pst[sequence]["tasks"])):
            result[sequence]["tasks"].append({
                "id": ra_pst[sequence]["tasks"][task],
                "deleted": solver.value(task_vars[sequence][task])
            })



    return result