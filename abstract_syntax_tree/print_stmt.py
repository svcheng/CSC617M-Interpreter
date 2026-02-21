from __future__ import annotations

from dataclasses import dataclass

from .abstract_node_classes import Expr, Node


@dataclass
class PrintStmt(Node):
    value: Expr

    def init_scope(self, scope):
        self.scope = scope
        self.value.init_scope(scope)

    def build_var_tables(self) -> None:
        self.value.build_var_tables()

    def check_types(self) -> None:
        from errors import VoidExpressionError

        assert self.scope is not None
        value_type = self.value.check_types()
        if value_type is None:
            raise VoidExpressionError(self.meta_info)
