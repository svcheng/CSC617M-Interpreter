from __future__ import annotations

from dataclasses import dataclass

from errors import (
    InvalidAttributeNameError,
    InvalidBaseTypeError,
    KeywordCollisionError,
    NameCollisionError,
    NonExistentNameError,
    RecursiveTypeDefinitionError,
)

from .abstract_node_classes import Node
from .identifier import Identifier
from .types import RESERVED_WORDS, ArrayType, Type


@dataclass
class TypeDec(Node):
    name: Identifier
    field_list: list[tuple[Identifier, Type]]

    def build_type_table(self):
        assert self.scope is not None
        type_name = str(self.name)
        meta = self.meta_info

        # check if definition repeated
        if type_name in RESERVED_WORDS:
            raise KeywordCollisionError(meta, identifier=type_name)
        if self.scope.type_in_scope(type_name):
            raise NameCollisionError(
                meta,
                identifier=type_name,
                alr_existing_construct="type",
            )

        # check field declarations
        for field_id, field_type in self.field_list:
            field_name, field_type_name = str(field_id), str(field_type.name)

            # stupid field declarations
            if field_name in RESERVED_WORDS:
                raise KeywordCollisionError(meta, identifier=field_name)
            if field_name == type_name:
                raise InvalidAttributeNameError(meta)
            if field_type_name == type_name:
                raise RecursiveTypeDefinitionError(meta)

            # types that don't exist
            if isinstance(field_type, ArrayType):
                base_type_name = str(field_type.base_type.name)
                if not self.scope.type_in_scope(base_type_name):
                    raise InvalidBaseTypeError(meta, base_type_name=base_type_name)
            elif not self.scope.type_in_scope(field_type_name):
                raise NonExistentNameError(
                    meta,
                    identifier=field_type_name,
                    expected_construct="type",
                )

        self.scope.type_table[type_name] = self
