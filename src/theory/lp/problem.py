"""_summary_
"""

#Import#########################################################################

from pulp import (
    LpAffineExpression,
    LpProblem,
    LpConstraint,
    LpConstraintEQ,
    LpConstraintGE,
    LpConstraintLE,
    LpContinuous,
    LpMinimize,
    LpSolution,
    LpSolver,
    LpVariable,
    lpSum,
)

from typing import Dict, Tuple, Union

from .parser import (
    AffineExpr,
    AssertLp,
    ConstraintLp,
    DomainLp,
    ObjectiveLp,
    Constraint,
    CType,
    Variable,
)

#Type#Alias#####################################################################

Assignment = Dict[str, float]

#Class#LP#Problem###############################################################


class ProblemLp:
    """_summary_
    """

    def __init__(self, id: str, solver: LpSolver):
        """_summary_

        :param id: _description_
        :type id: str
        :param solver: _description_
        :type solver: LpSolver
        """
        self.id: str = id
        self.solver: LpSolver = solver(msg=False)

        self.__cid2object: Dict[int, Constraint] = {}

        self.__problem: LpProblem = LpProblem(name=id, sense=LpMinimize)

        self.__variables: Dict[Variable, LpVariable] = {}

        self.__assignment: Assignment = {}
        self.__asserts: Dict[int, LpAffineExpression, float] = {}
        self.__objectives: Dict[int, LpAffineExpression] = {}

    def __build_LpAffineExpr(self, expr: AffineExpr) -> LpAffineExpression:
        """_summary_

        :param expr: _description_
        :type expr: AffineExpr
        :return: _description_
        :rtype: LpAffineExpression
        """
        lp_expr: LpAffineExpression = lpSum(
            coeff * self.__variables[var]
            for coeff, var in expr
        )
        return lp_expr

    def __add_variable(self, var_name: str) -> None:
        """_summary_

        :param var: _description_
        :type var: Variable
        """
        if var_name not in self.__variables:
            self.__variables[var_name] = LpVariable(
                var_name,
                lowBound=None,
                upBound=None,
                cat=LpContinuous
            )

    def add_assert(self, cid: int, cons: AssertLp) -> None:
        """_summary_

        :param cid: _description_
        :type cid: int
        :param cons: _description_
        :type cons: AssertLp
        """
        self.__cid2object[cid] = cons

        _, expr, op, bound = cons
        for _, var in expr:
            self.__add_variable(var)

        if op == '=':
            sense: int = LpConstraintEQ
        elif op == '<=':
            sense: int = LpConstraintLE
        elif op == '>=':
            sense: int = LpConstraintGE

        lp_expr: LpAffineExpression = self.__build_LpAffineExpr(expr)
        lp_constraint: LpConstraint = LpConstraint(
            e=lp_expr,
            sense=sense,
            rhs=bound,
            name=cid
        )

        self.__asserts[cid] = lp_constraint

    def add_constraint(self, cid: int, cons: ConstraintLp) -> None:
        """_summary_

        :param cid: _description_
        :type cid: int
        :param cons: _description_
        :type cons: ConstraintLp
        """
        self.__cid2object[cid] = cons

        _, expr, op, bound = cons
        for _, var in expr:
            self.__add_variable(var)

        if op == '=':
            sense: int = LpConstraintEQ
        elif op == '<=':
            sense: int = LpConstraintLE
        elif op == '>=':
            sense: int = LpConstraintGE

        lp_expr: LpAffineExpression = self.__build_LpAffineExpr(expr)
        lp_constraint: LpConstraint = LpConstraint(
            e=lp_expr,
            sense=sense,
            rhs=bound,
            name=str(cid)
        )

        self.__problem.addConstraint(lp_constraint, name=cid)

    def add_domain(self, cid: Union[int, None], dom: DomainLp) -> None:
        """_summary_

        :param cid: _description_
        :type cid: int
        :param var: _description_
        :type var: Variable
        """
        self.__cid2object[cid] = dom

        _, var_name, var_lower, var_upper = dom

        self.__add_variable(var_name)
        self.__variables[var_name].lowBound = var_lower
        self.__variables[var_name].upBound = var_upper
        self.__variables[var_name].bounds(var_lower, var_upper)

    def add_objective(self, cid: int, obj: ObjectiveLp) -> None:
        """_summary_

        :param cid: _description_
        :type cid: int
        :param obj: _description_
        :type obj: ObjectiveLp
        """
        self.__cid2object[cid] = obj

        _, expr, sense, _ = obj

        lp_expr: LpAffineExpression = sense * self.__build_LpAffineExpr(expr)

        self.__objectives[cid] = lp_expr

    def append(self, cid: int, cons: Constraint) -> None:
        """_summary_

        :param cid: _description_
        :type cid: int
        :param cons: _description_
        :type cons: Constraint
        """
        assert(cid not in self.__cid2object)
        ctype: CType = cons[0]
        if ctype == 'objective':
            self.add_objective(cid, cons)
        elif ctype == 'dom':
            self.add_domain(cid, cons)
        elif ctype == 'constraint':
            self.add_constraint(cid, cons)
        elif ctype == 'assert':
            self.add_assert(cid, cons)
        else:
            print('Error: Unknown constraint type:', ctype)
            exit(0)

    def remove_assert(self, cid: int) -> None:
        """_summary_

        :param cid: _description_
        :type cid: int
        """
        del self.__asserts[cid]
        del self.__cid2object[cid]

    def remove_constraint(self, cid: int) -> None:
        """_summary_

        :param cid: _description_
        :type cid: int
        """
        del self.__problem.constraints[str(cid)]
        del self.__cid2object[cid]

    def remove_domain(self, cid: int) -> None:
        """_summary_

        :param cid: _description_
        :type cid: int
        """
        dom: DomainLp = self.__cid2object[cid]
        self.__variables[dom[1]].lowBound = None
        self.__variables[dom[1]].upBound = None
        del self.__cid2object[cid]

    def remove_objective(self, cid: int) -> None:
        """_summary_

        :param cid: _description_
        :type cid: int
        """
        del self.__objectives[cid]
        del self.__cid2object[cid]

    def remove(self, cid: int) -> None:
        """_summary_

        :param cid: _description_
        :type cid: int
        """
        ctype: CType = self.__cid2object[cid][0]
        if ctype == 'assert':
            self.remove_assert(cid)
        elif ctype == 'constraint':
            self.remove_constraint(cid)
        elif ctype == 'dom':
            self.remove_domain(cid)
        elif ctype == 'objective':
            self.remove_objective(cid)
        else:
            print('Error: Unknown constraint type:', ctype)
            exit(0)

    def solve(self) -> Tuple[int, Union[Dict[str, float], None], float]:
        """_summary_

        :return: _description_
        :rtype: Tuple[int, Union[Dict[str, float], None], float]
        """
        return (1, None, -1)

    def __str__(self) -> str:
        return str(self.__problem)
