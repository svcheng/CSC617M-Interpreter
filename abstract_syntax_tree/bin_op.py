from __future__ import annotations

from dataclasses import dataclass
from typing import Never

from .abstract_node_classes import Expr
from .aux_classes import Scope
from .types import BOOL, FLOAT, INT, STR, ArrayType


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

        def raise_op_error() -> Never:
            raise OperatorTypeError(
                meta,
                op=op,
                type_names=[left_type_name, right_type_name],
            )

        match op:
            case "+" | "-" | "*" | "/":
                if left_type == STR and right_type == STR and op == "+":
                    op_type = STR
                elif left_type in numerical_types and right_type in numerical_types:
                    op_type = FLOAT if FLOAT in (left_type, right_type) else INT
                else:
                    raise_op_error()
                self.datatype = op_type
            case "<" | "<=" | ">" | ">=":
                if (
                    left_type not in numerical_types
                    or right_type not in numerical_types
                ):
                    raise_op_error()

                self.datatype = BOOL
            case "==" | "!=":  # any two types are permitted
                if left_type != right_type:
                    raise_op_error()
                # arrays
                elif isinstance(left_type, ArrayType):
                    left_dim = len(left_type.size)
                    right_dim = len(right_type.size)
                    left_array_name = f"{left_dim}D {left_type.base_type} arr"
                    right_array_name = f"{right_dim}D {right_type.base_type} arr"

                    # different base types
                    if left_type.base_type != right_type.base_type:
                        raise OperatorTypeError(
                            meta,
                            op=op,
                            type_names=[left_array_name, right_array_name],
                        )
                    # different dimensions
                    if left_dim != right_dim:
                        raise OperatorTypeError(
                            meta,
                            op=op,
                            type_names=[left_array_name, right_array_name],
                        )

                self.datatype = BOOL
            case "||" | "&&":
                if left_type != BOOL or right_type != BOOL:
                    raise_op_error()
                self.datatype = BOOL

        return self.datatype

    def check_null_references(self):
        self.left.check_null_references()
        self.right.check_null_references()
