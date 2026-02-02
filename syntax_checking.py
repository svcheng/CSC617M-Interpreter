from lark import Lark

from ast_constructor import (
    ArrAccess,
    ArrayType,
    Assignment,
    ASTConstructor,
    BinOp,
    Conditional,
    ConstDec,
    Expr,
    FieldAccess,
    ForLoop,
    FuncDec,
    Invocation,
    Literal,
    NotArrayType,
    PrintStmt,
    Program,
    RepeatLoop,
    ReturnStmt,
    ScanStmt,
    Type,
    TypeDec,
    UnaryOp,
    VarDec,
    WhileLoop,
)

symbol_table = dict()

CONSTANT = "constant"
VARIABLE = "variable"
CUSTOM_TYPE = "custom_type"
FUNCTION = "function"


def build_symbol_table(node):
    match node:
        case Program(const_decs, type_decs, func_decs, main_block):
            build_symbol_table(const_decs)
            build_symbol_table(type_decs)
            build_symbol_table(func_decs)
            for stmt in main_block:
                build_symbol_table(stmt)
        case ConstDec(name, value):
            if name in symbol_table:
                raise Exception
            symbol_table[node.name] = (CONSTANT, None)
        case VarDec(name, declared_type, init_value):
            if name in symbol_table:
                raise Exception

            symbol_table[node.name] = (VARIABLE, declared_type)
        case TypeDec(name, field_list):
            if name in symbol_table:
                raise Exception

            symbol_table[node.name] = (CUSTOM_TYPE, field_list)
        case FuncDec(name, args, return_type, body):
            if name in symbol_table:
                raise Exception

            symbol_table[name] = (FUNCTION, node)
        case Conditional(_, then_block, else_block):
            for stmt in then_block:
                build_symbol_table(stmt)
            if else_block is not None:
                for stmt in else_block:
                    build_symbol_table(stmt)
        # case ForLoop(iterator_name):
        #     symbol_table[iterator_name] = (FUNCTION, node)
        case _:
            pass


s1 = """
main: {
    let x = -5.0;
    var y = x + 7;
}
"""

# variable used before declaration
s2 = """
main: {
    let x = y + 1;
}
"""
