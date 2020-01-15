from consistent import find_most_central_consistent_solution
import csv


def solution(data, supp_levels, bounds, mode, output_file):
    """Prints the results in the specified format (mode). If an output_file is specified it is stored there"""

    # Sensitive cells are given an * in the output
    sensitive = {cell: "*" if info["sensitive"] else "" for cell, info in data["cells"].items()}
    output = {}

    # Mode 0 simply outputs np for suppressed cells instead of the nominal
    if mode == 0:
        col_headers = ["cell", "publication", "sensitive"]
        for cell, supp in supp_levels.items():
            published = "np" if supp > 0.5 else data["cells"][cell]["nominal"]
            output[cell] = {"cell": cell,
                            "publication": published,
                            "sensitive": sensitive[cell]}
            print("{:4.0f}: {} {}".format(cell, published, sensitive[cell]))

    elif mode == 1 or mode == 2:

        # Mode 1 outputs a lower an upper bound for suppressed cells instead of the nominal
        if mode == 1:
            col_headers = ["cell", "published_lower_bound", "published_upper_bound", "suppressed", "sensitive"]
            for cell, supp in supp_levels.items():
                published = (bounds[cell][0], bounds[cell][1]) if supp > 0.5 else data["cells"][cell]["nominal"]

                output[cell] = {"cell": cell,
                                "published_lower_bound": bounds[cell][0],
                                "published_upper_bound": bounds[cell][1],
                                "suppressed": True if supp > 0.5 else False,
                                "sensitive": sensitive[cell]}
                print("{:4.0f}: {} {}".format(cell, published, sensitive[cell]))

        # Mode 2 outputs a consistent table where the suppressed cells have error bars
        else:

            # Solves an LP to determine a consistent table with minimal additional errors
            find_most_central_consistent_solution(data, bounds)
            col_headers = ["cell", "published nominal", "published error", "suppressed", "sensitive"]

            for cell, supp in supp_levels.items():
                info = data["cells"][cell]

                # output format changes for suppressed cells
                if supp > 0.5:

                    error = info["new_diff"]/info["new_nominal"]*100
                    print ("{:4.0f}: {:8.1f} (+- {:1.1f}%) {}".format(cell, info["new_nominal"],
                                                                      error,
                                                                      sensitive[cell]))

                else:
                    error = 0
                    print("{:4.0f}: {:8.1f} {}".format(cell, info["nominal"], sensitive[cell]))

                output[cell] = {"cell": cell,
                                "published nominal": info["new_nominal"],
                                "published error": error,
                                "suppressed": True if supp > 0.5 else False,
                                "sensitive": sensitive[cell]}

    # Store in output file if one is specified
    if output_file:
        with open(output_file, "wb") as f_out:

            # Use the standard csv library
            writer = csv.DictWriter(f_out, fieldnames=col_headers)
            writer.writeheader()
            for cell, info in output.items():
                writer.writerow(info)
