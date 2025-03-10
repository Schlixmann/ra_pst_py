import gurobipy as gp
print("Gurobi:", gp.gurobi.version())

import docplex.cp
print("CP:", docplex.cp.__version_info__)

print(gp.GRB.VERSION_MAJOR, gp.GRB.VERSION_MINOR, gp.GRB.VERSION_TECHNICAL)

import cplex
print(cplex.Cplex().get_version())