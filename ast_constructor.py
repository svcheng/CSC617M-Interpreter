from dataclasses import dataclass
from typing import Any, Optional, Self

from lark import Lark, Token, Transformer, v_args
from lark.tree import Meta

# =====================
# Auxialliary info useful for syntax and semantic checking
# =====================


@dataclass
class VarInfo:
    is_constant: bool
    datatype: Optional["Type"]  # datatype=None for variables declared with assignment
    declared_in_cond_block: bool = False


@dataclass
class Scope:
    parent_scope: Optional[Self]  # has type Scope or None
    var_table: dict[str, VarInfo]

    def var_name_in_scope(self, var_name: str) -> bool:
        if var_name in self.var_table:
            return True
        elif self.parent_scope is not None and self.parent_scope.var_name_in_scope(
            var_name
        ):
            return True

        return False

    def insert_varname(self, var_name: str, var_info: VarInfo) -> None:
        self.var_table[var_name] = var_info

    def get_var_info(self, var_name: str) -> Optional[VarInfo]:
        if var_name in self.var_table:
            return self.var_table[var_name]
        elif self.parent_scope is not None:
            return self.parent_scope.get_var_info(var_name)
        else:
            return None

    def var_is_constant(self, var_name) -> bool:
        var_info = self.get_var_info(var_name)
        if var_info is None:
            return False

        return var_info.is_constant

    def conditionally_defined(self, var_name: str) -> bool:
        var_info = self.get_var_info(var_name)
        if var_info is None:
            return False

        return var_info.declared_in_cond_block


@dataclass
class MetaInfo:
    start_line: int
    end_line: int
    start_col: int
    end_col: int
    start_pos: int
    end_pos: int

    @staticmethod
    def from_meta(meta: Meta):
        return MetaInfo(
            meta.line,
            meta.end_line,
            meta.column,
            meta.end_column,
            meta.start_pos,
            meta.end_pos,
        )

    @staticmethod
    def from_token(token: Token):
        return MetaInfo(
            token.line,
            token.end_line,
            token.column,
            token.end_column,
            token.start_pos,
            token.end_pos,
        )


@dataclass
class Node:
    # will always be assigned None during ast construction, to be determined during syntax checking
    scope: Optional[Scope]
    meta_info: MetaInfo  # contains info about the rule matched like the line number, col number, etc.


# =====================
# Program Structure
# =====================


@dataclass
class Identifier(Node):
    name: str

    def __str__(self):
        return self.name


@dataclass
class Program(Node):
    type_decs: list["TypeDec"]
    func_decs: list["FuncDec"]
    main_block: list


# =====================
# Declarations
# =====================


@dataclass
class VarDec(Node):
    name: Identifier
    # quotations below so that IDE does not complain that Type is not defined
    declared_type: Optional["Type"]
    init_value: Optional["Expr"]


@dataclass
class ConstDec(Node):
    name: Identifier
    value: "Expr"


@dataclass
class TypeDec(Node):
    name: Identifier
    field_list: list[tuple[Identifier, "Type"]]


@dataclass
class FuncDec(Node):
    name: Identifier
    args: list[tuple[Identifier, "Type"]]
    return_type: Optional["Type"]
    body: list


# =====================
# Types
# =====================


@dataclass
class Type:
    name: str | Identifier


@dataclass
class NotArrayType(Type):
    pass


@dataclass
class ArrayType(Type):
    base_type: NotArrayType
    size: list["Expr"]


# =====================
# Statements
# =====================


@dataclass
class Assignment(Node):
    lval: "Expr"
    rval: "Expr"


@dataclass
class Conditional(Node):
    condition: "Expr"
    then_block: list
    else_block: Optional[list]


@dataclass
class ForLoop(Node):
    iterator_name: Identifier
    init_val: "Expr"
    cond: "Expr"
    step: "Expr"
    body: list


@dataclass
class WhileLoop(Node):
    cond: "Expr"
    body: list


@dataclass
class RepeatLoop(Node):
    cond: "Expr"
    body: list


@dataclass
class ReturnStmt(Node):
    value: Optional["Expr"]


@dataclass
class PrintStmt(Node):
    value: "Expr"


@dataclass
class ScanStmt(Node):
    lval: "Expr"


# =====================
# Expressions
# =====================


@dataclass
class Expr(Node):
    pass


@dataclass
class Literal(Expr):
    value: Any
    datatype: Optional[Type]  # type of None means type is still unknown


@dataclass
class ArrAccess(Expr):
    array_name: Identifier
    indices: list["Expr"]


@dataclass
class FieldAccess(Expr):
    record_name: Identifier
    attribute: Identifier


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
    name: Identifier
    args: list[Expr]


############################################################
# AST Functions/Classes
############################################################


def new_bin_op(meta, children, op: str):
    left, right = children
    return BinOp(
        scope=None, meta_info=MetaInfo.from_meta(meta), op=op, left=left, right=right
    )


def new_bool_op(meta, children, op: str):
    return new_bin_op(meta=meta, children=children, op=op)


@v_args(meta=True)
class ASTConstructor(Transformer):
    def return_fst(self, _, children):
        return children[0]

    def return_children(self, _, children):
        return children

    def IDENTIFIER(self, token):
        return Identifier(
            scope=None,
            meta_info=MetaInfo.from_token(token),
            name=token.value,
        )

    # =====================
    # Program Structure
    # =====================

    def program(self, meta, children):
        type_decs, func_decs, main_block = children
        return Program(
            scope=None,
            meta_info=MetaInfo.from_meta(meta),
            type_decs=type_decs,
            func_decs=func_decs,
            main_block=main_block,
        )

    const_decs = return_children
    type_decs = return_children
    func_decs = return_children

    def main_block(self, _, children):
        return children[1]  # index 0 is the "main" token

    stmts = return_children

    # =====================
    # Declarations
    # =====================

    def const_dec(self, meta, children):
        _, name, value = children
        return ConstDec(
            scope=None, meta_info=MetaInfo.from_meta(meta), name=name, value=value
        )

    def var_dec_no_assign(self, meta, children):
        _, name, declared_type = children
        return VarDec(
            scope=None,
            meta_info=MetaInfo.from_meta(meta),
            name=name,
            declared_type=declared_type,
            init_value=None,
        )

    def var_dec_assign(self, meta, children):
        _, name, init_value = children
        return VarDec(
            scope=None,
            meta_info=MetaInfo.from_meta(meta),
            name=name,
            declared_type=None,
            init_value=init_value,
        )

    def type_dec(self, meta, children):
        name = children[1]
        field_list = children[2]
        return TypeDec(
            scope=None,
            name=name,
            meta_info=MetaInfo.from_meta(meta),
            field_list=field_list,
        )

    field_list = return_children

    def field(self, _, children):
        attr_name, attr_type = children
        return (attr_name, attr_type)

    def func_dec(self, meta, children):
        return_type, name, args, body = children
        if args is None:
            args = []
        if body is None:
            body = []
        return FuncDec(
            scope=None,
            meta_info=MetaInfo.from_meta(meta),
            name=name,
            args=args,
            return_type=return_type,
            body=body,
        )

    stmts_with_return = return_children

    # =====================
    # Types
    # =====================

    def VOID(self, _):
        return None

    def not_array_type(self, _, children):
        type_name = children[0]
        return NotArrayType(name=type_name)

    def basic_type(self, _, children):
        name = children[0].value
        return name

    def array_type(self, _, children):
        base_type = children[0]
        size = children[2]
        return ArrayType(name="arr", base_type=base_type, size=size)

    # =====================
    # Statements
    # =====================

    def assignment(self, meta, children):
        lval, rval = children
        return Assignment(
            scope=None, meta_info=MetaInfo.from_meta(meta), lval=lval, rval=rval
        )

    def conditional(self, meta, children):
        condition = children[1]
        then_block = children[2]
        else_block = children[4] if len(children) > 3 else None
        return Conditional(
            scope=None,
            meta_info=MetaInfo.from_meta(meta),
            condition=condition,
            then_block=then_block,
            else_block=else_block,
        )

    def for_loop(self, meta, children):
        _, iterator_name, init_val, cond, step, body = children
        return ForLoop(
            scope=None,
            meta_info=MetaInfo.from_meta(meta),
            iterator_name=iterator_name,
            init_val=init_val,
            cond=cond,
            step=step,
            body=body,
        )

    def while_loop(self, meta, children):
        _, cond, body = children
        return WhileLoop(
            scope=None, meta_info=MetaInfo.from_meta(meta), cond=cond, body=body
        )

    def repeat_loop(self, meta, children):
        _, body, _, cond = children
        return RepeatLoop(
            scope=None, meta_info=MetaInfo.from_meta(meta), cond=cond, body=body
        )

    def return_stmt(self, meta, children):
        value = children[1] if len(children) > 1 else None
        return ReturnStmt(scope=None, meta_info=MetaInfo.from_meta(meta), value=value)

    def print_stmt(self, meta, children):
        value = children[1]
        return PrintStmt(scope=None, meta_info=MetaInfo.from_meta(meta), value=value)

    def scan_stmt(self, meta, children):
        lval = children[1]
        return ScanStmt(scope=None, meta_info=MetaInfo.from_meta(meta), lval=lval)

    # =====================
    # Expressions: Scalars
    # =====================

    def int_literal(self, meta, children):
        token = children[0]
        raw_value = token.value
        return Literal(
            scope=None,
            meta_info=MetaInfo.from_meta(meta),
            datatype=NotArrayType("int"),
            value=int(raw_value),
        )

    def float_literal(self, meta, children):
        token = children[0]
        raw_value = token.value
        return Literal(
            scope=None,
            meta_info=MetaInfo.from_meta(meta),
            datatype=NotArrayType("float"),
            value=float(raw_value),
        )

    def bool_literal(self, meta, children):
        token = children[0]
        raw_value = token.value
        return Literal(
            scope=None,
            meta_info=MetaInfo.from_meta(meta),
            datatype=NotArrayType("bool"),
            value=raw_value == "true",
        )

    def str_literal(self, meta, children):
        token = children[0]
        raw_value = token.value
        return Literal(
            scope=None,
            meta_info=MetaInfo.from_meta(meta),
            datatype=NotArrayType("str"),
            value=raw_value[1:-1],
        )

    def arr_access(self, meta, children):
        array_name, indices = children
        return ArrAccess(
            scope=None,
            meta_info=MetaInfo.from_meta(meta),
            array_name=array_name,
            indices=indices,
        )

    def field_access(self, meta, children):
        recordname, attribute = children
        return FieldAccess(
            scope=None,
            meta_info=MetaInfo.from_meta(meta),
            record_name=recordname,
            attribute=attribute,
        )

    exprs = return_children

    def invocation(self, meta, children):
        name = children[0]
        args = children[1] if children[1] is not None else []
        return Invocation(
            scope=None, meta_info=MetaInfo.from_meta(meta), name=name, args=args
        )

    # =====================
    # Expressions: Operations
    # =====================

    def add(self, meta, children):
        return new_bin_op(meta, children, "+")

    def sub(self, meta, children):
        return new_bin_op(meta, children, "-")

    def mul(self, meta, children):
        return new_bin_op(meta, children, "*")

    def div(self, meta, children):
        return new_bin_op(meta, children, "/")

    def eq(self, meta, children):
        return new_bool_op(meta, children, op="==")

    def ne(self, meta, children):
        return new_bool_op(meta, children, op="!=")

    def lt(self, meta, children):
        return new_bool_op(meta, children, op="<")

    def le(self, meta, children):
        return new_bool_op(meta, children, op="<=")

    def gt(self, meta, children):
        return new_bool_op(meta, children, op=">")

    def ge(self, meta, children):
        return new_bool_op(meta, children, op=">=")

    def lor(self, meta, children):
        return new_bool_op(meta, children, op="||")

    def land(self, meta, children):
        return new_bool_op(meta, children, op="&&")

    def lnot(self, meta, children):
        return UnaryOp(
            scope=None, meta_info=MetaInfo.from_meta(meta), op="!", arg=children[0]
        )


# testing
if __name__ == "__main__":
    parser = Lark.open(
        "grammar.lark", start="program", parser="lalr", propagate_positions=True
    )
    s = """
    main: {
        var x: int arr[5];
    }
    """
    parse_tree = parser.parse(s)
    ast = ASTConstructor().transform(parse_tree)
    print(ast)
