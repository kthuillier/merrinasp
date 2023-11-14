# -*- coding=utf-8 -*-

# ==============================================================================
# IMPORT
# ==============================================================================

from __future__ import annotations
from typing import Literal
from time import time
import sys

from optlang import (  # type: ignore
    interface,
    glpk_interface,
    gurobi_interface,
    cplex_interface
)

from merrinasp.theory.lra.logger import Logger
from merrinasp.theory.lra.cache import LpCache
from merrinasp.theory.language import LpConstraint

# ==============================================================================
# GLOBALS
# ==============================================================================

SLOPPY: bool = True

# ==============================================================================
# Lp Models
# ==============================================================================


class LpModel:

    def __init__(self: LpModel, lpsolver: str, pid: str) -> None:
        # ----------------------------------------------------------------------
        # LP Solver
        # ----------------------------------------------------------------------
        self.lpsolver = glpk_interface
        if lpsolver.lower() == 'glpk':
            self.lpsolver = glpk_interface
        elif lpsolver.lower() == 'cplex':
            self.lpsolver = cplex_interface
        elif lpsolver.lower() == 'gurobi':
            self.lpsolver = gurobi_interface
        else:
            print('Error: Unknown LP solver:', lpsolver)
            sys.exit(0)

        # ----------------------------------------------------------------------
        # Model data
        # ----------------------------------------------------------------------
        self.pid: str = pid
        self.model: interface.Model = self.lpsolver.Model(name=f'PID_{pid}')
        self.default_objective: interface.Objective = self.model.objective
        self.variables: dict[str, interface.Variable] = {}
        self.constraints_exists: dict[int, interface.Constraint] = {}
        self.constraints_forall: dict[int, tuple[interface.Objective,
                                                 Literal['<=', '>=', '='],
                                                 float]] = {}
        self.objectives: dict[int, interface.Objective] = {}

        # ----------------------------------------------------------------------
        # Statistics
        # ----------------------------------------------------------------------
        self.logger: Logger = Logger(self.pid)

        # ----------------------------------------------------------------------
        # Cache
        # ----------------------------------------------------------------------
        self.cache: LpCache = LpCache()
        self.description: dict[int, tuple[int, ...]] = {}
        self.description_db: dict[int, tuple[int, ...]] = {}

    # ==========================================================================
    # Builder
    # ==========================================================================
    def update(self: LpModel,
               constraints: list[tuple[int,
                                       LpConstraint,
                                       tuple[int, ...]]]) -> None:
        for cid, constraint, description in constraints:
            self.add(cid, constraint, description)

    def add(self: LpModel, cid: int, constraint: LpConstraint,
            description: tuple[int, ...]) -> None:
        constraint_type, expr, sense, b = constraint  # type: ignore
        # ----------------------------------------------------------------------
        # Instanciate new variables
        # ----------------------------------------------------------------------
        for _, var in expr:
            if var not in self.variables:
                lpvar: interface.Variable = self.lpsolver.Variable(
                    name=f'{var}',
                    type='continuous'
                )
                self.variables[var] = lpvar
                self.model.add(lpvar)
        # ----------------------------------------------------------------------
        # Preprocessing
        # ----------------------------------------------------------------------
        expression = sum(
            k * self.variables[var] for k, var in expr  # type: ignore
        )
        direction: str = 'min' if sense == '>=' else 'max'
        lb: float | None = None if sense == '<=' else b
        ub: float | None = None if sense == '>=' else b
        # ----------------------------------------------------------------------
        # Split the different constraint types
        # ----------------------------------------------------------------------
        if constraint_type == 'exists':
            assert cid not in self.constraints_exists
            lpconstraint: interface.Constraint = self.lpsolver.Constraint(
                name=f'cons_{cid}',
                expression=expression,
                lb=lb,
                ub=ub
            )
            self.description[cid] = description
            self.constraints_exists[cid] = lpconstraint
            self.model.add(lpconstraint, sloppy=SLOPPY)
        elif constraint_type == 'forall':
            assert cid not in self.constraints_forall
            lpforall: interface.Objective = self.lpsolver.Objective(
                name=f'forall_{cid}',
                expression=expression,
                direction=direction
            )
            self.description_db[cid] = description
            self.constraints_forall[cid] = (lpforall, sense, b)
        else:
            assert cid not in self.objectives
            lpobjective: interface.Objective = self.lpsolver.Objective(
                name=f'objective_{cid}',
                expression=expression,
                direction=direction
            )
            self.description_db[cid] = description
            self.objectives[cid] = lpobjective

    def remove(self: LpModel, cids: list[int]) -> None:
        for cid in cids:
            if cid in self.constraints_exists:
                constraint: interface.Constraint = self.constraints_exists[cid]
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

    # ==========================================================================
    # Solving
    # ==========================================================================
    def check_exists(self: LpModel) -> bool:
        # if len(self.constraints_forall) > 0:
        #     return True
        status, _ = self.__solve()
        return status in ('optimal', 'unbounded')

    def check_forall(self: LpModel) -> list[int]:
        conflicts: list[int] = []
        for cid, lpcons in self.constraints_forall.items():
            # ------------------------------------------------------------------
            # Add new objective
            # ------------------------------------------------------------------
            objective, sense, b = lpcons
            self.model.objective = objective
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
            self.model.objective = self.default_objective
            del self.description[cid]
        return conflicts

    def optimize(self: LpModel) -> tuple[list[float], list[tuple[str, float]]]:
        raise NotImplementedError()

    def __solve(self: LpModel) -> tuple[str, float | None]:
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
        status: str = self.model.optimize()
        optimum: float | None = None
        if status == 'optimal':
            optimum = float(self.model.objective.value)  # type: ignore
        self.cache.add(self.description.values(), status, optimum)
        dt = time() - dt
        self.logger.lpsolver_calls.append(dt)
        return status, optimum

    # ==========================================================================
    # Core conflicts
    # ==========================================================================
    def core_unsat_exists(self: LpModel) -> list[int]:
        conflicting_cids: list[int] = []
        removed_constraints: list[interface.Constraint] = []
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
                self.model.add(constraint, sloppy=SLOPPY)
                self.description[cid] = removed_description[cid]
                del removed_description[cid]
            else:
                removed_constraints.append(constraint)
        # ------------------------------------------------------------------
        # Re-add all the removed constraints
        # ------------------------------------------------------------------
        for constraint in removed_constraints:
            self.model.add(constraint, sloppy=SLOPPY)
        self.description = self.description | removed_description

        self.logger.conflicts_exists += 1
        return conflicting_cids

    def core_unsat_forall(self: LpModel, conflicts: list[int],
                          prop_cid: list[int],
                          unprop_cid: list[int]) -> list[tuple[int,
                                                               list[int],
                                                               list[int]]]:
        self.logger.conflicts_forall += 1
        return [(abs(cid), prop_cid, unprop_cid) for cid in conflicts]

    # ==========================================================================
    # Getters
    # ==========================================================================
    def get_statistics(self: LpModel) -> Logger:
        return self.logger

    def get_assignment(self: LpModel) -> dict[str, float]:
        return {var: var.primal for var in self.model.variables}
