# -*- coding=utf-8 -*-

# ==============================================================================
# IMPORT
# ==============================================================================

from __future__ import annotations

from clingo import (
    Assignment,
    PropagateInit,
    PropagateControl,
    TheoryAtom,
    TheoryElement,
    SymbolicAtom,
    Symbol,
)
from .model import LpModel

# ==============================================================================
# Lp Solver
# ==============================================================================

class LpSolver:

    def __init__(self: LpSolver, init: PropagateInit,
                 lpsolver: str = 'glpk') -> None:
        # ----------------------------------------------------------------------
        # Parameters
        # ----------------------------------------------------------------------
        self.lpsolver: str = lpsolver
        # ----------------------------------------------------------------------
        # Models
        # ----------------------------------------------------------------------
        self.models: list[LpModel] = []
        # ----------------------------------------------------------------------
        # Database - Clingo's ID
        # ----------------------------------------------------------------------
        # sid <-> cid/condid
        self.sid_to_ids: dict[int, list[int]] = {}
        self.id_to_sids: dict[int, list[int]] = {}
        # pid <-> cid
        self.pids_to_cids: dict[str, list[int]] = {}
        self.cids_to_pids: dict[int, str] = {}
        # cid <-> condid
        self.cids_to_condids: dict[int, list[int]] = {}
        self.condids_to_cids: dict[int, list[int]] = {}

        # ----------------------------------------------------------------------
        # Database - LP constraints
        # ----------------------------------------------------------------------
        self.constraints_conditions: dict[tuple[int,int], list[tuple[float,str]]] = {}

        # ----------------------------------------------------------------------
        # Initialize internal memory
        # ----------------------------------------------------------------------
        for atom in init.theory_atoms:
            pass
        # ----------------------------------------------------------------------
        # Initialize models
        # ----------------------------------------------------------------------

    # ==========================================================================
    # Initialization
    # ==========================================================================

    # ==========================================================================
    # Building
    # ==========================================================================

    def propagate(self: LpSolver, cid: int, condid: list[int]) -> None:
        raise NotImplementedError()

    def undo(self: LpSolver, cids: list[int]) -> None:
        raise NotImplementedError()

    # ==========================================================================
    # Solving
    # ==========================================================================

    def check_exists(self: LpSolver,
                     pid: str) -> None | list[int]:
        raise NotImplementedError()

    def check_forall(self: LpSolver,
                     pid: str) -> None | list[tuple[int, list[int]]]:
        raise NotImplementedError()

    def optimize(self: LpSolver,
                     pid: str) -> tuple[list[float], list[tuple[str, float]]]:
        raise NotImplementedError()

    # ==========================================================================
    # Querying
    # ==========================================================================
    def __complet_cid(self: LpSolver, cid: int) -> bool:
        if not self.cids_guess[cid]:
            return False
        if cid not in self.condids:
            return self.cids_values[cid]
        for condid in self.condids.get(cid, []):
            pass
        raise NotImplementedError()

    def __complet_pid(self: LpSolver, pid: int) -> bool:
        raise NotImplementedError()

    # ==========================================================================
    # Getters
    # ==========================================================================

    def get_statistics(self: LpSolver, pid: str) -> dict[str, dict[str, float]]:
        raise NotImplementedError()

    def get_assignement(self: LpSolver) -> dict[str, tuple[list[tuple[str, float]], list[float]]]:
        raise NotImplementedError()