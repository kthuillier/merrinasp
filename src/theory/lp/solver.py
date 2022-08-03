"""_summary_
"""

#Import#########################################################################

from pulp import (
    LpSolver,
    CPLEX_CMD,
    GUROBI_CMD,
    PULP_CBC_CMD,
)

from typing import Any, Dict, List, Tuple, Union

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

        self.__problems: Dict[str, ProblemLp] = {}

        self.__assignment: Dict[str, Dict[str, Union[float, None]]] = {}

    def backtrack(self, timestamp:int, pids: List[str]) -> None:
        """_summary_

        :param timestamp: _description_
        :type timestamp: int
        :param pids: _description_
        :type pids: List[str]
        """
        for pid in pids:
            self.__problems[pid].backtrack(timestamp)

    def update(self, timestamp:int, changes:Dict[str, List[Tuple[int, Constraint]]]) -> None:
        """_summary_

        :param timestamp: _description_
        :type timestamp: int
        :param changes: _description_
        :type changes: Dict[str, List[Tuple[int, Constraint]]]
        """
        for pid in changes:
            if pid not in self.__problems:
                self.__problems[pid] = ProblemLp(pid, self.__lp_solver)
                self.__assignment[pid] = {}
            cids: List[Tuple[int, Constraint]] = changes[pid]
            self.__problems[pid].update(timestamp, cids)

    def solve(self, pid: str) -> Tuple[int, Dict[str, float], float, List[int]]:
        """_summary_

        :param pid: _description_
        :type pid: str
        :return: _description_
        :rtype: Tuple[int, Dict[str, float], float, List[int]]
        """
        status, assignment, optimum = self.__problems[pid].solve()
        if status == 1 or status == -2:
            self.__assignment[pid] = assignment
            core_conflict: List[int] = None
        else:
            self.__assignment[pid] = {}
            core_conflict: List[int] = \
                self.__problems[pid].compute_core_conflict()
        return (status, assignment, optimum, core_conflict)
    
    def ensure(self, pid: str) -> bool:
        """_summary_

        :param pid: _description_
        :type pid: str
        :return: _description_
        :rtype: bool
        """
        all_asserts_valid: bool = self.__problems[pid].ensure()
        return all_asserts_valid

    def get_assignment(self) -> Dict[str, Dict[str, Union[float, None]]]:
        """_summary_

        :return: _description_
        :rtype: Dict[str, Dict[str, Union[float, None]]]
        """
        return self.__assignment

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
