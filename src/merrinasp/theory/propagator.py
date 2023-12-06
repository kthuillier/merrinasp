# -*- coding=utf-8 -*-

# ==============================================================================
# IMPORT
# ==============================================================================

from __future__ import annotations
from typing import Literal
from time import time

from clingo import (
    Assignment,
    PropagateInit,
    PropagateControl,
)

from merrinasp.theory.lra.logger import Logger
from merrinasp.theory.lra.solver import LpSolver

# ==============================================================================
# Propagator
# ==============================================================================


class LpPropagator:

    def __init__(self: LpPropagator, lpsolver: str = 'cbc') -> None:
        # ----------------------------------------------------------------------
        # Parameters
        # ----------------------------------------------------------------------
        self.__islazy: bool = False
        self.__isstrictforall: bool = False
        self.__show_lpassignment: bool = False
        self.__lpsolver: str = lpsolver
        # ----------------------------------------------------------------------
        # Checkers
        # ----------------------------------------------------------------------
        self.__checkers: list[LpChecker] = []
        # ----------------------------------------------------------------------
        # Constraints to add
        # ----------------------------------------------------------------------
        self.__waiting_nogoods: list[list[int]] = []

    # --------------------------------------------------------------------------
    # Clingo's propagator override functions
    # --------------------------------------------------------------------------
    def init(self: LpPropagator, init: PropagateInit) -> None:
        for _ in range(init.number_of_threads):
            optChecker: LpChecker = LpChecker(
                init,
                lazy=self.__islazy,
                lpsolver=self.__lpsolver,
                is_strict_forall=self.__isstrictforall
            )
            self.__checkers.append(optChecker)

    def undo(self: LpPropagator, thread_id: int,
             _: Assignment, changes: list[int]) -> None:
        self.__checkers[thread_id].undo(changes)

    def propagate(self: LpPropagator, control: PropagateControl,
                  changes: list[int]) -> None:
        # ----------------------------------------------------------------------
        # Check LP constraints
        # ----------------------------------------------------------------------
        lp_checker: LpChecker = self.__checkers[control.thread_id]
        lp_checker.propagate(control, changes)
        # ----------------------------------------------------------------------
        # Add waiting nogoods
        # ----------------------------------------------------------------------
        if not self.apply_nogoods(control):
            return
        nogoods: list[list[int]] | None = lp_checker.check()
        # ----------------------------------------------------------------------
        # Added and apply newly nogoods
        # ----------------------------------------------------------------------
        if nogoods is not None and len(nogoods) != 0:
            self.__waiting_nogoods.extend(nogoods)
            if not self.apply_nogoods(control):
                return

    def check(self: LpPropagator, control: PropagateControl) -> None:
        # ----------------------------------------------------------------------
        # Apply waiting nogoods
        # ----------------------------------------------------------------------
        if not self.apply_nogoods(control):
            return
        # ----------------------------------------------------------------------
        # Compute changes
        # ----------------------------------------------------------------------
        lp_checker: LpChecker = self.__checkers[control.thread_id]
        changes: list[int] = lp_checker.unguess(control)
        # ----------------------------------------------------------------------
        # Check LP constraints
        # ----------------------------------------------------------------------
        lp_checker.propagate(control, changes)
        nogoods: list[list[int]] | None = lp_checker.check()
        if self.__show_lpassignment and (nogoods is None or len(nogoods) == 0):
            lp_checker.compute_assignment()
        lp_checker.undo(changes)
        # ----------------------------------------------------------------------
        # Added and apply newly nogoods
        # ----------------------------------------------------------------------
        if nogoods is not None and len(nogoods) != 0:
            self.__waiting_nogoods.extend(nogoods)
            if not self.apply_nogoods(control):
                return

    # --------------------------------------------------------------------------
    # Model refiners
    # --------------------------------------------------------------------------
    def apply_nogoods(self: LpPropagator, control: PropagateControl) -> bool:
        while len(self.__waiting_nogoods) != 0:
            nogood: list[int] = self.__waiting_nogoods.pop()
            if not control.add_nogood(nogood, lock=True):
                return False
        return True

    # --------------------------------------------------------------------------
    # Getters
    # --------------------------------------------------------------------------

    def get_assignment(self: LpPropagator, thread_id: int) \
            -> dict[str, tuple[str, dict[str, float | None]]] | None:
        if self.__show_lpassignment:
            lp_checker: LpChecker = self.__checkers[thread_id]
            return lp_checker.get_assignment()
        return None

    def get_statistics(self: LpPropagator,
                       thread_id: int = -1) -> dict[str,
                                                    dict[str, float] | float]:
        preprocessing_times: list[float] = [0]
        all_loggers: list[Logger] = []
        # ----------------------------------------------------------------------
        # Extract logs
        # ----------------------------------------------------------------------
        if thread_id != -1 or len(self.__checkers) == 1:
            checker: LpChecker = self.__checkers[thread_id]
            preprocessing_time, loggers = checker.get_statistics()
            preprocessing_times.append(preprocessing_time)
            all_loggers.extend(loggers)
        else:
            for checker in self.__checkers:
                preprocessing_time, loggers = checker.get_statistics()
                preprocessing_times.append(preprocessing_time)
                all_loggers.extend(loggers)
        # ----------------------------------------------------------------------
        # Merge the statistics of all thread
        # ----------------------------------------------------------------------
        statistics: dict[str, dict[str, float] | float] = {
            'Preprocessing (s)': sum(preprocessing_times)
        } | Logger.merge(all_loggers)
        return statistics

    # --------------------------------------------------------------------------
    # Setters
    # --------------------------------------------------------------------------
    def lazy(self: LpPropagator, is_lazy: bool) -> None:
        self.__islazy = is_lazy

    def show_lpassignment(self: LpPropagator, show: bool) -> None:
        self.__show_lpassignment = show

    def strict_forall_check(self: LpPropagator, is_strict: bool) -> None:
        self.__isstrictforall = is_strict

# ==============================================================================
# Checker
# ==============================================================================


class LpChecker:

    def __init__(self: LpChecker, init: PropagateInit, lazy: bool = False,
                 lpsolver: str = 'cbc', is_strict_forall: bool = False) -> None:
        self.preprocessing_time: float = time()
        # ----------------------------------------------------------------------
        # Linear problem solvers
        # ----------------------------------------------------------------------
        self.lpsolver: LpSolver = LpSolver(
            init, lpsolver, strict_forall=is_strict_forall
        )
        # ----------------------------------------------------------------------
        # Database - Clingo Literals IDs
        # ----------------------------------------------------------------------
        self.sids_cids: dict[int, set[int]] = {}
        self.cids_sid: dict[int, int] = {}
        self.cids_guess: dict[int, bool] = {}
        self.cids_value: dict[int, bool] = {}
        self.cids_completed: dict[int, bool] = {}

        # ----------------------------------------------------------------------
        # Database - LP Constraints
        # ----------------------------------------------------------------------
        self.cids: dict[int, list[int]] = {}
        self.condids: dict[int, list[int]] = {}

        # ----------------------------------------------------------------------
        # Initialize internal memory
        # ----------------------------------------------------------------------
        for atom in init.theory_atoms:
            # ------------------------------------------------------------------
            # Parse literals data
            # ------------------------------------------------------------------
            cid: int = atom.literal
            sid: int = init.solver_literal(cid)
            self.sids_cids.setdefault(sid, set()).add(cid)
            self.cids_sid[cid] = sid
            self.cids.setdefault(cid, [])
            self.cids_guess[cid] = False
            self.cids_value[cid] = False
            self.cids_completed[cid] = False
            # ------------------------------------------------------------------
            # Parse conditions data
            # ------------------------------------------------------------------
            for element in atom.elements:
                condid: int = element.condition_id
                scondid: int = init.solver_literal(condid)
                self.sids_cids.setdefault(scondid, set()).add(condid)
                self.cids_sid[condid] = scondid
                self.cids[cid].append(condid)
                self.condids.setdefault(condid, []).append(cid)
                self.cids_guess[condid] = False
                self.cids_value[condid] = False

        # ----------------------------------------------------------------------
        # Declare watch variables
        # ----------------------------------------------------------------------
        if lazy:
            for sid in self.sids_cids:
                init.remove_watch(sid)
        else:
            for sid in self.sids_cids:
                init.add_watch(sid)
        self.preprocessing_time = time() - self.preprocessing_time

    # ==========================================================================
    # Clingo's propagator override functions
    # ==========================================================================
    def undo(self: LpChecker, changes: list[int]) -> None:
        changed_cids: set[int] = set()
        for sid in changes:
            for condid in self.sids_cids[sid]:
                if condid not in self.condids:
                    continue
                assert self.cids_guess[condid]
                for cid in self.condids[condid]:
                    if self.cids_guess[cid] and self.__cid_completed(cid):
                        changed_cids.add(cid)
                self.cids_guess[condid] = False
        for sid in changes:
            for cid in self.sids_cids[sid]:
                if cid not in self.cids:
                    continue
                assert self.cids_guess[cid]
                if self.__cid_completed(cid):
                    changed_cids.add(cid)
                self.cids_guess[cid] = False
        self.lpsolver.undo(list(changed_cids))

    def propagate(self: LpChecker, control: PropagateControl,
                  changes: list[int]) -> None:
        propagate_cids: list[tuple[int, bool, list[int]]] = []
        changed_cids: set[tuple[int, bool]] = set()
        changed_condids: set[tuple[int, bool]] = set()
        for sid in changes:
            sid_guess: bool | None = control.assignment.value(sid)
            assert sid_guess is not None
            for cid in self.sids_cids[sid]:
                self.cids_guess[cid] = True
                self.cids_value[cid] = sid_guess
                if cid in self.cids:
                    changed_cids.add((cid, sid_guess))
                elif cid in self.condids:
                    changed_condids.add((cid, sid_guess))
        for condid, sid_guess in changed_condids:
            for cid in self.condids[condid]:
                if self.cids_guess[cid]:
                    changed_cids.add((cid, self.cids_value[cid]))
        for cid, sid_guess in changed_cids:
            if self.__cid_completed(cid):
                condids: set[int] = set()
                for condid in self.cids[cid]:
                    assert self.cids_guess[condid]
                    if self.cids_value[condid]:
                        condids.add(condid)
                propagate_cids.append((cid, sid_guess, list(condids)))
        self.lpsolver.propagate(propagate_cids)

    def check(self: LpChecker) -> list[list[int]]:
        nogoods: list[list[int]] = []
        nogood: list[int]
        # ----------------------------------------------------------------------
        # Check and Generalize Exists conflicts
        # ----------------------------------------------------------------------
        exists_conflicts: list[list[int]] = self.lpsolver.check_exists()
        for conflict in exists_conflicts:
            nogood = self.__nogoods_exists(conflict)
            nogoods.append(nogood)
        # ----------------------------------------------------------------------
        # Check and Generalize Forall conflicts
        # ----------------------------------------------------------------------
        forall_conflicts: list[tuple[int, list[int], list[int]]] = \
            self.lpsolver.check_forall()
        for cid, p_cids, up_cids in forall_conflicts:
            nogood = self.__nogoods_forall(cid, p_cids, up_cids)
            nogoods.append(nogood)
        return nogoods

    # ==========================================================================
    # Nogoods refiners
    # ==========================================================================
    def __nogoods_forall(self: LpChecker, cid: int, prop_cids: list[int],
                         unprop_cids: list[int]) -> list[int]:
        nogood: set[int] = set()
        # ----------------------------------------------------------------------
        # Forall constraint structure is prohibited
        # ----------------------------------------------------------------------
        sid: int = self.cids_sid[cid]
        nogood.add(sid)
        for condid in self.cids[cid]:
            scondid: int = self.cids_sid[condid]
            if not self.cids_guess[condid] or not self.cids_value[condid]:
                nogood.add(-scondid)
            else:
                nogood.add(scondid)
        # ----------------------------------------------------------------------
        # For exists constraints, either:
        # 1) A condid of a guessed true constraints should be changed
        # ----------------------------------------------------------------------
        for p_cid in prop_cids:
            for p_condid in self.cids[p_cid]:
                assert self.cids_guess[p_condid]
                p_scondid: int = self.cids_sid[p_condid]
                if not self.cids_value[p_condid]:
                    nogood.add(-p_scondid)
                else:
                    nogood.add(p_scondid)
        # ----------------------------------------------------------------------
        # 2) A guessed false constraints should be added
        # ----------------------------------------------------------------------
        for up_cid in unprop_cids:
            assert self.cids_guess[up_cid]
            up_sid: int = self.cids_sid[up_cid]
            nogood.add(-up_sid)
        return list(nogood)

    def __nogoods_exists(self: LpChecker, cids: list[int]) -> list[int]:
        nogood: list[int] = []
        for cid in cids:
            sign: Literal[-1, 1] = -1 if cid < 0 else 1
            cid = abs(cid)
            sid: int = self.cids_sid[cid]
            nogood.append(sign * sid)
            if sign == 1:
                for condid in self.cids[cid]:
                    scondid: int = self.cids_sid[condid]
                    assert self.cids_guess[condid]
                    if self.cids_value[condid]:
                        nogood.append(scondid)
                    else:
                        nogood.append(-scondid)
        return nogood

    # ==========================================================================
    # Getters
    # ==========================================================================
    def __cid_completed(self: LpChecker, cid: int) -> bool:
        for condid in self.cids[cid]:
            if not self.cids_guess[condid]:
                return False
        return True

    def unguess(self: LpChecker, control: PropagateControl) -> list[int]:
        return list({
            self.cids_sid[cid]
            for cid, cid_guess in self.cids_guess.items()
            if not cid_guess
            and control.assignment.value(self.cids_sid[cid]) is not None
        })

    def get_statistics(self: LpChecker) -> tuple[float, list[Logger]]:
        return (self.preprocessing_time, self.lpsolver.get_statistics())

    def get_assignment(self: LpChecker) \
            -> dict[str, tuple[str, dict[str, float | None]]]:
        assignments: dict[str, tuple[str, dict[str, float | None]]] = \
            self.lpsolver.get_assignment()
        self.lpsolver.reset_assignment()
        return assignments

    def compute_assignment(self: LpChecker) -> None:
        self.lpsolver.optimize()
