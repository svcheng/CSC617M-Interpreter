from lark import Lark

from ast_constructor import ASTConstructor
from test_cases import VALID_PROGRAMS

parser = Lark.open("grammar.lark", start="program", parser="lalr")
s = """
main: {
    for (i;1;10;2) {}
}
"""
parse_tree = parser.parse(s)
print(parse_tree.pretty())
print()

ast = ASTConstructor().transform(parse_tree)
print(ast)
