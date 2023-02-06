"""_summary_
"""

#Import#########################################################################

from clingo import (
    ApplicationOptions,
    Control,
    Flag,
    Function,
    Model,
    SolveResult,
    StatisticsMap,
    String,
    clingo_main,
    solving,
)

from .theory.language import THEORY_LANGUAGE, rewrite
from .theory.propagator import OptPropagator

from sys import argv, exit
from typing import Dict, List

#Class#Application##############################################################


class Application:
    """_summary_
    """

    def __init__(self):
        """_summary_
        """
        self.program_name: str = 'clingopt'
        self.version: str = '0.0.1'
        self.opt_propagator = None
        self.lp_solver: str = 'coin'
        self.lp_epsilon: float = 10**-3
        self.show_continous_solutions_flag: Flag = Flag(False)
        self.continous_assignment: Dict[str, float] = None
        self.show_traces_flag: Flag = Flag(False)

    #Clingo#Function#Overwrite##################################################

    def register_options(self, options: ApplicationOptions) -> None:
        """_summary_

        :param options: _description_
        :type options: ApplicationOptions
        """
        group: str = 'ClingOPT Options'
        options.add(group, "lp-solver",
                    "Set LP solver\n"
                    "   <arg>: {cbc, gurobi, cplex} (default lp-solver=cbc)",
                    self.parse_lp_solver_option)

        options.add_flag(group, "show-opt-solution",
                         "Show LP solution and value of objective function",
                         self.show_continous_solutions_flag)

        options.add_flag(group, "trace",
                         "Enables detailed output of theory propagation",
                         self.show_traces_flag)

    def parse_lp_solver_option(self, s: str) -> bool:
        """_summary_

        :param s: _description_
        :type s: str
        :return: _description_
        :rtype: bool
        """
        if s in ['coin', 'cplex', 'gurobi']:
            self.lp_solver = s
            return True
        return False

    def validate_options(self) -> bool:
        """_summary_

        :return: _description_
        :rtype: bool
        """
        return True

    def main(self, control: Control, files: List[str]) -> None:
        """_summary_

        :param control: _description_
        :type control: Control
        :param files: _description_
        :type files: List[str]
        """

        # Initialize the contraint propagator
        self.opt_propagator = OptPropagator()
        control.register_propagator(self.opt_propagator)

        if not files:
            files = ['-']
        # Parse the input file with the theory language
        control.add('base', [], THEORY_LANGUAGE)
        rewrite(control, files)

        control.ground([('base', [])])

        control.solve(
            on_model=self.__on_model,
            on_statistics=self.__on_statistics,
            on_finish=self.__on_finish,
            yield_=False,
            async_=False,
        )

    #Auxiliary#Functions########################################################

    def print_model(self, model: solving.Model, _: Function) -> None:
        print(' '.join(
            f'{s}' for s in model.symbols(shown=True)
        ))
        if self.show_continous_solutions_flag.flag:
            assignments = self.opt_propagator.get_assignment(model.thread_id)
            print('LP Solutions:')
            for pid in sorted(assignments.keys()):
                pid: str
                align: int = 4
                pid_assignment, pid_optimum = assignments[pid]
                pid_optimum_str: List[str] = [str(opt) for opt in pid_optimum]
                if len(assignments) != 1:
                    print(f'    PID {pid}:')
                    align = 8
                # Status + Optimum
                if len(pid_optimum) != 0:
                    print(
                        ' ' * align + f'Optimums: {"; ".join(pid_optimum_str)}'
                    )
                is_unbounded: bool = float('inf') in pid_optimum or \
                    float('-inf') in pid_optimum
                # Variables
                if len(pid_optimum) == 0 or not is_unbounded:
                    variables_str: str = '; '.join(
                        f'{var_name} = {var_value}'
                        for var_name, var_value in sorted(pid_assignment)
                    )
                    print(' ' * align + f'{{ {variables_str} }}')
                
    def __on_model(self, model: Model) -> None:
        """_summary_

        :param model: _description_
        :type model: Model
        """
        pass
    
    def __on_statistics(self, step: StatisticsMap, acc: StatisticsMap) -> None:
        if len(self.statistics) != 0:
            statistics = self.opt_propagator.get_statistics(0)
            acc['Propagator'] = statistics

    def __on_finish(self, state: SolveResult) -> None:
        """_summary_

        :param state: _description_
        :type state: SolveResult
        """
        pass


def clingopt_main() -> None:
    """_summary_
    """
    exit(int(clingo_main(Application(), argv[1:])))


if __name__ == '__main__':
    clingopt_main()
