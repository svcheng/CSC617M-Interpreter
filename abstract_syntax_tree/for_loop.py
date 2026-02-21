from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from errors import MalformedForLoopError, VoidExpressionError

from .abstract_node_classes import Expr, Node
from .aux_classes import Scope, VarInfo
from .identifier import Identifier
from .types import INT, Type


@dataclass
class ForLoop(Node):
    iterator_name: Identifier
    range_start: Expr
    range_end: Expr
    step: Expr
    body: list

    def init_scope(self, scope: Scope):
        self.scope = Scope(scope)
        self.scope.insert_varname(str(self.iterator_name), VarInfo(False, INT))

        self.range_start.init_scope(scope)
        self.range_end.init_scope(scope)
        self.step.init_scope(scope)
        for stmt in self.body:
            stmt.init_scope(self.scope)

    def check_misplaced_returns(self):
        for stmt in self.body:
            stmt.check_misplaced_returns()

    def build_var_tables(self):
        assert self.scope is not None
        self.scope.insert_varname(str(self.iterator_name), VarInfo(False, INT))

        self.range_start.build_var_tables()
        self.range_end.build_var_tables()
        self.step.build_var_tables()
        for stmt in self.body:
            stmt.build_var_tables()

    def check_types(self):
        assert self.scope is not None

        # params should be integers
        for param_name, param in [
            ("Range start", self.range_start),
            ("Range end", self.range_end),
            ("Step", self.step),
        ]:
            param_type = param.check_types()
            if param_type is None:
                raise VoidExpressionError(self.meta_info)
            if param_type != INT:
                raise MalformedForLoopError(
                    self.meta_info,
                    param_name=param_name,
                    param_type=str(param_type.name),
                )

        for stmt in self.body:
            stmt.check_types()

    def _find_returns(self):
        return_stmts = []
        for stmt in self.body:
            return_stmts.extend(stmt._find_returns())
        return return_stmts
