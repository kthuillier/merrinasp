# -*- coding=utf-8 -*-

# ==============================================================================
# IMPORT
# ==============================================================================

from __future__ import annotations
from typing import Any, Literal
from time import time
import sys

from merrinasp.theory.language import LpConstraint
from merrinasp.theory.lra.logger import Logger
from merrinasp.theory.lra.cache import LpCache

# ==============================================================================
# Type Alias
# ==============================================================================

Sense = Literal['>=', '<=', '=']
LpStatus = Literal['optimal', 'unbounded', 'infeasible', 'undefined']
ExistsConstraint = tuple[Any, Sense, float]
ForallConstraint = tuple[Any, Sense, float]
Objective = tuple[Any, Sense, float]

# ==============================================================================
# Lp Models
# ==============================================================================


class ModelInterface:

    def __init__(self: ModelInterface, lpsolver: str, pid: str,
                 epsilon: float = 10**-6) \
            -> None:
        # ----------------------------------------------------------------------
        # ModelInterface data
        # ----------------------------------------------------------------------
        self.pid: str = pid
        self.lpsolver: str = lpsolver

        # ----------------------------------------------------------------------
        # Parameters
        # ----------------------------------------------------------------------
        self.epsilon: float = epsilon

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
        self.description_complement: list[tuple[int, ...]] = []
        self.added_order: list[int] = []

        # ----------------------------------------------------------------------
        # Problem structure
        # ----------------------------------------------------------------------
        self.constraints_exists: dict[int, ExistsConstraint]
        self.constraints_forall: dict[int, ForallConstraint]
        self.objectives: dict[int, Objective]

        # ----------------------------------------------------------------------
        # Model data
        # ----------------------------------------------------------------------
        self.default_objective: Any
        self.variables: dict[str, Any]
        self.constraints: dict[int, Any]

    # ==========================================================================
    # Builder
    # ==========================================================================
    def update(self: ModelInterface,
               constraints: list[tuple[int,
                                       LpConstraint,
                                       tuple[int, ...]]]) -> None:
        for cid, constraint, description in constraints:
            self.add(cid, constraint, description)

    def add(self: ModelInterface, cid: int, constraint: LpConstraint,
            description: tuple[int, ...]) -> None:
        constraint_type, expr, _, _ = constraint  # type: ignore
        # ----------------------------------------------------------------------
        # Instanciate new variables
        # ----------------------------------------------------------------------
        for _, var in expr:
            if var not in self.variables:
                self.variables[var] = self._add_lpvariable(var)
        # ----------------------------------------------------------------------
        # Split the different constraint types
        # ----------------------------------------------------------------------
        _, expr, sense, b = constraint  # type: ignore
        if constraint_type == 'exists':
            assert cid not in self.constraints
            self.description[cid] = description
            self.constraints_exists[cid] = (
                self._get_lpexpression(expr),
                sense,
                b
            )
            self.constraints[cid] = self._add_lpconstraint(cid)
            self.added_order.append(cid)
        elif constraint_type == 'forall':
            assert cid not in self.constraints_forall
            self.description_db[cid] = description
            self.constraints_forall[cid] = (
                self._add_lpobjective(expr, direction=sense),
                '>=',
                b if sense == '>=' else -b
            )
        else:
            assert cid not in self.objectives
            self.description_db[cid] = description
            self.objectives[cid] = (
                self._add_lpobjective(expr, direction=sense),
                sense,
                b
            )

    def add_constraint_exists(self: ModelInterface, cid: int,
                              constraint: LpConstraint,
                              description: tuple[int, ...]) -> None:
        _, expr, sense, b = constraint  # type: ignore
        # ----------------------------------------------------------------------
        # Build the constraints
        # ----------------------------------------------------------------------
        self.description[cid] = description
        self.constraints_exists[cid] = (
            self._get_lpexpression(expr),
            sense,
            b
        )
        self.constraints[cid] = self._add_lpconstraint(cid)
        self.added_order.append(cid)


    def remove(self: ModelInterface, cids: list[int]) -> None:
        for cid in cids:
            if cid in self.constraints:
                self._remove_lpconstraint(self.constraints[cid])
                del self.description[cid]
                del self.constraints_exists[cid]
                del self.constraints[cid]
                self.added_order.remove(cid)
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
    def check_exists(self: ModelInterface) -> bool:
        status, _ = self.__solve()
        return status in ('optimal', 'unbounded')

    def check_forall(self: ModelInterface) -> list[int]:
        conflicts: list[int] = []
        for cid, lpcons in self.constraints_forall.items():
            # ------------------------------------------------------------------
            # Add new objective
            # ------------------------------------------------------------------
            objective, sense, b = lpcons
            self._set_lpobjective(objective)
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
                if (sense == '>=' and not optimum >= b - self.epsilon) \
                        or (sense == '<=' and not optimum <= b + self.epsilon):
                    conflicts.append(cid)
            elif status == 'infeasible':
                # If one problem is infeasible, then all are
                self._set_lpobjective(self.default_objective)
                del self.description[cid]
                break
            elif status == 'unbounded':
                conflicts.append(cid)
            else:
                print('Error: Unknown LP solver status:', status)
                sys.exit(0)
            # ------------------------------------------------------------------
            # Remove current objective
            # ------------------------------------------------------------------
            self._set_lpobjective(self.default_objective)
            del self.description[cid]
        return conflicts

    def optimize(self: ModelInterface) \
            -> tuple[list[float], list[tuple[str, float]]]:
        raise NotImplementedError()

    def __solve(self: ModelInterface) -> tuple[str, float | None]:
        # ----------------------------------------------------------------------
        # CACHE: check if the problem has already been solved
        # ----------------------------------------------------------------------
        dt: float = time()
        cache_check: None | tuple[str, float | None] = self.cache.check(
            list(self.description.values()) + self.description_complement
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
        status, optimum = self._lpsolve()
        self.cache.add(
            list(self.description.values()) + self.description_complement,
            status,
            optimum
        )
        dt = time() - dt
        self.logger.lpsolver_calls.append(dt)
        return status, optimum

    # ==========================================================================
    # Core conflicts
    # ==========================================================================
    def core_unsat_exists(self: ModelInterface, lazy: bool = False) -> list[int]:
        # ----------------------------------------------------------------------
        # If Lazy: do not compute the unsatisfiable core
        # ----------------------------------------------------------------------
        if lazy:
            return list(self.constraints.keys())
        # ----------------------------------------------------------------------
        # Else: compute the unsatisfiable core
        # ----------------------------------------------------------------------
        conflicting_cids: list[int] = []
        removed_constraints: list[int] = []
        removed_description: dict[int, tuple[int, ...]] = {}
        for cid in self.constraints_exists:
            # ------------------------------------------------------------------
            # Remove a constraint
            # ------------------------------------------------------------------
            self._remove_lpconstraint(self.constraints[cid])
            removed_description[cid] = self.description[cid]
            del self.constraints[cid]
            del self.description[cid]
            # ------------------------------------------------------------------
            # Check the satisfiability
            # ------------------------------------------------------------------
            if self.check_exists():
                conflicting_cids.append(abs(cid))
                self.constraints[cid] = self._add_lpconstraint(cid)
                self.description[cid] = removed_description[cid]
                del removed_description[cid]
            else:
                removed_constraints.append(cid)
        # ------------------------------------------------------------------
        # Re-add all the removed constraints
        # ------------------------------------------------------------------
        for cid in removed_constraints:
            self.constraints[cid] = self._add_lpconstraint(cid)
        self.description = self.description | removed_description

        self.logger.conflicts_exists += 1
        return conflicting_cids

    def core_unsat_forall(self: ModelInterface, conflict: int,
                          unprop_cids: dict[int, list[tuple[LpConstraint, \
                              tuple[int, ...]]]], lazy: bool = False) \
                                  -> list[int]:
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
        self._set_lpobjective(objective)
        self.description[conflict] = self.description_db[conflict]
        # ----------------------------------------------------------------------
        # For each unused constraints group
        # ----------------------------------------------------------------------
        optimum_cores: list[int] = []
        to_remove_constraints: list[Any] = []
        for up_cid, up_constraints in unprop_cids.items():
            assert up_cid not in self.constraints
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
                    is_meaningfull = \
                        (sense == '>=' and optimum >= b - self.epsilon) or \
                        (sense == '<=' and optimum <= b + self.epsilon)
                elif status == 'infeasible':
                    is_meaningfull = True
                elif status == 'unbounded':
                    pass
                else:
                    print('Error: Unknown LP solver status:', status)
                    sys.exit(0)
                # --------------------------------------------------------------
                # Stop if the constraint is meaningfull
                # --------------------------------------------------------------
                if is_meaningfull:
                    self.remove([up_cid])
                    break
                to_remove_constraints.append(self.constraints[up_cid])
                self.description_complement.append(up_description)
                del self.description[up_cid]
                del self.constraints[up_cid]
                del self.constraints_exists[up_cid]
            # ------------------------------------------------------------------
            # if the constraint is meaningfull it is added to the optimum core
            # ------------------------------------------------------------------
            if is_meaningfull:
                optimum_cores.append(up_cid)
        # ----------------------------------------------------------------------
        # Remove all added constraints
        # ----------------------------------------------------------------------
        for lpconstraint in to_remove_constraints:
            self._remove_lpconstraint(lpconstraint)
            self.description_complement.clear()
        # ----------------------------------------------------------------------
        # Remove current objective
        # ----------------------------------------------------------------------
        self._set_lpobjective(self.default_objective)
        del self.description[conflict]
        return optimum_cores

    # ==========================================================================
    # Getters
    # ==========================================================================
    def get_statistics(self: ModelInterface) -> Logger:
        return self.logger

    def get_assignment(self: ModelInterface) -> dict[str, float | None]:
        return {var: self._get_lpvalue(var) for var in self.variables}

    # ==========================================================================
    # Refactoring
    # ==========================================================================

    def _lpinit(self: ModelInterface, pid: str) -> Any:
        raise NotImplementedError()

    def _add_lpvariable(self: ModelInterface, varname: str) -> Any:
        raise NotImplementedError()

    def _add_lpobjective(self: ModelInterface, expr: list[tuple[float, str]],
                           direction: Sense = '>=') -> Any:
        raise NotImplementedError()

    def _get_lpobjective(self: ModelInterface) -> Any:
        raise NotImplementedError()

    def _set_lpobjective(self: ModelInterface, objective: Any) -> None:
        raise NotImplementedError()

    def _get_lpexpression(self: ModelInterface, expr: list[tuple[float, str]],
                           inverse: bool = False) -> Any:
        raise NotImplementedError()

    def _add_lpconstraint(self: ModelInterface, cid: int) -> Any:
        raise NotImplementedError()

    def _remove_lpconstraint(self: ModelInterface, constraint: Any) -> None:
        raise NotImplementedError()

    def _lpsolve(self: ModelInterface) -> tuple[LpStatus, float | None]:
        raise NotImplementedError()

    def _get_lpvalue(self: ModelInterface, varname: str) -> float | None:
        raise NotImplementedError()