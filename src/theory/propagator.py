"""_summary_
"""

#Import#########################################################################

from clingo import (
    Assignment,
    PropagateInit,
    PropagateControl,
    TheoryAtom
)

from time import time

from typing import Any, Dict, List, Set, Tuple, Union

from .lp.parser import AffineExpr, CType, Constraint, Term, parse_atom

from .lp.solver import SolverLp

#Class#Checker##################################################################


class OptChecker:
    """_summary_
    """

    def __init__(self, init: PropagateInit, **kwargs):
        """_summary_

        :param mapping: _description_
        :type mapping: Dict[int, TheoryAtom]
        :param states: _description_
        :type states: Dict[int, bool]
        """
        #SOLVER#INITIALISATION##################################################
        lp_solver: str = 'cbc'
        if 'lp_solver' in kwargs:
            lp_solver: str = kwargs[lp_solver]

        self.__lp_solver: SolverLp = SolverLp(lp_solver)

        #MEMORY#INITIALISATION##################################################
        self.__cid_data: Dict[int, Dict[str, Any]] = {}
        self.__sid_data: Dict[int, Dict[str, Any]] = {}
        self.__pid_data: Dict[str, Dict[str, Any]] = {}
        self.__condid_data: Dict[int, Dict[str, Any]] = {}

        self.__cid_free: Set[int] = set()
        self.__cid_wait: Set[int] = set()
        self.__cid_added: Set[int] = set()

        #INITIALISE#OPTIMISATION#PROBLEM#STRUCTURE##############################
        changes: Set[int] = set()
        for atom in init.theory_atoms:
            atom: TheoryAtom

            cid, pid, data, condids = self.__extract_atom(atom)

            sid: int = init.solver_literal(cid)
            sid_guess: bool = init.assignment.value(sid)

            self.__cid_data[cid] = {
                'sid': sid,
                'pid': pid,
                'data': data,
                'guess': sid_guess,
                'condid': set(),
                'term': {},
                'complete': False,
            }

            self.__sid_data.setdefault(sid, {
                'cid': set(),
                'condid': set(),
                'guess': None
            })['cid'].add(cid)

            self.__pid_data.setdefault(pid, {
                'cid': set(),
                'complete': False
            })['cid'].add(cid)

            self.__cid_free.add(cid)
            if sid_guess is not None:
                changes.add(sid)

            for condid, term in condids.items():
                condid: int
                term: Tuple[float, Union[str, None]]

                scondid: int = init.solver_literal(condid)
                scondid_guess: bool = init.assignment.value(scondid)

                if scondid_guess is not None:
                    changes.add(scondid)

                self.__cid_data[cid]['condid'].add(condid)
                self.__cid_data[cid]['term'].setdefault(
                    condid, []).extend(term)

                self.__condid_data.setdefault(condid, {
                    'cid': set(),
                    'sid': scondid,
                    'guess': None
                })['cid'].add(cid)

                self.__sid_data.setdefault(scondid, {
                    'cid': set(),
                    'condid': set(),
                    'guess': None
                })['condid'].add(condid)

        #INITIALISE#WATCHED#VARIABLES###########################################
        for sid in self.__sid_data:
            init.add_watch(sid)

    def __extract_atom(self, atom: TheoryAtom) -> Tuple[int, str, Tuple, Dict]:
        """_summary_

        :param atom: _description_
        :type atom: TheoryAtom
        :return: _description_
        :rtype: Tuple[int, str, Tuple, Dict]
        """
        cid: int = atom.literal
        pid, constraint = parse_atom(atom)
        if constraint[0] == 'dom':
            variable: str = constraint[1]
            lower_bound: float = constraint[2]
            upper_bound: float = constraint[3]
            data: Tuple = ('dom', variable, (lower_bound, upper_bound))
            condids: Dict = {}
        elif constraint[0] == 'objective':
            condids: Dict = constraint[1]
            direction: int = constraint[2]
            weight: int = constraint[3]
            data: Tuple = ('objective', direction, weight)
        elif constraint[0] == 'constraint':
            condids = constraint[1]
            op: Union[str['<='], str['>='], str['=']] = constraint[2]
            bound: float = constraint[3]
            data: Tuple = ('constraint', op, bound)
        elif constraint[0] == 'assert':
            condids = constraint[1]
            op = constraint[2]
            bound = constraint[3]
            data: Tuple = ('assert', op, bound)
        return (cid, pid, data, condids)

    def __add_lpconstraints(self, timestamp: int, cids: Set[int]) -> None:
        """_summary_

        :param timestamp: _description_
        :type timestamp: int
        :param cids: _description_
        :type cids: Set[int]
        """
        changes: Dict[str, List[Tuple[int, Constraint]]] = {}
        for cid in cids:
            self.__cid_added.add(cid)
            pid: str = self.__cid_data[cid]['pid']
            ctype: CType = self.__cid_data[cid]['data'][0]
            if ctype in ['assert', 'constraint', 'objective']:
                expr: AffineExpr = []
                for condid, terms in self.__cid_data[cid]['term'].items():
                    condid: int
                    terms: List[Term]
                    guess_condid: bool = self.__condid_data[condid]['guess']
                    if (guess_condid is not None) and (guess_condid):
                        expr.extend(terms)
                if len(expr) == 0:
                    self.__cid_added.remove(cid)
                    continue
                cons: Constraint = (
                    ctype,
                    expr,
                    self.__cid_data[cid]['data'][1],
                    self.__cid_data[cid]['data'][2]
                )
            elif ctype == 'dom':
                var_name = self.__cid_data[cid]['data'][1]
                lower_bound, upper_bound = self.__cid_data[cid]['data'][2]
                cons: Constraint = ('dom', var_name, lower_bound, upper_bound)
            else:
                print('Error: unknown contraint type:', ctype)
                exit(0)

            changes.setdefault(pid, []).append((cid, cons))

        self.__lp_solver.update(timestamp, changes)

    def __remove_lpconstraints(self, timestamp: int, pids: List[str]) -> None:
        """_summary_

        :param timestamp: _description_
        :type timestamp: int
        """
        self.__lp_solver.backtrack(timestamp, pids)

    def undo(self, timestamp: int, changes: List[int]) -> None:
        """_summary_

        :param timestamp: _description_
        :type timestamp: int
        :param changes: _description_
        :type changes: List[int]
        """
        backtracked_pids: Set[str] = set()
        uncomplete_cid_changes: Set[int] = set()
        uncomplete_pid_changes: Set[str] = set()
        for sid in changes:
            sid: int
            self.__sid_data[sid]['guess'] = None
            for condid in self.__sid_data[sid]['condid']:
                condid: int
                self.__condid_data[condid]['guess'] = None
                uncomplete_cid_changes.update(
                    self.__condid_data[condid]['cid'])
            for cid in self.__sid_data[sid]['cid']:
                cid: int
                self.__cid_data[cid]['guess'] = None
                uncomplete_pid_changes.add(self.__cid_data[cid]['pid'])
                if cid in self.__cid_wait:
                    self.__cid_wait.remove(cid)
                elif cid in self.__cid_added:
                    self.__cid_added.remove(cid)
                    # TODO: update solver constraints set
                    pid: str = self.__cid_data[cid]['pid']
                    backtracked_pids.add(pid)
                self.__cid_free.add(cid)

        for u_cid in uncomplete_cid_changes:
            u_cid: str
            if len(self.__cid_data[u_cid]) != 0:
                self.__cid_data[u_cid]['complete'] = False
            uncomplete_pid_changes.add(self.__cid_data[u_cid]['pid'])
            if u_cid in self.__cid_added:
                self.__cid_added.remove(u_cid)
                # TODO: update solver constraints set
                pid: str = self.__cid_data[u_cid]['pid']
                backtracked_pids.add(pid)
            if u_cid not in self.__cid_free:
                self.__cid_wait.add(u_cid)

        self.__remove_lpconstraints(timestamp, backtracked_pids)

        for u_pid in uncomplete_pid_changes:
            self.__pid_data[u_pid]['complete'] = False

    def propagate(self, timestamp: int, control: PropagateControl, changes: List[int]) -> None:
        """_summary_

        :param timestamp: _description_
        :type timestamp: int
        :param control: _description_
        :type control: PropagateControl
        :param changes: _description_
        :type changes: List[int]
        """
        check_cid_complete: Set[int] = set()
        for sid in changes:
            sid: int
            sid_guess: bool = control.assignment.value(sid)
            if sid_guess is None:
                continue
            self.__sid_data[sid]['guess'] = sid_guess
            for condid in self.__sid_data[sid]['condid']:
                condid: int
                self.__condid_data[condid]['guess'] = sid_guess
                check_cid_complete.update(self.__condid_data[condid]['cid'])
            for cid in self.__sid_data[sid]['cid']:
                cid: int
                self.__cid_data[cid]['guess'] = sid_guess
                self.__cid_free.remove(cid)
                if sid_guess:
                    self.__cid_wait.add(cid)
                check_cid_complete.add(cid)

        lpconstraint_to_add: Set[int] = set()
        check_pid_complete: Set[str] = set()
        for cid in check_cid_complete:
            cid: int
            is_guess: bool = self.__cid_data[cid]['guess']
            is_complete: bool = self.__cid_data[cid]['complete']
            if not is_complete:
                is_complete = True
                for condid in self.__cid_data[cid]['condid']:
                    condid: int
                    if self.__condid_data[condid]['guess'] is None:
                        is_complete = False
                        break
                self.__cid_data[cid]['complete'] = is_complete
            if is_complete:
                check_pid_complete.add(self.__cid_data[cid]['pid'])

            if is_guess is None:
                continue
            elif is_complete and is_guess:
                self.__cid_wait.remove(cid)
                # TODO: update solver constraints set
                lpconstraint_to_add.add(cid)
            elif not is_complete and is_guess:
                assert(cid in self.__cid_wait)

        for pid in check_pid_complete:
            pid: str
            is_complete: bool = True
            for cid in self.__pid_data[pid]['cid']:
                cid: int
                is_guess: bool = self.__cid_data[cid]['guess']
                is_complete: bool = self.__cid_data[cid]['complete']
                if (is_guess is not None) and (is_complete):
                    self.__pid_data[pid]['complete'] = True

        self.__add_lpconstraints(timestamp, lpconstraint_to_add)

    def get_unguess(self) -> Set[int]:
        """_summary_

        :return: _description_
        :rtype: Set[int]
        """
        unguess_sid: Set[int] = set()
        for sid in self.__sid_data:
            if self.__sid_data[sid]['guess'] is None:
                unguess_sid.add(sid)
        return unguess_sid

    def __generate_core_nogoods(self, cids: List[int]) -> List[int]:
        """_summary_

        :param cids: _description_
        :type cids: List[int]
        :return: _description_
        :rtype: List[int]
        """
        nogood: Set[int] = set()
        for cid in cids:
            cid: int
            sid: int = self.__cid_data[cid]['sid']
            nogood.add(sid)
            for condid in self.__cid_data[cid]['condid']:
                scondid: int = self.__condid_data[condid]['sid']
                if self.__condid_data[condid]['guess']:
                    nogood.add(scondid)
                else:
                    nogood.add(-scondid)
                # nogood.add(scondid)
        return list(nogood)

    def __generate_assert_nogoods(self, pid: int) -> List[int]:
        """_summary_

        :param pid: _description_
        :type pid: int
        :return: _description_
        :rtype: List[int]
        """
        nogood: Set[int] = set()
        for cid in self.__pid_data[pid]['cid']:
            cid: int
            sid: int = self.__cid_data[cid]['sid']
            guess: bool = self.__cid_data[cid]['guess']
            if guess is None or not guess:
                nogood.add(-sid)
            else:
                nogood.add(sid)
                for condid in self.__cid_data[cid]['condid']:
                    condid_guess: bool = self.__condid_data[condid]['guess']
                    if condid_guess is None or not condid_guess:
                        scondid: int = self.__condid_data[condid]['sid']
                        nogood.add(-scondid)
        return list(nogood)

    def check(self) -> List[List[int]]:
        """_summary_

        :return: _description_
        :rtype: bool
        """
        nogoods: List[List[int]] = []
        for pid in self.__pid_data:
            if not self.__pid_data[pid]['complete']:
                continue
            assert(self.__pid_data[pid]['complete'])
            core_conflict: Union[None, List[int]] = self.__lp_solver.check(pid)
            if core_conflict is None:
                all_assert_valid: bool = self.__lp_solver.ensure(pid)
                if not all_assert_valid:
                    nogood: int = self.__generate_assert_nogoods(pid)
                    nogoods.append(nogood)
            else:
                nogood: List[int] = self.__generate_core_nogoods(core_conflict)
                nogoods.append(nogood)
        return nogoods

    def get_assignement(self) -> Dict[str, Tuple[List[Tuple[str, float]], List[float]]]:
        """_summary_

        :return: _description_
        :rtype: Dict[str, Tuple[List[Tuple[str, float]], List[float]]]
        """
        assignment: Dict[str, Tuple[List[Tuple[str, float]], List[float]]] = {}
        for pid in self.__pid_data:
            pid_assignment, optimums = self.__lp_solver.solve(pid)
            if pid_assignment is not None:
                assignment[pid] = (pid_assignment, optimums)
        return assignment
    
    def get_statistics(self) -> Dict[str, Dict[str, float]]:
        """_summary_

        :return: _description_
        :rtype: Dict[str, Dict[str, float]]
        """
        statistics: Dict[str, Dict[str, float]] = {}
        for pid in self.__pid_data:
            pid_statistics = self.__lp_solver.get_statistics(pid)
            statistics[pid] = pid_statistics
        return statistics
        

#Class#Propagator###############################################################


class OptPropagator:
    """_summary_
    """

    def __init__(self):
        """_summary_
        """
        self.__checkers: List[OptChecker] = []
        self.__waiting_nogoods: List[List[int]] = []

    def init(self, init: PropagateInit) -> None:
        """_summary_

        :param init: _description_
        :type init: PropagateInit
        """
        for _ in range(init.number_of_threads):
            optChecker: OptChecker = OptChecker(
                init
            )
            self.__checkers.append(optChecker)

    def undo(self, thread_id: int, assignment: Assignment, changes: List[int]) -> None:
        """_summary_

        :param thread_id: _description_
        :type thread_id: int
        :param assignment: _description_
        :type assignment: Assignment
        :param changes: _description_
        :type changes: List[int]
        """
        # print(f'UNDO n°{assignment.decision_level}:', changes)
        timestamp: int = assignment.decision_level
        self.__checkers[thread_id].undo(timestamp, changes)

    def propagate(self, control: PropagateControl, changes: List[int]) -> None:
        """_summary_

        :param control: _description_
        :type control: PropagateControl
        :param changes: _description_
        :type changes: List[int]
        """
        # print(f'PROPAGATE n°{control.assignment.decision_level}:', changes)
        while len(self.__waiting_nogoods) != 0:
            nogood: List[int] = self.__waiting_nogoods.pop()
            if not control.add_nogood(nogood, lock=True):
                return
        timestamp: int = control.assignment.decision_level
        optChecker: OptChecker = self.__checkers[control.thread_id]
        optChecker.propagate(timestamp, control, changes)
        # nogoods: Union[List[List], None] = optChecker.check()
        # if nogoods is not None:
        #     self.__waiting_nogoods.extend(nogoods)
        # while len(self.__waiting_nogoods) != 0:
        #     nogood: List[int] = self.__waiting_nogoods.pop()
        #     if not control.add_nogood(nogood):
        #         return


    def check(self, control: PropagateControl) -> None:
        """_summary_

        :param control: _description_
        :type control: PropagateControl
        """
        # print(f'CHECK n°{control.assignment.decision_level}:')
        timestamp: int = -control.assignment.decision_level
        optChecker: OptChecker = self.__checkers[control.thread_id]
        changes: Set[int] = optChecker.get_unguess()
        optChecker.propagate(timestamp, control, changes)
        nogoods: Union[List[List], None] = optChecker.check()
        optChecker.undo(timestamp, changes)
        if nogoods is not None:
            self.__waiting_nogoods.extend(nogoods)
        while len(self.__waiting_nogoods) != 0:
            nogood: List[int] = self.__waiting_nogoods.pop()
            if not control.add_nogood(nogood, lock=True):
                return

    def get_assignment(self, thread_id: int) -> Dict[str, Tuple[List[Tuple[str, float]], List[float]]]:
        """_summary_

        :param thread_id: _description_
        :type thread_id: int
        :return: _description_
        :rtype: Dict[str, Tuple[List[Tuple[str, float]], List[float]]]
        """
        optChecker: OptChecker = self.__checkers[thread_id]
        return optChecker.get_assignement()

    def get_statistics(self, thread_id: int) -> Dict[str, Dict[str, float]]:
        """_summary_

        :param thread_id: _description_
        :type thread_id: int
        :return: _description_
        :rtype: Dict[str, Dict[str, float]]
        """
        optChecker: OptChecker = self.__checkers[thread_id]
        return optChecker.get_statistics()