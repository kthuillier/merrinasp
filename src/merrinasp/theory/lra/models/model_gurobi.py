# -*- coding=utf-8 -*-

# ==============================================================================
# IMPORT
# ==============================================================================

from __future__ import annotations
from typing import Literal
from time import time
import sys

from gurobipy import Model, LinExpr, Constr, Var, GRB

from merrinasp.theory.lra.models.interface import ModelInterface
from merrinasp.theory.language import LpConstraint

# ==============================================================================
# GLOBALS
# ==============================================================================

# ==============================================================================
# Lp Models
# ==============================================================================


class ModelGurobiPy(ModelInterface):

    def __init__(self: ModelGurobiPy, lpsolver: str, pid: str) -> None:
        super().__init__(lpsolver, pid)
        # ----------------------------------------------------------------------
        # LP Solver
        # ----------------------------------------------------------------------
        # assert lpsolver == 'gurobi'
        self.lpsolver: str = lpsolver

        # ----------------------------------------------------------------------
        # Model data
        # ----------------------------------------------------------------------
        self.model: Model = Model(f'PID_{pid}')
        self.model.setParam('OutputFlag', 0)
        self.model.setParam('DualReductions', 0)
        self.default_objective: LinExpr = self.model.getObjective()  # type: ignore
        self.variables: dict[str, Var] = {}
        self.constraints_exists: dict[int, Constr] = {}
        self.constraints_exists_infos: dict[int, tuple[LinExpr | int,
                                                       Literal['<=',
                                                               '>=', '='],
                                                       float]] = {}
        self.constraints_forall: dict[int, tuple[LinExpr | int,
                                                 Literal['<=', '>=', '='],
                                                 float]] = {}
        self.objectives: dict[int, LinExpr | int] = {}

    # ==========================================================================
    # Builder
    # ==========================================================================

    def add(self: ModelGurobiPy, cid: int, constraint: LpConstraint,
            description: tuple[int, ...]) -> None:
        constraint_type, expr, sense, b = constraint  # type: ignore
        # ----------------------------------------------------------------------
        # Instanciate new variables
        # ----------------------------------------------------------------------
        for _, var in expr:
            if var not in self.variables:
                lpvar: Var = self.model.addVar(
                    name=f'{var}',
                    vtype=GRB.CONTINUOUS,
                    lb=float('-inf'),
                    ub=float('inf')
                )
                self.variables[var] = lpvar
        # ----------------------------------------------------------------------
        # Preprocessing
        # ----------------------------------------------------------------------
        expression: LinExpr | int = sum(
            k * self.variables[var] for k, var in expr
        )
        direction: str = 'min' if sense == '>=' else 'max'
        # ----------------------------------------------------------------------
        # Split the different constraint types
        # ----------------------------------------------------------------------
        if constraint_type == 'exists':
            assert cid not in self.constraints_exists
            if sense == '>=':
                lpconstraint = self.model.addConstr(
                    expression >= b,  # type: ignore
                    f'cons_{cid}'
                )
            elif sense == '<=':
                lpconstraint = self.model.addConstr(
                    expression <= b,  # type: ignore
                    f'cons_{cid}'
                )
            else:
                lpconstraint = self.model.addConstr(
                    expression == b,  # type: ignore
                    f'cons_{cid}'
                )
            self.description[cid] = description
            self.constraints_exists[cid] = lpconstraint
            self.constraints_exists_infos[cid] = (
                expression,
                sense,
                b
            )
        elif constraint_type == 'forall':
            assert cid not in self.constraints_forall
            lpforall: LinExpr | int = expression if direction == 'min' \
                else -expression
            self.description_db[cid] = description
            self.constraints_forall[cid] = (
                lpforall,
                '>=',
                b if direction == 'min' else -b
            )
        else:
            assert cid not in self.objectives
            lpobjective: LinExpr | int = expression if direction == 'min' \
                else -expression
            self.description_db[cid] = description
            self.objectives[cid] = lpobjective

    def remove(self: ModelGurobiPy, cids: list[int]) -> None:
        for cid in cids:
            if cid in self.constraints_exists:
                constraint: Constr = self.constraints_exists[cid]
                self.model.remove(constraint)
                del self.description[cid]
                del self.constraints_exists[cid]
            elif cid in self.constraints_forall:
                del self.description_db[cid]
                del self.constraints_forall[cid]
            elif cid in self.objectives:
                del self.description_db[cid]
                del self.objectives[cid]
            else:
                assert False

    # --------------------------------------------------------------------------
    # Auxiliary function
    # --------------------------------------------------------------------------

    def __add_lpconstraint(self: ModelGurobiPy, cid: int) -> None:
        expression, sense, b = self.constraints_exists_infos[cid]
        lpconstraint: Constr
        if sense == '>=':
            lpconstraint = self.model.addConstr(
                expression >= b,  # type: ignore
                f'cons_{cid}'
            )
        elif sense == '<=':
            lpconstraint = self.model.addConstr(
                expression <= b,  # type: ignore
                f'cons_{cid}'
            )
        else:
            lpconstraint = self.model.addConstr(
                expression == b,  # type: ignore
                f'cons_{cid}'
            )
        self.constraints_exists[cid] = lpconstraint

    # ==========================================================================
    # Solving
    # ==========================================================================
    def check_exists(self: ModelGurobiPy) -> bool:
        status, _ = self.__solve()
        return status in ('optimal', 'unbounded')

    def check_forall(self: ModelGurobiPy) -> list[int]:
        conflicts: list[int] = []
        for cid, lpcons in self.constraints_forall.items():
            # ------------------------------------------------------------------
            # Add new objective
            # ------------------------------------------------------------------
            objective, sense, b = lpcons
            self.model.setObjective(objective, sense=GRB.MINIMIZE)
            self.description[cid] = self.description_db[cid]
            # ------------------------------------------------------------------
            # Compute optimum
            # ------------------------------------------------------------------
            status, optimum = self.__solve()
            # ------------------------------------------------------------------
            # Split status
            # ------------------------------------------------------------------
            if status == 'optimal':
                assert optimum is not None
                if sense == '>=':  #  Case EXPR >= B
                    if optimum < b:
                        conflicts.append(cid)
                elif sense == '<=':  # Case EXPR <= B
                    if optimum > b:
                        conflicts.append(cid)
            elif status == 'infeasible':
                pass
            elif status == 'unbounded':
                conflicts.append(cid)
            else:
                print('Error: Unknown LP solver status:', status)
                sys.exit(0)
            # ------------------------------------------------------------------
            # Remove current objective
            # ------------------------------------------------------------------
            self.model.setObjective(self.default_objective, sense=GRB.MINIMIZE)
            del self.description[cid]
        return conflicts

    def __solve(self: ModelGurobiPy) -> tuple[str, float | None]:
        # ----------------------------------------------------------------------
        # CACHE: check if the problem has already been solved
        # ----------------------------------------------------------------------
        dt: float = time()
        cache_check: None | tuple[str, float | None] = self.cache.check(
            self.description.values()
        )
        if cache_check is not None:
            dt = time() - dt
            self.logger.cache_prevented.append(dt)
            return cache_check
        dt = time() - dt
        self.logger.cache_missed.append(dt)
        # ----------------------------------------------------------------------
        # SOLVER: solve the problem
        # ----------------------------------------------------------------------
        # Statuses:
        # 'optimal': 'An optimal solution as been found.'
        # 'infeasible': 'The problem has no feasible solutions.'
        # 'unbounded': 'The objective can be optimized infinitely.'
        # 'undefined': 'The solver determined that the problem is ill-formed.'
        dt = time()
        self.model.optimize()
        status_id: int = self.model.Status
        status: str = f'undefined-{status_id}'
        if status_id == GRB.OPTIMAL:
            status = 'optimal'
        elif status_id == GRB.UNBOUNDED:
            status = 'unbounded'
        elif status_id == GRB.INFEASIBLE:
            status = 'infeasible'
        optimum: float | None = None
        if status == 'optimal':
            optimum = float(self.model.ObjVal)  # type: ignore
        self.cache.add(self.description.values(), status, optimum)
        dt = time() - dt
        self.logger.lpsolver_calls.append(dt)
        return status, optimum

    # ==========================================================================
    # Core conflicts
    # ==========================================================================
    def core_unsat_exists(self: ModelGurobiPy, lazy: bool = False) -> list[int]:
        # ----------------------------------------------------------------------
        # If Lazy: do not compute the unsatisfiable core
        # ----------------------------------------------------------------------
        if lazy:
            return list(self.constraints_exists.keys())
        # ----------------------------------------------------------------------
        # Else: compute the unsatisfiable core
        # ----------------------------------------------------------------------
        conflicting_cids: list[int] = []
        removed_constraints: list[int] = []
        removed_description: dict[int, tuple[int, ...]] = {}
        for cid, constraint in self.constraints_exists.items():
            # ------------------------------------------------------------------
            # Remove a constraint
            # ------------------------------------------------------------------
            self.model.remove(constraint)
            removed_description[cid] = self.description[cid]
            del self.description[cid]
            # ------------------------------------------------------------------
            # Check the satisfiability
            # ------------------------------------------------------------------
            if self.check_exists():
                conflicting_cids.append(abs(cid))
                self.__add_lpconstraint(cid)
                self.description[cid] = removed_description[cid]
                del removed_description[cid]
            else:
                removed_constraints.append(cid)
        # ------------------------------------------------------------------
        # Re-add all the removed constraints
        # ------------------------------------------------------------------
        for cid in removed_constraints:
            self.__add_lpconstraint(cid)
        self.description = self.description | removed_description

        self.logger.conflicts_exists += 1
        return conflicting_cids

    def core_unsat_forall(self: ModelGurobiPy, conflict: int,
                          unprop_cids: dict[int, list[tuple[LpConstraint, tuple[int, ...]]]],
                          lazy: bool = False) -> list[int]:
        self.logger.conflicts_forall += 1
        # ----------------------------------------------------------------------
        # If Lazy: do not compute the optimum core
        # ----------------------------------------------------------------------
        if lazy:
            return list(unprop_cids.keys())
        # ----------------------------------------------------------------------
        # Add new objective
        # ----------------------------------------------------------------------
        objective, sense, b = self.constraints_forall[conflict]
        self.model.setObjective(objective, sense=GRB.MINIMIZE)
        self.description[conflict] = self.description_db[conflict]
        # ----------------------------------------------------------------------
        # For each unused constraints group
        # ----------------------------------------------------------------------
        optimum_cores: list[int] = []
        for up_cid, up_constraints in unprop_cids.items():
            assert up_cid not in self.constraints_exists
            is_meaningfull: bool = False
            # ------------------------------------------------------------------
            # For each unused constraints in the group
            # ------------------------------------------------------------------
            for up_constraint, up_description in up_constraints:
                # --------------------------------------------------------------
                # Add the constraint
                # --------------------------------------------------------------
                self.add(up_cid, up_constraint, up_description)
                # --------------------------------------------------------------
                # Compute optimum
                # --------------------------------------------------------------
                status, optimum = self.__solve()
                # --------------------------------------------------------------
                # Split status
                # --------------------------------------------------------------
                if status == 'optimal':
                    assert optimum is not None
                    is_meaningfull = (sense == '>=' and optimum >= b) or \
                        (sense == '<=' and optimum <= b)
                elif status == 'infeasible':
                    pass
                elif status == 'unbounded':
                    pass
                else:
                    print('Error: Unknown LP solver status:', status)
                    sys.exit(0)
                # --------------------------------------------------------------
                # Remove the constraint
                # --------------------------------------------------------------
                self.remove([up_cid])
                # --------------------------------------------------------------
                # Stop if the constraint is meaningfull
                # --------------------------------------------------------------
                if is_meaningfull:
                    break
            # ------------------------------------------------------------------
            # if the constraint is meaningfull it is added to the optimum core
            # ------------------------------------------------------------------
            optimum_cores.append(up_cid)
        # ----------------------------------------------------------------------
        # Remove current objective
        # ----------------------------------------------------------------------
        self.model.setObjective(self.default_objective, sense=GRB.MINIMIZE)
        del self.description[conflict]
        return optimum_cores

    # ==========================================================================
    # Getters
    # ==========================================================================
    def get_assignment(self: ModelGurobiPy) -> dict[str, float]:
        return {var.VarName: var.X for var in self.model.getVars()}
