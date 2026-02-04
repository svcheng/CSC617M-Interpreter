from lark import Lark

from ast_constructor import (
    ArrAccess,
    ArrayType,
    Assignment,
    ASTConstructor,
    BinOp,
    Conditional,
    ConstDec,
    FieldAccess,
    ForLoop,
    FuncDec,
    Identifier,
    Invocation,
    NotArrayType,
    PrintStmt,
    Program,
    RepeatLoop,
    ReturnStmt,
    ScanStmt,
    Scope,
    Type,
    TypeDec,
    UnaryOp,
    VarDec,
    VarInfo,
    WhileLoop,
)

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
warnings = []


# given the name of a record variable, returns its type
def get_record_type(record_var: str, scope: Scope):
    var_type = scope.var_table[record_var].datatype
    # should pass because record variables always declared with type
    assert var_type is not None

    var_type_name = str(var_type.name)
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
        if func_name in type_table:
            raise Exception(f"{func_name} is already defined as a custom type.")
        if func_name in func_table:
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
        case Program(_, _, _, body):
            for stmt in body:
                check_misplaced_returns(stmt)
        case ReturnStmt():
            raise Exception("Return statement outside of function declaration.")
        case Conditional(_, _, then_block, else_block):
            for stmt in then_block:
                check_misplaced_returns(stmt)
            if else_block is not None:
                for stmt in else_block:
                    check_misplaced_returns(stmt)
        case ForLoop(_, _, _, _, _, body):
            for stmt in body:
                check_misplaced_returns(stmt)
        case WhileLoop(_, _, body) | RepeatLoop(_, _, body):
            for stmt in body:
                check_misplaced_returns(stmt)
        case _:
            pass


# checks that return statements do not return values if in a void function, and do return values if not in a void func
def check_return_stmts(func_dec: FuncDec):
    func_name = str(func_dec.name)

    def visit(node):
        match node:
            case ReturnStmt(_, value):
                if func_dec.return_type is None and value is not None:
                    raise Exception(
                        f'Returning value in body of void function "{func_name}".'
                    )
                elif func_dec.return_type is not None and value is None:
                    raise Exception(
                        f'Non-void function "{func_name}" should return a value.'
                    )
            case Conditional(_, _, then_block, else_block):
                for stmt in then_block:
                    visit(stmt)
                if else_block is not None:
                    for stmt in else_block:
                        visit(stmt)
            case ForLoop(_, _, _, _, _, body):
                for stmt in body:
                    visit(stmt)
            case WhileLoop(_, _, body) | RepeatLoop(_, _, body):
                for stmt in body:
                    visit(stmt)
            case _:
                pass

    for stmt in func_dec.body:
        visit(stmt)


# builds symbol tables while checking for improper use of identifiers
def build_var_tables(node, cur_scope: Scope):
    match node:
        case Program(_, _, _, main_block):
            node.scope = cur_scope
            for stmt in main_block:
                build_var_tables(stmt, node.scope)

        case ConstDec(_, name, value):
            node.scope = cur_scope
            name = str(name)

            if name in RESERVED_WORDS:
                raise Exception(
                    f'Invalid identifier name: "{name}" is a reserved word.'
                )
            if name in type_table:
                raise Exception(f'"{name}" is already defined as a custom type.')
            if name in func_table:
                raise Exception(f'"{name}" is already defined as a function.')
            if cur_scope.var_name_in_scope(name):
                raise Exception(f"Name {name} has already been defined.")

            build_var_tables(value, cur_scope)
            cur_scope.insert_varname(name, VarInfo(True, None))
        case VarDec(_, name, declared_type, init_val):
            node.scope = cur_scope
            name = str(name)

            if name in RESERVED_WORDS:
                raise Exception(
                    f'Invalid identifier name: "{name}" is a reserved word.'
                )
            if name in type_table:
                raise Exception(f'"{name}" is already defined as a custom type.')
            if name in func_table:
                raise Exception(f'"{name}" is already defined as a function.')
            if cur_scope.var_name_in_scope(name):
                raise Exception(f"Name {name} has already been defined.")

            # check that declared type is valid
            if isinstance(declared_type, ArrayType):
                # check array dimensions for undeclared vars
                for dim in declared_type.size:
                    build_var_tables(dim, cur_scope)
            elif (
                declared_type is not None and str(declared_type.name) not in type_table
            ):
                raise Exception(f'No type named "{str(declared_type.name)}".')

            # check initial value
            if init_val is not None:
                build_var_tables(init_val, cur_scope)
            cur_scope.insert_varname(name, VarInfo(False, declared_type))

        ###############
        # Other Statements
        ###############
        case Assignment(_, lval, rval):
            node.scope = cur_scope
            build_var_tables(lval, cur_scope)
            build_var_tables(rval, cur_scope)
            # no constant assignment
            if cur_scope.var_is_constant(str(lval)):
                raise Exception("Constant values cannot be reassigned.")
        case Conditional(_, condition, then_block, else_block):
            node.scope = cur_scope
            build_var_tables(condition, cur_scope)

            # if and else blocks have separate scopes
            then_scope = Scope(cur_scope, dict())
            for stmt in then_block:
                build_var_tables(stmt, then_scope)

            else_scope = Scope(cur_scope, dict())
            if else_block is not None:
                for stmt in else_block:
                    build_var_tables(stmt, else_scope)

            # add symbols declared in if/else blocks so that user may be warned
            for var_name, var_info in then_scope.var_table.items():
                new_info = VarInfo(var_info.is_constant, var_info.datatype, True)
                cur_scope.insert_varname(var_name, new_info)
            for var_name, var_info in else_scope.var_table.items():
                new_info = VarInfo(var_info.is_constant, var_info.datatype, True)
                cur_scope.insert_varname(var_name, new_info)

        case ForLoop(_, iterator_name, init_val, cond, step, body):
            node.scope = Scope(cur_scope, dict())
            node.scope.insert_varname(
                str(iterator_name), VarInfo(False, NotArrayType("int"))
            )
            build_var_tables(init_val, cur_scope)
            build_var_tables(cond, cur_scope)
            build_var_tables(step, cur_scope)
            for stmt in body:
                build_var_tables(stmt, node.scope)
        case WhileLoop(_, cond, body) | RepeatLoop(_, cond, body):
            node.scope = cur_scope
            build_var_tables(cond, cur_scope)
            for stmt in body:
                build_var_tables(stmt, cur_scope)
        case ReturnStmt(_, value):
            node.scope = cur_scope
            if value is not None:
                build_var_tables(value, cur_scope)
        case PrintStmt(_, value):
            node.scope = cur_scope
            build_var_tables(value, cur_scope)
        case ScanStmt(_, lval):
            node.scope = cur_scope
            build_var_tables(lval, cur_scope)

        ###############
        # Expressions
        ###############
        case Identifier(_, name, _):  # for identifiers in expressions and assignment
            node.scope = cur_scope
            if not cur_scope.var_name_in_scope(name):
                raise Exception(f'"{name}" is not a defined variable.')

            # warn user if variable referenced was declared in a conditional
            if cur_scope.conditionally_defined(name):
                warnings.append(
                    f'Variable/Constant "{name}" was declared in a conditional body and may not be defined.'
                )
        case ArrAccess(_, _, array_name, indices):
            node.scope = cur_scope
            build_var_tables(array_name, cur_scope)
            for idx in indices:
                build_var_tables(idx, cur_scope)
        case FieldAccess(_, _, record_name, attribute):
            node.scope = cur_scope
            record_name, attribute = str(record_name), str(attribute)
            if not cur_scope.var_name_in_scope(record_name):
                raise Exception(f'There is no variable named "{record_name}".')

            # check that the record has that attribute
            var_type = get_record_type(record_name, cur_scope)
            assert var_type is not None
            if attribute not in [str(name) for name, _ in var_type.field_list]:
                raise Exception(
                    f'Type "{str(var_type.name)}" does not have attribute "{attribute}".'
                )
        case UnaryOp(_, _, _, arg):
            node.scope = cur_scope
            build_var_tables(arg, cur_scope)
        case BinOp(_, _, _, left, right):
            node.scope = cur_scope
            build_var_tables(left, cur_scope)
            build_var_tables(right, cur_scope)
        case Invocation(_, _, name, args):
            node.scope = cur_scope
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
                build_var_tables(arg, cur_scope)
        case _:
            pass


# enforces syntax and some semantics
def analyze(ast):
    build_type_and_function_tables(ast)
    for func_dec in ast.func_decs:
        check_return_stmts(func_dec)
    check_misplaced_returns(ast)
    build_var_tables(ast, Scope(None, dict()))


# tests
if __name__ == "__main__":
    s = """
    record pair {x: int}
    void func() {}
    main: {
        let x = 5;
        var z: int;
        func();
    }
    """
    parser = Lark.open("grammar.lark", start="program", parser="lalr")
    parse_tree = parser.parse(s)
    ast = ASTConstructor().transform(parse_tree)
    analyze(ast)
    print(warnings)
