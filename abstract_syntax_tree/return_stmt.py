from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from errors import MisplacedReturnError

from .abstract_node_classes import Expr, Node
from .aux_classes import Scope


@dataclass
class ReturnStmt(Node):
    value: Optional[Expr]

    def init_scope(self, scope: Scope):
        self.scope = scope
        if self.value is not None:
            self.value.init_scope(scope)

    def check_misplaced_returns(self) -> None:
        raise MisplacedReturnError(self.meta_info)

    def build_var_tables(self) -> None:
        if self.value is not None:
            self.value.build_var_tables()

    def _find_returns(self):
        return [self]
