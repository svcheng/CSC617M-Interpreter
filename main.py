from lark import Lark

from abstract_syntax_tree.aux_classes import Scope
from abstract_syntax_tree.program import Program
from ast_construction import ASTConstructor
from errors import CustomError


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
    except CustomError as e:
        print("Compilation failed with the following error:")
        print(e)
    except Exception as e:  # if this case is reached there is a bug (in our program)
        raise e


if __name__ == "__main__":
    s = """
        record pair {x: float, y: float}
        main: {
        var x = 5;
        let y = x;
        }
    """
    parser = Lark.open(
        "grammar.lark", start="program", parser="lalr", propagate_positions=True
    )
    parse_tree = parser.parse(s)
    ast = ASTConstructor(s).transform(parse_tree)

    analysis(ast)
