from gurobipy import *


class Attacker:
    """This class creates a gurobi model for the attacker problem. For every sensitive cell, the attacker tries to maximise / 
    minimise the possible value of a sensitive cell subject to a given suppression pattern."""

    def __init__(self, data, output_log=""):
        
        # Data handling
        self.data = data
        self.output_log = output_log
        
        # Build the model
        self.m = Model("attack")
        self.vars = {cell: self.m.addVar(vtype=GRB.CONTINUOUS, name='y_{}'.format(cell)) for cell in self.data["cells"].keys()}
        
        # The gamma constraints are simply the specified relations. The symbol 'gamma' comes from the FS paper
        self.gamma_constraints = self.add_gamma_constraints()
        
        # The current suppression pattern
        self.supp_level = {}
        
        # Do not print the solve logs. Remove this if you want to inspect the logs.
        self.m.setParam('OutputFlag', False)

    def add_gamma_constraints(self):
        """Simply the linear sum constraints. My = b where b are all zeros"""

        constraints = {}
        for relation_id, contributions in self.data["relations"].items():
            lhs = LinExpr((1, self.vars[cell]) for cell in contributions[0])
            rhs = LinExpr((1, self.vars[cell]) for cell in contributions[1])
            constraints[relation_id] = self.m.addConstr(
                lhs == rhs,
                name="gamma_{}".format(relation_id)
            )
        return constraints

    def set_objective(self, target_cell, maximise):
        """Either minimise or maximise the target cell"""
        
        if maximise:
            self.m.setObjective(self.vars[target_cell], sense=GRB.MAXIMIZE)
        else:
            self.m.setObjective(self.vars[target_cell], sense=GRB.MINIMIZE)

    def update_bounds(self, supp_level):
        """Change the bounds of the variables based on a given suppression level."""

        # Store the suppression pattern
        self.supp_level = supp_level

        # Update bounds
        for cell, info in self.data["cells"].items():
            self.vars[cell].setAttr(GRB.Attr.UB, info["nominal"] + info["UB"] * supp_level[cell])
            self.vars[cell].setAttr(GRB.Attr.LB, info["nominal"] - info["LB"] * supp_level[cell])

    def optimise(self, target_cell, maximise):
        """Solve the attacker problem in a given direction (maximise / minimise)"""

        self.set_objective(target_cell, maximise)
        self.m.optimize()
        return self.m.objVal
