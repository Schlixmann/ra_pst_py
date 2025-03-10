from docplex.cp.model import *
import json
import gurobipy as gp
from gurobipy import GRB


context.solver.local.execfile = '/opt/ibm/ILOG/CPLEX_Studio2211/cpoptimizer/bin/x86-64_linux/cpoptimizer'

def cp_solve():
    model = CpoModel()

    # Main task (abstract representation, optional)
    main_task = model.interval_var(optional=True, name="MainTask")

    # Alternative 1: Executed by resource1 with duration 3
    task_alt1 = model.interval_var(optional=True, size=3, name="Task_Alt1")

    # Alternative 2: Executed by resource2 with duration 1
    task_alt2 = model.interval_var(optional=True, size=1, name="Task_Alt2")

    # Additional task triggered by alternative 2 (executed by another resource, duration 1)
    extra_task = model.interval_var(optional=True, size=1, name="ExtraTask")

    # Enforce alternative execution: Either task_alt1 or task_alt2 must be chosen
    model.add(model.alternative(main_task, [task_alt1, task_alt2]))

    # If alternative 2 is chosen, extra_task must be present
    model.add(model.presence_of(extra_task) == model.presence_of(task_alt2))

    # Ensure that only one of the alternatives is executed
    model.add(model.presence_of(task_alt1) + model.presence_of(task_alt2) == 1)

    # Solve the model
    solution = model.solve()
    print(solution)

def cp_solve2():
    model = CpoModel()

    # Main task (abstract representation, optional)
    main_task = model.interval_var(optional=True, name="MainTask")

    # Alternative 1: Executed by resource1 with duration 3
    task_alt1 = model.interval_var(optional=True, size=3, name="Task_Alt1")

    # Alternative 2: Executed by resource2 with duration 1
    task_alt2 = model.interval_var(optional=True, size=1, name="Task_Alt2")

    # Additional task triggered by alternative 2 (executed by another resource, duration 1)
    extra_task = model.interval_var(optional=True, size=1, name="ExtraTask")

    # Enforce alternative execution: Either task_alt1 or task_alt2 must be chosen
    model.add(equal(presence_of(task_alt2), presence_of(extra_task)))

    # If alternative 2 is chosen, extra_task must be present
    model.add(model.presence_of(extra_task) == model.presence_of(task_alt2))

    # Ensure that only one of the alternatives is executed
    model.add(model.presence_of(task_alt1) + model.presence_of(task_alt2) == 1)

    # Solve the model
    solution = model.solve()
    print(solution)

if __name__ == "__main__":
    cp_solve()
    cp_solve2()