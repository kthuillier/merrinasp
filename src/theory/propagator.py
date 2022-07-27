"""_summary_
"""

#Import#########################################################################

from clingo import (
    Assignment,
    PropagateInit,
    PropagateControl,
    TheoryAtom,
    TheoryTerm,
)

from typing import Dict, List, Set, Tuple

from.language import parse_term

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

        self.__sid2cid: Dict[int, List[int]] = {}
        self.__cid2sid: Dict[int, List[int]] = {}

        self.__cid2condid: Dict[int, List[int]] = {}
        self.__condid2cid: Dict[int, List[int]] = {}

        self.__cidcondid2term: Dict[Tuple[int, int],
                                    List[List[TheoryTerm]]] = {}

        self.__sid2guess: Dict[int, bool] = {}
        self.__cid2guess: Dict[int, bool] = {}

        self.__cid_wait: Set[int] = set()
        self.__cid_added: Set[int] = set()
        self.__cid_free: Set[int] = set()

        for atom in init.theory_atoms:
            atom: TheoryAtom
            cid: int = atom.literal
            sid: int = init.solver_literal(cid)
            print('Atom:', atom)
            print('\tTerm:', atom.term)
            print('\tElements:')
            print('\tCID:', cid)
            print('\tSID:', sid)

            self.__cid2sid[cid] = sid
            self.__sid2cid.setdefault(sid, []).append(cid)

            is_all_condid_guess = True
            for element in atom.elements:
                print('\t\tElement:', element)
                print('\t\t\tCondition:', element.condition)
                print('\t\t\tConditionID:', element.condition_id)
                print('\t\t\tConditionSID:', init.solver_literal(element.condition_id))

                condid: int = element.condition_id

                self.__cid2condid.setdefault(cid, []).append(condid)
                self.__condid2cid.setdefault(condid, []).append(cid)

                condid_sid: int = init.solver_literal(condid)
                condid_guess: bool = init.assignment.value(condid_sid)
                if condid_guess is not None:
                    self.__sid2guess[condid_sid] = condid_guess
                else:
                    is_all_condid_guess = False

                self.__cidcondid2term.setdefault(
                    (cid, condid_sid),
                    []
                ).append(
                    [parse_term(term) for term in element.terms]
                )

            sid_guess: bool = init.assignment.value(sid)
            if sid_guess is not None:
                self.__cid2guess[cid] = sid_guess
                self.__sid2guess[sid] = sid_guess
                if sid_guess:
                    if is_all_condid_guess:
                        self.__cid_added.add(cid)
                    else:
                        self.__cid_wait.add(cid)
                else:
                    self.__cid_free.add(cid)

        self.is_complete: bool = len(self.__cid_free) == 0

    def undo(self, changes: List[int]) -> None:
        """_summary_

        :param changes: _description_
        :type changes: List[int]
        """
        print('Internal UNDO')
        for sid in changes:
            sid: int
            del self.__sid2guess[sid]
            if sid in self.__sid2cid:
                cids: List[int] = self.__sid2cid[sid]
                for cid in cids:
                    cid: int
                    del self.__cid2guess[cid]
                    if cid in self.__cid_wait:
                        self.__cid_wait.remove(cid)
                        self.__cid_free.add(cid)
                    elif cid in self.__cid_added:
                        self.__cid_added.remove(cid)
                        self.__cid_free.add(cid)
                    elif cid in self.__cid_free:
                        print('Error: Trying to remove an un-guessed literal.')
                        exit(0)
                    else:
                        self.__cid_free.add(cid)

            if sid in self.__condid2cid:
                cids: List[int] = self.__condid2cid[sid]
                for cid in cids:
                    cid: int
                    if cid in self.__cid_added:
                        self.__cid_added.remove(cid)
                        if cid in self.__cid2guess:
                            cid_guess:bool = self.__cid2guess[cid]
                            if cid_guess:
                                self.__cid_wait.add(cid)

        if self.is_complete:
            self.is_complete = len(self.__cid_free) == 0

    def propagate(self, control: PropagateControl, changes: List[int]) -> bool:
        """_summary_

        :param control: _description_
        :type control: PropagateControl
        :param changes: _description_
        :type changes: List[int]
        :return: _description_
        :rtype: bool
        """
        print('Internal PROPAGATE')
        changed_cids: Set[int] = set()

        for sid in changes:
            sid: int
            sid_guess: bool = control.assignment.value(sid)
            self.__sid2guess[sid] =  sid_guess

            if sid in self.__sid2cid:
                cids: List[int] = self.__cid2sid[sid]
                for cid in cids:
                    cid: int
                    self.__cid2guess[cid] = sid_guess
                    assert(cid in self.__cid_free)
                    self.__cid_free.remove(cid)
                    changed_cids.add(cid)
            
            if sid in self.__condid2cid:
                cids: List[int] = self.__condid2cid[sid]
                for cid in cids:
                    cid: int
                    changed_cids.add(cid)

        for cid in changed_cids:
            cid: int
            assert(cid not in self.__cid_free)
            cid_guess = self.__cid2guess[cid]
            if cid_guess:
                if self.__fully_assigned_theory_atom(cid):
                    self.__cid_added.add(cid)
                else:
                    self.__cid_wait.add(cid)

        return True

    def __fully_assigned_theory_atom(self, cid:int) -> bool:
        """_summary_

        :param cid: _description_
        :type cid: int
        :return: _description_
        :rtype: bool
        """
        all_condid_guess: bool = True
        for condid in self.__cid2condid[cid]:
            condid: int
            if condid not in self.__sid2guess:
                all_condid_guess = False
                break
        return all_condid_guess

    def get_unguess(self) -> Set[int]:
        """_summary_

        :return: _description_
        :rtype: Set[int]
        """
        unguess_condid: Set[int] = set()
        for cid in self.__cid_wait:
            cid: int
            for condid in self.__cid2condid[cid]:
                condid: int
                if condid not in self.__sid2guess:
                    unguess_condid.add(condid)
        unguess: Set[int] = unguess_condid.union(self.__cid_free)
        return unguess

    def check(self) -> bool:
        """_summary_

        :return: _description_
        :rtype: bool
        """
        print('Internal CHECK')
        return True
        solve_results: Tuple[int, Dict[str, float], float] = \
            self.__lp_solver.solve()
        if solve_results[0] == 1:
            self.__lp_assignment = solve_results[1]
            return True
        return False

    def get_assignement(self) -> Dict[str, float]:
        """_summary_

        :return: _description_
        :rtype: Dict[str, float]
        """
        return None
        return self.__lp_assignment

#Class#Propagator###############################################################


class OptPropagator:
    """_summary_
    """

    def __init__(self):
        """_summary_
        """
        self.__checkers: List[OptChecker] = []
        pass

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
        print(f'UNDO n°{assignment.decision_level}:', changes)
        self.__checkers[thread_id].undo(changes)

    def propagate(self, control: PropagateControl, changes: List[int]) -> None:
        """_summary_

        :param control: _description_
        :type control: PropagateControl
        :param changes: _description_
        :type changes: List[int]
        """
        print(f'PROPAGATE n°{control.assignment.decision_level}:', changes)
        optChecker: OptChecker = self.__checkers[control.thread_id]
        optChecker.propagate(control, changes)

    def check(self, control: PropagateControl) -> None:
        """_summary_

        :param control: _description_
        :type control: PropagateControl
        """
        print(f'CHECK n°{control.assignment.decision_level}:')
        optChecker: OptChecker = self.__checkers[control.thread_id]
        changes: Set[int] = optChecker.get_unguess()

        optChecker.propagate(control, changes)
        sat: bool = optChecker.check()
        optChecker.undo(changes)

        if not sat:
            nogood: List[int] = [
                1
            ]
            if not control.add_nogood(nogood):
                return

    def get_assignment(self, thread_id: int) -> Dict[str, float]:
        """_summary_

        :param thread_id: _description_
        :type thread_id: int
        :return: _description_
        :rtype: Dict[str,float]
        """
        optChecker: OptChecker = self.__checkers[thread_id]
        return optChecker.get_assignement()
