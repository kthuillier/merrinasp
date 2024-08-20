# MerrinASP: `merrinasp`

`merrinasp` is a generic implementation of the MERRIN-ASP approach (https://github.com/bioasp/merrin) extended to all linear optimization problems.
It extends the ASP solver `clingo` with linear constraints with one level of quantifiers (existential and universal).

## Install

### From the local repository

Install via pip:
```sh
pip install .
```

### From the remote GitHub repository

Install via pip:
```sh
pip install git+https://github.com/kthuillier/merrinasp
```

## Linear Programming Solver

`merrinasp` can use one of the following LP solvers for the resolution process:
- CPLEX, through `optlang` and `PuLP`
- GUROBI, through `gurobipy`
- CBC, through `PuLP`
- GLPK, through `optlang`

To be used, a solver must be installed by users with all the needed licenses.\
Note that CBC and GLPK will be installed by default with `merrinasp`.

## Syntax of linear constraints

Linear constraints can be expressed in the ASP model as follows:

| LP constraints                                                 | MerrinASP Syntax                                                                    |
| :------------------------------------------------------------- | :--------------------------------------------------------------------------------- |
| $w_1 \times x_1 + \cdots + w_n \times x_n \geq k$              | `&sum{`w<sub>1</sub>`*`x<sub>1</sub>`;`...`;`w<sub>n</sub>`*`x<sub>n</sub>`} >=` k |
| $domain(x)=\{l, \cdots, u\}$                                   | `&dom{`l`..`u`} =` x                                                               |
| $\displaystyle\min_x w_1 \times x_1 + \cdots + w_n \times x_n$ | `&minimize{`w<sub>1</sub>`*`x<sub>1</sub>`;`...`;`w<sub>n</sub>`*`x<sub>1</sub>`}` |
| $\displaystyle\max_x w_1 \times x_1 + \cdots + w_n \times x_n$ | `&maximize{`w<sub>1</sub>`*`x<sub>1</sub>`;`...`;`w<sub>n</sub>`*`x<sub>1</sub>`}` |
| $\forall x,\, w_1 \times x_1 + \cdots + w_n \times x_n \geq k$ | `&assert{`w<sub>1</sub>`*`x<sub>1</sub>`;`...`;`w<sub>n</sub>`*`x<sub>1</sub>`} >= k`   |

To avoid syntax clashes, you must quote `"` real numbers. Instead of `0.5` write `"0.5"`.

***Note 1:*** `&assert` statement allows modeling universally quantified linear constraints, *i.e.* given a linear problem, all solutions of the `&dom` and `&sum` constraints should satisfy the `&assert` constraints.

***Note 2:*** All linear constraints should be in the head of the ASP rules.

## Usage

`merrinasp` supports all `clingo` options.

```text
usage: merrinasp [number] [options] [files]

Options:
  --lp-solver=<arg>: Set LP solver
   <arg>: { gurobi, cbc, glpk, cplex-optlang, cplex-pulp } (default lp-solver=glpk)
  --[no-]show-lp-assignment: Show LP solution and the LP solver status for each partition of linear constraints
  --[no-]lazy-mode: Check the satisfiability of linear constraints at the end of the resolution process
  --[no-]strict-forall: Force the linear domains of forall constraints to be satisfiable
```

Example:
```sh
merrinasp -n 0 ./examples/test.lp
```

For more options you can ask for help as follows:
```sh
merrinasp --help
```

### Examples

Some test examples are provided in the folder `./examples`:
- `./examples/test.lp`: a small problem subdivided into 2 existentially quantified linear problems and 1 universally quantified linear problem.\
    Run with:
    ```sh
    merrinasp -n 0 ./examples/test.lp
    ```
- `./examples/test-show.lp`: a small problem subdivided into 2 quantified linear problems for which optimum LP variable assignment should be displayed.\
    Run with:
    ```sh
    merrinasp -n 0 ./examples/test-show.lp --show-lp-assignment
    ```
- `./examples/merrin/`: inferring regulatory rules from a set of observed time series.\
    Run with:
    ```sh
    merrinasp -n 0 --project --opt-strategy=usc --heuristic=Domain -c bounded_nonreach=0 --enum-mode=domRec --dom-mod=5,16 --opt-mode=optN  examples/merrin/model_merrin.lp examples/merrin/model_rfba_assert.lp examples/merrin/data/data_covert_kfp_100.lp
    ```

## References

To cite this tool:
> Kerian Thuillier, Anne Siegel, and Loïc Paulevé (2024). CEGAR-Based Approach for Solving Combinatorial Optimization Modulo Quantified Linear Arithmetics Problems.  Proceedings of the AAAI Conference on Artificial Intelligence, 38(8), 8146-8153. [https://doi.org/10.1609/aaai.v38i8.28654](https://doi.org/10.1609/aaai.v38i8.28654) \[[pdf](https://hal.science/hal-04420454/document)\]