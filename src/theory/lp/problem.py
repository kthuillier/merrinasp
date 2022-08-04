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
    LpSolver,
    LpStatus,
    LpVariable,
    lpSum,
    value
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

    class MemoryState:
        """_summary_
        """

        def __init__(self, timestamp: int = -1) -> None:
            """_summary_

            :param timestamp: _description_, defaults to -1
            :type timestamp: int, optional
            """
            self.timestamp: int = timestamp

            self.changes: List[int] = []

            self.asserts: List[int] = []

            self.status: LpStatus = 0
            self.assignment: List[Tuple[str, float]] = []
            self.optimums: List[Tuple[str, float]] = []

        def __str__(self) -> str:
            """_summary_

            :return: _description_
            :rtype: str
            """
            s = f'#MEMORY STATE: {self.timestamp}#\n'
            s += f'##Changes:\n\t{self.changes}\n'
            s += f'##Asserts:\n\t{self.asserts}\n'
            s += f'##Status:\n\t{self.status}\n'
            s += f'##Assignment:\n\t{self.assignment}\n'
            s += f'##Optimum:\n\t{self.optimums}\n'
            s += f'#################'
            return s

    def __init__(self, id: str, solver: LpSolver):
        """_summary_

        :param id: _description_
        :type id: str
        :param solver: _description_
        :type solver: LpSolver
        """
        self.id: str = id
        self.solver: LpSolver = solver(msg=False, warmStart=True)

        self.__timestamps: Dict[int, int] = {}
        self.__memory_stack: List[ProblemLp.MemoryState] = []

        self.__cid2object: Dict[int, Constraint] = {}

        self.__problem: LpProblem = LpProblem(name=id, sense=LpMinimize)
        self.__variables: Dict[Variable, LpVariable] = {}

        self.__assignment = {}
        self.__asserts: Dict[int, Tuple[LpAffineExpression, str, float]] = {}
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

        lp_expr: LpAffineExpression = self.__build_LpAffineExpr(expr)

        self.__asserts[cid] = (lp_expr, op, bound)
        self.__memory_stack[-1].asserts.append(cid)

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
        self.__problem.addConstraint(lp_constraint, name=str(cid))

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

        constraint: LpConstraint = LpConstraint(
            e=lp_expr,
            sense=LpConstraintEQ,
            rhs=0,
            name=str(cid),
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
        self.__memory_stack[-1].changes.append(cid)
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

    def __get_unused_variables(self, vars: List[str]) -> List[str]:
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
        if self.__problem.objective is not None:
            for obj_var in self.__problem.objective.toDict():
                if obj_var['name'] in vars:
                    vars.remove(obj_var['name'])
        return vars

    def __remove_unused_pulp_variable(self, restricted: List[str] = None) -> None:
        """_summary_

        :param restricted: _description_, defaults to None
        :type restricted: List[str], optional
        """
        if restricted is None:
            cons_var: List[str] = [
                var.name for var in self.__problem.variables()
            ]
        else:
            cons_var: List[str] = restricted
        unused_vars: List[str] = self.__get_unused_variables(cons_var)
        for unused_var in unused_vars:
            index: int = [
                var.name for var in self.__problem._variables
            ].index(unused_var)
            self.__problem._variables.pop(index)

        for i, var in list(self.__problem._variable_ids.items()):
            var: LpVariable
            if var.name in unused_vars:
                del self.__problem._variable_ids[i]

    def __remove_pulp_constraint(self, cid: int) -> Constraint:
        """_summary_

        :param cid: _description_
        :type cid: int
        """
        cons: LpConstraint = self.__problem.constraints[str(cid)]
        del self.__problem.constraints[str(cid)]
        self.__remove_unused_pulp_variable()
        return cons

    def remove_assert(self, cid: int) -> None:
        """_summary_

        :param cid: _description_
        :type cid: int
        """
        if cid in self.__memory_stack[-1].asserts:
            self.__memory_stack[-1].asserts.remove(cid)
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

    def update(self, timestamp: int, changes: List[Tuple[int, Constraint]]) -> None:
        """_summary_

        :param timestamp: _description_
        :type timestamp: int
        :param changes: _description_
        :type changes: List[Tuple[int, Constraint]]
        """
        #print('\t\t\tUpdating, BEFORE memory:')
        # if self.__memory_stack != []:
        #print('\t\t\t\t', self.__memory_stack[-1].timestamp)
        # else:
        # print('\t\t\t\tNONE')
        if timestamp not in self.__timestamps:
            self.__timestamps[timestamp] = len(self.__memory_stack)
            memory: ProblemLp.MemoryState = ProblemLp.MemoryState(timestamp)
            if len(self.__memory_stack) != 0:
                memory.asserts.extend(self.__memory_stack[-1].asserts)
            self.__memory_stack.append(memory)
        self.__memory_stack[-1].status = 0
        for cid, cons in changes:
            self.append(cid, cons)
        #print('\t\t\tUpdating, AFTER memory:')
        #print('\t\t\t\t', self.__memory_stack[-1].timestamp)

    def backtrack(self, timestamp: int) -> None:
        """_summary_

        :param timestamp: _description_
        :type timestamp: int
        """
        #print('\t\t\tBacktracking, BEFORE memory:')
        #print('\t\t\t\t', self.__memory_stack[-1].timestamp)
        index: int = self.__timestamps[timestamp]
        for t in range(index, len(self.__memory_stack)):
            for cid in self.__memory_stack[t].changes:
                self.remove(cid)
            del self.__timestamps[self.__memory_stack[t].timestamp]
        self.__memory_stack = self.__memory_stack[:index]
        #print('\t\t\tBacktracking, AFTER memory:')
        # if self.__memory_stack != []:
        #print('\t\t\t\t', self.__memory_stack[-1].timestamp)
        # else:
        # print('\t\t\t\tNONE')

    def compute_core_conflict(self) -> List[int]:
        """_summary_

        :return: _description_
        :rtype: List[int]
        """
        last_added: List[int] = []
        for i in range(1, len(self.__memory_stack) + 1):
            if self.__memory_stack[-i].status in [0, -1]:
                last_added.extend(self.__memory_stack[-i].changes)

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
        optimums: Union[List[float], None] = []
        fixed_cid: List[Tuple[LpVariable, int, int]] = []

        if self.__memory_stack[-1].status != 0:
            status: int = self.__memory_stack[-1].status
            assignment: Dict[str, float] = self.__memory_stack[-1].assignment
            optimums: List[Tuple[str, float]
                           ] = self.__memory_stack[-1].optimums
            return (status, assignment, optimums)

        self.__memory_stack[-1].status = 1
        for cid, opt_var in self.__objectives.items():
            cid: int
            opt_var: LpVariable

            obj_cons: LpConstraint = self.__problem.constraints[str(cid)]
            self.__problem.setObjective(opt_var)
            status: LpStatus = self.__problem.solve(self.solver)

            self.__memory_stack[-1].status = status

            if status == 1:
                fixed_cid.append((opt_var, opt_var.lowBound, opt_var.upBound))
                optimum: float = self.__cid2object[cid][2] * opt_var.varValue
                optimums.append((str(obj_cons), optimum))
                self.__memory_stack[-1].optimums.append(
                    (str(obj_cons), optimum))
                opt_var.fixValue()
            elif status == -2:
                optimum: float = self.__cid2object[cid][2] * float('-inf')
                optimums.append((str(obj_cons), optimum))
                self.__memory_stack[-1].optimums.append(
                    (str(obj_cons), optimum))
            else:
                assert(len(self.__memory_stack[-1].optimums) == 0)
                optimums = None
                break

        for opt_var, low, up in fixed_cid:
            opt_var.lowBound = low
            opt_var.upBound = up

        obj_var: List[str] = [var.name for var in self.__objectives.values()]
        for var in self.__problem.variables():
            if str(var) not in obj_var:
                self.__assignment[str(var)] = var.varValue
                self.__memory_stack[-1].assignment.append(
                    (str(var), var.varValue)
                )

        return (self.__memory_stack[-1].status, self.__assignment, optimums)

    def ensure(self) -> bool:
        """_summary_

        :return: _description_
        :rtype: bool
        """
        for cid in self.__memory_stack[-1].asserts[:]:
            expr, op, bound = self.__asserts[cid]
            if op == '=':
                self.__problem.setObjective(expr)
                self.__remove_unused_pulp_variable()
                self.__problem.solve(self.solver)
                if value(expr) == bound:
                    self.__problem.setObjective(-expr)
                    self.__remove_unused_pulp_variable()
                    self.__problem.solve(self.solver)
                    valid_assert: bool = value(expr) == bound
                else:
                    valid_assert: bool = False
            elif op == '<' or op == '<=':
                self.__problem.setObjective(-expr)
                self.__remove_unused_pulp_variable()
                status = self.__problem.solve(self.solver)
                if op == '<':
                    valid_assert: bool = value(expr) < bound
                else:
                    valid_assert: bool = value(expr) <= bound

            elif op == '>' or op == '>=':
                self.__problem.setObjective(expr)
                self.__remove_unused_pulp_variable()
                self.__problem.solve(self.solver)
                if op == '>':
                    valid_assert: bool = value(expr) > bound
                else:
                    valid_assert: bool = value(expr) >= bound

            if valid_assert:
                self.__memory_stack[-1].asserts.remove(cid)

        return len(self.__memory_stack[-1].asserts) == 0

    def __str__(self) -> str:
        """_summary_

        :return: _description_
        :rtype: str
        """
        return str(self.__problem)
