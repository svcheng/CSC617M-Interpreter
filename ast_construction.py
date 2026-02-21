from typing import Optional

from lark import Lark, Transformer, v_args

from abstract_syntax_tree.arr_access import ArrAccess
from abstract_syntax_tree.assignment import Assignment
from abstract_syntax_tree.aux_classes import MetaInfo
from abstract_syntax_tree.bin_op import BinOp
from abstract_syntax_tree.cast import Cast
from abstract_syntax_tree.conditional import Conditional
from abstract_syntax_tree.const_dec import ConstDec
from abstract_syntax_tree.field_access import FieldAccess
from abstract_syntax_tree.for_loop import ForLoop
from abstract_syntax_tree.func_dec import FuncDec
from abstract_syntax_tree.identifier import Identifier
from abstract_syntax_tree.invocation import Invocation
from abstract_syntax_tree.literal import Literal
from abstract_syntax_tree.print_stmt import PrintStmt
from abstract_syntax_tree.program import Program
from abstract_syntax_tree.repeat_loop import RepeatLoop
from abstract_syntax_tree.return_stmt import ReturnStmt
from abstract_syntax_tree.scan_stmt import ScanStmt
from abstract_syntax_tree.type_dec import TypeDec
from abstract_syntax_tree.types import (
    BOOL,
    CHAR,
    FLOAT,
    INT,
    STR,
    ArrayType,
    NotArrayType,
    Type,
)
from abstract_syntax_tree.unary_op import UnaryOp
from abstract_syntax_tree.var_dec import VarDec
from abstract_syntax_tree.while_loop import WhileLoop


@v_args(meta=True)
class ASTConstructor(Transformer):
    def __init__(self, program_str: str):
        super().__init__()
        self.program_str = program_str

    # =====================
    # Helper Methods
    # =====================

    def return_fst(self, _, children):
        return children[0]

    def return_children(self, _, children):
        return children

    def new_bin_op(self, meta, children, datatype: Optional[Type], op: str):
        left, right = children
        return BinOp(
            scope=None,
            meta_info=MetaInfo.from_meta(meta, self.program_str),
            datatype=datatype,
            op=op,
            left=left,
            right=right,
        )

    def new_bool_op(self, meta, children, op: str):
        return self.new_bin_op(meta=meta, children=children, datatype=BOOL, op=op)

    # =====================
    # Terminals
    # =====================

    def IDENTIFIER(self, token):
        return Identifier(
            scope=None,
            meta_info=MetaInfo.from_token(token, self.program_str),
            name=token.value,
        )

    def INT(self, token):
        raw_value = token.value
        return Literal(
            scope=None,
            meta_info=MetaInfo.from_token(token, self.program_str),
            datatype=INT,
            value=int(raw_value),
        )

    def FLOAT(self, token):
        raw_value = token.value
        return Literal(
            scope=None,
            meta_info=MetaInfo.from_token(token, self.program_str),
            datatype=FLOAT,
            value=float(raw_value),
        )

    def BOOLVAL(self, token):
        raw_value = token.value
        return Literal(
            scope=None,
            meta_info=MetaInfo.from_token(token, self.program_str),
            datatype=BOOL,
            value=raw_value == "true",
        )

    def CHARVAL(self, token):
        raw_value = token.value
        return Literal(
            scope=None,
            meta_info=MetaInfo.from_token(token, self.program_str),
            datatype=CHAR,
            value=raw_value[1:-1],
        )

    def STRVAL(self, token):
        raw_value = token.value
        return Literal(
            scope=None,
            meta_info=MetaInfo.from_token(token, self.program_str),
            datatype=STR,
            value=raw_value[1:-1],
        )

    # =====================
    # Program Structure
    # =====================

    def program(self, meta, children):
        type_decs, func_decs, main_block = children
        return Program(
            scope=None,
            meta_info=MetaInfo.from_meta(meta, self.program_str),
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
            scope=None,
            meta_info=MetaInfo.from_meta(meta, self.program_str),
            name=name,
            value=value,
        )

    def var_dec_no_assign(self, meta, children):
        _, name, declared_type = children
        return VarDec(
            scope=None,
            meta_info=MetaInfo.from_meta(meta, self.program_str),
            name=name,
            declared_type=declared_type,
            init_value=None,
        )

    def var_dec_assign(self, meta, children):
        _, name, init_value = children
        return VarDec(
            scope=None,
            meta_info=MetaInfo.from_meta(meta, self.program_str),
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
            meta_info=MetaInfo.from_meta(meta, self.program_str),
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
            meta_info=MetaInfo.from_meta(meta, self.program_str),
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
        return ArrayType(base_type=base_type, size=size)

    # =====================
    # Statements
    # =====================

    def assignment(self, meta, children):
        lval, rval = children
        return Assignment(
            scope=None,
            meta_info=MetaInfo.from_meta(meta, self.program_str),
            lval=lval,
            rval=rval,
        )

    def conditional(self, meta, children):
        condition = children[1]
        then_block = children[2]
        else_block = children[4] if len(children) > 3 else None
        return Conditional(
            scope=None,
            meta_info=MetaInfo.from_meta(meta, self.program_str),
            condition=condition,
            then_block=then_block,
            else_block=else_block,
        )

    def for_loop(self, meta, children):
        _, iterator_name, range_start, range_end, step, body = children
        return ForLoop(
            scope=None,
            meta_info=MetaInfo.from_meta(meta, self.program_str),
            iterator_name=iterator_name,
            range_start=range_start,
            range_end=range_end,
            step=step,
            body=body,
        )

    def while_loop(self, meta, children):
        _, cond, body = children
        return WhileLoop(
            scope=None,
            meta_info=MetaInfo.from_meta(meta, self.program_str),
            cond=cond,
            body=body,
        )

    def repeat_loop(self, meta, children):
        _, body, _, cond = children
        return RepeatLoop(
            scope=None,
            meta_info=MetaInfo.from_meta(meta, self.program_str),
            cond=cond,
            body=body,
        )

    def return_stmt(self, meta, children):
        value = children[1] if len(children) > 1 else None
        return ReturnStmt(
            scope=None,
            meta_info=MetaInfo.from_meta(meta, self.program_str),
            value=value,
        )

    def print_stmt(self, meta, children):
        value = children[1]
        return PrintStmt(
            scope=None,
            meta_info=MetaInfo.from_meta(meta, self.program_str),
            value=value,
        )

    def scan_stmt(self, meta, children):
        lval = children[1]
        return ScanStmt(
            scope=None, meta_info=MetaInfo.from_meta(meta, self.program_str), lval=lval
        )

    # =====================
    # Expressions: Scalars
    # =====================

    def arr_access(self, meta, children):
        array_name, indices = children
        return ArrAccess(
            scope=None,
            meta_info=MetaInfo.from_meta(meta, self.program_str),
            datatype=None,
            array_name=array_name,
            indices=indices,
        )

    def field_access(self, meta, children):
        recordname, attribute = children
        return FieldAccess(
            scope=None,
            meta_info=MetaInfo.from_meta(meta, self.program_str),
            datatype=None,
            record_name=recordname,
            attribute=attribute,
        )

    exprs = return_children

    def invocation(self, meta, children):
        name = children[0]
        args = children[1] if children[1] is not None else []
        return Invocation(
            scope=None,
            meta_info=MetaInfo.from_meta(meta, self.program_str),
            datatype=None,
            name=name,
            args=args,
        )

    def cast(self, meta, children):
        _, arg, target_type = children
        return Cast(
            scope=None,
            meta_info=MetaInfo.from_meta(meta, self.program_str),
            datatype=None,
            arg=arg,
            target_type=target_type,
        )

    # =====================
    # Expressions: Operations
    # =====================

    def add(self, meta, children):
        return self.new_bin_op(meta=meta, children=children, datatype=None, op="+")

    def sub(self, meta, children):
        return self.new_bin_op(meta=meta, children=children, datatype=None, op="-")

    def mul(self, meta, children):
        return self.new_bin_op(meta=meta, children=children, datatype=None, op="*")

    def div(self, meta, children):
        return self.new_bin_op(meta=meta, children=children, datatype=None, op="/")

    def eq(self, meta, children):
        return self.new_bool_op(meta, children, op="==")

    def ne(self, meta, children):
        return self.new_bool_op(meta, children, op="!=")

    def lt(self, meta, children):
        return self.new_bool_op(meta, children, op="<")

    def le(self, meta, children):
        return self.new_bool_op(meta, children, op="<=")

    def gt(self, meta, children):
        return self.new_bool_op(meta, children, op=">")

    def ge(self, meta, children):
        return self.new_bool_op(meta, children, op=">=")

    def lor(self, meta, children):
        return self.new_bool_op(meta, children, op="||")

    def land(self, meta, children):
        return self.new_bool_op(meta, children, op="&&")

    def lnot(self, meta, children):
        return UnaryOp(
            scope=None,
            meta_info=MetaInfo.from_meta(meta, self.program_str),
            datatype=None,
            op="!",
            arg=children[0],
        )


# for testing
if __name__ == "__main__":
    parser = Lark.open(
        "grammar.lark", start="program", parser="lalr", propagate_positions=True
    )
    s = """
    main: {
        let x = cast(x, "int");
    }
    """

    parse_tree = parser.parse(s)
    print(parse_tree.pretty())
    ast = ASTConstructor().transform(parse_tree)
    print(ast.main_block[0].value)
