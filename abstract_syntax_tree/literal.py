from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .abstract_node_classes import Expr


@dataclass
class Literal(Expr):
    value: Any

    def check_types(self):
        return self.datatype
