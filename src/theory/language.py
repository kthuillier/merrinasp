"""_summary_
"""

#Import#########################################################################

from clingo import (
    Control,
    String
)

from clingo.ast import (
    AST,
    Function,
    ProgramBuilder,
    SymbolicTerm,
    Transformer,
    parse_files,
)

from typing import Sequence

#Theory#Language################################################################

THEORY_LANGUAGE = """
#theory opt {
    continuous_term {
        - : 2, unary;
        * : 1, binary, left;
        / : 1, binary, left;
        + : 0, binary, left;
        - : 0, binary, left
    };
    constant {
        - : 0, unary
    };
    domain_term {
        - : 4, unary;
        * : 3, binary, left;
        / : 2, binary, left;
        + : 1, binary, left;
        - : 1, binary, left;
        .. : 0, binary, left
    };

    &dom/1 : domain_term, {=}, continuous_term, head;

    &sum/1 : continuous_term, {=, <=, >=}, continuous_term, head;

    &minimize/1 : continuous_term, head;
    &maximize/1 : continuous_term, head;

    &assert/1 : continuous_term, {=, <=, >=, <, >}, continuous_term, head
}.
"""

#Auxiliary#Functions############################################################


def rewrite(ctrl: Control, files: Sequence[str]):
    with ProgramBuilder(ctrl) as builder:
        hbt = HeadBodyTransformer()
        parse_files(
            files,
            lambda stm: builder.add(hbt.visit(stm))
        )


class HeadBodyTransformer(Transformer):
    """_summary_

    :param Transformer: _description_
    :type Transformer: _type_
    """

    def visit_Literal(self, lit: AST, in_lit: bool = False) -> AST:
        """_summary_

        :param lit: _description_
        :type lit: AST
        :param in_lit: _description_, defaults to False
        :type in_lit: bool, optional
        :return: _description_
        :rtype: AST
        """
        return lit.update(**self.visit_children(lit, True))

    def visit_TheoryAtom(self, atom: AST, in_lit: bool = False) -> AST:
        """_summary_

        :param atom: _description_
        :type atom: AST
        :param in_lit: _description_, defaults to False
        :type in_lit: bool, optional
        :return: _description_
        :rtype: AST
        """
        theory_op = ['dom', 'sum', 'maximize', 'minimize', 'assert']

        term = atom.term
        if term.name in theory_op and not term.arguments:
            atom.term = Function(
                term.location,
                term.name,
                [
                    Function(
                        term.location,
                        'pid',
                        [SymbolicTerm(term.location, String('default'))],
                        False
                    )
                ],
                False
            )
        return atom
