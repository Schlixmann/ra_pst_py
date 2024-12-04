from .builder import build_rapst
import gurobipy as gp
from gurobipy import GRB
import json


def configuration_ilp(ra_pst_json):
    """
    Construct the ILP fromulation from a JSON object to the Gurobi model
    The JSON object should be in the shape:
    {
      tasks: list of tasks,
      resources: list of resources,
      branches: {
        task : [
          {
            "jobs": [{
              "resource": resource,
              "cost": cost
            }],
            "deletes": [task]
          }
        ]
      }
    }
    """
    # Read JSON object
    with open(ra_pst_json, "r") as f:
        ra_pst = json.load(f)
        tasks = ra_pst["tasks"]
        branches = []
        branch_costs = []
        job_costs = []
        for task, b in ra_pst["branches"].items():
            for branch in b:
                branch["task"] = task
                branches.append(branch)
                branch_cost = sum(float(job[1]) for job in branch["jobs"])
                # for job in branch["jobs"]:
                #     # print(f'job: {branch["jobs"]}')
                #     # job_costs.append(float(job["cost"]))
                #     job_costs.append(float(job[1]))
                #     branch_cost += float(job[1])
                branch_costs.append(branch_cost)

    model = gp.Model('RA-PST configuration')

    # Variables:
    # Define branches
    x = model.addVars(len(branches), vtype=(GRB.BINARY), name='x')
    # Define tasks
    y = model.addVars(len(tasks), vtype=(GRB.BINARY), name='y')

    # Objective:
    # Minimize the cost of the chosen branches
    model.setObjective(gp.quicksum(branch_costs[i] * x[i] for i in range(len(branches))), GRB.MINIMIZE)

    # Constraints:
    # Set the number of chosen branches equal to 1 if the task is not deleted
    model.addConstrs(gp.quicksum(x[i] for i in range(len(branches)) if tasks[t] == branches[i]["task"]) == 1 - y[t] for t in range(len(tasks)))

    # If a branch is selected that deletes a task, the task is not chosen
    for t in range(len(tasks)):
        model.addConstrs(y[t] >= x[i] for i in range(len(branches)) if tasks[t] in branches[i]["deletes"])

    # If none of the branches that deletes the task is chosen, the task can not be set to deleted
    model.addConstrs(gp.quicksum(x[i] for i in range(len(branches)) if tasks[t] in branches[i]["deletes"]) >= y[t] for t in range(len(tasks)))

    model.optimize()

    for b in range(len(branches)):
        print(f'branch {b} ({branches[b]["task"]}, {branch_costs[b]}): {x[b].x}')
    for t in range(len(tasks)):
        print(f'task {t} deleted: {y[t].x}')

def scheduling_ilp(ra_pst_json):
    """
    Construct the ILP fromulation from a JSON object to the Gurobi model
    The JSON object should be in the shape:
    {
      tasks: list of tasks,
      resources: list of resources,
      branches: {
        task : [
          {
            "jobs": [{
              "resource": resource,
              "cost": cost
            }],
            "deletes": [task]
          }
        ]
      }
    }
    """
    # Read JSON object
    with open(ra_pst_json, "r") as f:
        ra_pst = json.load(f)
        tasks = ra_pst["tasks"]
        branches = []
        jobs = []
        job_costs = []
        precedence = []
        for task, b in ra_pst["branches"].items():
            for branch in b:
                branch["task"] = task
                branches.append(branch)
                first_job = True
                for job in branch["jobs"]:
                    jobs.append(job)
                    job_costs.append(float(job[1]))
                    if first_job:
                        first_job = False
                    else:
                        precedence.append((len(jobs)-2, len(jobs)-1))

    model = gp.Model('RA-PST scheduling')

    # Add variables
    c_max = model.addVar(vtype=(GRB.CONTINUOUS), name='c_max')
    t = model.addVars(len(jobs), vtype=(GRB.CONTINUOUS), name='t') # starting times of the jobs
    e = {}
    for i in range(len(jobs)):
        for j in range(i+1, len(jobs)):
            e[(i,j)] = model.addVar(vtype=(GRB.BINARY), name=f'e_{i}_{j}')
    w = sum(job_costs)

    # Objective
    model.setObjective(c_max, GRB.MINIMIZE)

    # Constraints
    # set $C_{max}$ to be at least the starting time of each job plus the processing time of the job
    model.addConstrs(t[i] + job_costs[i] <= c_max for i in range(len(jobs)))

    # For two jobs on the same resource, no overlap can occur
    model.addConstrs((t[i] - t[j] <= -job_costs[i] + w*(1-e[i,j]) for i in range(len(jobs)) for j in range(i+1, len(jobs)) if jobs[i][0] == jobs[j][0]))
    model.addConstrs((t[j] - t[i] <= -job_costs[j] + w*e[i,j] for i in range(len(jobs)) for j in range(i+1, len(jobs)) if jobs[i][0] == jobs[j][0]) )

    # Precedence constraints between individual jobs
    model.addConstrs((t[i] - t[j] <= -job_costs[i] for i, j in precedence) )
    model.addConstrs((t[j] - t[i] <= -job_costs[j] + w for i, j in precedence) )

    # Optimize
    model.optimize()

    print(f'c_max: {c_max.x}')

    for job in range(len(jobs)):
        print(f'job {job} ({jobs[job][0]}, {jobs[job][1]}): {t[job].x}')
    print(f'precedence: {precedence}')
    for i,j in precedence:
        print(f'precedence {i}-{j}: {e[i,j].x}')