from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .abstract_node_classes import Expr
from .types import Type


@dataclass
class Literal(Expr):
    value: Any

    def check_types(self) -> Optional[Type]:
        return self.datatype
