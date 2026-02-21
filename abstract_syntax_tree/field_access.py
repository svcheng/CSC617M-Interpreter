from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from errors import (
    InvalidIdentifierTypeError,
    NonExistentAttributeError,
    NonExistentNameError,
)

from .abstract_node_classes import Expr
from .identifier import Identifier
from .types import BASIC_TYPES, Type


@dataclass
class FieldAccess(Expr):
    record_name: Identifier
    attribute: Identifier

    def build_var_tables(self) -> None:
        assert self.scope is not None
        record_name = str(self.record_name)
        attribute = str(self.attribute)
        meta = self.meta_info

        # record name should be in scope
        if not self.scope.var_name_in_scope(record_name):
            raise NonExistentNameError(
                meta,
                identifier=record_name,
                expected_construct="variable/constant",
            )

        # record name should be a record and not some other var
        var_type = self.scope.get_type(record_name)
        assert var_type is not None
        var_type_name = str(var_type)
        if not self.scope.type_in_scope(var_type_name) or var_type_name in BASIC_TYPES:
            raise InvalidIdentifierTypeError(
                meta,
                var_name=record_name,
                var_type=var_type_name,
                expected_type="record",
            )

        # check that the record has that attribute
        type_dec = self.scope.get_type_dec(var_type_name)
        assert type_dec is not None
        if attribute not in [str(name) for name, _ in type_dec.field_list]:
            raise NonExistentAttributeError(
                meta,
                record_name=record_name,
                record_type_name=var_type_name,
                attr=attribute,
            )

    def check_types(self) -> Optional[Type]:
        assert self.scope is not None

        # get the type of the variable
        var_type = self.scope.get_type(str(self.record_name))
        assert var_type is not None
        type_dec = self.scope.get_type_dec(str(var_type.name))
        assert type_dec is not None

        # return the type of the attribute being referenced
        for field_name, field_type in type_dec.field_list:
            if str(field_name) == str(self.attribute):
                self.datatype = field_type
                return field_type
        return None
