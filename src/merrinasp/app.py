# -*- coding=utf-8 -*-

# ==============================================================================
# IMPORT
# ==============================================================================

from __future__ import annotations
import sys

from clingo import (
    ApplicationOptions,
    Control,
    Flag,
    StatisticsMap,
    clingo_main,
    solving,
)

from merrinasp.theory.language import THEORY_LANGUAGE, rewrite
from merrinasp.theory.propagator import LpPropagator
from merrinasp.theory.lra.models import AVAILABLE_LPSOLVERS

# ==============================================================================
# Application class
# ==============================================================================

# ==============================================================================
# Application class
# ==============================================================================


class Application:

    def __init__(self: Application):
        self.program_name: str = 'merrinasp'
        self.version: str = '1.0.0'
        self.propagator: LpPropagator | None = None
        self.lpsolver: str = 'cbc'
        self.lp_epsilon: float = 10**-3
        self.show_lpassignments_flag: Flag = Flag(False)
        self.continous_assignment: dict[str, float] | None = None
        self.lazy_mode: Flag = Flag(False)
        self.strict_forall: Flag = Flag(False)

    # --------------------------------------------------------------------------
    # Clingo options
    # --------------------------------------------------------------------------

    def register_options(self: Application,
                         options: ApplicationOptions) -> None:
        group: str = 'MerrinASP Options'
        options.add(group, "lp-solver",
                    "Set LP solver\n" + \
                    f"   <arg>: {{ {', '.join(AVAILABLE_LPSOLVERS)} }} (default lp-solver=cbc)",
                    self.parse_lp_solver_option)

        options.add_flag(group, "show-opt-solution",
                         "Show LP solution and value of objective function",
                         self.show_lpassignments_flag)

        options.add_flag(group, "lazy-mode",
                         "Lazy SMT resolution (increase resolution speed)",
                         self.lazy_mode)

        options.add_flag(group, "strict-forall",
                         "Force the linear domains of forall constraints to be satisfiable",
                         self.strict_forall)

    def parse_lp_solver_option(self: Application, s: str) -> bool:
        if s in AVAILABLE_LPSOLVERS:
            self.lpsolver = s  # type: ignore
            return True
        return False

    def validate_options(self: Application) -> bool:
        return True

    # --------------------------------------------------------------------------
    # Problem resolution
    # --------------------------------------------------------------------------

    def main(self: Application, control: Control, files: list[str]) -> None:
        # Initialize the contraint propagator
        self.propagator = LpPropagator(lpsolver=self.lpsolver)
        self.propagator.lazy(self.lazy_mode.flag)
        self.propagator.show_lpassignment(self.show_lpassignments_flag.flag)
        self.propagator.strict_forall_check(not self.strict_forall.flag)
        control.register_propagator(self.propagator)  # type: ignore

        if not files:
            files = ['-']
        # Parse the input file with the theory language
        control.add('base', [], THEORY_LANGUAGE)
        rewrite(control, files)

        control.ground([('base', [])])

        control.solve(
            on_statistics=self.__on_statistics,
            yield_=False,
            async_=False,
        )

    # --------------------------------------------------------------------------
    # Auxiliary functions
    # --------------------------------------------------------------------------

    def print_model(self: Application, model: solving.Model, _) -> None:
        assert self.propagator is not None
        print(' '.join(
            f'{s}' for s in model.symbols(shown=True)
        ))
        if self.show_lpassignments_flag.flag:
            assignments = self.propagator.get_assignment(model.thread_id)
            print(assignments)
        # if self.show_lpassignments_flag.flag:
        #     assignments = self.propagator.get_assignment(model.thread_id)
        #     print('LP Solutions:')
        #     for pid in sorted(assignments.keys()):
        #         pid: str
        #         align: int = 4
        #         pid_assignment, pid_optimum = assignments[pid]
        #         pid_optimum_str: list[str] = [str(opt) for opt in pid_optimum]
        #         if len(assignments) != 1:
        #             print(' ' * align + f'PID {pid}:')
        #             align += 4
        #         # Status + Optimum
        #         if len(pid_optimum) != 0:
        #             print(
        #                 ' ' * align + f'Optimums: {"; ".join(pid_optimum_str)}'
        #             )
        #         is_unbounded: bool = float('inf') in pid_optimum or \
        #             float('-inf') in pid_optimum
        #         # Variables
        #         if len(pid_optimum) == 0 or not is_unbounded:
        #             variables_str: str = '; '.join(
        #                 f'{var_name} = {var_value}'
        #                 for var_name, var_value in sorted(pid_assignment)
        #             )
        #             print(' ' * align + f'{{ {variables_str} }}')

    def __on_statistics(self: Application, _: StatisticsMap,
                        acc: StatisticsMap) -> None:
        assert self.propagator is not None
        statistics = self.propagator.get_statistics()
        acc['Propagator'] = statistics

# ==============================================================================
# Main
# ==============================================================================


def main() -> None:
    sys.exit(int(clingo_main(Application(), sys.argv[1:])))  # type: ignore


if __name__ == '__main__':
    main()
