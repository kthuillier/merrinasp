# -*- coding=utf-8 -*-

# ==============================================================================
# Imports
# ==============================================================================

from merrinasp.theory.lra.models.interface import ModelInterface
from merrinasp.theory.lra.models.model_pulp import ModelPuLP
from merrinasp.theory.lra.models.model_optlang import ModelOptlang
from merrinasp.theory.lra.models.model_gurobi import ModelGurobiPy
from merrinasp.theory.lra.models.model_glpk import ModelGLPK

# ==============================================================================
# Globals
# ==============================================================================

AVAILABLE_LPSOLVERS: list[str] = [
    'gurobi',
    'gurobi-optlang',
    'gurobi-pulp',
    'cbc',
    'glpk',
    'glpk-optlang',
    'cplex-optlang',
    'cplex-pulp'
]
