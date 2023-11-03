"""_summary_
"""

#Import#########################################################################

from optlang import (
    interface,
    glpk_interface,
    cplex_interface,
    gurobi_interface
)

from typing import Any, Dict, List, Tuple, Union, Set

from .parser import Constraint

from .problem import ProblemLp

#Class#PuLP#Solver##############################################################

class SolverLp:
    """_summary_
    """

    def __init__(self, lp_solver: str):
        """_summary_
        """

        self.__lp_solver = lp_solver
        

        self.__problems: Dict[str, ProblemLp] = {}

        self.__stats_backup: Dict[str, Dict[str, Dict[str, float]]] = {}
        self.__memory_backup: Dict[str, Tuple[Tuple,int,Tuple]] = {}

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
                self.__stats_backup[pid] = self.__problems[pid].get_statistics()
                self.__memory_backup[pid] = self.__problems[pid].get_cache()
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
                if pid in self.__stats_backup:
                    self.__problems[pid].set_statistics(self.__stats_backup[pid])
                    del self.__stats_backup[pid]
                if pid in self.__memory_backup:
                    self.__problems[pid].set_cache(self.__memory_backup[pid])
                    del self.__memory_backup[pid]
            cids: List[Tuple[int, Constraint]] = changes[pid]
            self.__problems[pid].update(timestamp, cids)

    def check(self, pid: str) -> List[int]:
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
        if pid in self.__problems:
            return self.__problems[pid].solve()
        return (None, [])

    def ensure(self, pid: str, unused_lp: Dict[int, List[Constraint]]) -> Dict[int, List[int]]:
        """_summary_

        :param pid: _description_
        :type pid: str
        :return: _description_
        :rtype: List[int]
        """
        if pid not in self.__problems:
            return {}
        not_valid_asserts_cid: Dict[int, List[int]] = self.__problems[pid].ensure(unused_lp)
        return not_valid_asserts_cid

    def get_statistics(self, pid: str) -> Dict[str, Dict[str, float]]:
        """_summary_

        :param pid: _description_
        :type pid: str
        :return: _description_
        :rtype: Dict[str, Dict[str, float]]
        """
        if pid in self.__problems:
            return self.__problems[pid].get_statistics()
        elif pid in self.__stats_backup:
            return self.__stats_backup[pid]
        return None