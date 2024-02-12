# -*- coding=utf-8 -*-

# ==============================================================================
# IMPORT
# ==============================================================================

from __future__ import annotations
from typing import Iterable

# ==============================================================================
# Type Alias
# ==============================================================================

CONSTRAINT = int
CFG = set[CONSTRAINT]
STATUS = tuple[CFG, float]

# ==============================================================================
# Lp Cache
# ==============================================================================


class LpCache:

    def __init__(self: LpCache) -> None:
        # ~ Cache size (used for statistics)
        self.__size: int = 0
        self.__maxsize: int = 0
        # ~ Borders
        self.__exist_sat_border: list[CFG] = []
        self.__exist_unsat_border: list[CFG] = []
        self.__forall_sat_border: dict[int | None,list[CFG]] = {}
        self.__forall_unsat_border: dict[int | None,list[CFG]] = {}

    def __add_exists_sat(self: LpCache, cfg: CFG) -> None:
        subset_cfgs: list[CFG] = []
        for cfg_ in self.__exist_sat_border:
            if cfg_.issuperset(cfg):
                return
            if cfg_.issubset(cfg):
                subset_cfgs.append(cfg_)
        self.__size -= len(subset_cfgs)
        for cfg_ in subset_cfgs:
            self.__exist_sat_border.remove(cfg_)
        self.__exist_sat_border.append(cfg)
        self.__size += 1
        self.__maxsize = max(self.__maxsize, self.__size)

    def __add_exists_unsat(self: LpCache, cfg: CFG) -> None:
        superset_cfgs: list[CFG] = []
        for cfg_ in self.__exist_unsat_border:
            if cfg_.issubset(cfg):
                return
            if cfg_.issuperset(cfg):
                superset_cfgs.append(cfg_)
        self.__size -= len(superset_cfgs)
        for cfg_ in superset_cfgs:
            self.__exist_unsat_border.remove(cfg_)
        self.__exist_unsat_border.append(cfg)
        self.__size += 1
        self.__maxsize = max(self.__maxsize, self.__size)

    def __add_forall_sat(self: LpCache, cfg: CFG, objective: int) -> None:
        if objective not in self.__forall_sat_border:
            self.__forall_sat_border[objective] = [cfg]
            return
        superset_cfgs: list[CFG] = []
        for cfg_ in self.__forall_sat_border[objective]:
            if cfg_.issubset(cfg):
                return
            if cfg_.issuperset(cfg):
                superset_cfgs.append(cfg_)
        self.__size -= len(superset_cfgs)
        for cfg_ in superset_cfgs:
            self.__forall_sat_border[objective].remove(cfg_)
        self.__forall_sat_border[objective].append(cfg)
        self.__size += 1
        self.__maxsize = max(self.__maxsize, self.__size)

    def __add_forall_unsat(self: LpCache, cfg: CFG, objective: int) -> None:
        if objective not in self.__forall_unsat_border:
            self.__forall_unsat_border[objective] = [cfg]
            return
        subset_cfgs: list[CFG] = []
        for cfg_ in self.__forall_unsat_border[objective]:
            if cfg_.issuperset(cfg):
                return
            if cfg_.issubset(cfg):
                subset_cfgs.append(cfg_)
        self.__size -= len(subset_cfgs)
        for cfg_ in subset_cfgs:
            self.__forall_unsat_border[objective].remove(cfg_)
        self.__forall_unsat_border[objective].append(cfg)
        self.__size += 1
        self.__maxsize = max(self.__maxsize, self.__size)

    def add(self: LpCache, description: Iterable[CONSTRAINT],
            objective: int | None, issat: bool) -> None:
        cfg: CFG = set(description)
        if objective is None:
            if issat:
                return self.__add_exists_sat(cfg)
            return self.__add_exists_unsat(cfg)
        if issat:
            return self.__add_forall_sat(cfg, objective)
        return self.__add_forall_unsat(cfg, objective)

    def __check_exists(self: LpCache, cfg: CFG) -> None | bool:
        is_sat: bool = any(
            cfg_.issuperset(cfg)
            for cfg_ in self.__exist_sat_border
        )
        if is_sat:
            return True
        is_unsat: bool = any(
            cfg_.issubset(cfg)
            for cfg_ in self.__exist_unsat_border
        )
        if is_unsat:
            return False
        return None

    def __check_forall(self: LpCache, cfg: CFG, objective: int) -> None | bool:
        is_sat: bool = any(
            cfg_.issubset(cfg)
            for cfg_ in self.__forall_sat_border.get(objective, [])
        )
        if is_sat:
            return True
        is_unsat: bool = any(
            cfg_.issuperset(cfg)
            for cfg_ in self.__forall_unsat_border.get(objective, [])
        )
        if is_unsat:
            return False
        return None

    def check(self: LpCache, description: Iterable[CONSTRAINT],
              objective: int | None) -> None | bool:
        cfg: CFG = set(description)
        if objective is None:
            return self.__check_exists(cfg)
        return self.__check_forall(cfg, objective)

    def get_size(self: LpCache) -> tuple[int, int]:
        return self.__size, self.__maxsize
