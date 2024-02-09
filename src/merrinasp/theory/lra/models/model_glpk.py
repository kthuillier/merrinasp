# -*- coding=utf-8 -*-

# ==============================================================================
# IMPORT
# ==============================================================================

from __future__ import annotations
from typing import Any

from swiglpk import (  # type: ignore
    glp_get_col_prim,
    GLP_CV,
    GLP_FEAS,
    GLP_INFEAS,
    GLP_NOFEAS,
    GLP_OPT,
    GLP_UNBND,
    glp_set_col_kind,
    glp_find_row,
    glp_get_obj_val,
    glp_set_obj_dir,
    glp_init_smcp,
    GLP_MIN,
    glp_smcp,
    GLP_OFF,
    glp_term_out,
    glp_create_index,
    glp_create_prob,
    glp_get_num_rows,
    glp_get_num_cols,
    glp_get_col_name,
    glp_set_prob_name,
    glp_set_obj_coef,
    glp_simplex,
    glp_get_status,
    glp_add_cols,
    glp_set_col_name,
    intArray,
    glp_add_rows,
    glp_set_row_name,
    doubleArray,
    glp_set_mat_row,
    glp_set_col_bnds,
    glp_set_row_bnds,
    GLP_FR,
    GLP_UP,
    GLP_LO,
    GLP_FX,
    glp_del_rows,
    glp_get_mat_row,
    glp_get_row_ub,
    glp_get_row_type,
    glp_get_row_lb,
    glp_get_row_name,
    glp_get_obj_coef,
    glp_adv_basis,
    glp_scale_prob,
    GLP_SF_AUTO
)


from merrinasp.theory.lra.models.interface import (
    ModelInterface,
    Sense,
    LpStatus
)

# ==============================================================================
# Type Alias
# ==============================================================================

ExistsConstraint = tuple[list[tuple[float, str]], Sense, float]
ForallConstraint = tuple[list[tuple[float, str]], Sense, float]

# ==============================================================================
# Globals
# ==============================================================================

INFINITY: float = 10*9

# ==============================================================================
# Lp Models
# ==============================================================================


class ModelGLPK(ModelInterface):

    def __init__(self: ModelGLPK, lpsolver: str, pid: str,
                 epsilon: float = 10**-6) \
            -> None:
        super().__init__(lpsolver, pid, epsilon=epsilon)
        # ----------------------------------------------------------------------
        # Problem structure
        # ----------------------------------------------------------------------
        self.constraints_exists: dict[int, ExistsConstraint] = {}
        self.constraints_forall: dict[int, ForallConstraint] = {}

        # ----------------------------------------------------------------------
        # Model data
        # ----------------------------------------------------------------------
        self.model: Any = self._lpinit(pid)
        self.default_objective: list[tuple[float, str]] = \
            self._get_lpobjective()
        self.variables: dict[str, int] = {}
        self.constraints: dict[int, str] = {}

    # ==========================================================================
    # Methods dedicated to the GUROBI solver
    # ==========================================================================

    def _lpinit(self: ModelGLPK, pid: str) -> Any:
        model: Any = glp_create_prob()
        glp_create_index(model)
        glp_set_prob_name(model, f'PID_{pid}')
        glp_set_obj_dir(model, GLP_MIN)
        self.__smcp = glp_smcp()
        glp_init_smcp(self.__smcp)
        glp_term_out(GLP_OFF)
        return model

    def _add_lpvariable(self: ModelGLPK, varname: str) -> int:
        glp_add_cols(self.model, 1)
        index = glp_get_num_cols(self.model)
        glp_set_col_name(self.model, index, varname)
        glp_set_col_bnds(self.model, index, GLP_FR, 0., 0.)
        glp_set_col_kind(self.model, index, GLP_CV)
        return index

    def _get_lpobjective(self: ModelGLPK) -> list[tuple[float, str]]:
        objective: list[tuple[float, str]] = []
        for varindex in range(glp_get_num_cols(self.model)):
            varname: str = glp_get_col_name(self.model, varindex)
            coeff: float = glp_get_obj_coef(self.model, varindex)
            objective.append((coeff, varname))
        return objective

    def _add_lpobjective(self: ModelGLPK,
                         expr: list[tuple[float, str]]) \
            -> list[tuple[float, str]]:
        return self._get_lpexpression(expr)

    def _set_lpobjective(self: ModelGLPK, objective: list[tuple[float, str]]) \
            -> None:
        self.__reset_lpobjective()
        for coeff, varname in objective:
            assert varname in self.variables
            varindex: int = self.variables[varname]
            glp_set_obj_coef(self.model, varindex, float(coeff))
        self.__clear_unused_lpvariable()

    def _get_lpexpression(self: ModelGLPK,
                          expr: list[tuple[float, str]]) \
            -> list[tuple[float, str]]:
        return expr

    def _add_lpconstraint(self: ModelGLPK, cid: int) -> str:
        expression, sense, b = self.constraints_exists[cid]
        glp_add_rows(self.model, 1)
        index: int = glp_get_num_rows(self.model)
        consname: str = f'cons_{cid}'
        glp_set_row_name(self.model, index, consname)

        num_cols: int = glp_get_num_cols(self.model)
        num_vars: int = len(expression)
        index_array: intArray = intArray(num_cols + 1)
        value_array: doubleArray = doubleArray(num_cols + 1)
        for i, (coeff, varname) in enumerate(expression):
            assert varname in self.variables
            varindex: int = self.variables[varname]
            index_array[i + 1] = varindex
            value_array[i + 1] = coeff
        glp_set_mat_row(self.model, index, num_vars, index_array, value_array)

        if sense == '<=':
            glp_set_row_bnds(self.model, index, GLP_UP, 0., b)
        elif sense == '>=':
            glp_set_row_bnds(self.model, index, GLP_LO, b, 0.)
        else:
            glp_set_row_bnds(self.model, index, GLP_FX, b, b)

        return consname

    # def _remove_lpconstraint(self: ModelGLPK, constraint: str) -> None:
    #     index: int = glp_find_row(self.model, constraint)
    #     if index == 0:
    #         return
    #     last_index: int = glp_get_num_rows(self.model)
    #     self.__switch_rows(index, last_index)
    #     num = intArray(2)
    #     num[1] = last_index
    #     glp_del_rows(self.model, 1, num)
    #     self.__clear_unused_lpvariable()

    def _remove_lpconstraint(self: ModelGLPK, constraint: str) -> None:
        index: int = glp_find_row(self.model, constraint)
        if index == 0:
            return
        num = intArray(2)
        num[1] = index
        glp_del_rows(self.model, 1, num)
        self.__clear_unused_lpvariable()

    def _lpsolve(self: ModelGLPK) -> tuple[LpStatus, float | None]:
        glp_scale_prob(self.model, GLP_SF_AUTO)
        status: LpStatus = self.__lpsolve_glpk()
        if status == 'undefined':
            glp_adv_basis(self.model, 0)
            status = self.__lpsolve_glpk()
        if status == 'optimal':
            return status, glp_get_obj_val(self.model)
        return status, None

    def _get_lpvalue(self: ModelGLPK, varname: str) -> float | None:
        assert varname in self.variables
        varindex: int = self.variables[varname]
        return glp_get_col_prim(self.model, varindex)

    # ==========================================================================
    # Methods dedicated to the GLPK solver
    # ==========================================================================

    def __clear_unused_lpvariable(self: ModelGLPK) -> None:
        #  TODO: remove unused variables, i.e. variables associated with
        # zeros columns
        pass

    def __reset_lpobjective(self: ModelGLPK) -> None:
        for varindex in self.variables.values():
            glp_set_obj_coef(self.model, varindex, 0.)

    def __lpsolve_glpk(self: ModelGLPK) -> LpStatus:
        glp_simplex(self.model, self.__smcp)
        glpk_status: int = glp_get_status(self.model)
        status: LpStatus = 'undefined'
        if glpk_status in [GLP_OPT, GLP_FEAS]:
            status = 'optimal'
        elif glpk_status in [GLP_INFEAS, GLP_NOFEAS]:
            status = 'infeasible'
        elif glpk_status == GLP_UNBND:
            status = 'unbounded'
        return status

    def __switch_rows(self: ModelGLPK, i: int, j: int) -> None:
        if i == j:
            return
        #  ----------------------------------------------------------------------
        #  Switch names
        #  ----------------------------------------------------------------------
        i_name: str = glp_get_row_name(self.model, i)
        j_name: str = glp_get_row_name(self.model, j)
        glp_set_row_name(self.model, i, j_name)
        glp_set_row_name(self.model, j, i_name)
        #  ----------------------------------------------------------------------
        # Switch bounds
        #  ----------------------------------------------------------------------
        i_type: Any = glp_get_row_type(self.model, i)
        i_lb: float = glp_get_row_lb(self.model, i)
        i_ub: float = glp_get_row_ub(self.model, i)
        j_type: Any = glp_get_row_type(self.model, j)
        j_lb: float = glp_get_row_lb(self.model, j)
        j_ub: float = glp_get_row_ub(self.model, j)
        glp_set_row_bnds(self.model, i, j_type, j_lb, j_ub)
        glp_set_row_bnds(self.model, j, i_type, i_lb, i_ub)
        # ----------------------------------------------------------------------
        # Switch coefficients
        # ----------------------------------------------------------------------
        num_cols: int = glp_get_num_cols(self.model)
        i_index_array: intArray = intArray(num_cols + 1)
        j_index_array: intArray = intArray(num_cols + 1)
        i_value_array: doubleArray = doubleArray(num_cols + 1)
        j_value_array: doubleArray = doubleArray(num_cols + 1)
        i_num: int = \
            glp_get_mat_row(self.model, i, i_index_array, i_value_array)
        j_num: int = \
            glp_get_mat_row(self.model, j, j_index_array, j_value_array)
        glp_set_mat_row(self.model, i, j_num, j_index_array, j_value_array)
        glp_set_mat_row(self.model, j, i_num, i_index_array, i_value_array)
