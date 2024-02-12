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
        self.lpsolver_calls_nb: int = 0
        self.lpsolver_calls_sum: float = 0
        self.cache_prevented_nb: int = 0
        self.cache_prevented_sum: float = 0
        self.cache_missed_nb: int = 0
        self.cache_missed_sum: float = 0
        self.cache_size: list[int] = [0, 0]
        self.conflicts_exists: int = 0
        self.conflicts_forall: int = 0
        self.model_updates_nb: int = 0
        self.model_updates_sum: float = 0
        self.model_backtracks_nb: int = 0
        self.model_backtracks_sum: float = 0

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
                    logger.model_updates_sum for logger in loggers
                ),
                'Backtracks (s)': sum(
                    logger.model_backtracks_sum for logger in loggers
                )
            },
            'Solving': {
                'Calls': sum(
                    logger.lpsolver_calls_nb for logger in loggers
                ),
                'Time (s)': sum(
                    logger.lpsolver_calls_sum for logger in loggers
                )
            },
            'Lp Cache': {
                'Cache guesses': sum(
                    logger.cache_prevented_nb for logger in loggers
                ),
                'Cache misses': sum(
                    logger.cache_missed_nb for logger in loggers
                ),
                'Cost (s)': sum(
                    logger.cache_missed_sum + logger.cache_prevented_sum
                    for logger in loggers
                ),
                'Size': {
                    'Current': max(
                        logger.cache_size[0]
                        for logger in loggers
                    ),
                    'Maximum': max(
                        logger.cache_size[1]
                        for logger in loggers
                    )
                }
            }
        }
        return statistics
