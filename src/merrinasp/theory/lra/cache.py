# -*- coding=utf-8 -*-

# ==============================================================================
# IMPORT
# ==============================================================================

from __future__ import annotations
from typing import Iterable

# ==============================================================================
# Lp Cache
# ==============================================================================


class LpCache:

    def __init__(self: LpCache) -> None:
        self.cache: dict[tuple[tuple[int, ...], ...],
                         tuple[str, float | None]] = {}

    def add(self: LpCache, description: Iterable[tuple[int, ...]], status: str,
            optimum: float | None = None) -> None:
        description_: tuple[tuple[int, ...], ...] = tuple(sorted(description))
        self.cache[description_] = (status, optimum)

    def check(self: LpCache, description: Iterable[tuple[int, ...]]) \
            -> None | tuple[str, float | None]:
        description_: tuple[tuple[int, ...], ...] = tuple(sorted(description))
        return self.cache.get(description_, None)
