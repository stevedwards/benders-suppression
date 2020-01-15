from collections import defaultdict
import re
import argparse


def data(my_file):
    """Reads the data in the standard form from file"""

    # Creates a default dictionary to initiate the data structure
    my_data = {"cells": {}, "relations": defaultdict(lambda: ([], [])), "sensitive cells": {}}

    # Initiates some booleans to check for incorrect format
    invalid_zeros = False
    invalid_bounds = False

    # Reads the file line by line
    with open(my_file, 'r') as f:
        for line_num, line in enumerate(f.readlines()):

            # Splits the line based on a range of different characters (this is due to the unconventional format)
            info =[item for item in re.split(':|\t|\(|\)|\n| ', line) if item]

            # Skip the first line - that zero does not represent anything as far as I know
            if line_num == 0:
                continue

            # Read the number of cells
            elif line_num == 1:
                num_vars = int(line.split()[0])

            # Reads the details for each cell
            elif line_num <= num_vars + 1:

                # Infer whether the cell is sensitive
                is_sensitive = info[3].strip() == 'u'
                cell_id = int(info[0])  # type: int

                # Check to see zero cells have been marked correctly
                if int(float(info[1])) == 0 and info[3].strip() != 'z' and not invalid_zeros:
                    print ValueError("{} Input data has a zero nominal value not indicated correctly".format(cell_id))
                    invalid_zeros = True

                # Check if bounds invalid
                if float(info[4]) > float(info[5]) and not invalid_bounds:
                    print ValueError("{} Lower bound exceeds upper bound".format(cell_id))
                    invalid_bounds = True

                # Stores the cell data in the data object
                my_data["cells"][cell_id] = {"nominal": int(float(info[1])),
                                             "sensitive": is_sensitive,
                                             "weight": int(float(info[2])),
                                             "lb": float(info[4]),
                                             "ub": float(info[5]),
                                             "LB": int(float(info[1])) - float(info[4]),
                                             "UB": float(info[5]) - int(float(info[1]))}

                # Stores the additional data for sensitive cells in the data object
                if is_sensitive:
                    my_data["sensitive cells"][cell_id] = {"UPL": float(info[7]),
                                                           "LPL": float(info[6])}

            # Reads the number of constraints
            elif line_num == num_vars + 2:
                num_constraints = int(line.split()[0])

            # Reads the details of each relation
            else:

                # Currently the code assumes cells do not have marginals. Check in case it does.
                if float(info[0]) != 0:
                    raise ValueError("Data in wrong format. A marginal value is given that is not defined as a cell")

                else:

                    # for each cell in the relation infer the cell and coefficient
                    for i in range(len(info[2::2])):
                        var_id = int(info[2+2*i])
                        coefficient = int(info[3+2*i])

                        # coefficients can only be 1 or -1 otherwise an error is raised
                        if coefficient == 1:
                            my_data["relations"][line_num][0].append(var_id)
                        elif coefficient == -1:
                            my_data["relations"][line_num][1].append(var_id)
                        else:
                            raise ValueError("variable {} coefficient {} not 1 or -1".format(var_id, coefficient))

        # Store some extra info
        my_data["num_relations"] = num_constraints
        my_data["num_nz"] = len([cell for cell, info in my_data["cells"].items() if info["nominal"] != 0])

        # Let cells track constraints that they are in. This is probably unnecessary as I was using it for something else
        for cell in my_data["cells"].keys():
            my_data["cells"][cell]["relations"] = []

        for name, reln_data in my_data["relations"].items():
            for cell in list(reln_data[0]) + list(reln_data[1]):
                my_data["cells"][cell]["relations"].append(name)

        return my_data


def files(cell_data, reln_data):
    """ Currently since function isn't used but can be to read the data in the ampl format Chris Mann is using for the
    reconstruction attacks.

    :param cell_data: the details of the cells
    :param reln_data: the details of the relations
    :return:
    """

    # initiates the data object
    data = {"cells": {}, "relations": defaultdict(lambda: ([], [])), "sensitive cells": {}}

    # Reads the cell data line by line
    with open(cell_data, "r") as f:
        lines = f.readlines()
        bound_fraction = 1
        protection_fraction = 0.1
        for line in lines[1:-1]:

            # Infers the cell info
            info = line.split()
            data["cells"][info[0]] = {"nominal": int(info[1]),
                                      "sensitive": int(info[2]),
                                      "lb": (1-bound_fraction)*int(info[1]),
                                      "ub": (1+bound_fraction)*int(info[1]),
                                      "LB": bound_fraction*int(info[1]),
                                      "UB": bound_fraction*int(info[1])}

            # If sensitive infers the additional info
            if info[2] == "1":
                data["sensitive cells"][info[0]] = {"UPL": protection_fraction*int(info[1]),
                                                    "LPL": protection_fraction*int(info[1])}

    # Reads the relation data line by line
    with open(reln_data, 'r') as f:
        lines = f.readlines()
        for line in lines[1:-1]:
            info = line.split()

            # Infers the coefficients of the relevant cells
            if info[2] == "1":
                data["relations"][info[0]][0].append(info[1])
            elif info[2] == "-1":
                data["relations"][info[0]][1].append(info[1])
            else:
                raise ValueError("wrong index")

    return data


def arguments():
    """Reads the arguments that can be given when executing the suppress.py file. Type python suppress.py --help for an
    explanation of the different parameters

    :return: an argparse object. Arguments are called by args.argument_name
    """

    # Create an argparse object using the standard library.
    parser = argparse.ArgumentParser()

    # A file name is a positional argument, i.e., must be given for the code to run.
    parser.add_argument("file_name", type=str, help="give relative path to data file")

    # The remaining arguments are optional
    parser.add_argument("--heuristic_time", type=int, help="provide a time limit to the master problem in seconds", default=1)

    parser.add_argument("--optimise_time", type=int, help="provide a time limit to the master problem in seconds",
                        default=600)

    parser.add_argument("--output", type=str, help="provide a filename where the resulting json file can be stored",
                        default="")

    parser.add_argument("--ignore_starting_constraints", action="store_true", help="Will start master problem with an empty "
                                                                                   "constraint pool")

    parser.add_argument("--heuristic_constraints",
                        type=int,
                        help="provide a limit to how many constraints are added during the subsolver stage per iteration for "
                             "the diving heuristic.",
                        default=50)

    parser.add_argument("--optimise_constraints",
                        type=int,
                        help="provide a limit to how many constraints are added during the subsolver stage per iteration "
                             "while "
                             "optimising.",
                        default=50)

    parser.add_argument("--multiplier",
                        type=float,
                        default=1.000,
                        help="Used to force the master problem to increase the number of suppressed cells by a certain "
                             "percentage")

    parser.add_argument("--mode",
                        type=int,
                        default=2,
                        help="Select the output mode for results: 0 - suppressed cells represented by np, 1: suppressed cells "
                             "represented by inference bounds (LB, UB), 2: suppressed cells represented by consistent published"
                             " values and error interval, i.e. a +- x percent")

    parser.add_argument("--heuristic_gap",
                        type=float,
                        default=0.000,
                        help="The optimality gap required for the master problem during the diving phase")

    parser.add_argument("--optimise_gap",
                        type=float,
                        default=0.000,
                        help="The optimality gap for the optimisation process")

    parser.add_argument("--optimise",
                        type=int,
                        default=0,
                        help="A flag to ensure that the solver tries to find the optimal solution after an initial feasible "
                             "solution is found. WARNING: this requires lazy constraints ")

    # Reads the arguments
    args = parser.parse_args()

    # Prints some important parameters so I don't forget what defaults are being used
    print("Filename: {}".format(args.file_name))
    print("Time per master solve: {}".format(args.heuristic_time))
    print("Max constraints added per subsolve iteration: {}".format(args.heuristic_constraints))
    print("Multiplier: {}".format(args.multiplier))
    print("Acceptable Gap: {}".format(args.heuristic_gap))
    print("Optimisation status: {}".format(args.optimise))
    if args.optimise:
        print("Time per master solve: {}".format(args.optimise_time))
        print("Max constraints added per subsolve iteration: {}".format(args.heuristic_constraints))
        print("Acceptable Gap: {}".format(args.optimise_gap))

    return args
