# -*- coding=utf-8 -*-

# ==============================================================================
# Imports
# ==============================================================================

from merrinasp.theory.lra.models.interface import ModelInterface
from merrinasp.theory.lra.models.model_pulp import ModelPuLP
from merrinasp.theory.lra.models.model_optlang import ModelOptlang
from merrinasp.theory.lra.models.model_gurobi import ModelGurobiPy

# ==============================================================================
# Globals
# ==============================================================================

AVAILABLE_LPSOLVERS: list[str] = [
    'gurobi',
    'cbc',
    'glpk',
    'cplex-optlang',
    'cplex-pulp'
]
