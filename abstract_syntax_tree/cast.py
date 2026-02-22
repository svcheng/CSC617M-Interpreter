from __future__ import annotations

from dataclasses import dataclass

from errors import (
    InvalidCastArgumentError,
    InvalidCastTargetError,
    NonExistentNameError,
    VoidExpressionError,
)

from .abstract_node_classes import Expr
from .aux_classes import Scope
from .literal import Literal
from .types import BASIC_TYPES, BOOL, CHAR, FLOAT, INT, STR, NotArrayType


@dataclass
class Cast(Expr):
    arg: Expr
    target_type: Literal

    def init_scope(self, scope: Scope):
        self.scope = scope
        self.arg.init_scope(scope)

    def build_var_tables(self):
        assert self.scope is not None
        # check that target type is a real (NotArray) type
        target_type = self.target_type.value
        if (
            target_type not in BASIC_TYPES
            and not self.scope.type_in_scope(target_type)
            and target_type != "arr"
        ):
            raise NonExistentNameError(
                self.meta_info,
                identifier=target_type,
                expected_construct="type",
            )

        self.arg.build_var_tables()

    def check_types(self):
        meta = self.meta_info
        arg_type = self.arg.check_types()

        # only basic types can be cast
        if arg_type is None:
            raise VoidExpressionError(meta)
        if str(arg_type) not in BASIC_TYPES:
            raise InvalidCastArgumentError(meta, arg_type=str(arg_type))

        # check target_type should be basic type and enforce type cast rules
        if arg_type in (INT, FLOAT):
            valid_targets = [INT, FLOAT, BOOL, CHAR, STR]
        elif arg_type == BOOL:
            valid_targets = [INT, FLOAT, BOOL, STR]
        elif arg_type == CHAR:
            valid_targets = [INT, CHAR, STR]
        elif arg_type == STR:
            valid_targets = [INT, FLOAT, BOOL, STR]
        else:
            valid_targets = []

        target_type = NotArrayType(self.target_type.value)
        if target_type not in valid_targets:
            raise InvalidCastTargetError(
                meta,
                arg_type=str(arg_type),
                target_type=str(target_type),
            )

        self.datatype = target_type
        return self.datatype

    def check_null_references(self):
        self.arg.check_null_references()
