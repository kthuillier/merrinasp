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
)

from theory.language import THEORY_LANGUAGE, rewrite

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
                    "   <arg>: {coin, gurobi, cplex} (default lp-solver=coin)",
                    self.parse_lp_solver_option)

        options.add_flag(group, "show-continous-solution",
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

    def __on_model(self, model: Model) -> None:
        """_summary_

        :param model: _description_
        :type model: Model
        """
        assignment = self.opt_propagator.assignment(model.thread_id)
        if assignment is not None:
            (opt, values) = assignment
            model.extend(
                [Function(
                    '_continous_optimum',
                    [
                        String(str(opt))
                    ]
                )])
            for name in values:
                model.extend(
                    [Function(
                        '_continous_solution',
                        [
                            Function(name, []),
                            String(str(values[name]))
                        ]
                    )])

    def __on_statistics(self, step: StatisticsMap, acc: StatisticsMap) -> None:
        """_summary_

        :param step: _description_
        :type step: StatisticsMap
        :param accumulated: _description_
        :type accumulated: StatisticsMap
        """
        pass

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
