# -*- coding=utf-8 -*-

# ==============================================================================
# IMPORT
# ==============================================================================

from __future__ import annotations
from time import time

from clingo import PropagateInit

from .logger import Logger
from .model import LpModel
from ..language import LpConstraint, ParsedLpConstraint, parse_atom

# ==============================================================================
# Solver
# ==============================================================================


class LpSolver:

    def __init__(self: LpSolver, init: PropagateInit,
                 lpsolver: str = 'glpk') -> None:
        # ----------------------------------------------------------------------
        # Parameters
        # ----------------------------------------------------------------------
        self.lpsolver: str = lpsolver

        # ----------------------------------------------------------------------
        # Database - Lp Models
        # ----------------------------------------------------------------------
        self.models: dict[str, LpModel] = {}
        self.models_forall: dict[str, list[int]] = {}

        # ----------------------------------------------------------------------
        # Database - LP constraints
        # ----------------------------------------------------------------------
        self.pids: dict[str, list[int]] = {}
        self.cids_guessed: dict[int, bool] = {}
        self.cids_propagated: dict[int, bool] = {}
        self.cids_constraints: dict[int, ParsedLpConstraint] = {}

        # ----------------------------------------------------------------------
        # Initialize internal memory
        # ----------------------------------------------------------------------
        self.preprocessing_time: float = time()
        for atom in init.theory_atoms:
            pid: str = str(atom.term.arguments[0])
            cid: int = atom.literal
            self.pids.setdefault(pid, []).append(cid)
            self.cids_guessed[cid] = False
            self.cids_propagated[cid] = False
            constraints: list[ParsedLpConstraint] = parse_atom(atom)
            assert 1 <= len(constraints) and len(constraints) <= 2
            self.cids_constraints[cid] = constraints[0]
            if constraints[0][0] == 'forall':
                self.models_forall.setdefault(pid, []).append(-cid)
            if len(constraints) == 2:
                self.cids_constraints[-cid] = constraints[1]
                if constraints[1][0] == 'forall':
                    self.models_forall.setdefault(pid, []).append(-cid)

        # ----------------------------------------------------------------------
        # Initialize Lp Models
        # ----------------------------------------------------------------------
        for pid in self.pids:
            self.models[pid] = LpModel(self.lpsolver, pid)

        self.preprocessing_time = time() - self.preprocessing_time

    # ==========================================================================
    # LP problem builders
    # ==========================================================================
    def propagate(self: LpSolver,
                  cids: list[tuple[int, bool, list[int]]]) -> None:
        propagate_constraints: dict[str, list[tuple[int,
                                                    LpConstraint,
                                                    tuple[int, ...]]]] = {}
        for cid, value, condid in cids:
            # ------------------------------------------------------------------
            # Update 'guess' status
            # ------------------------------------------------------------------
            self.cids_guessed[cid] = True
            if -cid in self.cids_constraints:
                self.cids_guessed[-cid] = True
            # ------------------------------------------------------------------
            # Compute new constraints
            # ------------------------------------------------------------------
            if value:
                self.cids_propagated[cid] = True
                pid, constraint = self.__get_constraints(cid, condid)
                description: tuple[int, ...] = self.__get_description(
                    cid,
                    condid
                )
                propagate_constraints.setdefault(pid, []).append(
                    (cid, constraint, description)
                )
                if -cid in self.cids_constraints:
                    pid, constraint = self.__get_constraints(-cid, condid)
                    description = self.__get_description(
                        -cid,
                        condid
                    )
                    propagate_constraints.setdefault(pid, []).append(
                        (-cid, constraint, description)
                    )
        # ----------------------------------------------------------------------
        # Propagate constraints to Lp Models
        # ----------------------------------------------------------------------
        for pid, constraints in propagate_constraints.items():
            self.models[pid].update(constraints)

    def undo(self: LpSolver, cids: list[int]) -> None:
        undo_constraints: dict[str, list[int]] = {}
        for cid in cids:
            # ------------------------------------------------------------------
            # Update 'guess' status
            # ------------------------------------------------------------------
            self.cids_guessed[cid] = False
            if -cid in self.cids_constraints:
                self.cids_guessed[-cid] = False
            self.cids_propagated[cid] = False
            # ------------------------------------------------------------------
            # Get constraints to remove from Lp Models
            # ------------------------------------------------------------------
            pid: str = self.cids_constraints[cid][1]
            undo_constraints.setdefault(pid, []).append(cid)
            if -cid in self.cids_constraints:
                pid = self.cids_constraints[-cid][1]
                undo_constraints.setdefault(pid, []).append(-cid)
        # ----------------------------------------------------------------------
        # Remove constraints from Lp Models
        # ----------------------------------------------------------------------
        for pid, constraints in undo_constraints.items():
            self.models[pid].remove(constraints)

    # ==========================================================================
    # LP problem solvers
    # ==========================================================================

    def check_exists(self: LpSolver) -> list[list[int]]:
        core_conflicts: list[list[int]] = []
        for pid in self.pids:
            sat: bool = self.models[pid].check_exists()
            if not sat:
                conflict: list[int] = self.models[pid].core_unsat_exists()
                conflict += self.models_forall.get(pid, [])
                core_conflicts.append(conflict)
        return core_conflicts

    def check_forall(self: LpSolver) -> list[tuple[int, list[int], list[int]]]:
        core_conflicts: list[tuple[int, list[int], list[int]]] = []
        for pid in self.get_pids(only_completed=True):
            unsat_cid: list[int] = self.models[pid].check_forall()
            if len(unsat_cid) > 0:
                prop_cids: list[int] = self.get_constraints(
                    pid,
                    only_propagated=True
                )
                unprop_cids: list[int] = [
                    cid
                    for cid in self.get_constraints(pid)
                    if cid not in prop_cids
                ]
                conflicts: list[tuple[int, list[int], list[int]]] = \
                    self.models[pid].core_unsat_forall(
                        unsat_cid,
                        prop_cids,
                        unprop_cids,
                )
                core_conflicts.extend(conflicts)
        return core_conflicts

    def optimize(self: LpSolver,
                 pid: str) -> tuple[list[float], list[tuple[str, float]]]:
        return self.models[pid].optimize()

    # ==========================================================================
    # Getters
    # ==========================================================================

    def __get_constraints(self: LpSolver, cid: int,
                          condids: list[int]) -> tuple[str, LpConstraint]:
        ctype, pid, expr, sense, bound = self.cids_constraints[cid]
        expr_: list[tuple[float, str]] = []
        for condid in condids:
            expr_.extend(expr[condid])
        return pid, (ctype, expr_, sense, bound)

    def __get_description(self: LpSolver, cid: int,
                          condids: list[int]) -> tuple[int, ...]:
        return tuple([cid] + sorted(condids))

    def get_pids(self: LpSolver, only_completed: bool = False) -> list[str]:
        def is_completed(pid: str) -> bool:
            for cid in self.pids[pid]:
                if not self.cids_guessed[cid]:
                    return False
            return True
        return [
            pid
            for pid in self.pids
            if not only_completed or is_completed(pid)
        ]

    def get_constraints(self: LpSolver, pid: str,
                        only_propagated: bool = False) -> list[int]:
        if only_propagated:
            return [cid for cid in self.pids[pid] if self.cids_propagated[cid]]
        return self.pids[pid]

    def get_statistics(self: LpSolver,
                       pid: str | None = None) -> list[Logger]:
        if pid is not None:
            return [self.models[pid].get_statistics()]
        return [model.get_statistics() for model in self.models.values()]

    def get_assignement(self: LpSolver,
                        pid: str) -> dict[str, float]:
        return self.models[pid].get_assignment()
