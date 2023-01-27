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

    def backtrack(self, timestamp: int, pids: List[str]) -> None:
        """_summary_

        :param timestamp: _description_
        :type timestamp: int
        :param pids: _description_
        :type pids: List[str]
        """
        for pid in pids:
            not_empty_problem: bool = self.__problems[pid].backtrack(timestamp)
            if not not_empty_problem:
                del self.__problems[pid]

    def update(self, timestamp: int, changes: Dict[str, List[Tuple[int, Constraint]]]) -> None:
        """_summary_

        :param timestamp: _description_
        :type timestamp: int
        :param changes: _description_
        :type changes: Dict[str, List[Tuple[int, Constraint]]]
        """
        for pid in changes:
            if pid not in self.__problems:
                self.__problems[pid] = ProblemLp(pid, self.__lp_solver)
            cids: List[Tuple[int, Constraint]] = changes[pid]
            self.__problems[pid].update(timestamp, cids)

    def check(self, pid: List[str]) -> List[int]:
        """_summary_

        :param pid: _description_
        :type pid: List[str]
        :return: _description_
        :rtype: List[int]
        """
        if pid not in self.__problems:
            return None
        return self.__problems[pid].check()

    def solve(self, pid: str) -> Tuple[Dict[str, float], List[float]]:
        """_summary_

        :param pid: _description_
        :type pid: str
        :return: _description_
        :rtype: Tuple[Dict[str, float], List[float]]
        """
        return self.__problems[pid].solve()

    def ensure(self, pid: str) -> bool:
        """_summary_

        :param pid: _description_
        :type pid: str
        :return: _description_
        :rtype: bool
        """
        if pid not in self.__problems:
            return True
        all_asserts_valid: bool = self.__problems[pid].ensure()
        return all_asserts_valid

    def get_statistics(self, pid: str) -> Dict[str, float]:
        """_summary_

        :param pid: _description_
        :type pid: str
        :return: _description_
        :rtype: Dict[str, float]
        """
        return self.__problems[pid].get_statistics()