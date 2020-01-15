# Context - What is suppression?
Suppression is a method to protect against published sensitive information by simply leaving certain cells in a table unpublished. As an introduction by way of example, suppression can be explained with respect to the following table. The following is a 2-dimensional table. 

| |A | B | C | Total|
|-|-|-|-|-|
|__I__| 20 | 50 | 10 | 80
|__II__ | 8 | 19 | __22__ | 49
|__III__ | 17 | 32 | 12 | 61
|__Total__ | 45 | 101 | 44 | 190

Say for some reason we cannot publish the row II column C value of 22. If we only remove this value, clearly the value can be reconstructed by, for example, considering the remaining values in row II: 49 - 19 - 8 = 22. Hence _secondary suppresion_ is required.

| |A | B | C | Total|
|-|-|-|-|-|
|__I__| 20 | 50 | 10 | 80
|__II__ | 8 | 19 | __np__ | 49
|__III__ | 17 | 32 | 12 | 61
|__Total__ | 45 | 101 | 44 | 190

A possible solution could be the following

| |A | B | C | Total|
|-|-|-|-|-|
|__I__| 20 | 50 | 10 | 80
|__II__ | np | 19 | __np__ | 49
|__III__ | np | 32 | np | 61
|__Total__ | 45 | 101 | 44 | 190

For a more in depth overview of the concept, as well as the model that formed the basis of this software, see the following [paper](https://pubsonline.informs.org/doi/10.1287/mnsc.47.7.1008.9805). 

# Installation inside NGD (How to get the code working on your machine)

1. Clone repo using

```
git clone https://git.infra.abs.gov.au/scm/cm/suppression.git
cd suppression
```

2. Open the Gurobi Interactive Shell (can access from start and typing "Gurobi" and is normally the first option)

3. Enter the following commands in the Gurobi Interactive Shell. Note that, inside NGD, if you cloned the repo onto your Desktop then the "absolute\path\to\the\repo" should be "P:\\Desktop\suppression".

```
import subprocess
os.chdir("absolute\path\to\the\repo")
subprocess.Popen("python suppress.py --help")
```

At this stage it should hopefully show the possible arguments for the program

4. Finally test the solver works using the following command in Gurobi Interactive Shell immediately after the previous points

```
subprocess.Popen("python suppress.py example.csp")
```

# Flags

There are many optional flags that can be passed to the solver from the command line to influence its behavior. For a full list of flags run the following ```subprocess.Popen("python suppress.py --help")```. A number of important flags are given below

##### Filename
A relative path to a datafile is the only required parameter to the solver. See Input Data Format for more inforamation.

##### Optimiser (--optimise 1)
By default only the diving heuristic is run. The solution can be improved by feeding it into a complete benders decomposition however currently this requires lazy-constraints which are not available inside NGD. This feature can be used when Gurobi 9 is available. The amount of time given to the complete solver can be configured with --optimise_time x, where x is the desired number of seconds (this does not include the time to obtain an initial feasible solution)

##### Mode (--optimise 1)
The solution can be outputted in three different modes. See Output Data Format for the details.

##### Multiplier (--multiplier 1.05)
In case the diving heuristic is still taking to much time, a multiplier can be used to force the master problem to complete more suppressions each iteration. By default this value is 1.00 which means that the number of suppressions in subsequent iterations is at least the number of iterations in the previous master problem solve. If the value is increased to 1.05 this means that 5% additional suppressions are requied between consecutive iterations. The larger the value the quicker the diving heuristic will solve but very likely this will come at the expense of quality. 

##### Output file (--output filename.csv)
Will solve the output to filename.csv. See Output Data Format for more information.



# Input Data Format

The input data format has the following format,


```
0
n
i a_i w_i s_i lb_i ub_i LPL_i UPL_i 0
...
...
...
...
m
b_j  : i' (1 or -1) i'' (1 or -1) ... i^'(b_j) (1 or -1)
...
...
...
```

where,
* n is the total number of cells
* i is the cell index
* a_i is the nominal (true) cell value
* w_i is the weight of the cell. Cells with higher weights are less likely to be suppressed
* s_i is the status of the cell, which can take one of three options
    + z - the cell must be zero
    + u - the cell is sensitive
    + s - the cell can be suppressed
* lb_i is the lowest possible value that cell i could take
* ub_i is the largest possible value that cell i could take
* LPL_i is the lower protection level of cell i - the number of possible values less than the nominal that i could take
* UPL_i is the upper protection level of cell i - the number of possible values more than the nominal that i could take
* m is the total number of relations
* b_j is the marginal of the relations - currently the model ignores this value and assumes it equals zero
* i', i'', ...,  i'(b_j) are the non-zero cell indices that are considered by relation j.

The example file has a csv file format but observe that this is very misleading. This comes from the example files in the literature. Simply speaking the file format first considers the cell information (first the number of cells, then for each cell all of its information). Secondally, the format considers the relation information (first the number of relations, then for each relation all of its information). 

# Output Data Format

There are three possible output data formats determing on the solve mode flag. All outputs are in a .csv file.

1. Standard Output  (--mode 0)
Simply outputs the nominal value or np for suppressed cells. The first column corresponds to the cell id, the second is the published nominal value or np (not published) the third column contains a * symbol if the cell is sensitive. This helps distinguish between primary and secondary suppression,
```
cell, publication, sensitive
1, a_1, 
2, np, *
3, np, 
```

2. Bounds Output  (--mode 2)
Publishes an acceptable lower and upper bound for each cell. The first column corresponds to the cell id, the second is the published lower bound, the third is the published upper bound, the forth column is a boolean specifying whether the cells was partially suppressed or not, the final third column contains a * symbol if the cell is sensitive. 
```
cell, published_lower_bound, published_upper_bound,  suppressed, sensitive
1, L_1, U_1, False,  
2, L_2, U_2, True, *
3, L_3, U_3, True, 
```

3. Synthetic Output  (--mode 2)
Reconstructs a consistent solution within the bounds published in the Bounds Output method. The first column corresponds to the cell id, the second is the new published nominal value, the third column is an error bar, the forth column is a boolean specifying whether the cells was partially suppressed or not, the final third column contains a * symbol if the cell is sensitive. 
```
cell, published nominal, published error,  suppressed, sensitive
1, a_1*, 0, False,  
2, a_2*, 12.0%, True, *
3, a_3*, 5.2%, True, 
```

# Code Structure

The code is divided into 7 python files. The main file is suppress.py, which can be run from the command line. The main file imports three files. Firstly read.py, which provides functions to read commandline arguments and the input data. Secondly write.py, which outputs the solution to a file. Thirdly, solver.py, which contains a Solver class that constitutes the benders decomposition solver. The solver contains an object of the master problem and subproblem classes, which are defined in master.py and subproblem.py, respectively. The attacker subproblem is represented as another class of which the subproblem contains a single instance - it is significantly more efficient to modify a single attacker problem then continuously building ones as they are required.

The code structure can be visualised below, where points import the functionality of their subpoints.
* suppress.py
   * solver.py
        * master.py
        * subproblem.py
            * attacker.py
    * read.py
    * write.py


