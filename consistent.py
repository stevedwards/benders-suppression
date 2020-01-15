from gurobipy import *


def find_most_central_consistent_solution(data, bounds):
    """Determines a consistent set of values for the cells within certain bounds that minimises the distance from the centre of
    the bounds, weighted strongly towards secondary suppression.

    bounds is a dictionary whose keys are cells and values are tuples where the values are the lower and upper inference
    bounds"""
    
    # Create an LP model and turns off the output flag
    model = Model("consistent")
    model.setParam('OutputFlag', False)
    
    # A is the centre of the bound and B is the gap from the centre to the limits.
    A = {cell: (bound[0]+bound[1])/2 for cell, bound in bounds.items()}
    B = {cell: (bound[1]-bound[0])/2 for cell, bound in bounds.items()}

    # Define variables
    z_min_vars = {cell: model.addVar(vtype=GRB.CONTINUOUS,
                                     lb=0,
                                     ub=B[cell] - 1 if A[cell] - B[cell] == 0 and B[cell] > 0 else B[cell],
                                     obj=1 if info['sensitive'] else 100) for cell, info in data["cells"].items()}

    z_max_vars = {cell: model.addVar(vtype=GRB.CONTINUOUS,
                                     lb=0,
                                     ub=B[cell],
                                     obj=1 if info['sensitive'] else 100) for cell, info in data["cells"].items()}

    # Define constraints
    for relation, (lhs, rhs) in data['relations'].items():
        model.addConstr(
            quicksum(A[cell] + z_max_vars[cell] - z_min_vars[cell] for cell in lhs) ==
            quicksum(A[cell] + z_max_vars[cell] - z_min_vars[cell] for cell in rhs)
        )

    # Solve the model
    model.optimize()

    # Store the solution as new attributes in the data.
    for cell, info in data["cells"].items():
        new_nominal = A[cell] + z_max_vars[cell].x - z_min_vars[cell].x
        data["cells"][cell]["new_nominal"] = new_nominal
        data["cells"][cell]["new_diff"] = B[cell] + max(z_max_vars[cell].x, z_min_vars[cell].x)
