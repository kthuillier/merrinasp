# -*- coding=utf-8 -*-

# ==============================================================================
# IMPORT
# ==============================================================================

from __future__ import annotations
from typing import Literal
from time import time
import sys

from pulp import ( #type: ignore
    LpAffineExpression,
    LpProblem,
    LpConstraint,
    LpConstraintEQ,
    LpConstraintGE,
    LpConstraintLE,
    LpContinuous,
    LpMinimize,
    LpSolver,
    CPLEX_PY,
    GUROBI,
    PULP_CBC_CMD,
    LpStatus,
    LpVariable,
    lpSum,
    value
)

from merrinasp.theory.lra.models.interface import ModelInterface, EPSILON
from merrinasp.theory.language import LpConstraint as TypeLpConstraint

# ==============================================================================
# Lp Models
# ==============================================================================


class ModelPuLP(ModelInterface):

    def __init__(self: ModelPuLP, lpsolver: str, pid: str) -> None:
        super().__init__(lpsolver, pid)
        # ----------------------------------------------------------------------
        # LP Solver
        # ----------------------------------------------------------------------
        self.interface: LpSolver = PULP_CBC_CMD(msg=False, warmStart=True)
        if lpsolver.lower() == 'cbc':
            self.interface = PULP_CBC_CMD(msg=False, warmStart=True)
        elif lpsolver.lower() == 'cplex':
            self.interface = CPLEX_PY(msg=False, warmStart=False)
        elif lpsolver.lower() == 'gurobi':
            self.interface = GUROBI(msg=False, warmStart=True)
        else:
            print('Error: Unknown LP solver:', lpsolver)
            sys.exit(0)

        # ----------------------------------------------------------------------
        # Model data
        # ----------------------------------------------------------------------
        self.model: LpProblem = LpProblem(name=f'PID_{pid}', sense=LpMinimize)
        self.default_objective: LpAffineExpression = self.model.objective
        self.variables: dict[str, LpVariable] = {}
        self.constraints_exists: dict[int, LpConstraint] = {}
        self.constraints_forall: dict[int, tuple[LpAffineExpression,
                                                 Literal['<=', '>=', '='],
                                                 float]] = {}
        self.objectives: dict[int, LpAffineExpression] = {}
        self.description: dict[int, tuple[int, ...]]

        # ----------------------------------------------------------------------
        # FIXME: Debug
        # ----------------------------------------------------------------------
        self._description_dbg: list[tuple[int, ...]] = []

    # ==========================================================================
    # Builder
    # ==========================================================================
    def add(self: ModelPuLP, cid: int, constraint: TypeLpConstraint,
            description: tuple[int, ...]) -> None:
        constraint_type, expr, sense, b = constraint  # type: ignore
        # ----------------------------------------------------------------------
        # Instanciate new variables
        # ----------------------------------------------------------------------
        for _, var in expr:
            if var not in self.variables:
                lpvar: LpVariable = LpVariable(
                    name=f'{var}',
                    cat=LpContinuous,
                    lowBound=None,
                    upBound=None
                )
                self.variables[lpvar.name] = lpvar
        # ----------------------------------------------------------------------
        # Preprocessing
        # ----------------------------------------------------------------------
        expression: LpAffineExpression = lpSum(
            k * self.variables[var] for k, var in expr  # type: ignore
        )
        direction: str = 'min' if sense == '>=' else 'max'
        op: int = LpConstraintEQ
        if sense == '<=':
            op = LpConstraintLE
        elif sense == '>=':
            op = LpConstraintGE
        # ----------------------------------------------------------------------
        # Split the different constraint types
        # ----------------------------------------------------------------------
        if constraint_type == 'exists':
            assert cid not in self.constraints_exists
            lpconstraint: LpConstraint = LpConstraint(
                name=f'cons_{cid}',
                e=expression,
                rhs=b,
                sense=op
            )
            self.description[cid] = description
            self.constraints_exists[cid] = lpconstraint
            self.model.add(lpconstraint)
        elif constraint_type == 'forall':
            assert cid not in self.constraints_forall
            lpforall: LpAffineExpression = expression if direction == 'min' \
                else -expression
            self.description_db[cid] = description
            self.constraints_forall[cid] = (
                lpforall,
                '>=',
                b if direction == 'min' else -b
            )
        else:
            assert cid not in self.objectives
            lpobjective: LpAffineExpression = expression if direction == 'min' \
                else -expression
            self.description_db[cid] = description
            self.objectives[cid] = lpobjective
        self.added_order.append(cid)

    def remove(self: ModelPuLP, cids: list[int]) -> None:
        for cid in cids:
            if cid in self.constraints_exists:
                constraint: LpConstraint = self.constraints_exists[cid]
                self.__remove_lpconstraint(constraint)
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
            self.added_order.remove(cid)
        self.__clear_unused_lpvariable()

    # --------------------------------------------------------------------------
    # Auxiliary functions
    # --------------------------------------------------------------------------
    def __remove_lpconstraint(self: ModelPuLP,
                            constraint: LpConstraint) -> None:
        del self.model.constraints[constraint.name]

    def __clear_unused_lpvariable(self: ModelPuLP) -> None:
        # ----------------------------------------------------------------------
        # Get used variables
        # ----------------------------------------------------------------------
        def __get_used_lpvariable() -> set[str]:
            used_vars: set[str] = set()
            for constraint in self.model.constraints.values():
                expression = constraint.toDict()['coefficients']
                for var in expression:
                    used_vars.add(var['name'])
            if self.model.objective is not None:
                expression = self.model.objective.toDict() #type: ignore
                for var in expression:
                    used_vars.add(var['name'])
            return used_vars
        used_vars: set[str] = __get_used_lpvariable()
        # ----------------------------------------------------------------------
        # Get unused variables
        # ----------------------------------------------------------------------
        unused_vars: set[str] = {
            var.name
            for var in self.model.variables()
            if var.name not in used_vars
        }
        # ----------------------------------------------------------------------
        # Remove unused variables
        # ----------------------------------------------------------------------
        # Remove index
        for var in unused_vars:
            indexes: list[str] = [var_.name for var_ in self.model._variables]
            index: int = indexes.index(var)
            self.model._variables.pop(index)
        # Remove IDs
        for i, lpvar in list(self.model._variable_ids.items()):
            if lpvar.name in unused_vars:
                del self.model._variable_ids[i]

    # ==========================================================================
    # Solving
    # ==========================================================================
    def check_exists(self: ModelPuLP) -> bool:
        # if len(self.constraints_forall) > 0:
        #     return True
        status, _ = self.__solve()
        return status in ('optimal', 'unbounded')

    def check_forall(self: ModelPuLP) -> list[int]:
        conflicts: list[int] = []
        for cid, lpcons in self.constraints_forall.items():
            # ------------------------------------------------------------------
            # Add new objective
            # ------------------------------------------------------------------
            objective, sense, b = lpcons
            self.model.objective = objective
            self.__clear_unused_lpvariable()
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
            self.__clear_unused_lpvariable()
            del self.description[cid]
        return conflicts

    def __solve(self: ModelPuLP) -> tuple[str, float | None]:
        # ----------------------------------------------------------------------
        # CACHE: check if the problem has already been solved
        # ----------------------------------------------------------------------
        dt: float = time()
        cache_check: None | tuple[str, float | None] = self.cache.check(
            list(self.description.values()) + self._description_dbg
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
        # LpStatus = {
        #     0: "Not Solved",
        #     1: "Optimal",
        #     -1: "Infeasible",
        #     -2: "Unbounded",
        #     -3: "Undefined",
        # }
        dt = time()
        status: str = LpStatus[self.model.solve(self.interface)].lower()
        optimum: float | None = None
        if status == 'optimal' and self.model.objective is not None:
            optimum = value(self.model.objective)  # type: ignore
        self.cache.add(
            list(self.description.values()) + self._description_dbg,
            status, optimum)
        dt = time() - dt
        self.logger.lpsolver_calls.append(dt)
        return status, optimum

    # ==========================================================================
    # Core conflicts
    # ==========================================================================
    def core_unsat_exists(self: ModelPuLP, lazy: bool = False) -> list[int]:
        # ----------------------------------------------------------------------
        # If Lazy: do not compute the unsatisfiable core
        # ----------------------------------------------------------------------
        if lazy:
            return list(self.constraints_exists.keys())
        # ----------------------------------------------------------------------
        # Else: compute the unsatisfiable core
        # ----------------------------------------------------------------------
        conflicting_cids: list[int] = []
        removed_constraints: list[LpConstraint] = []
        removed_description: dict[int, tuple[int, ...]] = {}
        for cid in reversed(self.added_order):
            constraint: LpConstraint = self.constraints_exists[cid]
            # ------------------------------------------------------------------
            # Remove a constraint
            # ------------------------------------------------------------------
            self.__remove_lpconstraint(constraint)
            self.__clear_unused_lpvariable()
            removed_description[cid] = self.description[cid]
            del self.description[cid]
            # ------------------------------------------------------------------
            # Check the satisfiability
            # ------------------------------------------------------------------
            if self.check_exists():
                conflicting_cids.append(abs(cid))
                self.model.add(constraint)
                self.description[cid] = removed_description[cid]
                del removed_description[cid]
            else:
                removed_constraints.append(constraint)
        # ----------------------------------------------------------------------
        # Re-add all the removed constraints
        # ----------------------------------------------------------------------
        for constraint in removed_constraints:
            self.model.add(constraint)
        self.description = self.description | removed_description

        self.logger.conflicts_exists += 1
        return conflicting_cids

    def core_unsat_forall(self: ModelPuLP, conflict: int,
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
        self.__clear_unused_lpvariable()
        self.description[conflict] = self.description_db[conflict]
        # ----------------------------------------------------------------------
        # For each unused constraints group
        # ----------------------------------------------------------------------
        optimum_cores: list[int] = []
        to_remove_constraints: list[LpConstraint] = []
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
                    is_meaningfull = \
                        (sense == '>=' and optimum >= b - EPSILON) or \
                        (sense == '<=' and optimum <= b + EPSILON)
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
                lpconstraint: LpConstraint = self.constraints_exists[up_cid]
                to_remove_constraints.append(lpconstraint)
                self._description_dbg.append(up_description)
                del self.description[up_cid]
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
            self.__remove_lpconstraint(lpconstraint)
            self.__clear_unused_lpvariable()
            self._description_dbg.clear()
        # ----------------------------------------------------------------------
        # Remove current objective
        # ----------------------------------------------------------------------
        self.model.objective = self.default_objective
        del self.description[conflict]
        return optimum_cores

    # ==========================================================================
    # Getters
    # ==========================================================================
    def get_assignment(self: ModelPuLP) -> dict[str, float]:
        return {
            name: float(value(var)) #type: ignore
            for name, var in self.variables.items()
            if value(var) is not None
        }
