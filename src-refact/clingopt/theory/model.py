# -*- coding=utf-8 -*-

# ==============================================================================
# IMPORT
# ==============================================================================

from __future__ import annotations
from typing import Literal
import sys

from optlang import (  # type: ignore
    interface,
    glpk_interface,
    gurobi_interface,
    cplex_interface
)

# ==============================================================================
# Types
# ==============================================================================

Constraint = tuple[
    Literal['exists', 'forall', 'objective'],
    list[tuple[float, str]],
    float | None,
    float | None
]

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
        self.variables: dict[str, interface.Variable] = {}
        self.constraints_exists: dict[int, interface.Constraint] = {}
        self.constraints_forall: dict[int, tuple[interface.Objective,
                                                 float | None,
                                                 float | None]] = {}
        self.objectives: dict[int, interface.Objective] = {}

    # ==========================================================================
    # Builder
    # ==========================================================================
    def add(self: LpModel, cid: int, constraint: Constraint) -> None:
        constraint_type, expr, lb, ub = constraint
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
        # ----------------------------------------------------------------------
        # Preprocessing
        # ----------------------------------------------------------------------
        expression = sum(
            k * self.variables[var] for k, var in expr # type: ignore
        )
        direction: str = 'min' if lb is not None else 'max'
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
            self.constraints_exists[cid] = lpconstraint
            self.model.add(lpconstraint)
        elif constraint_type == 'forall':
            assert cid not in self.constraints_forall
            lpforall: interface.Objective = self.lpsolver.Objective(
                name=f'forall_{cid}',
                expression=expression,
                direction=direction
            )
            self.constraints_forall[cid] = (lpforall, lb, ub)
        else:
            assert cid not in self.objectives
            lpobjective: interface.Objective = self.lpsolver.Objective(
                name=f'forall_{cid}',
                expression=expression,
                direction=direction
            )
            self.objectives[cid] = lpobjective

    def update(self: LpModel, constraints: list[tuple[int, Constraint]]) -> None:
        for cid, constraint in constraints:
            self.add(cid, constraint)

    def remove(self: LpModel, cids: list[int]) -> None:
        for cid in cids:
            if cid in self.constraints_exists:
                constraint: interface.Constraint = self.constraints_exists[cid]
                self.model.remove(constraint)
                del self.constraints_exists[cid]
            elif cid in self.constraints_forall:
                del self.constraints_forall[cid]
            elif cid in self.objectives:
                del self.objectives[cid]

    # ==========================================================================
    # Solving
    # ==========================================================================
    def check_exists(self: LpModel) -> bool:
        status: str = self.__solve()
        return status in ('optimal', 'unbounded')

    def check_forall(self: LpModel) -> list[int]:
        conflicts: list[int] = []
        for cid, lpcons in self.constraints_forall.items():
            # ------------------------------------------------------------------
            # Add new objective
            # ------------------------------------------------------------------
            objective, lb, ub = lpcons
            assert lb is None or ub is None
            self.model.add(objective)
            # ------------------------------------------------------------------
            # Compute optimum
            # ------------------------------------------------------------------
            status: str = self.__solve()
            # ------------------------------------------------------------------
            # Split status
            # ------------------------------------------------------------------
            if status == 'optimal':
                optimum: float = float(self.model.objective.value)
                if lb is not None:  #  Case EXPR >= LB
                    if optimum < lb:
                        conflicts.append(cid)
                elif ub is not None:  # Case EXPR <= LB
                    if optimum > ub:
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
            self.model.remove(objective)
        return conflicts

    def optimize(self: LpModel) -> None:
        raise NotImplementedError()

    def __solve(self: LpModel) -> str:
        # Statuses:
        # 'optimal': 'An optimal solution as been found.'
        # 'infeasible': 'The problem has no feasible solutions.'
        # 'unbounded': 'The objective can be optimized infinitely.'
        # 'undefined': 'The solver determined that the problem is ill-formed.'
        status: str = self.model.optimize()
        return status

    # ==========================================================================
    # Core conflicts
    # ==========================================================================
    def core_unsat_exists(self: LpModel) -> list[int]:
        conflicting_cids: list[int] = []
        removed_constraints: list[interface.Constraint] = []
        for cid, constraint in self.constraints_exists.items():
            # ------------------------------------------------------------------
            # Remove a constraint
            # ------------------------------------------------------------------
            self.model.remove(constraint)
            # ------------------------------------------------------------------
            # Check the satisfiability
            # ------------------------------------------------------------------
            if self.check_exists():
                conflicting_cids.append(cid)
                self.model.add(constraint)
            else:
                removed_constraints.append(constraint)
        # ------------------------------------------------------------------
        # Re-add all the removed constraints
        # ------------------------------------------------------------------
        for constraint in removed_constraints:
            self.model.add(constraint)
        return conflicting_cids

    def core_unsat_forall(self: LpModel, conflicts: list[int]) -> list[tuple[int, list[int]]]:
        return [
            (cid, list(self.constraints_exists.keys()))
            for cid in conflicts
        ]

    # ==========================================================================
    # Getters
    # ==========================================================================
    def get_assignment(self: LpModel) -> dict[str, float]:
        return {var: var.primal for var in self.model.variables}
