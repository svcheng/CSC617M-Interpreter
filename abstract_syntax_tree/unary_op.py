from __future__ import annotations

from dataclasses import dataclass

from errors import OperatorTypeError, VoidExpressionError

from .abstract_node_classes import Expr
from .aux_classes import Scope
from .types import BOOL


@dataclass
class UnaryOp(Expr):
    op: str
    arg: Expr

    def init_scope(self, scope: Scope):
        self.scope = scope
        self.arg.init_scope(scope)

    def build_var_tables(self):
        self.arg.build_var_tables()

    def check_types(self):
        arg_type = self.arg.check_types()
        if arg_type is None:
            raise VoidExpressionError(self.meta_info)
        if arg_type != BOOL:
            raise OperatorTypeError(
                self.meta_info,
                op=self.op,
                type_names=[str(arg_type.name)],
            )

        self.datatype = arg_type
        return arg_type

    def check_null_references(self):
        self.arg.check_null_references()
