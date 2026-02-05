from typing import Optional

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
    Literal,
    MetaInfo,
    NotArrayType,
    PrintStmt,
    Program,
    RepeatLoop,
    ReturnStmt,
    ScanStmt,
    Scope,
    TypeDec,
    UnaryOp,
    VarDec,
    VarInfo,
    WhileLoop,
)

INT, FLOAT, BOOL, CHAR, STR = "int", "float", "bool", "char", "str"
BASIC_TYPES = {INT, FLOAT, BOOL, CHAR, STR}
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
    "arr",
    "void",
    "print",
    "scan",
} | BASIC_TYPES

####################
# Error Classes
####################


class CustomError(Exception):
    def __init__(
        self,
        msg_prefix: str,
        error_msg: str,
        program_str: str,
        meta_info: MetaInfo,
        show_code_block: bool = True,
    ):
        self.msg_prefix = msg_prefix
        self.error_msg = error_msg
        self.program_str = program_str
        self.meta_info = meta_info
        self.show_code_block = show_code_block
        final_error_msg = self.format_error_msg()
        super().__init__(final_error_msg)

    def format_error_msg(self):
        start_idx, end_idx = self.meta_info.start_pos, self.meta_info.end_pos
        program_segment = self.program_str[start_idx:end_idx]

        if self.meta_info.start_line != self.meta_info.end_line:
            line_num = f"lines {self.meta_info.start_line}-{self.meta_info.end_line}:"
        else:
            line_num = f"line {self.meta_info.start_line}:"

        dashes = "-" * 50
        msg = self.msg_prefix + line_num + " " + self.error_msg + "\n"
        if self.show_code_block:
            msg = msg + (dashes + "\n" + program_segment + "\n" + dashes)
        return msg


class Warning(CustomError):
    def __init__(
        self,
        program_str: str,
        meta_info: MetaInfo,
        error_msg: str,
        show_code_block: bool = True,
    ):
        msg_prefix = "WARNING: In "
        super().__init__(
            msg_prefix=msg_prefix,
            error_msg=error_msg,
            program_str=program_str,
            meta_info=meta_info,
            show_code_block=show_code_block,
        )


class KeywordCollisionError(CustomError):
    error_name = "KEYWORD-COLLISION ERROR"

    def __init__(self, program_str: str, meta_info: MetaInfo, identifier: str):
        msg_prefix = self.error_name + " found in "
        error_msg = f'"{identifier}" is a reserved word and cannot be an identifier'
        super().__init__(
            msg_prefix=msg_prefix,
            error_msg=error_msg,
            program_str=program_str,
            meta_info=meta_info,
        )


class NameCollisionError(CustomError):
    error_name = "NAME-COLLISION ERROR"

    def __init__(
        self,
        program_str: str,
        meta_info: MetaInfo,
        identifier: str,
        alr_existing_construct: str,
    ):
        msg_prefix = self.error_name + " found in "
        error_msg = (
            f'"{identifier}" is already bound to an existing {alr_existing_construct}'
        )
        super().__init__(
            msg_prefix=msg_prefix,
            error_msg=error_msg,
            program_str=program_str,
            meta_info=meta_info,
        )


class RecursiveTypeDefinitionError(CustomError):
    error_name = "RECURSIVE-TYPE-DEFINITION ERROR"
    error_msg = "Recursive definition of custom type"

    def __init__(self, program_str: str, meta_info: MetaInfo):
        msg_prefix = self.error_name + " found in type declaration, "
        super().__init__(
            msg_prefix=msg_prefix,
            error_msg=self.error_msg,
            program_str=program_str,
            meta_info=meta_info,
        )


class InvalidAttributeNameError(CustomError):
    error_name = "INVALID-ATTRIBUTE-NAME ERROR"
    error_msg = "Name of custom type and its attributes must be distinct"

    def __init__(self, program_str: str, meta_info: MetaInfo):
        msg_prefix = self.error_name + " found in type declaration, "
        super().__init__(
            msg_prefix=msg_prefix,
            error_msg=self.error_msg,
            program_str=program_str,
            meta_info=meta_info,
        )


class NonExistentAttributeError(CustomError):
    error_name = "NON-EXISTENT-ATTRIBUTE ERROR"

    def __init__(
        self,
        program_str: str,
        meta_info: MetaInfo,
        record_name: str,
        record_type_name: str,
        attr: str,
    ):
        msg_prefix = self.error_name + " found in field access "
        error_msg = f'Variable "{record_name}" of type "{record_type_name}" does not have attribute "{attr}"'
        super().__init__(
            msg_prefix=msg_prefix,
            error_msg=error_msg,
            program_str=program_str,
            meta_info=meta_info,
            show_code_block=False,
        )


class NonExistentNameError(CustomError):
    error_name = "NON-EXISTENT-NAME ERROR"

    def __init__(
        self,
        program_str: str,
        meta_info: MetaInfo,
        identifier: str,
        expected_construct: str,
    ):
        msg_prefix = self.error_name + " found in "
        error_msg = f'"{identifier}" is not a defined {expected_construct}'
        super().__init__(
            msg_prefix=msg_prefix,
            error_msg=error_msg,
            program_str=program_str,
            meta_info=meta_info,
            show_code_block="variable" not in expected_construct,
        )


class InvalidBaseTypeError(CustomError):
    error_name = "INVALID-BASE-TYPE ERROR"

    def __init__(self, program_str: str, meta_info: MetaInfo, base_type_name: str):
        msg_prefix = self.error_name + " found in "
        error_msg = f'"{base_type_name}" is not a valid base type'
        super().__init__(
            msg_prefix=msg_prefix,
            error_msg=error_msg,
            program_str=program_str,
            meta_info=meta_info,
        )


class MisplacedReturnError(CustomError):
    error_name = "MISPLACED-RETURN ERROR"
    error_msg = "Return statement outside of function declaration"

    def __init__(self, program_str: str, meta_info: MetaInfo):
        msg_prefix = self.error_name + " found in "
        super().__init__(
            msg_prefix=msg_prefix,
            error_msg=self.error_msg,
            program_str=program_str,
            meta_info=meta_info,
        )


class ReturnValueExistenceError(CustomError):
    error_name = "RETURN-VALUE-EXISTENCE ERROR"

    def __init__(
        self, program_str: str, meta_info: MetaInfo, func_name: str, is_void: bool
    ):
        msg_prefix = self.error_name + " found in "
        error_msg = (
            f'Returning value in void function "{func_name}"'
            if is_void
            else f'Non-void function "{func_name}" should return a value'
        )
        super().__init__(
            msg_prefix=msg_prefix,
            error_msg=error_msg,
            program_str=program_str,
            meta_info=meta_info,
        )


class IncorrectParameterCountError(CustomError):
    error_name = "INCORRECT-PARAMETER-COUNT ERROR"

    def __init__(
        self,
        program_str: str,
        meta_info: MetaInfo,
        func_invoked: str,
        actual_count: int,
        expected_count: int,
    ):
        msg_prefix = self.error_name + " found in "
        error_msg = f'{actual_count} parameter{"" if actual_count == 1 else "s"} passed to function "{func_invoked}" (expected {expected_count})'
        super().__init__(
            msg_prefix=msg_prefix,
            error_msg=error_msg,
            program_str=program_str,
            meta_info=meta_info,
        )


class ConstantReassignmentError(CustomError):
    error_name = "CONSTANT-RE-ASSIGNMENT ERROR"
    error_msg = "Constants cannot be re-assigned"

    def __init__(self, program_str: str, meta_info: MetaInfo):
        msg_prefix = self.error_name + " found in "
        super().__init__(
            msg_prefix=msg_prefix,
            error_msg=self.error_msg,
            program_str=program_str,
            meta_info=meta_info,
        )


################################################################
# Analyzer class: enforces syntactic (and some semantic) rules
################################################################


class ProgramAnalyzer:
    def __init__(self, program_str: str, ast: Program):
        self.program_str = program_str
        self.ast = ast
        self.type_table: dict[str, Optional[TypeDec]] = {k: None for k in BASIC_TYPES}
        self.func_table: dict[str, FuncDec] = dict()
        self.warnings = []

    ####################
    # Helper methods
    ####################

    # given the name of a record variable, returns its type
    def get_record_type(self, record_var: str, scope: Scope) -> Optional[TypeDec]:
        var_type = scope.var_table[record_var].datatype
        # should pass because record variables always declared with type
        assert var_type is not None

        var_type_name = str(var_type.name)
        return self.type_table[var_type_name]

    ####################
    # Analysis passes
    ####################

    # constructs symbol tables for custom types and functions while doing syntax checking for them
    def build_type_and_function_tables(self):
        for type_dec in self.ast.type_decs:
            type_name = str(type_dec.name)
            dec_meta = type_dec.meta_info

            # check if definition repeated
            if type_name in RESERVED_WORDS:
                raise KeywordCollisionError(
                    self.program_str, dec_meta, identifier=type_name
                )
            if type_name in self.type_table:
                raise NameCollisionError(
                    self.program_str,
                    dec_meta,
                    identifier=type_name,
                    alr_existing_construct="type",
                )

            # check field declarations
            for field_id, field_type in type_dec.field_list:
                field_name, field_type_name = str(field_id), str(field_type.name)

                # stupid field declarations
                if field_name in RESERVED_WORDS:
                    raise KeywordCollisionError(
                        self.program_str, dec_meta, identifier=field_name
                    )
                if field_name == type_name:
                    raise InvalidAttributeNameError(self.program_str, dec_meta)
                if field_type_name == type_name:
                    raise RecursiveTypeDefinitionError(self.program_str, dec_meta)

                # types that don't exist
                if not isinstance(field_type, ArrayType):
                    if field_type_name not in self.type_table:
                        raise NonExistentNameError(
                            self.program_str,
                            dec_meta,
                            identifier=field_type_name,
                            expected_construct="type",
                        )
                else:
                    base_type_name = str(field_type.base_type.name)
                    if base_type_name not in self.type_table:
                        raise InvalidBaseTypeError(
                            self.program_str, dec_meta, base_type_name=base_type_name
                        )

            self.type_table[type_name] = type_dec

        for func_dec in self.ast.func_decs:
            func_name = str(func_dec.name)
            dec_meta = func_dec.meta_info

            if func_name in self.type_table:
                raise NameCollisionError(
                    self.program_str,
                    dec_meta,
                    identifier=func_name,
                    alr_existing_construct="type",
                )
            if func_name in self.func_table:
                raise NameCollisionError(
                    self.program_str,
                    dec_meta,
                    identifier=func_name,
                    alr_existing_construct="function",
                )

            # check arguments
            for arg_name, arg_type in func_dec.args:
                arg_name, arg_type_name = str(arg_name), str(arg_type.name)

                if arg_name in RESERVED_WORDS:
                    raise KeywordCollisionError(
                        self.program_str, dec_meta, identifier=arg_name
                    )

                # arg_type must be a valid type
                if not isinstance(arg_type, ArrayType):
                    if arg_type_name not in self.type_table:
                        raise NonExistentNameError(
                            self.program_str,
                            dec_meta,
                            identifier=arg_type_name,
                            expected_construct="type",
                        )
                else:
                    base_type_name = str(arg_type.base_type.name)
                    if base_type_name not in self.type_table:
                        raise InvalidBaseTypeError(
                            self.program_str, dec_meta, base_type_name
                        )

            self.func_table[func_name] = func_dec

    # checks for return statements not in function declarations
    def check_misplaced_returns(self, node):
        match node:
            case Program():
                for stmt in node.main_block:
                    self.check_misplaced_returns(stmt)
            case ReturnStmt():
                raise MisplacedReturnError(self.program_str, node.meta_info)
            case Conditional():
                for stmt in node.then_block:
                    self.check_misplaced_returns(stmt)
                if node.else_block is not None:
                    for stmt in node.else_block:
                        self.check_misplaced_returns(stmt)
            case ForLoop():
                for stmt in node.body:
                    self.check_misplaced_returns(stmt)
            case WhileLoop() | RepeatLoop():
                for stmt in node.body:
                    self.check_misplaced_returns(stmt)
            case _:
                pass

    # checks that return statements do not return values if in a void function, and do return values if not in a void func
    def check_return_stmts(self, func_dec: FuncDec):
        func_name = str(func_dec.name)

        def visit(node):
            match node:
                case ReturnStmt():
                    value = node.value
                    if func_dec.return_type is None and value is not None:
                        raise ReturnValueExistenceError(
                            self.program_str,
                            node.meta_info,
                            func_name=func_name,
                            is_void=True,
                        )
                    elif func_dec.return_type is not None and value is None:
                        raise ReturnValueExistenceError(
                            self.program_str,
                            node.meta_info,
                            func_name=func_name,
                            is_void=False,
                        )
                case Conditional():
                    for stmt in node.then_block:
                        visit(stmt)
                    if node.else_block is not None:
                        for stmt in node.else_block:
                            visit(stmt)
                case ForLoop():
                    for stmt in node.body:
                        visit(stmt)
                case WhileLoop() | RepeatLoop():
                    for stmt in node.body:
                        visit(stmt)
                case _:
                    pass

        for stmt in func_dec.body:
            visit(stmt)

    # builds symbol tables while checking for improper use of identifiers
    def build_var_tables(self, node, cur_scope: Scope):
        match node:
            case Program():
                node.scope = cur_scope

                for func_dec in node.func_decs:
                    new_scope = Scope(None, dict())
                    self.build_var_tables(func_dec, new_scope)

                for stmt in node.main_block:
                    self.build_var_tables(stmt, cur_scope)
            case FuncDec(_, _, name, args, _, body):
                node.scope = cur_scope
                for arg_name, arg_type in args:
                    cur_scope.insert_varname(
                        str(arg_name), VarInfo(False, arg_type, False)
                    )
                for stmt in body:
                    self.build_var_tables(stmt, cur_scope)
            case ConstDec(_, meta, name, value):
                node.scope = cur_scope
                name = str(name)

                # check if name is valid
                if name in RESERVED_WORDS:
                    raise KeywordCollisionError(self.program_str, meta, identifier=name)
                if name in self.type_table:
                    raise NameCollisionError(
                        self.program_str,
                        meta,
                        identifier=name,
                        alr_existing_construct="type",
                    )
                if name in self.func_table:
                    raise NameCollisionError(
                        self.program_str,
                        meta,
                        identifier=name,
                        alr_existing_construct="function",
                    )
                if cur_scope.var_name_in_scope(name):
                    raise NameCollisionError(
                        self.program_str,
                        meta,
                        identifier=name,
                        alr_existing_construct="variable or constant",
                    )

                self.build_var_tables(value, cur_scope)
                cur_scope.insert_varname(name, VarInfo(True, None))
            case VarDec(_, meta, name, declared_type, init_val):
                node.scope = cur_scope
                name = str(name)

                # check if name is valid
                if name in RESERVED_WORDS:
                    raise KeywordCollisionError(self.program_str, meta, identifier=name)
                if name in self.type_table:
                    raise NameCollisionError(
                        self.program_str,
                        meta,
                        identifier=name,
                        alr_existing_construct="type",
                    )
                if name in self.func_table:
                    raise NameCollisionError(
                        self.program_str,
                        meta,
                        identifier=name,
                        alr_existing_construct="function",
                    )
                if cur_scope.var_name_in_scope(name):
                    raise NameCollisionError(
                        self.program_str,
                        meta,
                        identifier=name,
                        alr_existing_construct="variable or constant",
                    )

                # check that declared type is valid
                if isinstance(declared_type, ArrayType):
                    # check array dimensions for undeclared vars
                    for dim in declared_type.size:
                        self.build_var_tables(dim, cur_scope)
                elif (
                    declared_type is not None
                    and str(declared_type.name) not in self.type_table
                ):
                    raise NonExistentNameError(
                        self.program_str,
                        meta,
                        identifier=str(declared_type.name),
                        expected_construct="type",
                    )

                # check initial value
                if init_val is not None:
                    self.build_var_tables(init_val, cur_scope)
                cur_scope.insert_varname(name, VarInfo(False, declared_type))

            ####################
            # Other Statements
            ####################

            case Assignment(_, meta, lval, rval):
                node.scope = cur_scope
                self.build_var_tables(lval, cur_scope)
                self.build_var_tables(rval, cur_scope)
                # no constant assignment
                if cur_scope.var_is_constant(str(lval)):
                    raise ConstantReassignmentError(self.program_str, meta)
            case Conditional(_, _, condition, then_block, else_block):
                node.scope = cur_scope
                self.build_var_tables(condition, cur_scope)

                # if and else blocks have separate scopes
                then_scope = Scope(cur_scope, dict())
                for stmt in then_block:
                    self.build_var_tables(stmt, then_scope)

                else_scope = Scope(cur_scope, dict())
                if else_block is not None:
                    for stmt in else_block:
                        self.build_var_tables(stmt, else_scope)

                # add symbols declared in if/else blocks so that user may be warned
                for var_name, var_info in then_scope.var_table.items():
                    new_info = VarInfo(var_info.is_constant, var_info.datatype, True)
                    cur_scope.insert_varname(var_name, new_info)
                for var_name, var_info in else_scope.var_table.items():
                    new_info = VarInfo(var_info.is_constant, var_info.datatype, True)
                    cur_scope.insert_varname(var_name, new_info)
            case ForLoop(_, _, iterator_name, init_val, cond, step, body):
                node.scope = Scope(cur_scope, dict())
                node.scope.insert_varname(
                    str(iterator_name), VarInfo(False, NotArrayType("int"))
                )
                self.build_var_tables(init_val, cur_scope)
                self.build_var_tables(cond, cur_scope)
                self.build_var_tables(step, cur_scope)
                for stmt in body:
                    self.build_var_tables(stmt, node.scope)
            case WhileLoop() | RepeatLoop():
                node.scope = cur_scope
                self.build_var_tables(node.cond, cur_scope)
                for stmt in node.body:
                    self.build_var_tables(stmt, cur_scope)
            case ReturnStmt():
                node.scope = cur_scope
                if node.value is not None:
                    self.build_var_tables(node.value, cur_scope)
            case PrintStmt():
                node.scope = cur_scope
                self.build_var_tables(node.value, cur_scope)
            case ScanStmt():
                node.scope = cur_scope
                self.build_var_tables(node.lval, cur_scope)

            ################
            # Expressions
            ################

            # for identifiers in expressions and assignment
            case Identifier(_, meta, name):
                node.scope = cur_scope
                if not cur_scope.var_name_in_scope(name):
                    raise NonExistentNameError(
                        self.program_str,
                        meta,
                        identifier=name,
                        expected_construct="variable/constant",
                    )

                # warn user if variable referenced was declared in a conditional
                if cur_scope.conditionally_defined(name):
                    warning = Warning(
                        self.program_str,
                        meta,
                        f'Variable/Constant "{name}" was declared in a conditional body and may not be defined.',
                        show_code_block=False,
                    )
                    self.warnings.append(warning)
            case ArrAccess():
                node.scope = cur_scope
                self.build_var_tables(node.array_name, cur_scope)
                for idx in node.indices:
                    self.build_var_tables(idx, cur_scope)
            case FieldAccess(_, meta, record_name, attribute):
                node.scope = cur_scope
                record_name, attribute = str(record_name), str(attribute)
                if not cur_scope.var_name_in_scope(record_name):
                    raise NonExistentNameError(
                        self.program_str,
                        meta,
                        identifier=record_name,
                        expected_construct="variable/constant",
                    )

                # check that the record has that attribute
                var_type = self.get_record_type(record_name, cur_scope)
                assert var_type is not None
                if attribute not in [str(name) for name, _ in var_type.field_list]:
                    raise NonExistentAttributeError(
                        self.program_str,
                        meta,
                        record_name=record_name,
                        record_type_name=str(var_type.name),
                        attr=attribute,
                    )
            case UnaryOp():
                node.scope = cur_scope
                self.build_var_tables(node.arg, cur_scope)
            case BinOp():
                node.scope = cur_scope
                self.build_var_tables(node.left, cur_scope)
                self.build_var_tables(node.right, cur_scope)
            case Invocation(_, meta, name, args):
                node.scope = cur_scope
                name = str(name)

                # check that function exists
                if name not in self.func_table:
                    raise NonExistentNameError(
                        self.program_str,
                        meta,
                        identifier=name,
                        expected_construct="function",
                    )

                # check for correct num of function args
                expected_count = len(self.func_table[name].args)
                actual_count = len(args)
                if expected_count != actual_count:
                    raise IncorrectParameterCountError(
                        self.program_str,
                        meta,
                        func_invoked=name,
                        actual_count=actual_count,
                        expected_count=expected_count,
                    )

                for arg in args:
                    self.build_var_tables(arg, cur_scope)
            case _:
                pass

    def check_types(self, node):
        match node:
            case Program():
                for stmt in node.main_block:
                    self.check_types(stmt)

            ###############
            # Expressions
            ###############
            case Literal():
                return node.datatype
            case ArrAccess(_, meta, array_name, indices):
                # check that indices are ints
                for idx in indices:
                    idx_type = self.check_types(idx)
                    assert idx_type is not None
                    type_name = str(idx_type.name)
                    if type_name != "int":
                        raise Exception("Indices must have type: int.")

                # get base type of array (if it is an array)
                assert (
                    node.scope is not None
                )  # asserts here to prevent IDE warnings, these shouldn't be None because build_var_tables is called before check_types
                var_info = node.scope.get_var_info(str(array_name))
                assert var_info is not None and var_info.datatype is not None
                type_name = str(var_info.datatype.name)
                if type_name != "arr":
                    raise Exception(f'"{str(array_name)}" is not an array.')

                return var_info.datatype

    # enforces syntax and some semantics
    def analyze(self):
        try:
            self.build_type_and_function_tables()
            for func_dec in self.ast.func_decs:
                self.check_return_stmts(func_dec)
            self.check_misplaced_returns(ast)
            self.build_var_tables(ast, Scope(None, dict()))
        except Exception as e:
            print(e)
        # check_types(ast)

        for warning in self.warnings:
            print()
            print(warning)


# tests
if __name__ == "__main__":
    s = """
    record pair {x: int, y: float}
    int func(x: str, y: int) {
        return 4;
    }
    main: {
        let x= 5;
        if (4 < 5) {
            var x = 5;
        }
        x = 6;
    }
    """
    parser = Lark.open(
        "grammar.lark", start="program", parser="lalr", propagate_positions=True
    )
    parse_tree = parser.parse(s)
    ast = ASTConstructor().transform(parse_tree)

    program_analyzer = ProgramAnalyzer(s, ast)
    program_analyzer.analyze()
    # print(program_analyzer.warnings)
