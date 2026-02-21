from __future__ import annotations

from dataclasses import dataclass

from errors import (
    NonExistentAttributeError,
    NonExistentNameError,
    NonRecordFieldAccessError,
)

from .abstract_node_classes import Expr
from .identifier import Identifier
from .types import BASIC_TYPES


@dataclass
class FieldAccess(Expr):
    record_name: Identifier
    attributes: list[Identifier]

    def build_var_tables(self):
        assert self.scope is not None

        # variable should be in scope
        var_name = str(self.record_name)
        if not self.scope.var_name_in_scope(var_name):
            raise NonExistentNameError(
                self.meta_info,
                identifier=var_name,
                expected_construct="variable/constant",
            )

    def check_types(self):
        assert self.scope is not None
        meta = self.meta_info
        var_name = str(self.record_name)

        # variable should be a record
        var_type = self.scope.get_type(var_name)
        assert var_type is not None
        var_type_name = str(var_type)
        if not self.scope.type_in_scope(var_type_name) or var_type_name in BASIC_TYPES:
            raise NonRecordFieldAccessError(meta, var_name=var_name)

        # check that each attr is really an attribute of the previous one, and is itself a record (unless it is the last)
        prev_type_dec = self.scope.get_type_dec(var_type_name)
        attr_type = None
        for i, attr in enumerate(self.attributes):
            assert prev_type_dec is not None
            attr = str(attr)
            valid = False

            # check that attr is in the field list of the prev record
            for field_name, field_type in prev_type_dec.field_list:
                if attr == str(field_name):
                    valid = True
                    attr_type = field_type

            if not valid:
                raise NonExistentAttributeError(
                    meta,
                    record_type_name=str(prev_type_dec.name),
                    attr=attr,
                )
            assert attr_type is not None

            # set new type dec
            prev_type_dec = self.scope.get_type_dec(str(attr_type.name))
            # only last attr can have basic type
            if prev_type_dec is None and (i + 1) < len(self.attributes):
                raise NonRecordFieldAccessError(meta, var_name=attr)

        self.datatype = attr_type
        return self.datatype
