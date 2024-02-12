# -*- coding=utf-8 -*-

# ==============================================================================
# IMPORT
# ==============================================================================

from __future__ import annotations
import sys

from pulp import (  # type: ignore
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
    LpStatus as PulpStatus,
    LpVariable,
    lpSum,
    value
)

from merrinasp.theory.lra.models.interface import (
    ModelInterface,
    Sense,
    LpStatus
)
from merrinasp.theory.lra.cache import LpCache

# ==============================================================================
# Type Alias
# ==============================================================================

ExistsConstraint = tuple[LpAffineExpression, Sense, float]
ForallConstraint = tuple[LpAffineExpression, Sense, float]

# ==============================================================================
# Lp Models
# ==============================================================================


class ModelPuLP(ModelInterface):

    def __init__(self: ModelPuLP, lpsolver: str, pid: str,
                 cache: LpCache = LpCache(), epsilon: float = 10**-6) \
            -> None:
        super().__init__(lpsolver, pid, epsilon=epsilon, cache=cache)
        # ----------------------------------------------------------------------
        # Problem structure
        # ----------------------------------------------------------------------
        self.constraints_exists: dict[int, ExistsConstraint] = {}
        self.constraints_forall: dict[int, ForallConstraint] = {}

        # ----------------------------------------------------------------------
        # Lp solver interface
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
        self.model: LpProblem = self._lpinit(pid)
        self.default_objective: LpAffineExpression = self._get_lpobjective()
        self.variables: dict[str, LpVariable] = {}
        self.constraints: dict[int, LpConstraint] = {}

    # ==========================================================================
    # Methods dedicated to the GUROBI solver
    # ==========================================================================

    def _lpinit(self: ModelPuLP, pid: str) -> LpProblem:
        return LpProblem(name=f'PID_{pid}', sense=LpMinimize)

    def _add_lpvariable(self: ModelPuLP, varname: str) \
            -> LpVariable:
        lpvar: LpVariable = LpVariable(
            name=f'{varname}', cat=LpContinuous, lowBound=None, upBound=None
        )
        self.model.addVariable(lpvar)
        return lpvar

    def _get_lpobjective(self: ModelPuLP) -> LpAffineExpression:
        return self.model.objective  # type: ignore

    def _add_lpobjective(self: ModelPuLP,
                         expr: list[tuple[float, str]]) -> LpAffineExpression:
        return self._get_lpexpression(expr)

    def _set_lpobjective(self: ModelPuLP, objective: LpAffineExpression) \
            -> None:
        self.model.objective = objective
        self.__clear_unused_lpvariable()

    def _get_lpexpression(self: ModelPuLP,
                          expr: list[tuple[float, str]]) -> LpAffineExpression:
        expression: LpAffineExpression = lpSum(
            coeff * self.variables[var] for coeff, var in expr
        )
        return expression

    def _add_lpconstraint(self: ModelPuLP, cid: int) -> LpConstraint:
        expression, sense, b = self.constraints_exists[cid]
        op: int = LpConstraintEQ
        if sense == '<=':
            op = LpConstraintLE
        elif sense == '>=':
            op = LpConstraintGE
        lpconstraint: LpConstraint = LpConstraint(
            name=f'cons_{cid}',
            e=expression,
            rhs=b,
            sense=op
        )
        self.model.addConstraint(lpconstraint)
        return lpconstraint

    def _remove_lpconstraint(self: ModelPuLP,
                             constraint: LpConstraint) -> None:
        del self.model.constraints[constraint.name]
        self.__clear_unused_lpvariable()

    def _lpsolve(self: ModelPuLP) -> tuple[LpStatus, float | None]:
        status: LpStatus = \
            PulpStatus[self.model.solve(
                self.interface)].lower()  # type: ignore
        if status == 'optimal' and self.model.objective is not None:
            return status, value(self.model.objective)  # type: ignore
        return status, None

    def _get_lpvalue(self: ModelPuLP, varname: str) -> float | None:
        assert varname in self.variables
        return value(self.variables[varname])  # type: ignore

    # ==========================================================================
    # Methods dedicated to the GUROBI solver
    # ==========================================================================

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
                expression = self.model.objective.toDict()  # type: ignore
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
