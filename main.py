import argparse
import dataclasses
from pathlib import Path

from lark import Lark

from abstract_syntax_tree.aux_classes import Scope
from abstract_syntax_tree.program import Program
from ast_construction import ASTConstructor
from errors import CustomError
from scanner import scan


def print_ast(node, indent=0):
    pad = "  " * indent

    if not dataclasses.is_dataclass(node):
        if isinstance(node, tuple):
            for item in node:
                print_ast(item, indent + 2)
        else:
            print(f"{pad}{repr(node)}")
        return

    print(f"{pad}{type(node).__name__}")
    for field in dataclasses.fields(node):
        if field.name in ("scope", "meta_info"):
            continue
        print(f"{pad}  {field.name}:")

        value = getattr(node, field.name)
        if isinstance(value, list):
            if not value:
                print(f"{pad}    []")
            for item in value:
                print_ast(item, indent + 2)
        # elif isinstance(value, tuple):
        #     for item in value:
        #         print_ast(item, indent + 2)
        else:
            print_ast(value, indent + 2)


def analysis(ast: Program):
    try:
        ast.init_scope(Scope(None))
        ast.build_type_table()
        ast.build_func_table()
        ast.check_misplaced_returns()
        ast.build_var_tables()
        ast.check_types()
        ast.check_returns()
        ast.check_null_references()
        ast.ensure_exhaustive_returns()
    except CustomError as e:
        print("Compilation failed with the following error:")
        print(e)
    except Exception as e:  # if this case is reached there is a bug (in our program)
        raise e


if __name__ == "__main__":
    # read inputs and perform scanning
    arg_parser = argparse.ArgumentParser(description="Interpreter")
    arg_parser.add_argument("filename", help="Source file to interpret")
    arg_parser.add_argument("-so", "--output", help="Write scanner output to file")
    args = arg_parser.parse_args()

    program_str = Path(args.filename).read_text(encoding="utf-8")
    scan(program_str, args.output)

    # parse program, create parse tree
    parser = Lark.open(
        "grammar.lark", start="program", parser="lalr", propagate_positions=True
    )
    parse_tree = parser.parse(program_str)

    # print("=========================== Parse Tree ===========================")
    # print(parse_tree.pretty())

    # create AST
    ast = ASTConstructor(program_str).transform(parse_tree)

    # perform "compile time" (pre-execution) syntax and semantic checking
    analysis(ast)

    # print(
    #     "=========================== Abstract Syntax Tree ==========================="
    # )
    # print_ast(ast)
