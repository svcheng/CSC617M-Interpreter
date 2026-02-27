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
        ast.ensure_exhaustive_returns()
    except CustomError as e:
        print("Compilation failed with the following error:")
        print(e)
    except Exception as e:  # if this case is reached there is a bug (in our program)
        raise e


if __name__ == "__main__":
    s = """
        int func() {
            while (3 < 4) {
                return 4;
            }
            if (5 < 4) {
                let x = 6;
                return 4;
            } else {
                let x = 6;
                while (true) {
                if (8 == 7) {return 4;} else {return 5;}
                }

            }
            return 5;
        }
        main: {
        }
    """
    parser = Lark.open(
        "grammar.lark", start="program", parser="lalr", propagate_positions=True
    )
    parse_tree = parser.parse(s)
    ast = ASTConstructor(s).transform(parse_tree)

    analysis(ast)
