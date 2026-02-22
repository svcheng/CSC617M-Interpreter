from __future__ import annotations

from dataclasses import dataclass

from abstract_syntax_tree.identifier import Identifier
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

    def build_var_tables(self):
        self.lval.build_var_tables()
        self.rval.build_var_tables()

        # no constant assignment
        assert self.scope is not None
        if self.scope.var_is_constant(str(self.lval)):
            raise ConstantReassignmentError(self.meta_info)

    def check_types(self):
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

    def check_null_references(self):
        self.rval.check_null_references()

        assert self.scope is not None
        if isinstance(self.lval, Identifier):
            self.scope.initialize(str(self.lval))
