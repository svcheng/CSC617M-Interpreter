from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from errors import NonExistentNameError, NullReferenceError

from .abstract_node_classes import Node

if TYPE_CHECKING:
    from .types import Type


@dataclass
class Identifier(Node):
    name: str

    def __str__(self) -> str:
        return self.name

    def build_var_tables(self):
        assert self.scope is not None
        if not self.scope.var_name_in_scope(self.name):
            raise NonExistentNameError(
                self.meta_info,
                identifier=self.name,
                expected_construct="variable/constant",
            )

    def check_types(self) -> Optional[Type]:
        assert self.scope is not None
        return self.scope.get_type(str(self.name))

    def check_null_references(self):
        assert self.scope is not None
        name = str(self.name)

        if not self.scope.is_initialized(name):
            raise NullReferenceError(self.meta_info, var_name=name)
