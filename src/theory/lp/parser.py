"""_summary_
"""

#Import#########################################################################

from clingo import (
    TheoryAtom,
    TheoryElement,
    TheoryTerm,
    TheoryTermType,
)

from typing import Dict, List, Literal, Tuple, Union

#Type#Alias#####################################################################

Term = Tuple[float, str]
Variable = Tuple[str, Union[float, None], Union[float, None]]
AffineExpr = List[Term]
AffineExprData = Dict[int, List[Term]]
LpOperator = Literal['<=', '>=', '=']

CType = Literal['assert', 'constraint', 'dom', 'objective']

DomainData = Tuple[Literal['dom'], str, float, float]
DomainLp = Tuple[Literal['dom'], str, float, float]

ObjectiveData = Tuple[Literal['objective'], AffineExprData, int, int]
ObjectiveLp = Tuple[Literal['objective'], AffineExpr, int, int]

ConstraintData = Tuple[Literal['constraint'],
                       AffineExprData, LpOperator, float]
ConstraintLp = Tuple[Literal['constraint'], AffineExpr, LpOperator, float]

AssertData = Tuple[Literal['assert'], AffineExprData, LpOperator, float]
AssertLp = Tuple[Literal['assert'], AffineExpr, LpOperator, float]

ConstraintAtom = Union[AssertData, ConstraintData, DomainData, ObjectiveData]
Constraint = Union[AssertLp, ConstraintLp, DomainLp, ObjectiveLp]

#Clingo#Term#Parsing############################################################


def parse_atom(atom: TheoryAtom) -> Tuple[str, ConstraintAtom]:
    """_summary_

    :param term: _description_
    :type term: TheoryAtom
    :return: _description_
    :rtype: Constraint
    """
    if atom.term.name == 'dom':
        pid: str = str(atom.term.arguments[0])
        return (pid, parse_lpdomain(atom))
    if atom.term.name == 'maximize' or atom.term.name == 'minimize':
        pid: str = str(atom.term.arguments[0])
        return (pid, parse_objective(atom))
    if atom.term.name == 'sum':
        pid: str = str(atom.term.arguments[0])
        return (pid, parse_constraint(atom))
    if atom.term.name == 'assert':
        pid: str = str(atom.term.arguments[0])
        return (pid, parse_assert(atom))
    print('Error: Unknown theory atom:', atom)
    exit(0)


def parse_lpdomain(atom: TheoryAtom) -> DomainData:
    """_summary_

    :param atom: _description_
    :type atom: TheoryAtom
    :return: _description_
    :rtype: DomainData
    """
    assert(atom.term.name == 'dom')
    assert(len(atom.elements) == 1)
    assert(len(atom.elements[0].terms) == 1)
    assert(atom.elements[0].terms[0].name == '..')
    lower_term: TheoryTerm = atom.elements[0].terms[0].arguments[0]
    upper_term: TheoryTerm = atom.elements[0].terms[0].arguments[1]

    lower_bound: float = parse_numeric(lower_term)
    upper_bound: float = parse_numeric(upper_term)

    assert(atom.guard[0] == '=')
    variable: str = parse_str(atom.guard[1])

    return ('dom', variable, lower_bound, upper_bound)


def parse_objective(atom: TheoryAtom) -> ObjectiveData:
    """_summary_

    :param atom: _description_
    :type atom: TheoryAtom
    :return: _description_
    :rtype: ObjectiveData
    """
    if atom.term.name == 'maximize':
        direction: int = -1
    elif atom.term.name == 'minimize':
        direction: int = 1
    else:
        print('Error: unknown theory atom:', atom)
        exit(0)
    weight: int = 1
    affine_expr: AffineExprData = parse_affineExpr(atom.elements)
    return ('objective', affine_expr, direction, weight)


def parse_constraint(atom: TheoryAtom) -> ConstraintData:
    """_summary_

    :param atom: _description_
    :type atom: TheoryAtom
    :return: _description_
    :rtype: ConstraintData
    """
    assert(atom.term.name == 'sum')
    affine_expr: AffineExprData = parse_affineExpr(atom.elements)
    op: LpOperator = atom.guard[0]
    bound: float = parse_numeric(atom.guard[1])
    return ('constraint', affine_expr, op, bound)


def parse_assert(atom: TheoryAtom) -> AssertData:
    """_summary_

    :param atom: _description_
    :type atom: TheoryAtom
    :return: _description_
    :rtype: AssertData
    """
    assert(atom.term.name == 'assert')
    affine_expr: AffineExprData = parse_affineExpr(atom.elements)
    op: LpOperator = atom.guard[0]
    bound: float = parse_numeric(atom.guard[1])
    return ('assert', affine_expr, op, bound)


def parse_affineExpr(elements: List[TheoryElement]) -> AffineExprData:
    """_summary_

    :param elements: _description_
    :type elements: List[TheoryElement]
    :return: _description_
    :rtype: AffineExprData
    """
    affine_expr: AffineExprData = {}
    for element in elements:
        element: TheoryElement
        condid: int = element.condition_id
        term: Term = parse_term(element.terms[0])
        affine_expr.setdefault(condid, []).append(term)
    return affine_expr


def parse_term(term: TheoryTerm) -> Term:
    """_summary_

    :param term: _description_
    :type term: TheoryTerm
    :return: _description_
    :rtype: Term
    """
    term_type: TheoryTermType = term.type
    if term_type is TheoryTermType.Symbol:
        try:
            float(term.name.strip('"'))
            print('Non valid LP variable name:', term.name)
            exit(0)
        except:
            return (1, term.name)
    if term_type is TheoryTermType.Function:
        term_name: str = term.name
        assert(term_name not in ['+', '/', '..'])
        if term_name == '*':
            weight: float = parse_numeric(term.arguments[0])
            variable: str = parse_str(term.arguments[1])
            return (weight, variable)
        if term_name == '-':
            assert(len(term.arguments) == 1)
            variable: str = parse_str(term.arguments[0])
            return (-1, variable)
        return (1, parse_str(term))
    print('Format error: ', term)
    exit(0)


def parse_numeric(term: TheoryTerm) -> float:
    """_summary_

    :param term: _description_
    :type term: TheoryTerm
    :return: _description_
    :rtype: float
    """
    term_type: TheoryTermType = term.type
    if term_type is TheoryTermType.Number:
        return term.number
    if term_type is TheoryTermType.Symbol:
        return float(term.name.strip('"'))
    if term_type is TheoryTermType.Function:
        assert(term.name in ['+', '-', '*', '/'])
        parsed_args = [
            parse_numeric(arg) for arg in term.arguments
        ]
        if term.name == '+':
            return parsed_args[0] + parsed_args[1]
        elif term.name == '-':
            if len(parsed_args) == 1:
                return -parsed_args[0]
            return parsed_args[0] - parsed_args[1]
        elif term.name == '*':
            return parsed_args[0] * parsed_args[1]
        elif term.name == '/':
            return parsed_args[0] / parsed_args[1]


def parse_str(term: TheoryTerm) -> Variable:
    """_summary_

    :param term: _description_
    :type term: TheoryTerm
    :return: _description_
    :rtype: str
    """
    term_type: TheoryTermType = term.type
    if term_type is TheoryTermType.Number:
        return str(term.number)
    if term_type is TheoryTermType.Symbol:
        return term.name
    return str(term)
