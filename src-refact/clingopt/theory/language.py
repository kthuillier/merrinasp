# -*- coding=utf-8 -*-

# ==============================================================================
# IMPORT
# ==============================================================================

from __future__ import annotations

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

# ==============================================================================
# THEORY LANGUAGE for Linear constraints
# ==============================================================================

THEORY_LANGUAGE: str = """
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

THEORY_OPERATORS: list[str] = ['dom', 'sum', 'maximize', 'minimize', 'assert']

# ==============================================================================
# Clingo AST rewriter
# ==============================================================================


class HeadBodyTransformer(Transformer):

    def visit_Literal(self, lit: AST, _: bool = False) -> AST:
        return lit.update(**self.visit_children(lit, True))

    def visit_TheoryAtom(self, atom: AST, _: bool = False) -> AST:
        term = atom.term
        if term.name in THEORY_OPERATORS and not term.arguments:  # type: ignore
            atom.term = Function(
                term.location,  # type: ignore
                term.name,  # type: ignore
                [
                    Function(
                        term.location,  # type: ignore
                        'pid',
                        [SymbolicTerm(term.location, String('default'))], # type: ignore
                        False
                    )
                ],
                False
            )
        return atom


def rewrite(ctrl: Control, files: list[str]) -> None:
    with ProgramBuilder(ctrl) as builder:
        hbt = HeadBodyTransformer()
        parse_files(
            files,
            lambda stm: builder.add(hbt.visit(stm))
        )
