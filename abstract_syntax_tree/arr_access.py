from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from errors import (
    IncorrectIndexDimensionError,
    InvalidIdentifierTypeError,
    InvalidIndexTypeError,
    VoidExpressionError,
)

from .abstract_node_classes import Expr
from .aux_classes import Scope
from .identifier import Identifier
from .types import CHAR, INT, STR, ArrayType, Type


@dataclass
class ArrAccess(Expr):
    array_name: Identifier
    indices: list[Expr]

    def init_scope(self, scope: Scope):
        self.scope = scope
        self.array_name.init_scope(scope)
        for idx in self.indices:
            idx.init_scope(scope)

    def build_var_tables(self) -> None:
        self.array_name.build_var_tables()
        for idx in self.indices:
            idx.build_var_tables()

    def check_types(self) -> Optional[Type]:
        assert self.scope is not None
        arr_name = str(self.array_name)
        meta = self.meta_info

        # check that indices are ints
        for i, idx in enumerate(self.indices):
            idx_type = idx.check_types()
            if idx_type is None:
                raise VoidExpressionError(meta)
            if idx_type != INT:
                raise InvalidIndexTypeError(meta, i + 1, wrong_type=str(idx_type))

        # check if number of indices matches dimension
        var_type = self.scope.get_type(arr_name)
        assert var_type is not None
        num_indices = len(self.indices)

        if isinstance(var_type, ArrayType):
            arr_dim = len(var_type.size)
            if num_indices != arr_dim:
                raise IncorrectIndexDimensionError(
                    meta,
                    arr_name=arr_name,
                    expected_dim=arr_dim,
                    num_indices=num_indices,
                )
            self.datatype = var_type.base_type
            return self.datatype
        elif var_type == STR:
            if num_indices != 1:
                raise IncorrectIndexDimensionError(
                    meta,
                    arr_name=arr_name,
                    expected_dim=1,
                    num_indices=num_indices,
                )
            self.datatype = CHAR
            return self.datatype
        else:
            raise InvalidIdentifierTypeError(
                meta,
                var_name=arr_name,
                var_type=str(var_type),
                expected_type="arr or str",
            )
