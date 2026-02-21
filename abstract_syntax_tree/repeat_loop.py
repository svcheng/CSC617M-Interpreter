from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from errors import InvalidConditionError, VoidExpressionError

from .abstract_node_classes import Expr, Node
from .aux_classes import Scope
from .types import BOOL, Type


@dataclass
class RepeatLoop(Node):
    cond: Expr
    body: list

    def init_scope(self, scope):
        self.scope = scope
        self.cond.init_scope(scope)
        new_scope = Scope(scope)
        for stmt in self.body:
            stmt.init_scope(new_scope)

    def check_misplaced_returns(self):
        for stmt in self.body:
            stmt.check_misplaced_returns()

    def build_var_tables(self):
        self.cond.build_var_tables()
        for stmt in self.body:
            stmt.build_var_tables()

    def check_types(self):
        assert self.scope is not None
        # condition must be boolean
        cond_type = self.cond.check_types()
        if cond_type is None:
            raise VoidExpressionError(self.meta_info)
        if cond_type != BOOL:
            raise InvalidConditionError(self.meta_info, cond_type=str(cond_type.name))
        for stmt in self.body:
            stmt.check_types()

    def _find_returns(self):
        return_stmts = []
        for stmt in self.body:
            return_stmts.extend(stmt._find_returns())

        return return_stmts
