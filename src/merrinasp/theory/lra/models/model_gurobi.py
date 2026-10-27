# -*- coding=utf-8 -*-

# ==============================================================================
# IMPORT
# ==============================================================================

from __future__ import annotations

from gurobipy import Model, LinExpr, Constr, Var, GRB, Env

from merrinasp.theory.lra.models.interface import (
    ModelInterface,
    Sense,
    LpStatus
)
from merrinasp.theory.lra.cache import LpCache

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
                 cache: LpCache = LpCache(), epsilon: float = 10**-6) \
            -> None:
        super().__init__(lpsolver, pid, epsilon=epsilon, cache=cache)
        # ----------------------------------------------------------------------
        # Problem structure
        # ----------------------------------------------------------------------
        self.constraints_exists: dict[int, ExistsConstraint] = {}
        self.constraints_forall: dict[int, ForallConstraint] = {}

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
        # ~ Remove all automated logs message when calling Gurobi solver
        ENV: Env = Env(empty=True)
        ENV.setParam("OutputFlag", 0)
        ENV.setParam("LogToConsole", 0)
        ENV.start()
        # ~ Init model
        model: Model = Model(f'PID_{pid}', env = ENV)
        model.setParam(GRB.Param.OutputFlag, 0)
        model.setParam(GRB.Param.LogToConsole, 0)
        model.setParam(GRB.Param.DualReductions, 0)
        # ~ Provide a Farkas certificate (FarkasDual) for infeasible models
        model.setParam(GRB.Param.InfUnbdInfo, 1)
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

    def _add_lpobjective(self: ModelGurobiPy,
                         expr: list[tuple[float, str]]) -> LinExpr:
        return self._get_lpexpression(expr)

    def _set_lpobjective(self: ModelGurobiPy, objective: LinExpr) -> None:
        self.model.setObjective(objective, sense=GRB.MINIMIZE)

    def _get_lpexpression(self: ModelGurobiPy,
                          expr: list[tuple[float, str]]) -> LinExpr:
        expression: LinExpr = sum(
            coeff * self.variables[var] for coeff, var in expr  # type: ignore
        )
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
            # ~ Gurobi's UNBOUNDED only proves an unbounded ray, not that the
            # model is feasible: check feasibility with a zero objective
            status = 'unbounded' if self.__is_feasible() else 'infeasible'
        elif status_id == GRB.INFEASIBLE:
            status = 'infeasible'
            self._unsat_core = self.__infeasibility_core()
        return status, None

    def __is_feasible(self: ModelGurobiPy) -> bool:
        objective: LinExpr = self.model.getObjective()  # type: ignore
        self.model.setObjective(LinExpr(), sense=GRB.MINIMIZE)
        self.model.optimize()
        self.logger.lpsolver_calls_nb += 1
        feasible: bool = self.model.Status != GRB.INFEASIBLE
        if not feasible:
            self._unsat_core = self.__infeasibility_core()
        self.model.setObjective(objective, sense=GRB.MINIMIZE)
        return feasible

    def __infeasibility_core(self: ModelGurobiPy) -> list[int] | None:
        # ~ The support of the Farkas dual is an infeasible subsystem
        cids: list[int] = list(self.constraints.keys())
        if len(cids) == 0:
            return None
        try:
            farkas: list[float] = self.model.getAttr(
                GRB.Attr.FarkasDual,
                [self.constraints[cid] for cid in cids]
            )
        except Exception:  # pylint: disable=broad-except
            return None
        return [cid for cid, y in zip(cids, farkas) if abs(y) > 1e-9]

    def _get_lpvalue(self: ModelGurobiPy, varname: str) -> float | None:
        assert varname in self.variables
        return self.variables[varname].X
