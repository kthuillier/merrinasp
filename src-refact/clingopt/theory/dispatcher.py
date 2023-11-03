# -*- coding=utf-8 -*-

# ==============================================================================
# IMPORT
# ==============================================================================

from __future__ import annotations

from time import time

from clingo import PropagateInit

from .lpsolver import LpConstraint

# ==============================================================================
# Dispatcher
# ==============================================================================


class LpDispatcher:

    def __init__(self: LpDispatcher, init: PropagateInit,
                 lpsolver: str = 'glpk') -> None:
        # ----------------------------------------------------------------------
        # Parameters
        # ----------------------------------------------------------------------
        self.lpsolver: str = lpsolver

        # ----------------------------------------------------------------------
        # Database - Lp Models
        # ----------------------------------------------------------------------

        # ----------------------------------------------------------------------
        # Database - LP constraints
        # ----------------------------------------------------------------------
        self.cids_type: dict[int, bool]
        self.cids_constraints: dict[int, list[LpConstraint]] = {}

        # ----------------------------------------------------------------------
        # Initialize internal memory
        # ----------------------------------------------------------------------
        self.preprocessing_time: float = time()
        for atom in init.theory_atoms:
            cid: int = atom.literal
            pid: str = str(atom.term.arguments[0])
            for element in atom.elements:
                condid: int = element.condition_id
        self.preprocessing_time = time() - self.preprocessing_time

    # ==========================================================================
    # LP problem builders
    # ==========================================================================
    def propagate(self: LpDispatcher, cid: int, condid: list[int]) -> None:
        raise NotImplementedError()

    def undo(self: LpDispatcher, cids: list[int]) -> None:
        raise NotImplementedError()

    def check_exists(self: LpDispatcher,
                     pid: str) -> None | list[int]:
        raise NotImplementedError()

    def check_forall(self: LpDispatcher,
                     pid: str) -> None | list[tuple[int, list[int]]]:
        raise NotImplementedError()

    def optimize(self: LpDispatcher,
                     pid: str) -> tuple[list[float], list[tuple[str, float]]]:
        raise NotImplementedError()

    # ==========================================================================
    # Getters
    # ==========================================================================

    def get_statistics(self: LpDispatcher, pid: str) -> dict[str, dict[str, float]]:
        raise NotImplementedError()

    def get_assignement(self: LpDispatcher) -> dict[str, tuple[list[tuple[str, float]], list[float]]]:
        raise NotImplementedError()