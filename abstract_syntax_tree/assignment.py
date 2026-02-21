from __future__ import annotations

from dataclasses import dataclass

from errors import ConstantReassignmentError, TypeMismatchError, VoidExpressionError

from .abstract_node_classes import Expr, Node
from .aux_classes import Scope


@dataclass
class Assignment(Node):
    lval: Expr
    rval: Expr

    def init_scope(self, scope: Scope):
        self.scope = scope
        self.lval.init_scope(scope)
        self.rval.init_scope(scope)

    def build_var_tables(self) -> None:
        self.lval.build_var_tables()
        self.rval.build_var_tables()

        # no constant assignment
        assert self.scope is not None
        if self.scope.var_is_constant(str(self.lval)):
            raise ConstantReassignmentError(self.meta_info)

    def check_types(self) -> None:
        left_type = self.lval.check_types()
        assert left_type is not None

        right_type = self.rval.check_types()
        if right_type is None:
            raise VoidExpressionError(self.meta_info)

        if left_type != right_type:
            raise TypeMismatchError(
                self.meta_info,
                str(left_type.name),
                str(right_type.name),
            )
