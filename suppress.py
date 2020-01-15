from solver import Solver
import read
import write


def run(my_data, my_args):
    """ Executes the solver, runs the diving heuristic, and then seeds into the complete solver if required

    :param my_data: returned from read.data(filename)
    :param my_args: returned from read.arguments()
    """

    # Creates a solver object and prints the details of the problem
    solver = Solver(my_data, my_args.ignore_starting_constraints)
    solver.master.print_details()

    # Runs the diving heuristic with the specified parameters
    print("%%%%%%%%%%%%%%%%%%%%%\n  DIVING HEURISTIC\n%%%%%%%%%%%%%%%%%%%%%")
    solver.solve(max_iterations_per_sub_problem=my_args.heuristic_constraints, time_limit=my_args.heuristic_time,
                 dummy_multiplier=my_args.multiplier,
                 gap=my_args.heuristic_gap,
                 complete=False)

    # Runs the diving heuristic with the specified parameters and prints the results
    supp_level, bounds = solver.remove_redundant_suppressions()
    solver.master.print_results()

    # Seeds the complete solver with the solution from the heuristic and executes the solver, if required
    if my_args.optimise:
        solver.master.provide_feasible_solution(supp_level)
        print("%%%%%%%%%%%%%%%%%%%%%\n  OPTIMISING\n%%%%%%%%%%%%%%%%%%%%%")
        solver.solve(max_iterations_per_sub_problem=my_args.optimise_constraints, time_limit=my_args.optimise_time,
                     gap=my_args.optimise_gap, dummy_multiplier=1, complete=True)
        solver.master.print_results()

    # Writes the solution to file.
    write.solution(my_data, supp_level, bounds, my_args.mode, my_args.output)
    print("press <ENTER> to finish")


if __name__ == "__main__":
    """This is what will be run when this script is executed, e.g., when python suppress.py is called from the commandline """

    args = read.arguments()
    data = read.data(args.file_name)
    run(data, args)
