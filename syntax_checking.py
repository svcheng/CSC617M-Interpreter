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
    Identifier,
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

CONSTANT = "constant"
VARIABLE = "variable"
CUSTOM_TYPE = "custom_type"
FUNCTION = "function"

RESERVED_WORDS = {
    "true",
    "false",
    "let",
    "var",
    "if",
    "else",
    "for",
    "while",
    "repeat",
    "until",
    "return",
    "main",
    "record",
    "int",
    "float",
    "bool",
    "char",
    "str",
    "arr",
    "void",
    "print",
    "scan",
}
BASIC_TYPES = {"int", "float", "bool", "char", "str"}
type_table: dict[str, TypeDec | None] = {k: None for k in BASIC_TYPES}
func_table: dict[str, FuncDec] = dict()
var_table: dict[str, tuple[str, Type | None]] = dict()


# given the name of a record variable, returns its type
def get_record_type(record_var: str):
    var_type = var_table[record_var][1]
    var_type_name = str(
        var_type.name
    )  # is not None because record variables always declared with type
    return type_table[var_type_name]


# constructs symbol tables for custom types and functions while doing syntax checking for them
def build_type_and_function_tables(program: Program):
    for type_dec in program.type_decs:
        type_name = str(type_dec.name)

        # check if definition repeated
        if type_name in type_table:
            raise Exception(f'Re-definition of custom type "{type_name}".')

        # check field declarations
        for field_name, field_type in type_dec.field_list:
            field_name, field_type_name = str(field_name), str(field_type.name)

            # stupid field declarations
            if field_name == type_name:
                raise Exception(
                    "Name of custom type and its attributes must be distinct."
                )
            if field_type_name == type_name:
                raise Exception("Recursive definition of custom type.")

            # types that don't exist
            if not isinstance(field_type, ArrayType):
                if field_type_name not in type_table:
                    raise Exception(f'"{field_type_name}" is not a type.')
            else:
                base_type_name = str(field_type.base_type.name)
                if base_type_name not in type_table:
                    raise Exception(f'"{base_type_name}" is not a valid base type.')

        type_table[type_name] = type_dec

    for func_dec in program.func_decs:
        func_name = str(func_dec.name)
        if func_table.get(func_name) is not None:
            raise Exception(f'Redefinition of function "{func_name}".')

        # check arguments
        for arg_name, arg_type in func_dec.args:
            arg_name, arg_type_name = str(arg_name), str(arg_type.name)

            if not isinstance(arg_type, ArrayType):
                if arg_type_name not in type_table:
                    raise Exception(f'"{arg_type_name}" is not a type.')
            else:
                base_type_name = str(arg_type.base_type.name)
                if base_type_name not in type_table:
                    raise Exception(f'"{base_type_name}" is not a valid base type.')

        func_table[func_name] = func_dec


# checks for return statements not in function declarations
def check_misplaced_returns(node):
    match node:
        case Program(_, _, body):
            for stmt in body:
                check_misplaced_returns(stmt)
        case ReturnStmt():
            raise Exception("Return statement outside of function declaration.")
        case Conditional(_, then_block, else_block):
            for stmt in then_block:
                check_misplaced_returns(stmt)
            if else_block is not None:
                for stmt in else_block:
                    check_misplaced_returns(stmt)
        case ForLoop(_, _, _, _, body):
            for stmt in body:
                check_misplaced_returns(stmt)
        case WhileLoop(_, body) | RepeatLoop(_, body):
            for stmt in body:
                check_misplaced_returns(stmt)
        case _:
            pass


# checks that return statements do not return values if in a void function, and do return values if not in a void func
def check_return_stmts(func_dec: FuncDec):
    func_name = str(func_dec.name)

    def visit(node):
        match node:
            case ReturnStmt(value):
                if func_dec.return_type is None and value is not None:
                    raise Exception(
                        f'Returning value in body of void function "{func_name}".'
                    )
                elif func_dec.return_type is not None and value is None:
                    raise Exception(
                        f'Non-void function "{func_name}" should return a value.'
                    )
            case Conditional(_, then_block, else_block):
                for stmt in then_block:
                    visit(stmt)
                if else_block is not None:
                    for stmt in else_block:
                        visit(stmt)
            case ForLoop(_, _, _, _, body):
                for stmt in body:
                    visit(stmt)
            case WhileLoop(_, body) | RepeatLoop(_, body):
                for stmt in body:
                    visit(stmt)
            case _:
                pass

    for stmt in func_dec.body:
        visit(stmt)


# builds symbol table while checking for improper use of identifiers
def build_var_table(node):
    match node:
        case Program(_, _, main_block):
            for stmt in main_block:
                build_var_table(stmt)

        case ConstDec(name, value):
            name = str(name)

            if name in RESERVED_WORDS:
                raise Exception(
                    f'Invalid identifier name: "{name}" is a reserved word.'
                )
            if name in var_table:
                raise Exception(f"Name {name} has already been defined.")

            build_var_table(value)
            var_table[name] = (CONSTANT, None)
        case VarDec(name, declared_type, init_val):
            name = str(name)

            if name in RESERVED_WORDS:
                raise Exception(
                    f'Invalid identifier name: "{name}" is a reserved word.'
                )
            if name in var_table:
                raise Exception(f"Name {name} has already been defined.")

            # check that declared type is valid
            if isinstance(declared_type, ArrayType):
                # check array dimensions for undeclared vars
                for dim in declared_type.size:
                    build_var_table(dim)
            elif (
                declared_type is not None and str(declared_type.name) not in type_table
            ):
                raise Exception(f'No type named "{str(declared_type.name)}".')

            # check initial value
            if init_val is not None:
                build_var_table(init_val)
            var_table[name] = (VARIABLE, declared_type)

        ###############
        # Statements
        ###############
        case Assignment(lval, rval):
            build_var_table(lval)
            build_var_table(rval)
        case Conditional(condition, then_block, else_block):
            build_var_table(condition)
            for stmt in then_block:
                build_var_table(stmt)
            if else_block is not None:
                for stmt in else_block:
                    build_var_table(stmt)
        case ForLoop(iterator_name, init_val, cond, step, body):
            var_table[str(iterator_name)] = (VARIABLE, NotArrayType("int"))
            build_var_table(init_val)
            build_var_table(cond)
            build_var_table(step)
            for stmt in body:
                build_var_table(stmt)
        case WhileLoop(cond, body) | RepeatLoop(cond, body):
            build_var_table(cond)
            for stmt in body:
                build_var_table(stmt)
        case ReturnStmt(value):
            if value is not None:
                build_var_table(value)
        case PrintStmt(value):
            build_var_table(value)
        case ScanStmt(lval):
            build_var_table(lval)

        ###############
        # Expressions
        ###############
        case Identifier(name, _):  # for identifiers in expressions
            if name not in var_table:
                raise Exception(f'"{name}" is not a defined variable.')
        case ArrAccess(_, array_name, indices):
            build_var_table(array_name)
            for idx in indices:
                build_var_table(idx)
        case FieldAccess(_, record_name, attribute):
            record_name, attribute = str(record_name), str(attribute)
            if record_name not in var_table:
                raise Exception(f'There is no variable named "{record_name}".')

            # check that the record has that attribute
            var_type = get_record_type(record_name)
            if attribute not in [str(name) for name, _ in var_type.field_list]:
                raise Exception(
                    f'Type "{str(var_type.name)}" does not have attribute "{attribute}".'
                )
        case UnaryOp(_, _, arg):
            build_var_table(arg)
        case BinOp(_, _, left, right):
            build_var_table(left)
            build_var_table(right)
        case Invocation(_, name, args):
            name = str(name)
            # check that function exists
            if name not in func_table:
                raise Exception(f'There is no function named "{name}".')

            # check for correct num of function args
            expected_num = len(func_table[name].args)
            actual_num = len(args)
            if expected_num != actual_num:
                raise Exception(
                    f'{actual_num} parameter{"s" if actual_num > 1 else ""} passed to function "{name}" (expected {expected_num}).'
                )

            for arg in args:
                build_var_table(arg)
        case _:
            pass


# tests
if __name__ == "__main__":
    s = """
    void func() {
        return;
    }
    main: {
        var let = 5;
    }
    """
    parser = Lark.open("grammar.lark", start="program", parser="lalr")
    parse_tree = parser.parse(s)
    ast = ASTConstructor().transform(parse_tree)

    build_type_and_function_tables(ast)
    for func_dec in ast.func_decs:
        check_return_stmts(func_dec)
    check_misplaced_returns(ast)

    build_var_table(ast)

    for k, v in var_table.items():
        print(k, v)
