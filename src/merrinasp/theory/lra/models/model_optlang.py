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

from merrinasp.theory.lra.models.interface import ModelInterface
from merrinasp.theory.language import LpConstraint

# ==============================================================================
# GLOBALS
# ==============================================================================

SLOPPY: bool = False

# ==============================================================================
# Lp Models
# ==============================================================================


class ModelOptlang(ModelInterface):

    def __init__(self: ModelOptlang, lpsolver: str, pid: str) -> None:
        super().__init__(lpsolver, pid)
        # ----------------------------------------------------------------------
        # LP Solver
        # ----------------------------------------------------------------------
        self.interface = glpk_interface
        if lpsolver.lower() == 'glpk':
            self.interface = glpk_interface
        elif lpsolver.lower() == 'cplex':
            self.interface = cplex_interface
        elif lpsolver.lower() == 'gurobi':
            self.interface = gurobi_interface
        else:
            print('Error: Unknown LP solver:', lpsolver)
            sys.exit(0)

        # ----------------------------------------------------------------------
        # Model data
        # ----------------------------------------------------------------------
        self.model: interface.Model = self.interface.Model(name=f'PID_{pid}')
        self.default_objective: interface.Objective = self.model.objective
        self.variables: dict[str, interface.Variable] = {}
        self.constraints_exists: dict[int, interface.Constraint] = {}
        self.constraints_forall: dict[int, tuple[interface.Objective,
                                                 Literal['<=', '>=', '='],
                                                 float]] = {}
        self.objectives: dict[int, interface.Objective] = {}

        self.description: dict[int, tuple[int, ...]]

    # ==========================================================================
    # Builder
    # ==========================================================================

    def add(self: ModelOptlang, cid: int, constraint: LpConstraint,
            description: tuple[int, ...]) -> None:
        constraint_type, expr, sense, b = constraint  # type: ignore
        # ----------------------------------------------------------------------
        # Instanciate new variables
        # ----------------------------------------------------------------------
        for _, var in expr:
            if var not in self.variables:
                lpvar: interface.Variable = self.interface.Variable(
                    name=f'{var}',
                    type='continuous'
                )
                self.variables[var] = lpvar
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
            lpconstraint: interface.Constraint = self.interface.Constraint(
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
            lpforall: interface.Objective = self.interface.Objective(
                name=f'forall_{cid}',
                expression=expression,
                direction=direction
            )
            self.description_db[cid] = description
            self.constraints_forall[cid] = (lpforall, sense, b)
        else:
            assert cid not in self.objectives
            lpobjective: interface.Objective = self.interface.Objective(
                name=f'objective_{cid}',
                expression=expression,
                direction=direction
            )
            self.description_db[cid] = description
            self.objectives[cid] = lpobjective

    def remove(self: ModelOptlang, cids: list[int]) -> None:
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
    def check_exists(self: ModelOptlang) -> bool:
        # if len(self.constraints_forall) > 0:
        #     return True
        status, _ = self.__solve()
        return status in ('optimal', 'unbounded')

    def check_forall(self: ModelOptlang) -> list[int]:
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

    def __solve(self: ModelOptlang) -> tuple[str, float | None]:
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
    def core_unsat_exists(self: ModelOptlang, lazy: bool = False) -> list[int]:
        # ----------------------------------------------------------------------
        # If Lazy: do not compute the unsatisfiable core
        # ----------------------------------------------------------------------
        if lazy:
            return list(self.constraints_exists.keys())
        # ----------------------------------------------------------------------
        # Else: compute the unsatisfiable core
        # ----------------------------------------------------------------------
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

    def core_unsat_forall(self: ModelOptlang, conflict: int,
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
        self.model.objective = objective
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
        self.model.objective = self.default_objective
        del self.description[conflict]
        return optimum_cores

    # ==========================================================================
    # Getters
    # ==========================================================================
    def get_assignment(self: ModelOptlang) -> dict[str, float]:
        return {var: var.primal for var in self.model.variables}
