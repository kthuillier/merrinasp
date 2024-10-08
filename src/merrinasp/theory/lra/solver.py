# -*- coding=utf-8 -*-

# ==============================================================================
# IMPORT
# ==============================================================================

from __future__ import annotations
from typing import Generator
from time import time

from clingo import PropagateInit

from merrinasp.theory.lra.logger import Logger
from merrinasp.theory.lra.models import (
    ModelInterface,
    ModelGurobiPy,
    ModelPuLP,
    ModelGLPK
)
from merrinasp.theory.language import (
    LpConstraint,
    ParsedLpConstraint,
    parse_atom
)
from merrinasp.theory.lra.cache import LpCache


# ==============================================================================
# Type Alias
# ==============================================================================

PID = str
SID = int
DESCRIPTION = int

# ==============================================================================
# Solver
# ==============================================================================

class LpSolver:

    def __init__(self: LpSolver, init: PropagateInit,
                 lpsolver: str = 'glpk', strict_forall: bool = True) -> None:
        self.preprocessing_time: float = time()
        # ----------------------------------------------------------------------
        # Select LpSolver
        # ----------------------------------------------------------------------
        self.__init_lpsolver(lpsolver, strict_forall)
        self.__cache: LpCache = LpCache()

        # ----------------------------------------------------------------------
        # Database - Lp Models
        # ----------------------------------------------------------------------
        self.models: dict[str, ModelInterface] = {}
        self.models_forall: dict[str, list[int]] = {}

        # ----------------------------------------------------------------------
        # Database - LP constraints
        # ----------------------------------------------------------------------
        self.pids: dict[str, list[int]] = {}
        self.cids_guessed: dict[int, bool] = {}
        self.cids_propagated: dict[int, bool] = {}
        self.cids_constraints: dict[int, ParsedLpConstraint] = {}
        self.cids_grounded_constraints: \
            dict[int, list[tuple[LpConstraint, int]]] = {}

        self.pids_checked_exists: dict[str, bool] = {}
        self.pids_checked_forall: dict[str, bool] = {}

        # ----------------------------------------------------------------------
        # Initialize internal memory
        # ----------------------------------------------------------------------
        self.__init_memory(init)

        # ----------------------------------------------------------------------
        # Assignment
        # ----------------------------------------------------------------------
        self.assignments: dict[str,
                               tuple[str, None | dict[str, float | None]]] = {}
        self.statistics: dict[str, Logger] = {}

        self.preprocessing_time = time() - self.preprocessing_time

    def __init_lpsolver(self: LpSolver, lpsolver: str,
                        strict_forall: bool) -> None:
        self.strict_forall: bool = strict_forall
        self.lpsolver: str = lpsolver
        self.lpsolver_interface: type[ModelInterface] = ModelGLPK
        if self.lpsolver == 'cbc':
            self.lpsolver_interface = ModelPuLP
        elif self.lpsolver == 'glpk':
            self.lpsolver_interface = ModelGLPK
        elif self.lpsolver == 'gurobi':
            self.lpsolver_interface = ModelGurobiPy
        elif '-optlang' in self.lpsolver:
            self.lpsolver = self.lpsolver.removesuffix('-optlang')
            from merrinasp.theory.lra.models.model_optlang import ModelOptlang
            self.lpsolver_interface = ModelOptlang
        elif '-pulp' in self.lpsolver:
            self.lpsolver = self.lpsolver.removesuffix('-pulp')
            self.lpsolver_interface = ModelPuLP
        else:
            print(f'Warning: unknown LP solver {self.lpsolver}.')
            print('Set to default value "glpk".')

    def __init_memory(self: LpSolver, init: PropagateInit) -> None:
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

    # ==========================================================================
    # LP problem builders
    # ==========================================================================
    def propagate(self: LpSolver,
                  cids: list[tuple[int, bool, list[int]]]) -> None:
        propagate_constraints: dict[str, list[tuple[int,
                                                    LpConstraint,
                                                    int]]] = {}
        for cid, value, condid in cids:
            # ------------------------------------------------------------------
            # Update 'guess' status
            # ------------------------------------------------------------------
            self.cids_guessed[cid] = True
            if -cid in self.cids_constraints:
                self.cids_guessed[-cid] = True
            # ------------------------------------------------------------------
            # Compute new lp constraints to propagate
            # ------------------------------------------------------------------
            if value:
                self.cids_propagated[cid] = True
                pid, constraint = self.__get_constraints(cid, condid)
                description: int = self.__get_description(
                    cid,
                    condid
                )
                propagate_constraints.setdefault(pid, []).append(
                    (cid, constraint, description)
                )
                if -cid in self.cids_constraints:
                    self.cids_propagated[-cid] = True
                    pid, constraint = self.__get_constraints(-cid, condid)
                    description = self.__get_description(
                        -cid,
                        condid
                    )
                    propagate_constraints.setdefault(pid, []).append(
                        (-cid, constraint, description)
                    )
            else:
                self.cids_propagated[cid] = False
                if -cid in self.cids_constraints:
                    self.cids_propagated[-cid] = False
        # ----------------------------------------------------------------------
        # Propagate constraints to Lp Models
        # ----------------------------------------------------------------------
        for pid, constraints in propagate_constraints.items():
            if pid not in self.models:
                self.models[pid] = self.lpsolver_interface(
                    self.lpsolver, pid, cache=self.__cache
                )
                if pid in self.statistics:
                    self.models[pid].logger = self.statistics[pid]
                    del self.statistics[pid]
            self.models[pid].update(constraints)
            self.pids_checked_exists[pid] = False
            self.pids_checked_forall[pid] = False

    def undo(self: LpSolver, cids: list[int]) -> None:
        undo_constraints: dict[str, list[int]] = {}
        for cid in cids:
            # ------------------------------------------------------------------
            # Update 'guess' status
            # ------------------------------------------------------------------
            self.cids_guessed[cid] = False
            if -cid in self.cids_constraints:
                self.cids_guessed[-cid] = False
            # ------------------------------------------------------------------
            # Get constraints to remove from Lp Models
            # ------------------------------------------------------------------
            if self.cids_propagated[cid]:
                pid: str = self.cids_constraints[cid][1]
                undo_constraints.setdefault(pid, []).append(cid)
                if -cid in self.cids_constraints:
                    pid = self.cids_constraints[-cid][1]
                    undo_constraints.setdefault(pid, []).append(-cid)
            self.cids_propagated[cid] = False
        # ----------------------------------------------------------------------
        # Remove constraints from Lp Models
        # ----------------------------------------------------------------------
        for pid, constraints in undo_constraints.items():
            self.models[pid].remove(constraints)
            self.pids_checked_exists[pid] = False
            self.pids_checked_forall[pid] = False
            if self.models[pid].is_empty():
                self.statistics[pid] = self.models[pid].logger
                del self.models[pid]

    # ==========================================================================
    # LP problem solvers
    # ==========================================================================

    def check_exists(self: LpSolver) -> list[list[int]]:
        core_conflicts: list[list[int]] = []
        for pid in self.get_pids(only_completed=True):
            if self.pids_checked_exists[pid]:
                continue
            sat: bool = self.models[pid].check_exists()
            self.pids_checked_exists[pid] = True
            if not sat:
                conflict: list[int] = self.models[pid].core_unsat_exists()
                if self.strict_forall:
                    conflict += self.models_forall.get(pid, [])
                core_conflicts.append(conflict)
        return core_conflicts

    def check_forall(self: LpSolver) -> list[tuple[int, list[int], list[int]]]:
        core_conflicts: list[tuple[int, list[int], list[int]]] = []
        for pid in self.get_pids(only_completed=True):
            if pid not in self.models_forall:
                continue
            if self.pids_checked_forall[pid]:
                continue
            unsat_cid: list[int] = self.models[pid].check_forall()
            self.pids_checked_forall[pid] = True
            if len(unsat_cid) > 0:
                prop_cids: list[int] = self.get_constraints(
                    pid,
                    only_propagated=True
                )
                unprop_cids: dict[int, list[tuple[LpConstraint,
                                                  int]]] = {
                    cid: self.__ground_lpconstraints(cid)
                    for cid in self.get_constraints(pid)
                    if cid not in prop_cids
                }
                conflicts: list[tuple[int, list[int], list[int]]] = []
                for conflict in unsat_cid:
                    conflicts.append((
                        abs(conflict),
                        prop_cids,
                        self.models[pid].core_unsat_forall(
                            conflict,
                            unprop_cids
                        )
                    ))
                core_conflicts.extend(conflicts)
        return core_conflicts

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
                          condids: list[int]) -> int:
        _, (ctype, expr_, sense, bound) = self.__get_constraints(cid, condids)
        expr_str: str = ' + '.join(
            f'{coeff} * {var}'
            for coeff, var in sorted(expr_)
        )
        description: tuple[str, str] = (
            ctype,
            f'{expr_str} {sense} {bound}'
        )
        return hash(description)

    def get_pids(self: LpSolver, only_completed: bool = False) -> list[str]:
        def is_completed(pid: str) -> bool:
            for cid in self.pids[pid]:
                if not self.cids_guessed[cid]:
                    return False
            return True
        return [
            pid
            for pid in self.models
            if not only_completed or is_completed(pid)
        ]

    def get_constraints(self: LpSolver, pid: str,
                        only_propagated: bool = False) -> list[int]:
        if only_propagated:
            return [
                cid
                for cid in self.pids[pid]
                if self.cids_propagated[cid]
                and -cid not in self.models_forall[pid]
            ]
        return [
            cid
            for cid in self.pids[pid]
            if -cid not in self.models_forall[pid]
        ]

    def get_statistics(self: LpSolver,
                       pid: str | None = None) -> list[Logger]:
        if pid is not None:
            return [self.models[pid].get_statistics()]
        loggers: list[Logger] = [
            model.get_statistics()
            for model in self.models.values()
        ]
        for logger in loggers:
            logger.cache_size[0], logger.cache_size[1] = self.__cache.get_size()
        return loggers

    # ==========================================================================
    # Assignment related functions
    # ==========================================================================

    def get_assignment(self: LpSolver) \
            -> dict[str, tuple[str, None | dict[str, float | None]]]:
        return self.assignments.copy()

    def reset_assignment(self: LpSolver) -> None:
        self.assignments.clear()

    def optimize(self: LpSolver) \
            -> dict[str, tuple[str, None | dict[str, float | None]]]:
        self.assignments.clear()
        for pid in self.get_pids(only_completed=True):
            self.assignments[pid] = self.models[pid].optimize()
        return self.assignments

    # ==========================================================================
    # Auxiliary functions
    # ==========================================================================

    def __ground_lpconstraints(self: LpSolver, cid: int) \
            -> list[tuple[LpConstraint, int]]:
        # ----------------------------------------------------------------------
        # Recursive function yielding list of list of grounded LpConstraint
        # ----------------------------------------------------------------------
        def partition(condids: list[int]) \
                -> Generator[list[list[int]], None, None]:
            if len(condids) == 1:
                yield [condids]
                return
            first = condids[0]
            for smaller in partition(condids[1:]):
                for n, subset in enumerate(smaller):
                    yield smaller[:n] + [[first] + subset] + smaller[n+1:]
                yield [[first]] + smaller
        # ----------------------------------------------------------------------
        # Check if the grounding is already known
        # ----------------------------------------------------------------------
        if cid in self.cids_grounded_constraints:
            return self.cids_grounded_constraints[cid]
        # ----------------------------------------------------------------------
        # Compute the Grounded LpConstraints
        # ----------------------------------------------------------------------
        ctype, _, expr, sense, b = self.cids_constraints[cid]
        lpconstraints: list[tuple[LpConstraint, int]] = []
        for list_grounded_condids in partition(list(expr.keys())):
            for grounded_condids in list_grounded_condids:
                lpconstraint: LpConstraint = (
                    ctype,
                    sum(
                        (expr[condid] for condid in grounded_condids),
                        []
                    ),
                    sense,
                    b,
                )
                description: int = self.__get_description(
                    cid,
                    grounded_condids
                )
                lpconstraints.append((lpconstraint, description))
        self.cids_grounded_constraints[cid] = lpconstraints
        return lpconstraints
