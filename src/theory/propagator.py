"""_summary_
"""

#Import#########################################################################

from clingo import (
    Assignment,
    PropagateInit,
    PropagateControl,
    TheoryAtom,
    SymbolicAtom,
    Symbol
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
            lp_solver: str = kwargs['lp_solver']

        self.__lp_solver: SolverLp = SolverLp(lp_solver)

        #CONSTRAINT#INITIALISATION##############################################
        self.__lp_constraints: Dict[int, Dict[int, Dict[Tuple[int,], Constraint]]] = {}
        
        #MEMORY#INITIALISATION##################################################
        self.__cid_data: Dict[int, Dict[str, Any]] = {}
        self.__sid_data: Dict[int, Dict[str, Any]] = {}
        self.__pid_data: Dict[str, Dict[str, Any]] = {}
        self.__condid_data: Dict[int, Dict[str, Any]] = {}

        #INITIALISE#OPTIMISATION#PROBLEM#STRUCTURE##############################
        changes: Set[int] = set()
        for atom in init.theory_atoms:
            atom: TheoryAtom

            cid, pid, data, condids = self.__extract_atom(atom)

            sid: int = init.solver_literal(cid)
            sid_guess: bool = init.assignment.value(sid)

            self.__cid_data[cid] = {
                'atom': str(atom),
                'sid': sid,
                'pid': pid,
                'data': data,
                'guess': None,
                'condid': set(),
                'term': {},
                'complete': False,
                'constraints': [],
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

            self.__cid_data[cid]['constraints'] = self.__extract_lpconstraints(cid)

        #LAZY#MODE#INITIALISATION###############################################
        lazy_mode: bool = False
        if 'lazy_mode' in kwargs:
            lazy_mode: bool = kwargs['lazy_mode']
            
        #INITIALISE#WATCHED#VARIABLES###########################################
        for sid in self.__sid_data:
            if not lazy_mode:
                init.add_watch(sid)
            else:
                init.remove_watch(sid)
        #TEST###################################################################
        for pid in self.__pid_data:
            assert(self.__pid_data[pid]['complete'] is None or not self.__pid_data[pid]['complete'])
        

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

    def __rec_extract_lpconstraints(self, cid: int, condids: List[int]) -> List[Tuple[List[int], List[Term]]]:
        if len(condids) == 0:
            return [([], [])]
        condid: int = condids[0]
        terms: List[Term] = self.__cid_data[cid]['term'][condid]
        extracted_lpconstraints = self.__rec_extract_lpconstraints(cid, condids[1:])
        extracted_lpconstraints_ = []
        for ext_condids, ext_terms in extracted_lpconstraints:
            # case: true
            extracted_lpconstraints_+= [
                ([condid] + ext_condids, terms + ext_terms)
            ]
            # case: false
            if self.__condid_data[condid]['sid'] > 1:
                extracted_lpconstraints_+= [
                    ([f'-{condid}'] + ext_condids, ext_terms)
                ]
        return extracted_lpconstraints_

    def __extract_lpconstraints(self, cid: int) -> List[Tuple[List[int], Union[Constraint, None]]]:
        """_summary_

        :param timestamp: _description_
        :type timestamp: int
        :param cids: _description_
        :type cids: Set[int]
        """
        pid: str = self.__cid_data[cid]['pid']
        ctype: CType = self.__cid_data[cid]['data'][0]
        if ctype in ['assert', 'constraint', 'objective']:
            extract_lpconstraints = self.__rec_extract_lpconstraints(
                cid, list(self.__cid_data[cid]['term'].keys())
            )
            output: List[Tuple[List[int], Union[Constraint, None]]] = []
            for ext_condids, ext_terms in extract_lpconstraints:
                cons: Constraint = (
                    ctype,
                    ext_terms,
                    self.__cid_data[cid]['data'][1],
                    self.__cid_data[cid]['data'][2]
                ) #type: ignore
                output.append((ext_condids, cons))
            return output
        elif ctype == 'dom':
            var_name = self.__cid_data[cid]['data'][1]
            lower_bound, upper_bound = self.__cid_data[cid]['data'][2]
            cons: Constraint = ('dom', var_name, lower_bound, upper_bound)
            return [([], cons)]
        else:
            print('Error: unknown contraint type:', ctype)
            exit(0)

    def __add_lpconstraints(self, timestamp: int, cids: Set[int]) -> None:
        """_summary_

        :param timestamp: _description_
        :type timestamp: int
        :param cids: _description_
        :type cids: Set[int]
        """
        changes: Dict[str, List[Tuple[int, Constraint]]] = {}
        for cid in cids:
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
                    continue
                cons: Constraint = (
                    ctype,
                    expr,
                    self.__cid_data[cid]['data'][1],
                    self.__cid_data[cid]['data'][2]
                ) #type: ignore
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
        # ======================================================================
        # Update SID state
        # ======================================================================
        lpconstraints_to_remove: Set[str] = set()
        pid_to_decomplete: Set[str] = set()
        for sid in changes:
            sid: int
            self.__sid_data[sid]['guess'] = None
            for condid in self.__sid_data[sid]['condid']:
                condid: int
                assert(self.__condid_data[condid]['guess'] is not None)
                self.__condid_data[condid]['guess'] = None
                for cid in self.__condid_data[condid]['cid']:
                    cid: int
                    self.__cid_data[cid]['complete'] = False
                    pid: str = self.__cid_data[cid]['pid']
                    pid_to_decomplete.add(pid)
                    cid_guess: Union[bool, None] = self.__cid_data[cid]['guess']
                    if cid_guess:
                        lpconstraints_to_remove.add(pid)
            for cid in self.__sid_data[sid]['cid']:
                cid: int
                cid_guess: Union[bool, None] = self.__cid_data[cid]['guess']
                if cid_guess is None:
                    continue
                self.__cid_data[cid]['guess'] = None
                pid: str = self.__cid_data[cid]['pid']
                pid_to_decomplete.add(pid)
                if cid_guess and self.__cid_data[cid]['complete']:
                    lpconstraints_to_remove.add(pid)
        if len(lpconstraints_to_remove) != 0:
            self.__remove_lpconstraints(timestamp, lpconstraints_to_remove)
        # ======================================================================
        # Update PID complete state
        # ======================================================================
        for pid in pid_to_decomplete:
            pid: str
            self.__pid_data[pid]['complete'] = False

    def propagate(self, timestamp: int, control: PropagateControl, changes: List[int]) -> None:
        """_summary_

        :param timestamp: _description_
        :type timestamp: int
        :param control: _description_
        :type control: PropagateControl
        :param changes: _description_
        :type changes: List[int]
        """
        # print('\tChanges:')
        # for sid in sorted(changes):
        #     if sid <= 1:
        #         continue
        #     sid_guess: bool = control.assignment.value(sid)
        #     for cid in sorted(self.__sid_data[sid]['cid']):
        #         print('\t\t', self.__cid_data[cid]['atom'], sid_guess)
        # ======================================================================
        # Update SID states
        # ======================================================================
        cid_to_check_complete: Set[int] = set()
        for sid in changes:
            sid: int
            sid_guess: bool = control.assignment.value(sid)
            if sid_guess is None:
                continue
            assert(self.__sid_data[sid]['guess'] is None)
            self.__sid_data[sid]['guess'] = sid_guess
            for condid in self.__sid_data[sid]['condid']:
                condid: int
                assert(self.__condid_data[condid]['guess'] is None)
                self.__condid_data[condid]['guess'] = sid_guess
                cid_to_check_complete.update(self.__condid_data[condid]['cid'])
            for cid in self.__sid_data[sid]['cid']:
                cid: int
                assert(self.__cid_data[cid]['guess'] is None or self.__cid_data[cid]['guess'] == sid_guess)
                self.__cid_data[cid]['guess'] = sid_guess
                cid_to_check_complete.add(cid)
        # ======================================================================
        # Update CID complete state
        # ======================================================================
        pid_to_check_complete: Set[int] = set()
        lpconstraints_to_add: Set[int] = set()
        for cid in cid_to_check_complete:
            cid: int
            cid_complete: bool = True
            for condid in self.__cid_data[cid]['condid']:
                condid_guess: Union[None, bool] = self.__condid_data[condid]['guess']
                cid_complete = cid_complete and (condid_guess is not None)
            assert(cid_complete or not self.__cid_data[cid]['complete'])
            self.__cid_data[cid]['complete'] = cid_complete
            if cid_complete:
                pid: str = self.__cid_data[cid]['pid']
                pid_to_check_complete.add(pid)
                cid_guess: Union[None, bool] = self.__cid_data[cid]['guess']
                if cid_guess is not None and cid_guess:
                    lpconstraints_to_add.add(cid)
        if len(lpconstraints_to_add) != 0:
            self.__add_lpconstraints(timestamp, lpconstraints_to_add)
        # ======================================================================
        # Update PID complete state
        # ======================================================================
        complete_pid: Set[str] = set()
        for pid in pid_to_check_complete:
            pid: str
            pid_complete: bool = True
            for cid in self.__pid_data[pid]['cid']:
                cid_guess: Union[None, bool] = self.__cid_data[cid]['guess']
                cid_complete: bool = self.__cid_data[cid]['complete']
                pid_complete = pid_complete and (cid_guess is not None) and cid_complete
            assert(pid_complete or not self.__pid_data[pid]['complete'])
            self.__pid_data[pid]['complete'] = pid_complete
            if pid_complete:
                complete_pid.add(pid)
                
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

    def __generate_assert_nogoods(self, pid: int, cid_asserts: Dict[int, List[int]]) -> List[List[int]]:
        """_summary_

        :param pid: _description_
        :type pid: int
        :return: _description_
        :rtype: List[int]
        """
        # nogood: Set[int] = set()
        # for cid in self.__pid_data[pid]['cid']:
        #     cid: int
        #     sid: int = self.__cid_data[cid]['sid']
        #     guess: bool = self.__cid_data[cid]['guess']
        #     if guess is None or not guess:
        #         nogood.add(-sid)
        # for cid in cid_asserts:
        #     sid: int = self.__cid_data[cid]['sid']
        #     nogood.add(sid)
        #     for condid in self.__cid_data[cid]['condid']:
        #         condid_guess: bool = self.__condid_data[condid]['guess']
        #         scondid: int = self.__condid_data[condid]['sid']
        #         if condid_guess is None or not condid_guess:
        #             nogood.add(-scondid)
        #         else:
        #             nogood.add(scondid)
        nogoods: List[List[int]] = []
        for cid_assert in cid_asserts:
            nogood: List[int] = []
            sid: int = self.__cid_data[cid_assert]['sid']
            nogood.append(sid)
            for condid in self.__cid_data[cid_assert]['condid']:
                condid_guess: bool = self.__condid_data[condid]['guess']
                scondid: int = self.__condid_data[condid]['sid']
                if condid_guess is None or not condid_guess:
                    nogood.append(-scondid)
                else:
                    nogood.append(scondid)
            for cid_a in cid_asserts[cid_assert]:
                sid_a: int = self.__cid_data[cid_a]['sid']
                nogood.append(-sid_a)
            nogoods.append(nogood)
        return nogoods

    def __get_unused_lpconstraints(self, pid: str) -> Dict[int, List[Constraint]]:
        output: Dict[int, List[Constraint]] = {}
        for cid in self.__pid_data[pid]['cid']:
            cid_guess: bool = self.__cid_data[cid]['guess']
            if cid_guess is not None and cid_guess:
                continue
            cid_constraints: List[Constraint] = [
                constraints
                for _, constraints in self.__cid_data[cid]['constraints']
            ]
            output[cid] = cid_constraints
        return output

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
                unused_lpconstraints: Dict[int, List[Constraint]] = self.__get_unused_lpconstraints(pid)
                not_valid_asserts_cid: Dict[int, List[int]] = self.__lp_solver.ensure(pid, unused_lpconstraints)
                if len(not_valid_asserts_cid) != 0:
                    nogood: List[List[int]] = self.__generate_assert_nogoods(pid, not_valid_asserts_cid)
                    nogoods.extend(nogood)
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
    
    def get_statistics(self) -> Dict[str, Dict[str, Dict[str, float]]]:
        """_summary_

        :return: _description_
        :rtype: Dict[str, Dict[str, Dict[str, float]]]
        """
        statistics: Dict[str, Dict[str, Dict[str, float]]] = {}
        for pid in self.__pid_data:
            pid_statistics = self.__lp_solver.get_statistics(pid)
            if pid_statistics is not None:
                statistics[pid] = pid_statistics
        return statistics
        

#Class#Propagator###############################################################


class OptPropagator:
    """_summary_
    """

    def __init__(self):
        """_summary_
        """
        #CHECKERS#SETTINGS######################################################
        self.__is_lazy: bool = False
        self.__lp_solver:str = 'cbc'
        self.__checkers: List[OptChecker] = []
        self.__waiting_nogoods: List[List[int]] = []
        #DATABASE###############################################################
        self.__atom_db: Dict[Symbol, Tuple[int, int]] = {}

    def init(self, init: PropagateInit) -> None:
        """_summary_

        :param init: _description_
        :type init: PropagateInit
        """
        #INITIALISE#DB##########################################################
        for satom in init.symbolic_atoms:
            satom: SymbolicAtom
            cid: int = satom.literal
            sid: int = init.solver_literal(cid)
            self.__atom_db[satom.symbol] = (cid, sid)
        #INITIALISE#CHECKERS####################################################
        for _ in range(init.number_of_threads):
            optChecker: OptChecker = OptChecker(
                init,
                lazy_mode=self.__is_lazy,
                lp_solver=self.__lp_solver
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
        # Add all waiting nogoods
        while len(self.__waiting_nogoods) != 0:
            nogood: List[int] = self.__waiting_nogoods.pop()
            if not control.add_nogood(nogood, lock=True):
                return
        # Propagate phases
        timestamp: int = control.assignment.decision_level
        optChecker: OptChecker = self.__checkers[control.thread_id]
        optChecker.propagate(timestamp, control, changes)
        # Check if all fully assigned problems
        nogoods: Union[List[List], None] = optChecker.check()
        # Add newly add nogoods
        if nogoods is not None:
            self.__waiting_nogoods.extend(nogoods)
        while len(self.__waiting_nogoods) != 0:
            nogood: List[int] = self.__waiting_nogoods.pop()
            if not control.add_nogood(nogood, lock=True):
                return


    def check(self, control: PropagateControl) -> None:
        """_summary_

        :param control: _description_
        :type control: PropagateControl
        """
        # print(f'CHECK n°{control.assignment.decision_level}:')
        # Add all waiting nogoods
        while len(self.__waiting_nogoods) != 0:
            nogood: List[int] = self.__waiting_nogoods.pop()
            if not control.add_nogood(nogood, lock=True):
                return
        # Check phases
        timestamp: int = -control.assignment.decision_level
        optChecker: OptChecker = self.__checkers[control.thread_id]
        changes: Set[int] = optChecker.get_unguess()
        optChecker.propagate(timestamp, control, changes)
        nogoods: Union[List[List], None] = optChecker.check()
        optChecker.undo(timestamp, changes)
        # Add newly add nogoods
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

    def get_statistics(self, thread_id: int=-1) -> Dict[str, Dict[str, float]]:
        """_summary_

        :param thread_id: _description_
        :type thread_id: int
        :return: _description_
        :rtype: Dict[str, Dict[str, float]]
        """
        statistics: Dict[str,Dict[str,float]] = {
            'Sub-problems': {},
            'NoGoods': {'Assert': 0, 'Core Conflict': 0},
            'LP Solver': {'Calls': 0, 'Time (s)': 0, 'Prevent calls': 0, 'Prevent cost (s)': 0}
        }
        to_consider_checkers: List[OptChecker] = self.__checkers
        if thread_id != -1:
            to_consider_checkers = [self.__checkers[thread_id]]
        for optChecker in to_consider_checkers:                
            t_statistics: Dict[str,Union[Dict[str,float], float]] = optChecker.get_statistics()
            for pid in optChecker.get_statistics():
                pid_category: str = pid.rsplit('(')[0]
                if pid_category not in statistics['Sub-problems']:
                    statistics['Sub-problems'][pid_category] = 0
                statistics['Sub-problems'][pid_category] += 1
                statistics['NoGoods']['Assert'] += t_statistics[pid]['NoGoods']['Assert']
                statistics['NoGoods']['Core Conflict'] += t_statistics[pid]['NoGoods']['Core Conflict']
                statistics['LP Solver']['Calls'] += t_statistics[pid]['LP Solver']['Calls']
                statistics['LP Solver']['Time (s)'] += t_statistics[pid]['LP Solver']['Time (s)']
                statistics['LP Solver']['Prevent calls'] += t_statistics[pid]['LP Solver']['Prevent calls']
                statistics['LP Solver']['Prevent cost (s)'] += t_statistics[pid]['LP Solver']['Prevent cost (s)']
        return statistics
    
    def set_lazy_mode(self, is_lazy:bool) -> None:
        self.__is_lazy = is_lazy
    
    def add_nogood(self, satoms: List[Tuple[Symbol, bool]]) -> None:
        nogood: List[int] = [
            self.__atom_db[satom][1] * (1 if value else -1)
            for satom, value in satoms
        ]
        self.__waiting_nogoods.append(nogood)
        
    def add_clause(self, satoms: List[Tuple[Symbol, bool]]) -> None:
        clause: List[int] = [
            self.__atom_db[satom][1] * (-1 if value else 1)
            for satom, value in satoms
        ]
        self.__waiting_nogoods.append(clause)