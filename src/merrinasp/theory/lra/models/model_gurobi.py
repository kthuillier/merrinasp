# -*- coding=utf-8 -*-

# ==============================================================================
# IMPORT
# ==============================================================================

from __future__ import annotations

from gurobipy import Model, LinExpr, Constr, Var, GRB

from merrinasp.theory.lra.models.interface import (
    ModelInterface,
    Sense,
    LpStatus
)

# ==============================================================================
# Type Alias
# ==============================================================================

ExistsConstraint = tuple[LinExpr, Sense, float]
ForallConstraint = tuple[LinExpr, Sense, float]
Objective = tuple[LinExpr, Sense, float]

# ==============================================================================
# Lp Models
# ==============================================================================


class ModelGurobiPy(ModelInterface):

    def __init__(self: ModelGurobiPy, lpsolver: str, pid: str,
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
        # Model data
        # ----------------------------------------------------------------------
        self.model: Model = self._lpinit(pid)
        self.default_objective: LinExpr = self._get_lpobjective()
        self.variables: dict[str, Var] = {}
        self.constraints: dict[int, Constr] = {}

    # ==========================================================================
    # Methods dedicated to the GUROBI solver
    # ==========================================================================

    def _lpinit(self: ModelGurobiPy, pid: str) -> Model:
        model: Model = Model(f'PID_{pid}')
        model.setParam('OutputFlag', 0)
        model.setParam('DualReductions', 0)
        return model

    def _add_lpvariable(self: ModelGurobiPy, varname: str) -> Var:
        lpvar: Var = self.model.addVar(
            name=f'{varname}',
            vtype=GRB.CONTINUOUS,
            lb=float('-inf'),
            ub=float('inf')
        )
        return lpvar

    def _get_lpobjective(self: ModelGurobiPy) -> LinExpr:
        return self.model.getObjective()  # type: ignore

    def _add_lpobjective(self: ModelGurobiPy, expr: list[tuple[float, str]],
                           direction: Sense = '>=') -> LinExpr:
        return self._get_lpexpression(expr, inverse=direction == '<=')

    def _set_lpobjective(self: ModelGurobiPy, objective: LinExpr) -> None:
        self.model.setObjective(objective, sense=GRB.MINIMIZE)

    def _get_lpexpression(self: ModelGurobiPy,
                           expr: list[tuple[float, str]],
                           inverse: bool = False) -> LinExpr:
        expression: LinExpr = sum(
            coeff * self.variables[var] for coeff, var in expr  # type: ignore
        )
        if inverse:
            return -expression
        return expression

    def _add_lpconstraint(self: ModelGurobiPy, cid: int) -> Constr:
        expression, sense, b = self.constraints_exists[cid]
        if sense == '>=':
            return self.model.addConstr(
                expression >= b,  # type: ignore
                f'cons_{cid}'
            )
        if sense == '<=':
            return self.model.addConstr(
                expression <= b,  # type: ignore
                f'cons_{cid}'
            )
        return self.model.addConstr(
            expression == b,  # type: ignore
            f'cons_{cid}'
        )

    def _remove_lpconstraint(self: ModelGurobiPy, constraint: Constr) -> None:
        self.model.remove(constraint)

    def _lpsolve(self: ModelGurobiPy) -> tuple[LpStatus, float | None]:
        self.model.optimize()
        status_id: int = self.model.Status
        status: LpStatus = 'undefined'
        if status_id == GRB.OPTIMAL:
            return 'optimal', self.model.ObjVal
        if status_id == GRB.UNBOUNDED:
            status = 'unbounded'
        elif status_id == GRB.INFEASIBLE:
            status = 'infeasible'
        return status, None

    def _get_lpvalue(self: ModelGurobiPy, varname: str) -> float | None:
        assert varname in self.variables
        return self.variables[varname].X
