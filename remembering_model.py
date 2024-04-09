import sys
from typing import Hashable

from ortools.sat.python import cp_model

ModelVar = cp_model.IntVar | cp_model.BoolVarT
VarKey = tuple[Hashable, ...]
VarRecord = tuple[type[int] | type[bool], int | None, int | None, VarKey]


class KeyCollision(Exception):
    pass


# RememberingModel is an extension to cp_model.CpModel that remembers the vars you add to the model
# under a "key" which is a tuple passed when creating the var. It has no knowledge of the problem domain.
class RememberingModel:
    def __init__(self, debug: bool = False) -> None:
        self.debug = debug
        self.model = cp_model.CpModel()
        self.store: dict[VarKey, ModelVar] = {}
        self._check: dict[str, VarRecord] = {}

    def _var_name(self, var_type: type[int] | type[bool], lbound: int | None, ubound: int | None, key: VarKey) -> str:
        # For readability, we store variables under pretty simple names but here we make sure our model has
        # no collisions despite the simplicity of the variable names.
        name = " ".join(str(v) for v in key)
        record = (var_type, lbound, ubound, key)
        existing = self._check.get(name)
        if existing and existing != record:
            raise KeyCollision(f"{record} conflicts with {existing}")
        self._check[name] = record
        return name

    def add(self, constraint: cp_model.BoundedLinearExpression | bool) -> cp_model.Constraint:
        if self.debug:
            print("[MODEL][CON]", constraint, file=sys.stderr)
        return self.model.Add(constraint)

    def new_int_var(self, lbound: int, ubound: int, key: VarKey) -> cp_model.IntVar:
        name = self._var_name(int, lbound, ubound, key)
        v = self.model.NewIntVar(lbound, ubound, name)
        self.store[key] = v
        if self.debug:
            print("[MODEL][INT]", v, file=sys.stderr)
        return v

    def new_bool_var(self, key: VarKey) -> cp_model.BoolVarT:
        name = self._var_name(bool, None, None, key)
        v = self.model.NewBoolVar(name)
        self.store[key] = v
        if self.debug:
            print("[MODEL][BOOL]", v, file=sys.stderr)
        return v

    def maximize(self, objective: cp_model.ObjLinearExprT) -> None:
        self.model.Maximize(objective)
