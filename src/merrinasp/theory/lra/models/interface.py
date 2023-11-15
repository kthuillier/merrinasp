# -*- coding=utf-8 -*-

# ==============================================================================
# IMPORT
# ==============================================================================

from __future__ import annotations

from merrinasp.theory.lra.logger import Logger
from merrinasp.theory.lra.cache import LpCache
from merrinasp.theory.language import LpConstraint

# ==============================================================================
# Lp Models
# ==============================================================================


class ModelInterface:

    def __init__(self: ModelInterface, lpsolver: str, pid: str) -> None:
        # ----------------------------------------------------------------------
        # Model data
        # ----------------------------------------------------------------------
        self.pid: str = pid
        self.lpsolver: str = lpsolver

        # ----------------------------------------------------------------------
        # Statistics
        # ----------------------------------------------------------------------
        self.logger: Logger = Logger(self.pid)

        # ----------------------------------------------------------------------
        # Cache
        # ----------------------------------------------------------------------
        self.cache: LpCache = LpCache()
        self.description: dict[int, tuple[int, ...]] = {}
        self.description_db: dict[int, tuple[int, ...]] = {}
        self.added_order: list[int] = []

    # ==========================================================================
    # Builder
    # ==========================================================================
    def update(self: ModelInterface,
               constraints: list[tuple[int,
                                       LpConstraint,
                                       tuple[int, ...]]]) -> None:
        for cid, constraint, description in constraints:
            self.add(cid, constraint, description)

    def add(self: ModelInterface, cid: int, constraint: LpConstraint,
            description: tuple[int, ...]) -> None:
        raise NotImplementedError()

    def remove(self: ModelInterface, cids: list[int]) -> None:
        raise NotImplementedError()

    # ==========================================================================
    # Solving
    # ==========================================================================
    def check_exists(self: ModelInterface) -> bool:
        raise NotImplementedError()

    def check_forall(self: ModelInterface) -> list[int]:
        raise NotImplementedError()

    def optimize(self: ModelInterface) -> tuple[list[float],
                                                list[tuple[str, float]]]:
        raise NotImplementedError()

    # ==========================================================================
    # Core conflicts
    # ==========================================================================
    def core_unsat_exists(self: ModelInterface,
                          lazy: bool = False) -> list[int]:
        raise NotImplementedError()

    def core_unsat_forall(self: ModelInterface, conflict: int,
                          unprop_cids: dict[int, list[tuple[LpConstraint, tuple[int, ...]]]],
                          lazy: bool = False) -> list[int]:
        raise NotImplementedError()

    # ==========================================================================
    # Getters
    # ==========================================================================
    def get_statistics(self: ModelInterface) -> Logger:
        return self.logger

    def get_assignment(self: ModelInterface) -> dict[str, float]:
        raise NotImplementedError()
