from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from errors import InvalidConditionError, VoidExpressionError

from .abstract_node_classes import Expr, Node
from .aux_classes import Scope
from .types import BOOL


@dataclass
class Conditional(Node):
    condition: Expr
    then_block: list
    else_block: Optional[list]

    def init_scope(self, scope: Scope):
        self.scope = scope
        self.condition.init_scope(scope)

        # if and else blocks have separate scopes
        then_scope = Scope(scope)
        for stmt in self.then_block:
            stmt.init_scope(then_scope)

        if self.else_block is not None:
            else_scope = Scope(scope)
            for stmt in self.else_block:
                stmt.init_scope(else_scope)

    def check_misplaced_returns(self):
        for stmt in self.then_block:
            stmt.check_misplaced_returns()
        if self.else_block is not None:
            for stmt in self.else_block:
                stmt.check_misplaced_returns()

    def build_var_tables(self):
        self.condition.build_var_tables()
        for stmt in self.then_block:
            stmt.build_var_tables()
        if self.else_block is not None:
            for stmt in self.else_block:
                stmt.build_var_tables()

    def check_types(self):
        assert self.scope is not None

        # condition must be boolean
        cond_type = self.condition.check_types()
        if cond_type is None:
            raise VoidExpressionError(self.meta_info)
        if cond_type != BOOL:
            raise InvalidConditionError(self.meta_info, cond_type=str(cond_type.name))

        for stmt in self.then_block:
            stmt.check_types()
        if self.else_block is not None:
            for stmt in self.else_block:
                stmt.check_types()

    def _find_returns(self):
        return_stmts = []
        for stmt in self.then_block:
            return_stmts.extend(stmt._find_returns())
        if self.else_block is not None:
            for stmt in self.else_block:
                return_stmts.extend(stmt._find_returns())
        return return_stmts

    def check_null_references(self):
        self.condition.check_null_references()
        for stmt in self.then_block:
            stmt.check_null_references()
        if self.else_block is not None:
            for stmt in self.else_block:
                stmt.check_null_references()
