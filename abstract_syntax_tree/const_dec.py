from __future__ import annotations

from dataclasses import dataclass

from errors import (
    KeywordCollisionError,
    MutableConstantError,
    NameCollisionError,
    VoidExpressionError,
)

from .abstract_node_classes import Expr, Node
from .aux_classes import Scope, VarInfo
from .identifier import Identifier
from .types import BASIC_TYPES, RESERVED_WORDS


@dataclass
class ConstDec(Node):
    name: Identifier
    value: Expr

    def init_scope(self, scope: Scope):
        self.scope = scope
        self.value.init_scope(scope)

    def build_var_tables(self):
        assert self.scope is not None
        name = str(self.name)
        meta = self.meta_info

        # check if name is valid
        if name in RESERVED_WORDS:
            raise KeywordCollisionError(meta, identifier=name)
        if self.scope.type_in_scope(name):
            raise NameCollisionError(
                meta,
                identifier=name,
                alr_existing_construct="type",
            )
        if self.scope.function_in_scope(name):
            raise NameCollisionError(
                meta,
                identifier=name,
                alr_existing_construct="function",
            )
        if self.scope.var_name_in_scope(name):
            raise NameCollisionError(
                meta,
                identifier=name,
                alr_existing_construct="variable or constant",
            )

        self.value.build_var_tables()
        self.scope.insert_varname(name, VarInfo(True, None))

    def check_types(self):
        value_type = self.value.check_types()
        type_name = str(value_type)
        if value_type is None:
            raise VoidExpressionError(self.meta_info)
        elif type_name not in BASIC_TYPES:
            raise MutableConstantError(self.meta_info, type_name=type_name)

        assert self.scope is not None
        self.scope.set_type(str(self.name), datatype=value_type)

    def check_null_references(self):
        self.value.check_null_references()

        # constants are always initialized
        assert self.scope is not None
        self.scope.initialize(str(self.name))
