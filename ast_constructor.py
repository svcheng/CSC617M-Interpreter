from dataclasses import dataclass
from typing import Any, List, Optional

from lark import Transformer

# =====================
# Program Structure
# =====================


@dataclass
class Program:
    const_decs: list["ConstDec"]
    type_decs: list
    func_decs: list
    main_block: list


# =====================
# Declarations
# =====================


@dataclass
class VarDec:
    name: str
    declared_type: Optional["Type"]
    init_value: Optional["Expr"]


@dataclass
class ConstDec:
    name: str
    value: "Expr"


@dataclass
class TypeDec:
    name: str
    field_list: list[tuple]


@dataclass
class FuncDec:
    name: str
    args: Optional[list[tuple[str, "Type"]]]
    return_type: Optional["Type"]
    body: list


# =====================
# Types
# =====================


class Type:
    pass


@dataclass
class NotArrayType(Type):
    name: str


@dataclass
class ArrayType(Type):
    base_type: NotArrayType
    size: list["Expr"]


# =====================
# Statements
# =====================


@dataclass
class Assignment:
    lval: "Expr"
    rval: "Expr"


@dataclass
class Conditional:
    condition: "Expr"
    then_block: list
    else_block: Optional[list]


@dataclass
class ForLoop:
    iterator_name: str
    init_val: "Expr"
    cond: "Expr"
    step: "Expr"
    body: list


@dataclass
class WhileLoop:
    cond: "Expr"
    body: list


@dataclass
class RepeatLoop:
    cond: "Expr"
    body: list


@dataclass
class ReturnStmt:
    value: Optional["Expr"]


@dataclass
class PrintStmt:
    value: str


@dataclass
class ScanStmt:
    lval: "Expr"


# =====================
# Expressions
# =====================


@dataclass
class Expr:
    type: Optional[Type]  # type of None means type is still unknown


@dataclass
class Literal(Expr):
    raw_value: str
    value: Any


@dataclass
class ArrAccess(Expr):
    array_name: str
    indices: list["Expr"]


@dataclass
class FieldAccess(Expr):
    record_name: str
    attribute: str


@dataclass
class UnaryOp(Expr):
    op: str
    arg: Expr


@dataclass
class BinOp(Expr):
    op: str
    left: Expr
    right: Expr


@dataclass
class Invocation(Expr):
    name: str
    args: Optional[List[Expr]]


############################################################
# AST Functions/Classes
############################################################


def new_bin_op(items, op: str, type_name: Optional[str] = None):
    left, right = items
    if type_name is not None:
        type = NotArrayType(type_name)
    else:
        type = None
    return BinOp(type=type, op=op, left=left, right=right)


def new_bool_op(items, op: str):
    return new_bin_op(items=items, op=op, type_name="bool")


class ASTConstructor(Transformer):
    def return_fst(self, items):
        return items[0]

    def return_children(self, items):
        return items

    def IDENTIFIER(self, token):
        return token.value

    # =====================
    # Program Structure
    # =====================

    def program(self, items):
        const_decs, type_decs, func_decs, main_block = items

        return Program(
            const_decs=const_decs,
            type_decs=type_decs,
            func_decs=func_decs,
            main_block=main_block,
        )

    const_decs = return_children
    type_decs = return_children
    func_decs = return_children

    def main_block(self, items):
        return items[1]  # index 0 is the "main" token

    stmts = return_children

    # =====================
    # Declarations
    # =====================

    def const_dec(self, items):
        _, name, value = items
        return ConstDec(name=name, value=value)

    def var_dec_no_assign(self, items):
        _, name, declared_type = items
        return VarDec(name=name, declared_type=declared_type, init_value=None)

    def var_dec_assign(self, items):
        _, name, init_value = items
        return VarDec(name=name, declared_type=None, init_value=init_value)

    def type_dec(self, items):
        name = items[1]
        field_list = items[2]
        return TypeDec(name=name, field_list=field_list)

    field_list = return_children

    def field(self, items):
        attr_name, attr_type = items
        return (attr_name, attr_type)

    def func_dec(self, items):
        return_type, name, args, body = items
        return FuncDec(name=name, args=args, return_type=return_type, body=body)

    stmts_with_return = return_children

    # =====================
    # Types
    # =====================

    def VOID(self, _):
        return None

    def not_array_type(self, items):
        type_name = items[0]
        return NotArrayType(name=type_name)

    def basic_type(self, items):
        name = items[0].value
        return name

    def array_type(self, items):
        base_type = items[0]
        size = items[2]
        return ArrayType(base_type=base_type, size=size)

    # =====================
    # Statements
    # =====================

    def assignment(self, items):
        lval, rval = items
        return Assignment(lval=lval, rval=rval)

    def conditional(self, items):
        condition = items[1]
        then_block = items[2]
        else_block = items[4] if len(items) > 5 else None
        return Conditional(
            condition=condition, then_block=then_block, else_block=else_block
        )

    def for_loop(self, items):
        _, iterator_name, init_val, cond, step, body = items
        return ForLoop(
            iterator_name=iterator_name,
            init_val=init_val,
            cond=cond,
            step=step,
            body=body,
        )

    def while_loop(self, items):
        _, cond, body = items
        return WhileLoop(cond=cond, body=body)

    def repeat_loop(self, items):
        _, body, _, cond = items
        return RepeatLoop(cond=cond, body=body)

    def return_stmt(self, items):
        value = items[1] if len(items) > 1 else None
        return ReturnStmt(value=value)

    def print_stmt(self, items):
        value = items[1]
        return PrintStmt(value=value)

    def scan_stmt(self, items):
        lval = items[1]
        return ScanStmt(lval=lval)

    # =====================
    # Expressions: Scalars
    # =====================

    def int_literal(self, items):
        raw_value = items[0].value
        return Literal(
            type=NotArrayType("int"), raw_value=raw_value, value=int(raw_value)
        )

    def float_literal(self, items):
        raw_value = items[0].value
        return Literal(
            type=NotArrayType("float"), raw_value=raw_value, value=float(raw_value)
        )

    def bool_literal(self, items):
        raw_value = items[0].value
        return Literal(
            type=NotArrayType("bool"), raw_value=raw_value, value=(raw_value == "true")
        )

    def str_literal(self, items):
        raw_value = items[0].value
        return Literal(
            type=NotArrayType("string"), raw_value=raw_value, value=raw_value[1:-1]
        )

    def arr_access(self, items):
        array_name, indices = items
        return ArrAccess(type=None, array_name=array_name, indices=indices)

    def field_access(self, items):
        recordname, attribute = items
        return FieldAccess(type=None, record_name=recordname, attribute=attribute)

    exprs = return_children

    def invocation(self, items):
        name = items[0]
        args = items[1]
        return Invocation(type=None, name=name, args=args)

    # =====================
    # Expressions: Operations
    # =====================

    def add(self, items):
        return new_bin_op(items, "+")

    def sub(self, items):
        return new_bin_op(items, "-")

    def mul(self, items):
        return new_bin_op(items, "*")

    def div(self, items):
        return new_bin_op(items, "/")

    def eq(self, items):
        return new_bool_op(items, op="==")

    def ne(self, items):
        return new_bool_op(items, op="!=")

    def lt(self, items):
        return new_bool_op(items, op="<")

    def le(self, items):
        return new_bool_op(items, op="<=")

    def gt(self, items):
        return new_bool_op(items, op=">")

    def ge(self, items):
        return new_bool_op(items, op=">=")

    def lor(self, items):
        return new_bool_op(items, op="||")

    def land(self, items):
        return new_bool_op(items, op="&&")

    def lnot(self, items):
        return UnaryOp(type=None, op="!", arg=items[0])
