from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from errors import (
    KeywordCollisionError,
    NameCollisionError,
    NonExistentNameError,
    VoidExpressionError,
)

from .abstract_node_classes import Expr, Node
from .aux_classes import Scope, VarInfo
from .identifier import Identifier
from .types import BASIC_TYPES, RESERVED_WORDS, ArrayType, Type


@dataclass
class VarDec(Node):
    name: Identifier
    declared_type: Optional[Type]
    init_value: Optional[Expr]

    def init_scope(self, scope: Scope):
        self.scope = scope
        if isinstance(self.declared_type, ArrayType):
            for dim in self.declared_type.size:
                dim.init_scope(scope)
        if self.init_value is not None:
            self.init_value.init_scope(scope)

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

        # check that declared type is valid
        if isinstance(self.declared_type, ArrayType):
            # check for undeclared vars in array dimensions
            for dim in self.declared_type.size:
                dim.build_var_tables()
        elif self.declared_type is not None and not self.scope.type_in_scope(
            str(self.declared_type)
        ):
            raise NonExistentNameError(
                meta,
                identifier=str(self.declared_type),
                expected_construct="type",
            )

        # check initial value
        if self.init_value is not None:
            self.init_value.build_var_tables()
        self.scope.insert_varname(name, VarInfo(False, self.declared_type))

    def check_types(self):
        assert self.scope is not None
        name = str(self.name)
        if self.declared_type is None:
            assert self.init_value is not None
            value_type = self.init_value.check_types()
            if value_type is None:
                raise VoidExpressionError(self.meta_info)
            self.scope.set_type(name, datatype=value_type)
        elif self.init_value is None:
            assert self.declared_type is not None
            self.scope.set_type(name, datatype=self.declared_type)

    def check_null_references(self):
        assert self.scope is not None
        name = str(self.name)
        if self.init_value is not None:
            # guaranteed variable is a basic type
            self.init_value.check_null_references()
            self.scope.initialize(name)

        # to allow record to record assignment and array assignment
        own_type = self.scope.get_type(name)
        if str(own_type) not in BASIC_TYPES:
            self.scope.initialize(name)
