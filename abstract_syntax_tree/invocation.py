from __future__ import annotations

from dataclasses import dataclass

from abstract_syntax_tree.aux_classes import Scope
from errors import (
    IncorrectParameterCountError,
    IncorrectParameterTypeError,
    NonExistentNameError,
    VoidExpressionError,
)

from .abstract_node_classes import Expr
from .identifier import Identifier


@dataclass
class Invocation(Expr):
    name: Identifier
    args: list[Expr]

    def init_scope(self, scope: Scope):
        self.scope = scope
        for arg in self.args:
            arg.init_scope(scope)

    def build_var_tables(self):
        assert self.scope is not None
        name = str(self.name)
        meta = self.meta_info

        # check that function exists
        if not self.scope.function_in_scope(name):
            raise NonExistentNameError(
                meta,
                identifier=name,
                expected_construct="function",
            )

        # check for correct num of function args
        expected_count = len(self.scope.get_func_dec(name).args)
        actual_count = len(self.args)
        if expected_count != actual_count:
            raise IncorrectParameterCountError(
                meta,
                func_invoked=name,
                actual_count=actual_count,
                expected_count=expected_count,
            )

        for arg in self.args:
            arg.build_var_tables()

    def check_types(self):
        assert self.scope is not None

        func_dec = self.scope.get_func_dec(str(self.name))
        meta = self.meta_info

        # check param types
        for i, (arg_name, arg_type) in enumerate(func_dec.args):
            param_type = self.args[i].check_types()

            # param is invocation of void function
            if param_type is None:
                raise VoidExpressionError(meta)

            # param otherwise has wrong type
            if param_type != arg_type:
                raise IncorrectParameterTypeError(
                    meta,
                    func_name=str(self.name),
                    arg_name=str(arg_name),
                    arg_type=str(arg_type.name),
                    param_type=str(param_type.name),
                )

        self.datatype = func_dec.return_type  # may be None if func is void
        return self.datatype

    def check_null_references(self):
        for arg in self.args:
            arg.check_null_references()
