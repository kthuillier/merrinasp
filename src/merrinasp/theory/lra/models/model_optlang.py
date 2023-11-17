# -*- coding=utf-8 -*-

# ==============================================================================
# IMPORT
# ==============================================================================

from __future__ import annotations
from typing import Any
import sys

from optlang import (  # type: ignore
    interface,
    glpk_interface,
    gurobi_interface,
    cplex_interface
)

from merrinasp.theory.lra.models.interface import (
    ModelInterface,
    Sense,
    LpStatus
)

# ==============================================================================
# Type Alias
# ==============================================================================

ExistsConstraint = tuple[Any, Sense, float]
ForallConstraint = tuple[Any, Sense, float]
Objective = tuple[Any, Sense, float]

# ==============================================================================
# Lp Models
# ==============================================================================


class ModelOptlang(ModelInterface):

    def __init__(self: ModelOptlang, lpsolver: str, pid: str,
                 epsilon: float = 10**-6) \
            -> None:
        super().__init__(lpsolver, pid, epsilon=epsilon)
        # ----------------------------------------------------------------------
        # Problem structure
        # ----------------------------------------------------------------------
        self.constraints_exists: dict[int, ExistsConstraint] = {}
        self.constraints_forall: dict[int, ForallConstraint] = {}
        self.objectives: dict[int, Objective] = {}

        # ----------------------------------------------------------------------
        # Lp solver interface
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
        self.model: interface.Model = self._lpinit(pid)
        self.default_objective: interface.Objective = self._get_lpobjective()
        self.variables: dict[str, interface.Variable] = {}
        self.constraints: dict[int, interface.Constraint] = {}

    # ==========================================================================
    # Methods dedicated to the GUROBI solver
    # ==========================================================================

    def _lpinit(self: ModelOptlang, pid: str) -> interface.Model:
        return self.interface.Model(f'PID_{pid}')

    def _add_lpvariable(self: ModelOptlang, varname: str) \
            -> interface.Variable:
        lpvar: interface.Variable = self.interface.Variable(
            name=f'{varname}', type='continuous'
        )
        self.model.add(lpvar)
        return lpvar

    def _get_lpobjective(self: ModelOptlang) -> interface.Objective:
        return self.model.objective

    def _add_lpobjective(self: ModelOptlang, expr: list[tuple[float, str]],
                           direction: Sense = '>=') -> interface.Objective:
        expression: Any = self._get_lpexpression(
            expr, inverse=direction == '<='
        )
        return self.interface.Objective(expression, direction='min')

    def _set_lpobjective(self: ModelOptlang, objective: interface.Objective) \
            -> None:
        self.model.objective = objective

    def _get_lpexpression(self: ModelOptlang,
                           expr: list[tuple[float, str]],
                           inverse: bool = False) -> Any:
        expression: Any = sum(
            coeff * self.variables[var] for coeff, var in expr  # type: ignore
        )
        if inverse:
            return -expression
        return expression

    def _add_lpconstraint(self: ModelOptlang, cid: int) \
            -> interface.Constraint:
        expression, sense, b = self.constraints_exists[cid]
        lb: float | None = None if sense == '<=' else b
        ub: float | None = None if sense == '>=' else b
        lpconstraint: interface.Constraint = self.interface.Constraint(
            name=f'cons_{cid}',
            expression=expression,
            lb=lb,
            ub=ub
        )
        self.model.add(lpconstraint)
        return lpconstraint

    def _remove_lpconstraint(self: ModelOptlang,
                              constraint: interface.Constraint) -> None:
        self.model.remove(constraint)

    def _lpsolve(self: ModelOptlang) -> tuple[LpStatus, float | None]:
        status: LpStatus = self.model.optimize()
        if status == 'optimal':
            return status, float(self.model.objective.value)  # type: ignore
        return status, None

    def _get_lpvalue(self: ModelOptlang, varname: str) -> float | None:
        assert varname in self.variables
        return self.variables[varname].primal
