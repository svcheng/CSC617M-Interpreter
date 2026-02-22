from __future__ import annotations

from dataclasses import dataclass

from .abstract_node_classes import Expr
from .aux_classes import Scope
from .types import BOOL, FLOAT, INT, STR


@dataclass
class BinOp(Expr):
    op: str
    left: Expr
    right: Expr

    def init_scope(self, scope: Scope):
        self.scope = scope
        self.left.init_scope(scope)
        self.right.init_scope(scope)

    def build_var_tables(self):
        self.left.build_var_tables()
        self.right.build_var_tables()

    def check_types(self):
        from errors import OperatorTypeError, VoidExpressionError

        numerical_types = (INT, FLOAT)
        meta = self.meta_info
        op = self.op

        left_type = self.left.check_types()
        right_type = self.right.check_types()
        if left_type is None or right_type is None:
            raise VoidExpressionError(meta)
        left_type_name = str(left_type)
        right_type_name = str(right_type)

        match op:
            case "+" | "-" | "*" | "/":
                if left_type == STR and right_type == STR and op == "+":
                    op_type = STR
                elif left_type in numerical_types and right_type in numerical_types:
                    op_type = FLOAT if FLOAT in (left_type, right_type) else INT
                else:
                    raise OperatorTypeError(
                        meta,
                        op=op,
                        type_names=[left_type_name, right_type_name],
                    )
                self.datatype = op_type
            case "==" | "!=" | "<" | "<=" | ">" | ">=":
                if (
                    left_type not in numerical_types
                    or right_type not in numerical_types
                ):
                    raise OperatorTypeError(
                        meta,
                        op=op,
                        type_names=[left_type_name, right_type_name],
                    )
                self.datatype = BOOL
            case "||" | "&&":
                if left_type != BOOL or right_type != BOOL:
                    raise OperatorTypeError(
                        meta,
                        op=op,
                        type_names=[left_type_name, right_type_name],
                    )
                self.datatype = BOOL

        return self.datatype

    def check_null_references(self):
        self.left.check_null_references()
        self.right.check_null_references()
