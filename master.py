from attacker import *


class Master:
    """The master problem is represented as its own class. The Master problem tries to minimise the amount of cells that
    must be suppressed subject to some initial constraints as well as constraints added by the attacker sub-problems.
    """

    def __init__(self, data, ignore_starting_constraints):

        # Ensures that the master problem can access the data
        self.data = data

        # Creates a Gurobi model for the master problem and a binary variable for each cell
        self.mdl = Model("master")
        self.vars = self.create_vars()

        # Adds the initial constraints unless specified otherwise
        if not ignore_starting_constraints:
            self.create_initial_constraints()

    def create_vars(self):
        """Creates a binary variable for each cell. If the value of the variable is 1 then the cell must be suppressed, and 0
        if it is published exactly. Primary suppressions are forced to be 1 and structural zeros are forced to be 0."""

        my_vars = {}
        for cell_name, cell_data in self.data["cells"].iteritems():
            my_vars[cell_name] = self.mdl.addVar(vtype=GRB.BINARY, name=str(cell_name),
                                                 lb=cell_data["sensitive"],
                                                 ub=0 if cell_data["nominal"] == 0 else 1,
                                                 obj=cell_data["weight"] if "weight" in cell_data.keys() else 1)

        return my_vars

    def create_initial_constraints(self):
        """Initiates the constraint pool with two classes of constraints. The first ensures that each relation containing
        primary suppression provides at least enough protection for those cells. The second ensures that a relation cannot have
        exactly one suppressed cell"""

        # Iterate over each relation, collect all the cells into a list, and check how many sensitive cells there are
        for relation, cells in self.data['relations'].items():
            all_cells = cells[0] + cells[1]
            num_sensitive_cells = sum(self.data["cells"][cell]["sensitive"] for cell in all_cells)

            # Then iterate over all the cells in the relation and check if they are sensitive
            for cell in all_cells:
                if self.data["cells"][cell]["sensitive"]:

                    # Check if protected by primary suppression
                    Q_plus = cells[1] if cell in cells[0] else cells[0]
                    Q_minus = cells[0] if cell in cells[0] else cells[1]
                    UPL = self.data["sensitive cells"][cell]["UPL"]
                    LPL = self.data["sensitive cells"][cell]["LPL"]

                    # Check if the Upper Protection Level is violated
                    if sum(self.data["cells"][cell_name]['UB'] for cell_name in Q_plus
                           if self.data["cells"][cell_name]["sensitive"] and cell != cell_name) + \
                            sum(self.data["cells"][cell_name]['LB'] for cell_name in Q_minus if
                                self.data["cells"][cell_name]["sensitive"] and cell != cell_name) < UPL:

                        # If so add a constraint to ensure it is protected
                        self.mdl.addConstr(
                            quicksum(
                                min(self.data["cells"][cell_name]["UB"], UPL) * self.vars[cell_name] for cell_name in Q_plus if
                                cell_name !=
                                cell) +
                            quicksum(
                                min(self.data["cells"][cell_name]["LB"], UPL) * self.vars[cell_name] for cell_name in Q_minus if
                                cell_name
                                != cell) >= UPL, name="init_upper_{}".format(relation)
                        )

                    # Check if the Lower Protection Level is violated
                    if sum(self.data["cells"][cell_name]['UB'] for cell_name in Q_minus
                           if self.data["cells"][cell_name]["sensitive"] and cell != cell_name) + \
                            sum(self.data["cells"][cell_name]['LB'] for cell_name in Q_plus if
                                self.data["cells"][cell_name]["sensitive"] and cell != cell_name) < LPL:

                        # If so add a constraint to ensure it is protected
                        self.mdl.addConstr(
                            quicksum(min(self.data["cells"][cell_name]["UB"], LPL)*self.vars[cell_name]
                                     for cell_name in Q_minus if cell_name != cell) +
                            quicksum(
                                min(self.data["cells"][cell_name]["LB"], LPL) * self.vars[cell_name] for cell_name in Q_plus if
                                cell_name
                                != cell) >= LPL, name="init_lower{}".format(relation)
                        )

            # Bridgeless constraints are only relevant if the relation has less than 2 primary suppressions
            if num_sensitive_cells < 2:
                for cell in all_cells:

                    # If one cell is suppressed then so to must another
                    self.mdl.addConstr(quicksum(self.vars[cell_name] for cell_name in all_cells if cell_name != cell and
                                                self.data["cells"][cell_name]["nominal"] > 0
                                                ) >= self.vars[cell], name="init_bridge_{}_{}".format(relation, cell))

    def provide_feasible_solution(self, supp_levels):
        """Provides the Gurobi Model with a feasible suppression pattern as a initial feasible solution"""

        for cell, value in supp_levels.items():
            self.vars[cell].start = value

    def print_details(self):
        """Prints the number of cells, number of primary suppressions, and number of relations"""

        print("{} number cells".format(len(self.data["cells"])))
        print("{} number primary".format(len(self.data["sensitive cells"])))
        print("{} number relations".format(len(self.data["relations"])))

    def print_results(self):
        """Prints the objective, number of primary suppressions, secondary suppressions, and unsuppressed cells """

        num_primary = len(self.data["sensitive cells"])
        num_secondary = sum(var.x > 0.5 for var in self.vars.values()) - num_primary
        num_unsuppressed = len(self.data["cells"]) - num_primary - num_secondary

        print("objective {}".format(self.mdl.ObjVal))
        print("{} primary suppressions".format(num_primary))
        print("{} secondary suppressions".format(num_secondary))
        print("{} unsuppressed cells".format(num_unsuppressed))
