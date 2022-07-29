"""_summary_
"""

#Import#########################################################################

from pulp import (
    LpSolver,
    CPLEX_CMD,
    GUROBI_CMD,
    PULP_CBC_CMD,
)

from typing import Any, Dict, Tuple

from .parser import Constraint

from .problem import ProblemLp

#Class#PuLP#Solver##############################################################


class SolverLp:
    """_summary_
    """

    def __init__(self, lp_solver: str):
        """_summary_
        """

        self.__lp_solver: LpSolver = PULP_CBC_CMD
        if lp_solver == 'cbc':
            self.__lp_solver = PULP_CBC_CMD
        elif lp_solver == 'cplex':
            self.__lp_solver = CPLEX_CMD
        elif lp_solver == 'gurobi':
            self.__lp_solver = GUROBI_CMD
        else:
            print(f'LP Solver ("{lp_solver}") does not exist.')
            exit(0)

        self.__problems: Dict[Any, ProblemLp] = {}

    def append(self, pid: Any, cid: int, cons: Constraint) -> None:
        """_summary_

        :param pid: _description_
        :type pid: Any
        :param cid: _description_
        :type cid: int
        :param cons: _description_
        :type cons: List[Tuple[int, str]]
        """
        print('SOLVER -- add_constraint()')
        print('\tProblem:', pid)
        print('\tConstraint:', cid, cons)
        if pid not in self.__problems:
            self.__problems[pid] = ProblemLp(pid, self.__lp_solver)
        self.__problems[pid].append(cid, cons)

    def remove(self, pid: Any, cid: int) -> None:
        """_summary_

        :param pid: _description_
        :type pid: Any
        :param cid: _description_
        :type cid: int
        """
        print('SOLVER -- remove_constraints()')
        print('\tProblem:', pid)
        print('\tConstraint:', cid)
        self.__problems[pid].remove(cid)

    def solve(self, pid: int) -> Tuple[int, Dict[str, float], float]:
        print('SOLVER -- solve()')
        return (1, None, -1)

    def print_problem(self, pid: str) -> str:
        """_summary_

        :param pid: _description_
        :type pid: str
        :return: _description_
        :rtype: str
        """
        s: str = f'Problem "{pid}":\n'
        s += str(self.__problems[pid])
        return s

    def __str__(self) -> str:
        """_summary_

        :return: _description_
        :rtype: str
        """
        s: str = ('-' * 40) + '\n'
        for pid in self.__problems:
            pid: str
            s += self.print_problem(pid)
            s += '\n' + ('-' * 20) + '\n'
        return s
