from attacker import Attacker
from collections import defaultdict
from gurobipy import *


class SubProblem:
    """The sub-problems consist of solving a series of attacker sub-problems. Given the similarity of the attacker problems,
    we only build a single Attacker object and change the objective function between different solve calls.

    It is possible to detect that some attacker problems do not need to be solved. This is explained very well in the FS paper.
    For each sensitive cells a HIGH and a LOW value are tracked, which are originally set to their nominal value. The solutions
    to attacker problems are used to update these values. If the HIGH exceeds the upper protection limit then it is clearly
    already feasible

    It is also not necessary to solve all attacker problems if the suppression pattern is known to be invalid. Hence a
    parameter is given that limits the maximum number of constraints added per sub-problem iteration, set by default to 50
    which is the same as Tau-Argus from what I understand.

    The subproblem can either be solved during a callback or in a more classical benders decomposition. The functions used to
    add constraints to the master problem differ slightly as a result so need to be considered explicitly.
    """

    def __init__(self, master, data, callback=False, max_iterations_per_sub_problem=50):

        # The location of the master problem object is stored so constraints can be added directly as they are found.
        self.master = master

        # The data and parameters are stored as attributes.
        self.data = data
        self.callback = callback
        self.max_constraints_per_iteration = max_iterations_per_sub_problem
        self.constraints_added = False

        # If the sub-problems are run in extended mode then HIGH LOW track all suppressed cells not just the sensitive ones
        self.extended = False
        self.HIGH_LOW_cells = []

        # A single Attacker object is created. This makes solving a lot more efficient
        self.attacker = Attacker(data)

        # Sort the sensitive cells based on the size of their UPL and LPL
        self.non_increasing_UPL_sensitive_cells = sorted(self.data["sensitive cells"].keys(),
                                                         key=lambda x: self.data["sensitive cells"][x]["UPL"], reverse=True)

        self.non_increasing_LPL_sensitive_cells = sorted(self.data["sensitive cells"].keys(),
                                                         key=lambda x: self.data["sensitive cells"][x]["LPL"], reverse=True)

        # The HIGH and LOW parameters are initiated to their nominal values.
        self.HIGH = self.default_nominal_dict()
        self.LOW = self.default_nominal_dict()

    def reset_high_low(self):
        """Reset the HIGH and LOW parameters to their nominal values. This is done between consecutive solves of the
        subproblem in the complete solve mode. It does not need to be performed in the diving heuristic"""

        self.HIGH = self.default_nominal_dict()
        self.LOW = self.default_nominal_dict()

    def solve(self, reset_model=False, refresh_bounds=True, extended=False):
        """ Refine assumes the first callback is to check the trivial seed solution, and the second callback is to
        check the solution where only primary suppression is completed.
        """

        # The attacker model is reset between subsequent subproblems iterations but not between individual attacker solvers
        if reset_model:
            self.attacker.m.reset()

        # Track how many constraints are added in this subproblem iteration
        self.constraints_added = 0

        # Reset the HIGH and LOW parameters if necessary
        if refresh_bounds:
            self.reset_high_low()

        # Set relevant cells to keep track of HIGH and LOWS. This is typically just the sensitive cells but sometimes all
        # suppressed cells
        self.HIGH_LOW_cells = [cell for cell, supp in self.attacker.supp_level.items() if supp > 0.5] if extended else \
            self.data["sensitive cells"].keys()

        # Solve all the UPL in non-increasing order
        for sensitive_cell in self.non_increasing_UPL_sensitive_cells:
            if self.constraints_added <= self.max_constraints_per_iteration:
                self.process_upper_protection_level(sensitive_cell)

        # Solve all the LPL in non-increasing order
        for sensitive_cell in self.non_increasing_LPL_sensitive_cells:
            if self.constraints_added <= self.max_constraints_per_iteration:
                self.process_lower_protection_level(sensitive_cell)

    def process_upper_protection_level(self, sensitive_cell):
        """Process the upper protection level of a specific sensitive cell. Checks if the attacker problem must be solved and
        if so solves appropriately and either adds a constraint or updates the HIGH LOW parameter"""

        cell_nominal = self.data["cells"][sensitive_cell]["nominal"]
        cell_UPL = self.data["sensitive cells"][sensitive_cell]["UPL"]

        # Checks to see if the limit has not yet been exceeded and if so solves the attacker problem accordingly
        if self.HIGH[sensitive_cell] < cell_nominal + cell_UPL:
            y_max = self.attacker.optimise(sensitive_cell, maximise=True)

            # Either adds a constraint or updates HIGH and LOW
            if cell_nominal + cell_UPL > y_max:
                self.add_upper_constraint_to_master(sensitive_cell)
                self.constraints_added += 1
            else:
                self.update_high_low()

    def process_lower_protection_level(self, sensitive_cell):
        """Process the lower protection level of a specific sensitive cell. Checks if the attacker problem must be solved and
               if so solves appropriately and either adds a constraint or updates the HIGH LOW parameter"""

        cell_nominal = self.data["cells"][sensitive_cell]["nominal"]
        cell_LPL = self.data["sensitive cells"][sensitive_cell]["LPL"]

        # Checks to see if the limit has not yet been exceeded and if so solves the attacker problem accordingly
        if self.LOW[sensitive_cell] > cell_nominal - cell_LPL:
            y_min = self.attacker.optimise(sensitive_cell, maximise=False)

            # Either adds a constraint or updates HIGH and LOW
            if cell_nominal - cell_LPL < y_min:
                self.add_lower_constraint_to_master(sensitive_cell)
                self.constraints_added += 1
            else:
                self.update_high_low()

    def positive_reduced_cost(self):
        """Determines the cells that have a positive reduced cost in the current solution of the attacker problem"""

        for cell in self.data["cells"].keys():
            if self.attacker.vars[cell].RC > 0:
                yield cell, abs(self.attacker.vars[cell].RC)

    def negative_reduced_cost(self):
        """Determines the cells that have a negative reduced cost in the current solution of the attacker problem"""
        for cell in self.data["cells"].keys():
            if self.attacker.vars[cell].RC < 0:
                yield cell, abs(self.attacker.vars[cell].RC)

    def add_upper_constraint_to_master(self, sensitive_cell):
        """Adds a constraint due to the violation of the UPL of specific sensitive cell. This is well explained in the FS paper"""

        protection_limit = self.data["sensitive cells"][sensitive_cell]["UPL"]

        # The first expression are for cells with positive reduced cost
        first_expr = LinExpr((min(value * self.data["cells"][cell]["UB"], protection_limit),
                              self.master.vars[cell]) for cell, value in self.positive_reduced_cost() if
                             self.data["cells"][cell]["nominal"] != 0)

        # The second expression are for cells with negative reduced cost
        second_expr = LinExpr((min(value * self.data["cells"][cell]["LB"], protection_limit),
                               self.master.vars[cell]) for cell, value in self.negative_reduced_cost() if
                              self.data["cells"][cell]["nominal"] != 0)

        # The functions used to add the constraint are slightly different based on whether its a lazy constraint or not
        if self.callback:
            self.master.mdl.cbLazy(
                first_expr + second_expr >= protection_limit
            )
        else:
            self.master.mdl.addConstr(
                first_expr + second_expr >= protection_limit, name="lazy_upper_{}".format(sensitive_cell)
            )

    def add_lower_constraint_to_master(self, sensitive_cell):
        """Adds a constraint due to the violation of the LPL of specific sensitive cell. This is well explained in the FS paper"""

        protect_limit = self.data["sensitive cells"][sensitive_cell]["LPL"]

        # The first expression are for cells with positive reduced cost
        first_expr = LinExpr((min(value * self.data["cells"][cell]["LB"], protect_limit),
                              self.master.vars[cell]) for cell, value in self.positive_reduced_cost())

        # The second expression are for cells with negative reduced cost
        second_expr = LinExpr((min(value * self.data["cells"][cell]["UB"], protect_limit),
                               self.master.vars[cell]) for cell, value in self.negative_reduced_cost())

        # The functions used to add the constraint are slightly different based on whether its a lazy constraint or not
        if self.callback:
            self.master.mdl.cbLazy(
                first_expr + second_expr >= protect_limit
            )

        else:
            self.master.mdl.addConstr(
                first_expr + second_expr >= protect_limit, name="lazy_lower_{}".format(
                    sensitive_cell)
            )

    def update_high_low(self):
        """Update the HIGH and LOW dictionaries based off allowable solutions to the attacker problem"""

        for sensitive_cell in self.HIGH_LOW_cells:
            self.HIGH[sensitive_cell] = max(self.HIGH[sensitive_cell],
                                            self.attacker.vars[sensitive_cell].x)

            self.LOW[sensitive_cell] = min(self.LOW[sensitive_cell],
                                           self.attacker.vars[sensitive_cell].x)

    def default_nominal_dict(self):
        """A function to initiate a dictionary to the nominal values. This is probably an unnecessary efficieny improvement"""
        return KeyDependentDict(lambda x: self.data['cells'][x]["nominal"])


class KeyDependentDict(defaultdict):
    """Makes a new class which inherits from the defaultdict so that the default value is a function of the key"""

    def __init__(self, f_of_x):
        super(KeyDependentDict, self).__init__(None)  # base class doesn't get a factory
        self.f_of_x = f_of_x  # save f(x)

    def __missing__(self, key):  # called when a default needed
        ret = self.f_of_x(key)  # calculate default value
        self[key] = ret  # and install it in the dict
        return ret
