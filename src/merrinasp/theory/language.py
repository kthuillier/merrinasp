# -*- coding=utf-8 -*-

# ==============================================================================
# IMPORT
# ==============================================================================

from __future__ import annotations

from math import nan
from typing import Literal
import sys

from clingo import (
    Control,
    String,
    Number,
    TheoryAtom,
    TheoryElement,
    TheoryTerm,
    TheoryTermType,
)

from clingo.ast import (
    AST,
    Function,
    ProgramBuilder,
    SymbolicTerm,
    Transformer,
    parse_files,
    TheoryGuard
)

# ==============================================================================
# Types
# ==============================================================================

LpOperator = Literal['dom', 'sum', 'maximize', 'minimize', 'assert']

ParsedLpConstraint = tuple[
    Literal['exists', 'forall', 'objective'],
    str,
    dict[int, list[tuple[float, str]]],
    Literal['=', '<=', '>='],
    float,
]

LpConstraint = tuple[
    Literal['exists', 'forall', 'objective'],
    list[tuple[float, str]],
    Literal['<=', '>=', '='],
    float
]

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

    &minimize/1 : continuous_term, {@}, constant, head;
    &maximize/1 : continuous_term, {@}, constant, head;

    &assert/1 : continuous_term, {=, <=, >=, <, >}, continuous_term, head
}.
"""

THEORY_OPERATORS: list[LpOperator] = [
    'dom', 'sum', 'maximize', 'minimize', 'assert']

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
                        [SymbolicTerm(
                            term.location,  # type: ignore
                            String('default'))],
                        False
                    )
                ],
                False
            )
        if term.name in ['minimize', 'maximize'] and not atom.guard:  # type: ignore
            atom.guard = TheoryGuard(
                '@',
                SymbolicTerm(term.location, Number(0))  # type: ignore
            )
        return atom


def rewrite(ctrl: Control, files: list[str]) -> None:
    with ProgramBuilder(ctrl) as builder:
        hbt = HeadBodyTransformer()
        parse_files(
            files,
            lambda stm: builder.add(hbt.visit(stm))
        )

# ==============================================================================
# PARSERS
# ==============================================================================

# ------------------------------------------------------------------------------
# Theory Atoms
# ------------------------------------------------------------------------------


def parse_atom(atom: TheoryAtom) -> list[ParsedLpConstraint]:
    atom_op: LpOperator = atom.term.name  # type: ignore
    if atom_op == 'dom':
        return parse_lpdomain(atom)
    if atom_op in ('maximize', 'minimize'):
        return parse_objective(atom)
    if atom_op == 'sum':
        return parse_constraint(atom)
    if atom_op == 'assert':
        return parse_assert(atom)
    print('Error: Unknown theory atom:', atom)
    sys.exit(0)

# ------------------------------------------------------------------------------
# Constraints
# ------------------------------------------------------------------------------


def parse_lpdomain(atom: TheoryAtom) -> list[ParsedLpConstraint]:
    # --------------------------------------------------------------------------
    # Ensure the atom structure -   `&dom(pid){L..U}=V`
    # --------------------------------------------------------------------------
    assert len(atom.elements) == 1
    assert len(atom.elements[0].terms) == 1
    assert atom.elements[0].terms[0].name == '..'
    # --------------------------------------------------------------------------
    # Parse bounds
    # --------------------------------------------------------------------------
    lower_bound: float = parse_numeric(
        atom.elements[0].terms[0].arguments[0]
    )
    upper_bound: float = parse_numeric(
        atom.elements[0].terms[0].arguments[1]
    )
    # --------------------------------------------------------------------------
    # Variable
    # --------------------------------------------------------------------------
    guard: tuple[str, TheoryTerm] | None = atom.guard
    assert guard is not None
    assert guard[0] == '='
    variable: str = parse_str(guard[1])
    # --------------------------------------------------------------------------
    # Constraints
    # --------------------------------------------------------------------------
    pid: str = str(atom.term.arguments[0])
    expr: dict[int, list[tuple[float, str]]] = {0: [(1, variable)]}
    if lower_bound == upper_bound:
        return [('exists', pid, expr, '=', lower_bound)]
    return [
        ('exists', pid, expr, '>=', lower_bound),
        ('exists', pid, expr, '<=', upper_bound),
    ]


def parse_objective(atom: TheoryAtom) -> list[ParsedLpConstraint]:
    # --------------------------------------------------------------------------
    # Parse direction
    # --------------------------------------------------------------------------
    name: str = atom.term.name
    direction: Literal['<=', '>='] = '>='
    if name == 'maximize':
        direction = '<='
    elif name == 'minimize':
        direction = '>='
    else:
        print('Error: unknown theory atom:', atom)
        sys.exit(0)
    weight: int = atom.guard[1].number  # type: ignore
    # --------------------------------------------------------------------------
    # Parse expression
    # --------------------------------------------------------------------------
    pid: str = str(atom.term.arguments[0])
    affine_expr: dict[int, list[tuple[float, str]]] = parse_expr(
        atom.elements
    )
    return [('objective', pid, affine_expr, direction, weight)]


def parse_constraint(atom: TheoryAtom) -> list[ParsedLpConstraint]:
    # --------------------------------------------------------------------------
    # Parse bound
    # --------------------------------------------------------------------------
    guard: tuple[str, TheoryTerm] | None = atom.guard
    assert guard is not None
    op: Literal['=', '<=', '>='] = guard[0]  # type: ignore
    bound: float = parse_numeric(guard[1])
    # --------------------------------------------------------------------------
    # Parse expression
    # --------------------------------------------------------------------------
    pid: str = str(atom.term.arguments[0])
    affine_expr: dict[int, list[tuple[float, str]]] = parse_expr(
        atom.elements
    )
    return [('exists', pid, affine_expr, op, bound)]


def parse_assert(atom: TheoryAtom) -> list[ParsedLpConstraint]:
    # --------------------------------------------------------------------------
    # Parse bound
    # --------------------------------------------------------------------------
    guard: tuple[str, TheoryTerm] | None = atom.guard
    assert guard is not None
    op: Literal['=', '<=', '>='] = guard[0]  # type: ignore
    bound: float = parse_numeric(guard[1])
    # --------------------------------------------------------------------------
    # Parse expression
    # --------------------------------------------------------------------------
    pid: str = str(atom.term.arguments[0])
    affine_expr: dict[int, list[tuple[float, str]]] = parse_expr(
        atom.elements
    )
    # --------------------------------------------------------------------------
    # Build constraints
    # --------------------------------------------------------------------------
    if op == '=':
        return [('forall', pid, affine_expr, '<=', bound),
                ('forall', pid, affine_expr, '>=', bound)]
    return [('forall', pid, affine_expr, op, bound)]


# ------------------------------------------------------------------------------
# Affine Expression - Conditions
# ------------------------------------------------------------------------------

def parse_expr(elements: list[TheoryElement]) -> dict[int,
                                                      list[tuple[float, str]]]:
    affine_expr: dict[int, list[tuple[float, str]]] = {}
    for element in elements:
        condid: int = element.condition_id
        term: tuple[float, str] = parse_term(element.terms[0])
        affine_expr.setdefault(condid, []).append(term)
    return affine_expr


def parse_term(term: TheoryTerm) -> tuple[float, str]:
    term_type: TheoryTermType = term.type
    if term_type is TheoryTermType.Symbol:
        return parse_term_symbol(term)
    if term_type is TheoryTermType.Function:
        return parse_term_function(term)
    print('Format error: ', term)
    sys.exit(0)


def parse_term_symbol(term: TheoryTerm) -> tuple[float, str]:
    name: str = term.name
    try:
        float(name.strip('"'))
        print('Non valid LP variable name:', name)
        sys.exit(0)
    except ValueError:
        return (1, name)


def parse_term_function(term: TheoryTerm) -> tuple[float, str]:
    name: str = term.name
    variable: str = ''
    assert name not in ['+', '/', '..']
    if name == '*':
        weight: float = parse_numeric(term.arguments[0])
        variable = parse_str(term.arguments[1])
        return (weight, variable)
    if name == '-':
        assert len(term.arguments) == 1
        variable = parse_str(term.arguments[0])
        return (-1, variable)
    return (1, parse_str(term))

# ------------------------------------------------------------------------------
# Basic Types
# ------------------------------------------------------------------------------


def parse_numeric(term: TheoryTerm) -> float:
    term_type: TheoryTermType = term.type
    if term_type is TheoryTermType.Number:
        return term.number
    if term_type is TheoryTermType.Symbol:
        return float(term.name.strip('"'))
    if term_type is TheoryTermType.Function:
        assert (term.name in ['+', '-', '*', '/'])
        return parse_numeric_function(term)
    return nan


def parse_numeric_function(term: TheoryTerm) -> float:
    parsed_args = [
        parse_numeric(arg) for arg in term.arguments
    ]
    if term.name == '+':
        return parsed_args[0] + parsed_args[1]
    if term.name == '-':
        if len(parsed_args) == 1:
            return -parsed_args[0]
        return parsed_args[0] - parsed_args[1]
    if term.name == '*':
        return parsed_args[0] * parsed_args[1]
    if term.name == '/':
        return parsed_args[0] / parsed_args[1]
    return nan


def parse_str(term: TheoryTerm) -> str:
    term_type: TheoryTermType = term.type
    if term_type is TheoryTermType.Number:
        return str(term.number)
    if term_type is TheoryTermType.Symbol:
        return term.name
    return str(term)
