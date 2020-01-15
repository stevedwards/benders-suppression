from master import Master
from subproblem import SubProblem
from gurobipy import *


class Solver:
    """The solver consists of the full Benders decomposition and can be run either as a diving heuristic of a complete search"""

    def __init__(self, data, ignore_starting_constraints=False):
        self.data = data

        # Create the master and sub-problem objects
        self.master = Master(self.data, ignore_starting_constraints)
        self.sub_problem = SubProblem(self.master, self.data)

    def solve(self, max_iterations_per_sub_problem, time_limit, dummy_multiplier, gap, complete):
        """ Execute the Benders Decomposition according to the following parameters

        :param max_iterations_per_sub_problem: The maximum number of constraints added for each subproblem iteration
        :param time_limit: The time limit to solve the master problem
        :param dummy_multiplier: Used to control how quickly the heuristic increases the current number of suppressions
        :param gap: The acceptable limit for the master problem
        :param complete: A boolean that indicates whether the heuristic or complete solve should be called
        """

        self.sub_problem.max_constraints_per_iteration = max_iterations_per_sub_problem
        self.master.mdl.setParam("TimeLimit", time_limit)
        self.master.mdl.setParam("MIPGap", gap)

        # Execute either the complete solve or the heuristic. Note the complete solve requires LazyConstraints
        if complete:
            self.master.mdl.setParam('OutputFlag', True)
            self.master.mdl.params.LazyConstraints = 1
            self.complete_solve()
        else:
            self.master.mdl.setParam('OutputFlag', False)
            self.heuristic_solve(dummy_multiplier)

    def heuristic_solve(self, dummy_multiplier):
        """Executes the diving heuristic. The term 'diving' implies that there is no backtracking. Hence once a cell is
        suppressed by the master problem, it will remain suppressed in subsequent iterations.

        To speed up the heuristic we use a 'dummy_multiplier' to ensure that between subsequent solves of the master problem, at
        least a certain more suppressions must be performed. This is achieved through a 'dummy_constraint' that we must track
        carefully and remove if we are to then run the complete solver.
        """

        # The HIGH LOW parameters are set to the nominal values, and to begin the dummy constraint does not exist
        self.sub_problem.reset_high_low()
        dummy_constraint = 0

        # Iterate until a solution is found
        while True:

            # The master problem is solved until a limit is reached (gap or time)
            self.master.mdl.optimize()

            # Remove the dummy constraint
            if dummy_constraint:
                self.master.mdl.remove(dummy_constraint)

            # The suppression patterns is then used to update the bounds in the attacker subproblem
            supp_levels = {cell: var.x for cell, var in self.master.vars.items()}
            self.sub_problem.attacker.update_bounds(supp_levels)

            # The sub-problems are solved and the HIGH LOW parameters never need to be refreshed - this is incorrect for complete
            self.sub_problem.solve(refresh_bounds=False)

            # Check to see if any constraints must be added
            if self.sub_problem.constraints_added > 0:
                print("Sub problems added {} new constraints".format(self.sub_problem.constraints_added))

                # This is the diving component. If a cell is suppressed in one iteration then it must be subsequently.
                for cell in self.data["cells"].keys():
                    self.master.vars[cell].setAttr(GRB.Attr.LB, supp_levels[cell])

                # Use the dummy_multiplier to ensure at least a certain number of suppressions occur in the next iteration
                num_suppressions = sum(1 for value in supp_levels.values() if value >= 1)
                enforced_num_suppressions = min(num_suppressions * dummy_multiplier, self.data["num_nz"])
                dummy_constraint = self.master.mdl.addConstr(
                    quicksum(self.master.mdl.getVars()) >= enforced_num_suppressions
                )

                # Print out the current number of suppressions and the new minimum
                print("Current number of suppressions: {} \nIncreasing to: {}".format(
                    num_suppressions, enforced_num_suppressions))

            # If no constraints are added then the solution is feasible
            else:
                print("SOLUTION FOUND!!!!!!!!!!!")
                break

        # Remove the additional restrictions
        self.reset_lower_bounds()

    def reset_lower_bounds(self):
        """Resets the lower bounds of the variables in the master problem to their initial values, i.e., sensitive cells are 1
        and 0 otherwise."""

        for cell, info in self.data["cells"].items():
            self.master.vars[cell].setAttr(GRB.Attr.LB, info["sensitive"])

    def complete_solve(self):
        """Performs the complete Benders Decomposition with Lazy Constraints to check feasible integer solutions as they are
        found"""

        # Ensures that the subproblem is solved with callbacks
        self.sub_problem.callback = True

        # Overloads the model variable with additional parameters so they can be used in the callback
        self.master.mdl._vars = self.master.vars
        self.master.mdl._data = self.data
        self.master.mdl._sub_problem = self.sub_problem

        # Solves the model
        self.master.mdl.optimize(my_callback)

    def add_trivial_mip_start(self):
        """Adds the starting solution where all cells are supppressed. Currently this is unused."""

        for cell, var in self.master.vars.items():
            is_zero = self.data["cells"][cell]["nominal"] == 0
            var.start = 0.0 if is_zero else 1.0

    def remove_redundant_suppressions(self):
        """Removes redundant suppressions by resolving the subproblem whilst also tracking secondary suppressions. If
        the HIGH and LOW values are the same afterwards then this implies a redundancy. This does not ensure that all
        redundancies are found but does provide a bound on all suppressed cells."""

        # Update the bounds on the subproblem and resolve in the extended mode (tracks the secondary suppressions)
        supp_levels = {cell: var.x for cell, var in self.master.vars.items()}
        self.sub_problem.attacker.update_bounds(supp_levels)
        self.sub_problem.solve(refresh_bounds=True, extended=True)

        # Check
        redundancies_found = 0
        bounds = {}
        for cell, supp in self.sub_problem.attacker.supp_level.items():
            bounds[cell] = (self.sub_problem.LOW[cell], self.sub_problem.HIGH[cell]) \
                if supp > 0.5 else (self.data["cells"][cell]["nominal"], self.data["cells"][cell]["nominal"])

            if supp > 0.5 and bounds[cell][1] - bounds[cell][0] <= 0:
                redundancies_found += 1
                self.sub_problem.attacker.supp_level[cell] = 0
                supp_levels[cell] = 0

        print("Removed {} redundancies".format(redundancies_found))
        return supp_levels, bounds

    def fix_upper_bounds(self):
        """Function used to remove redundant suppressions. Unsuppressed cells are forced to remain unsuppressed. Currently
        unused"""

        for cell, info in self.data["cells"].items():
            if self.master.vars[cell].x < 0.5:
                self.master.vars[cell].setAttr(GRB.Attr.UB, 0)


def my_callback(model, where):
    """The callback function used in the complete solve."""

    # Whenever an integer feasible solution is found
    if where == GRB.Callback.MIPSOL:

        # Solve the subproblem for the suppression pattern corresponding to this value
        supp_levels = {cell: min(max(model.cbGetSolution(model._vars[cell]), 0), 1) for cell, var in model._vars.items()}
        model._sub_problem.attacker.update_bounds(supp_levels)
        model._sub_problem.solve()






