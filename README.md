# MerrinASP: `clingopt`

`clingopt` is a generic implementation of the MERRIN-ASP approach (https://github.com/bioasp/merrin) extended to all the linear optimisation problem.
It extends the ASP solver `clingo` with linear constraints.

## Install

### From the local repository

Install via pip:
```sh
pip install .
```

### From the remote github repository

Install via pip:
```sh
TODO
```

## Linear Programming Solver

`clingopt` can use one of the three following LP solvers for the resolution process:
- CPLEX
- GUROBI
- CBC
To be used, a solver must be installed by user. Note that CBC will be installed by default with `clingopt`. 

## Syntax of linear constraints

Linear constraints can be expressed in the ASP model as follows:

| LP constraints                                                 | ClingoLP Syntax                                                                    |
| :------------------------------------------------------------- | :--------------------------------------------------------------------------------- |
| $w_1 \times x_1 + \cdots + w_n \times x_n \geq k$              | `&sum{`w<sub>1</sub>`*`x<sub>1</sub>`;`...`;`w<sub>n</sub>`*`x<sub>n</sub>`} >=` k |
| $domain(x)=\{l, \cdots, u\}$                                   | `&dom{`l`..`u`} =` x                                                               |
| $\displaystyle\min_x w_1 \times x_1 + \cdots + w_n \times x_n$ | `&minimize{`w<sub>1</sub>`*`x<sub>1</sub>`;`...`;`w<sub>n</sub>`*`x<sub>1</sub>`}` |
| $\displaystyle\max_x w_1 \times x_1 + \cdots + w_n \times x_n$ | `&maximize{`w<sub>1</sub>`*`x<sub>1</sub>`;`...`;`w<sub>n</sub>`*`x<sub>1</sub>`}` |
| $\forall x,\, w_1 \times x_1 + \cdots + w_n \times x_n \geq k$ | `&assert{`w<sub>1</sub>`*`x<sub>1</sub>`;`...`;`w<sub>n</sub>`*`x<sub>1</sub>`} >= k`   |

To avoid syntax clashes, you must quote `"` real numbers. Instead of `0.5` write `"0.5"`.

***Note:*** `&assert` statement allows ensuring that all valid solution satisfying the linear constraint satisfy some linear constraints.

## Usage

`clingopt` supports all `clingo` options.

```text
usage: clingopt [number] [options] [files]

Options:
  --lp-solver=<arg>       : Set LP solver
   <arg>: {cbc, gurobi, cplex} (default lp-solver=cbc)
  --[no-]show-opt-solution: Show LP solution and value of objective function
  --[no-]lazy-mode: Check the satisfiability of linear constraints at the end of the resolution process
```

Example:
```sh
clingopt 0 --show-opt-solution example_encoding.lp example_instance.lp
```

For more options you can ask for help as follows:
```sh
clingopt --help
```
  
### Examples

Some test examples are provided in the folder `./examples`:
- `./examples/merrin/`: inferring regulatory rules from a set of observed time series.

    Run with:
    ```sh
    clingopt -n 0 --project --opt-strategy=usc --heuristic=Domain -c bounded_nonreach=0 --enum-mode=domRec --dom-mod=5,16 --opt-mode=optN  examples/merrin/model_merrin.lp examples/merrin/model_rfba_assert.lp examples/merrin/data/data_covert_kfp_100.lp
    ```
