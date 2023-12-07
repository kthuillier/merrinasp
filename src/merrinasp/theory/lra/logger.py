# -*- coding=utf-8 -*-

# ==============================================================================
# IMPORT
# ==============================================================================

from __future__ import annotations

# ==============================================================================
# Logger
# ==============================================================================


class Logger:

    def __init__(self: Logger, pid: str) -> None:
        self.id: str = pid
        self.lpsolver_calls: list[float] = []
        self.cache_prevented: list[float] = []
        self.cache_missed: list[float] = []
        self.conflicts_exists: int = 0
        self.conflicts_forall: int = 0
        self.model_updates: list[float] = []
        self.model_backtracks: list[float] = []

    @classmethod
    def merge(cls: type[Logger],
              loggers: list[Logger]) -> dict[str, dict[str, float] | float]:
        statistics: dict = {}
        statistics['Partitions'] = len(loggers)
        statistics['Conflicts'] = {
            'Forall': sum(
                logger.conflicts_forall for logger in loggers
            ),
            'Exists': sum(
                logger.conflicts_exists for logger in loggers
            )
        }
        statistics['LP Solver'] = {
            'Modifications': {
                'Updates (s)': sum(
                    sum(logger.model_updates) for logger in loggers
                ),
                'Backtracks (s)': sum(
                    sum(logger.model_backtracks) for logger in loggers
                )
            },
            'Solving': {
                'Calls': sum(
                    len(logger.lpsolver_calls) for logger in loggers
                ),
                'Time (s)': sum(
                    sum(logger.lpsolver_calls) for logger in loggers
                )
            },
            'Lp Cache': {
                'Cache guesses': sum(
                    len(logger.cache_prevented) for logger in loggers
                ),
                'Cache misses': sum(
                    len(logger.cache_missed) for logger in loggers
                ),
                'Cost (s)': sum(
                    sum(logger.cache_missed) + sum(logger.cache_prevented)
                    for logger in loggers
                )
            }
        }
        return statistics
