"""_summary_
"""

#Import#########################################################################

from operator import index
from pulp import (
    LpAffineExpression,
    LpProblem,
    LpConstraint,
    LpConstraintEQ,
    LpConstraintGE,
    LpConstraintLE,
    LpContinuous,
    LpMinimize,
    LpSolver,
    LpStatus,
    LpVariable,
    lpSum,
)

from typing import Dict, List, Tuple, Union

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
        self.solver: LpSolver = solver(msg=False, warmStart=True)

        self.__untrack_changes: List[int] = []
        self.__changes_stack: List[List[int]] = []

        self.__cid2object: Dict[int, Constraint] = {}

        self.__problem: LpProblem = LpProblem(name=id, sense=LpMinimize)
        self.__variables: Dict[Variable, LpVariable] = {}

        self.__assignment = {}
        self.__asserts: Dict[int, LpAffineExpression, float] = {}
        self.__objectives: Dict[int, LpVariable] = {}

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
                var_name, lowBound=None, upBound=None, cat=LpContinuous
            )

    def add_assert(self, cid: int, cons: AssertLp) -> None:
        """_summary_

        :param cid: _description_
        :type cid: int
        :param cons: _description_
        :type cons: AssertLp
        """
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
        lp_constraint: LpConstraint = LpConstraint(e=lp_expr, sense=sense, rhs=bound, name=cid
                                                   )

        self.__asserts[cid] = lp_constraint

    def add_constraint(self, cid: int, cons: ConstraintLp) -> None:
        """_summary_

        :param cid: _description_
        :type cid: int
        :param cons: _description_
        :type cons: ConstraintLp
        """
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
        lp_constraint: LpConstraint = LpConstraint(e=lp_expr, sense=sense, rhs=bound, name=str(cid)
                                                   )

        self.__problem.addConstraint(lp_constraint, name=cid)

    def add_domain(self, cid: Union[int, None], dom: DomainLp) -> None:
        """_summary_

        :param cid: _description_
        :type cid: int
        :param var: _description_
        :type var: Variable
        """
        _, var_name, var_lower, var_upper = dom

        self.__add_variable(var_name)
        self.__variables[var_name].lowBound = var_lower
        self.__variables[var_name].upBound = var_upper

    def add_objective(self, cid: int, obj: ObjectiveLp) -> None:
        """_summary_

        :param cid: _description_
        :type cid: int
        :param obj: _description_
        :type obj: ObjectiveLp
        """
        _, expr, sense, _ = obj
        for _, var in expr:
            self.__add_variable(var)

        var_name: str = f'Opt_{cid}'
        self.__add_variable(var_name)
        variable: LpVariable = self.__variables[var_name]

        lp_expr: LpAffineExpression = sense * self.__build_LpAffineExpr(expr)
        lp_expr.addterm(variable, -1)

        constraint: LpConstraint = LpConstraint(e=lp_expr, sense=LpConstraintEQ, rhs=0, name=str(cid),
                                                )
        self.__problem.addConstraint(constraint)
        self.__objectives[cid] = variable

    def append(self, cid: int, cons: Constraint) -> None:
        """_summary_

        :param cid: _description_
        :type cid: int
        :param cons: _description_
        :type cons: Constraint
        """
        assert(cid not in self.__cid2object)
        self.__cid2object[cid] = cons
        self.__untrack_changes.append(cid)
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

    def update_stack(self) -> None:
        """_summary_
        """
        if len(self.__untrack_changes) != 0:
            self.__changes_stack.append(self.__untrack_changes.copy())
            self.__untrack_changes.clear()

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
        self.__remove_pulp_constraint(cid)
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
        del self.__problem.constraints[str(cid)]
        del self.__objectives[cid]
        del self.__cid2object[cid]

    def remove(self, cid: int) -> None:
        """_summary_

        :param cid: _description_
        :type cid: int
        """
        if cid in self.__untrack_changes:
            self.__untrack_changes.remove(cid)
        else:
            assert(len(self.__untrack_changes) == 0)
            assert(cid in self.__changes_stack[-1])
            self.__untrack_changes = self.__changes_stack[-1]
            self.__untrack_changes.remove(cid)
            self.__changes_stack = self.__changes_stack[:-1]
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
    
    def __get_unused_variables(self, vars:List[str]) -> List[str]:
        """_summary_

        :param vars: _description_
        :type vars: List[str]
        :return: _description_
        :rtype: List[str]
        """
        for curr_cid in self.__problem.constraints:
            curr_cons: LpConstraint = self.__problem.constraints[curr_cid]
            for curr_var in curr_cons.toDict()['coefficients']:
                if curr_var['name'] in vars:
                    vars.remove(curr_var['name'])
        return vars
    
    def __remove_pulp_constraint(self, cid: int) -> Constraint:
        """_summary_

        :param cid: _description_
        :type cid: int
        """
        cons: LpConstraint = self.__problem.constraints[str(cid)]
        del self.__problem.constraints[str(cid)]
        cons_var: List[LpVariable] = [
            var_name for _, var_name in self.__cid2object[cid][1]
        ]
        unused_vars: List[str] = self.__get_unused_variables(cons_var)
        for i, var in enumerate(self.__problem._variables):
            var: LpVariable
            if var.name in unused_vars:
                del self.__problem._variables[i]
        return cons
            
    def compute_core_conflict(self) -> List[int]:
        """_summary_

        :return: _description_
        :rtype: List[int]
        """
        assert(len(self.__untrack_changes) == 0)
        last_added: List[int] = self.__changes_stack[-1]

        core_conflict: List[int] = []
        constraint_cache: List[Tuple[cid, LpConstraint]] = []

        for cid in last_added:
            ctype: CType = self.__cid2object[cid][0]
            if ctype == 'constraint' or ctype == 'objective':
                cons: LpConstraint = self.__remove_pulp_constraint(cid)
                status: LpStatus = self.__problem.solve(self.solver)
                if status != -1:
                    core_conflict.append(cid)
                    self.__problem.addConstraint(cons, name=cid)
                    self.__problem.modifiedVariables
                else:
                    constraint_cache.append((cid, cons))
        
        for cid, cons in constraint_cache:
            self.__problem.addConstraint(cons, name=cid)
        
        return core_conflict

    def solve(self) -> Tuple[int, Union[Dict[str, float], None], List[Tuple[str, float]]]:
        """_summary_

        :return: _description_
        :rtype: Tuple[int, Union[Dict[str, float], None], float]
        """
        self.update_stack()
        
        optimums: Union[List[float], None] = []
        fixed_cid: List[Tuple[LpVariable, int, int]] = []
        for cid, opt_var in self.__objectives.items():
            cid: int
            opt_var: LpVariable

            obj_cons: LpConstraint = self.__problem.constraints[str(cid)]
            self.__problem.setObjective(lpSum(opt_var))
            status: LpStatus = self.__problem.solve(self.solver)
            
            if status == 1:
                fixed_cid.append((opt_var, opt_var.lowBound, opt_var.upBound))
                optimum: float = self.__cid2object[cid][2] * opt_var.varValue
                optimums.append((str(obj_cons), optimum))
                opt_var.fixValue()
            elif status == -2:
                optimum: float = self.__cid2object[cid][2] * opt_var.varValue
                optimums.append(str(obj_cons), optimum)
            else:
                optimums = None
                break

        for opt_var, low, up in fixed_cid:
            opt_var.lowBound = low
            opt_var.upBound = up
        
        obj_var: List[str] = [var.name for var in self.__objectives.values()]
        for var in self.__problem.variables():
            if str(var) not in obj_var:
                self.__assignment[str(var)] = var.varValue
                
        return (status, self.__assignment, optimums)
    
    def ensure(self) -> List[Tuple[int, bool]]:
        """"""

    def __str__(self) -> str:
        return str(self.__problem)
