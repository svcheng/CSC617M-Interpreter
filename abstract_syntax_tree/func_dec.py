from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from abstract_syntax_tree.aux_classes import MetaInfo
from errors import (
    InvalidBaseTypeError,
    InvalidReturnValueError,
    KeywordCollisionError,
    NameCollisionError,
    NonExistentNameError,
    ReturnValueExistenceError,
    VoidExpressionError,
)

from .abstract_node_classes import Expr, Node
from .aux_classes import Scope, VarInfo
from .identifier import Identifier
from .types import RESERVED_WORDS, ArrayType, Type


@dataclass
class FuncDec(Node):
    name: Identifier
    args: list[tuple[Identifier, Type]]
    return_type: Optional[Type]
    body: list

    def init_scope(self, scope: Scope):
        self.scope = scope
        for stmt in self.body:
            stmt.init_scope(self.scope)

    def build_func_table(self):
        assert self.scope is not None
        func_name = str(self.name)
        meta = self.meta_info

        if self.scope.type_in_scope(func_name):
            raise NameCollisionError(
                meta,
                identifier=func_name,
                alr_existing_construct="type",
            )
        if self.scope.function_in_scope(func_name):
            raise NameCollisionError(
                meta,
                identifier=func_name,
                alr_existing_construct="function",
            )

        # check arguments
        for arg_name, arg_type in self.args:
            arg_name, arg_type_name = str(arg_name), str(arg_type.name)

            if arg_name in RESERVED_WORDS:
                raise KeywordCollisionError(meta, identifier=arg_name)

            # arg_type must be a valid type
            if isinstance(arg_type, ArrayType):
                base_type_name = str(arg_type.base_type.name)
                if not self.scope.type_in_scope(base_type_name):
                    raise InvalidBaseTypeError(meta, base_type_name)
            elif not self.scope.type_in_scope(arg_type_name):
                raise NonExistentNameError(
                    meta,
                    identifier=arg_type_name,
                    expected_construct="type",
                )

        self.scope.func_table[func_name] = self

    def build_var_tables(self):
        assert self.scope is not None
        for arg_name, arg_type in self.args:
            self.scope.insert_varname(str(arg_name), VarInfo(False, arg_type))
        for stmt in self.body:
            stmt.build_var_tables()

    def check_types(self):
        for stmt in self.body:
            stmt.check_types()

    def check_returns(self):
        return_stmts = self._find_returns()
        for return_stmt in return_stmts:
            self._check_return(return_stmt.meta_info, return_stmt.value)

    def _check_return(self, meta: MetaInfo, value: Expr):
        func_name = str(self.name)
        expected_return_type = self.return_type

        # void functions cannot return a value, non-void funcs must return one
        if expected_return_type is None and value is None:
            return
        elif expected_return_type is None and value is not None:
            raise ReturnValueExistenceError(
                meta,
                func_name=func_name,
                is_void=True,
            )
        elif expected_return_type is not None and value is None:
            raise ReturnValueExistenceError(
                meta,
                func_name=func_name,
                is_void=False,
                show_code_block=False,
            )
        assert expected_return_type is not None

        #  check that return types are equal, at this point func is not void and return value exists
        actual_return_type = value.check_types()

        if actual_return_type is None:  # void func was invoked on the right
            raise VoidExpressionError(meta)
        elif expected_return_type != actual_return_type:
            raise InvalidReturnValueError(
                meta,
                func_name=func_name,
                expected_type=str(expected_return_type.name),
                actual_type=str(actual_return_type.name),
            )
        elif isinstance(expected_return_type, ArrayType) and isinstance(
            actual_return_type, ArrayType
        ):  # type names are not equal
            expected_base_type = expected_return_type.base_type
            actual_base_type = actual_return_type.base_type
            dim1, dim2 = len(expected_return_type.size), len(actual_return_type.size)
            formatted_t1 = f"{dim1}-D {expected_return_type.name} arr"
            formatted_t2 = f"{dim2}-D {actual_return_type.name} arr"

            # check that base types are same and that number of indices matches array dimension
            if expected_base_type != actual_base_type or dim1 != dim2:
                raise InvalidReturnValueError(
                    meta,
                    func_name=func_name,
                    expected_type=formatted_t1,
                    actual_type=formatted_t2,
                )

    def _find_returns(self):
        return_stmts = []
        for stmt in self.body:
            stmt_returns = stmt._find_returns()
            return_stmts.extend(stmt_returns)

        return return_stmts

    def check_null_references(self):
        for stmt in self.body:
            stmt.check_null_references()
