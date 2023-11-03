# -*- coding=utf-8 -*-

# ==============================================================================
# IMPORT
# ==============================================================================

from __future__ import annotations

from time import time

from clingo import (
    Assignment,
    PropagateInit,
    PropagateControl,
)

from .dispatcher import LpDispatcher

# from .lp.solver import LpDispatcher

# ==============================================================================
# Propagator
# ==============================================================================


class LpPropagator:

    def __init__(self: LpPropagator) -> None:
        # ----------------------------------------------------------------------
        # Parameters
        # ----------------------------------------------------------------------
        self.__islazy: bool = False
        self.__lpsolver: str = 'glpk'
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
                lpsolver=self.__lpsolver
            )
            self.__checkers.append(optChecker)

    def undo(self: LpPropagator, thread_id: int,
             _: Assignment, changes: list[int]) -> None:
        self.__checkers[thread_id].undo(changes)

    def propagate(self: LpPropagator, control: PropagateControl,
                  changes: list[int]) -> None:
        # ----------------------------------------------------------------------
        # Apply waiting nogoods
        # ----------------------------------------------------------------------
        if not self.apply_nogoods(control):
            return
        # ----------------------------------------------------------------------
        # Check LP constraints
        # ----------------------------------------------------------------------
        lp_checker: LpChecker = self.__checkers[control.thread_id]
        lp_checker.propagate(control, changes)
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
        changes: list[int] = lp_checker.unguess()
        # ----------------------------------------------------------------------
        # Check LP constraints
        # ----------------------------------------------------------------------
        lp_checker.propagate(control, changes)
        nogoods: list[list[int]] | None = lp_checker.check()
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
            -> dict[str, tuple[list[float], list[tuple[str, float]]]]:
        lp_checker: LpChecker = self.__checkers[thread_id]
        return lp_checker.get_assignement()

    def get_statistics(self: LpPropagator, thread_id: int = -1) -> dict[str, dict[str, float]]:
        raise NotImplementedError()

    # --------------------------------------------------------------------------
    # Setters
    # --------------------------------------------------------------------------
    def lazy(self: LpPropagator, is_lazy: bool) -> None:
        self.__islazy = is_lazy

# ==============================================================================
# Checker
# ==============================================================================


class LpChecker:

    def __init__(self: LpChecker, init: PropagateInit,
                 lazy: bool = False, lpsolver: str = 'glpk') -> None:
        # ----------------------------------------------------------------------
        # Linear problem solvers
        # ----------------------------------------------------------------------
        self.lpdispatcher: LpDispatcher = LpDispatcher(init, lpsolver)

        # ----------------------------------------------------------------------
        # Database - Clingo Literals IDs
        # ----------------------------------------------------------------------
        self.sids: dict[int, list[int]] = {}
        self.cids_sid: dict[int, int] = {}
        self.cids_guess: dict[int, bool] = {}
        self.cids_value: dict[int, bool] = {}

        # ----------------------------------------------------------------------
        # Database - LP Constraints
        # ----------------------------------------------------------------------
        self.pids: dict[str, list[int]] = {}
        self.cids: dict[int, list[int]] = {}
        self.condids: dict[int, list[int]] = {}

        # ----------------------------------------------------------------------
        # Initialize internal memory
        # ----------------------------------------------------------------------
        self.preprocessing_time: float = time()
        for atom in init.theory_atoms:
            cid: int = atom.literal
            pid: str = str(atom.term.arguments[0])
            self.pids.setdefault(pid, []).append(cid)
            sid: int = init.solver_literal(cid)
            self.sids.setdefault(sid, []).append(cid)
            self.cids_sid[cid] = sid
            self.cids_guess[cid] = False
            self.cids_value[cid] = False
            for element in atom.elements:
                condid: int = element.condition_id
                scondid: int = init.solver_literal(condid)
                self.sids.setdefault(scondid, []).append(condid)
                self.cids.setdefault(cid, []).append(condid)
                self.condids.setdefault(condid, []).append(cid)
                self.cids_guess[condid] = False
                self.cids_value[condid] = False

        # ----------------------------------------------------------------------
        # Declare watch variables
        # ----------------------------------------------------------------------
        if lazy:
            for sid in self.sids:
                init.add_watch(sid)
        else:
            for sid in self.sids:
                init.remove_watch(sid)
        self.preprocessing_time = time() - self.preprocessing_time

    # ==========================================================================
    # Clingo's propagator override functions
    # ==========================================================================
    def undo(self: LpChecker, changes: list[int]) -> None:
        changed_cids: list[int] = []
        for sid in changes:
            for cid in self.sids[sid]:
                if cid in self.cids and self.cids_guess[cid]:
                    changed_cids.append(cid)
                self.cids_guess[cid] = False
        self.lpdispatcher.undo(changed_cids)

    def propagate(self: LpChecker, control: PropagateControl,
                  changes: list[int]) -> None:
        for sid in changes:
            changed_cids: list[int] = []
            sid_guess: bool | None = control.assignment.value(sid)
            assert sid_guess is not None
            for cid in self.sids[sid]:
                self.cids_guess[cid] = True
                self.cids_value[cid] = sid_guess
                if cid in self.cids:
                    changed_cids.append(cid)
            if not sid_guess:  # Case: false -> update the status
                continue
            for cid in changed_cids:
                condids: list[int] = []
                for condid in self.cids[cid]:
                    assert self.cids_guess[condid]
                    if self.cids_value[condid]:
                        condids.append(condid)
                self.lpdispatcher.propagate(cid, condids)

    def check(self: LpChecker) -> list[list[int]]:
        nogoods: list[list[int]] = []
        for pid in self.pids:
            exists_conflict: None | list[int] = self.lpdispatcher.check_exists(
                pid)
            if exists_conflict is None:  # Case: no conflict
                forall_conflict: None | list[tuple[int, list[int]]
                                             ] = self.lpdispatcher.check_forall(pid)
                if forall_conflict is not None:
                    forall_nogoods: list[list[int]] = self.__nogoods_forall(
                        forall_conflict)
                    nogoods.extend(forall_nogoods)
            else:  # Case: conflict
                exists_nogood: list[int] = self.__nogoods_exists(
                    exists_conflict)
                nogoods.append(exists_nogood)
        return nogoods

    # ==========================================================================
    # Nogoods refiners
    # ==========================================================================
    def __nogoods_forall(self: LpChecker,
                         cids: list[tuple[int, list[int]]]) -> list[list[int]]:
        nogoods: list[list[int]] = []
        for cid, lcids in cids:
            nogood: list[int] = []
            sid: int = self.cids_sid[cid]
            nogood.append(sid)
            for condid in self.cids[cid]:
                scondid: int = self.cids_sid[condid]
                if not self.cids_guess[condid] or not self.cids_value[condid]:
                    nogood.append(-scondid)
                else:
                    nogood.append(scondid)
            for lcid in lcids:
                lsid: int = self.cids_sid[lcid]
                nogood.append(-lsid)
            nogoods.append(nogood)
        return nogoods

    def __nogoods_exists(self: LpChecker, cids: list[int]) -> list[int]:
        nogood: list[int] = []
        for cid in cids:
            sid: int = self.cids_sid[cid]
            nogood.append(sid)
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
    def unguess(self: LpChecker) -> list[int]:
        return [cid
                for cid, cid_guess in self.cids_guess.items()
                if not cid_guess
                ]

    def get_statistics(self: LpChecker) -> dict[str, dict[str, dict[str, float]]]:
        statistics: dict[str, dict[str, dict[str, float]]] = {}
        for pid in self.pids:
            pid_statistics: dict[str, dict[str, float]
                                 ] = self.lpdispatcher.get_statistics(pid)
            if pid_statistics is not None:
                statistics[pid] = pid_statistics
        return statistics

    def get_assignement(self: LpChecker) -> dict[str, tuple[list[float], list[tuple[str, float]]]]:
        assignment: dict[str, tuple[list[float], list[tuple[str, float]]]] = {}
        for pid in self.pids:
            optimums, pid_assignment = self.lpdispatcher.optimize(pid)
            if pid_assignment is not None:
                assignment[pid] = (optimums, pid_assignment)
        return assignment
