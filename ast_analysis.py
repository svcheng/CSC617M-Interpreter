from typing import Optional

from lark import Lark

from ast_constructor import ASTConstructor
from ast_definition import (
    BOOL,
    CHAR,
    FLOAT,
    INT,
    STR,
    ArrAccess,
    ArrayType,
    Assignment,
    BinOp,
    Conditional,
    ConstDec,
    FieldAccess,
    ForLoop,
    FuncDec,
    Identifier,
    Invocation,
    Literal,
    Node,
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
from errors import (
    ConstantReassignmentError,
    CustomError,
    ImmutableScanTarget,
    IncorrectIndexDimensionError,
    IncorrectParameterCountError,
    IncorrectParameterTypeError,
    InvalidAttributeNameError,
    InvalidBaseTypeError,
    InvalidConditionError,
    InvalidIdentifierTypeError,
    InvalidIndexTypeError,
    InvalidReturnValueError,
    KeywordCollisionError,
    MalformedForLoopError,
    MisplacedReturnError,
    NameCollisionError,
    NonExistentAttributeError,
    NonExistentNameError,
    OperatorTypeError,
    RecursiveTypeDefinitionError,
    ReturnValueExistenceError,
    TypeMismatchError,
    VoidExpressionError,
    Warning,
)

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

    # constructs symbol table for custom types while doing syntax checking on the declarations
    def build_type_table(self):
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
                if isinstance(field_type, ArrayType):
                    base_type_name = str(field_type.base_type.name)
                    if base_type_name not in self.type_table:
                        raise InvalidBaseTypeError(
                            self.program_str, dec_meta, base_type_name=base_type_name
                        )
                elif field_type_name not in self.type_table:
                    raise NonExistentNameError(
                        self.program_str,
                        dec_meta,
                        identifier=field_type_name,
                        expected_construct="type",
                    )

            self.type_table[type_name] = type_dec

    # constructs symbol table for functions while doing syntax checking on the declarations
    def build_function_table(self):
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
                if isinstance(arg_type, ArrayType):
                    base_type_name = str(arg_type.base_type.name)
                    if base_type_name not in self.type_table:
                        raise InvalidBaseTypeError(
                            self.program_str, dec_meta, base_type_name
                        )
                elif arg_type_name not in self.type_table:
                    raise NonExistentNameError(
                        self.program_str,
                        dec_meta,
                        identifier=arg_type_name,
                        expected_construct="type",
                    )

            self.func_table[func_name] = func_dec

    # checks for return statements not in function declarations
    def check_misplaced_returns(self):
        def visit(node: Node):
            match node:
                case ReturnStmt():
                    raise MisplacedReturnError(self.program_str, node.meta_info)
                case Conditional():
                    for stmt in node.then_block:
                        visit(stmt)
                    if node.else_block is not None:
                        for stmt in node.else_block:
                            visit(stmt)
                case ForLoop() | WhileLoop() | RepeatLoop():
                    for stmt in node.body:
                        visit(stmt)
                case _:
                    pass

        for stmt in self.ast.main_block:
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
                    cur_scope.insert_varname(str(arg_name), VarInfo(False, arg_type))
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
            case ForLoop(_, _, iterator_name, range_start, range_end, step, body):
                node.scope = Scope(cur_scope, dict())
                node.scope.insert_varname(
                    str(iterator_name), VarInfo(False, NotArrayType("int"))
                )
                self.build_var_tables(range_start, cur_scope)
                self.build_var_tables(range_end, cur_scope)
                self.build_var_tables(step, cur_scope)
                for stmt in body:
                    self.build_var_tables(stmt, node.scope)
            case WhileLoop() | RepeatLoop():
                node.scope = cur_scope
                self.build_var_tables(node.cond, cur_scope)

                new_scope = Scope(cur_scope, dict())
                for stmt in node.body:
                    self.build_var_tables(stmt, new_scope)
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
            case ArrAccess():
                node.scope = cur_scope
                self.build_var_tables(node.array_name, cur_scope)
                for idx in node.indices:
                    self.build_var_tables(idx, cur_scope)
            case FieldAccess(_, meta, _, record_name, attribute):
                node.scope = cur_scope
                record_name, attribute = str(record_name), str(attribute)

                # record name should be in scope
                if not cur_scope.var_name_in_scope(record_name):
                    raise NonExistentNameError(
                        self.program_str,
                        meta,
                        identifier=record_name,
                        expected_construct="variable/constant",
                    )

                # record name should be a record and not some other var
                var_type = cur_scope.get_type(record_name)
                assert var_type is not None  # assert just here to prevent IDE warning
                var_type_name = str(var_type.name)
                if var_type_name not in self.type_table or var_type_name in BASIC_TYPES:
                    raise InvalidIdentifierTypeError(
                        self.program_str,
                        meta,
                        var_name=record_name,
                        var_type=var_type_name,
                        expected_type="record",
                    )

                # check that the record has that attribute
                type_dec = self.type_table[var_type_name]
                assert type_dec is not None
                if attribute not in [str(name) for name, _ in type_dec.field_list]:
                    raise NonExistentAttributeError(
                        self.program_str,
                        meta,
                        record_name=record_name,
                        record_type_name=var_type_name,
                        attr=attribute,
                    )
            case UnaryOp():
                node.scope = cur_scope
                self.build_var_tables(node.arg, cur_scope)
            case BinOp():
                node.scope = cur_scope
                self.build_var_tables(node.left, cur_scope)
                self.build_var_tables(node.right, cur_scope)
            case Invocation(_, meta, _, name, args):
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

    # performs type checking on all statements and expressions except for validating return types
    def check_types(self, node: Node) -> Type | None:
        match node:
            case Program():
                for func_dec in node.func_decs:
                    self.check_types(func_dec)
                for stmt in node.main_block:
                    self.check_types(stmt)
            case FuncDec():
                for stmt in node.body:
                    self.check_types(stmt)
            ###############
            # Statements
            ###############
            case ConstDec(scope, meta, name, value):
                assert scope is not None
                value_type = self.check_types(value)
                if value_type is None:
                    raise VoidExpressionError(self.program_str, meta)
                scope.set_type(str(name), datatype=value_type)
            case VarDec(scope, meta, name, declared_type, init_value):
                assert scope is not None
                if declared_type is None:
                    assert init_value is not None
                    value_type = self.check_types(init_value)
                    if value_type is None:
                        raise VoidExpressionError(self.program_str, meta)
                    scope.set_type(str(name), datatype=value_type)
                elif init_value is None:
                    assert declared_type is not None
                    scope.set_type(str(name), datatype=declared_type)
            case Assignment(_, meta, lval, rval):
                left_type = self.check_types(lval)
                assert left_type is not None

                right_type = self.check_types(rval)
                if right_type is None:
                    raise VoidExpressionError(self.program_str, meta)

                # left and right types should match
                if left_type != right_type:
                    raise TypeMismatchError(
                        self.program_str,
                        meta,
                        str(left_type.name),
                        str(right_type.name),
                    )
            case Conditional(scope, meta, cond, then_block, else_block):
                assert scope is not None

                # condition must be boolean
                cond_type = self.check_types(cond)
                if cond_type is None:
                    raise VoidExpressionError(self.program_str, meta)
                if cond_type != NotArrayType(BOOL):
                    raise InvalidConditionError(
                        self.program_str, meta, cond_type=str(cond_type.name)
                    )

                for stmt in then_block:
                    self.check_types(stmt)
                if else_block is not None:
                    for stmt in else_block:
                        self.check_types(stmt)
            case ForLoop(scope, meta, _, range_start, range_end, step, body):
                assert scope is not None

                # params should be integers
                for param_name, param in [
                    ("Range start", range_start),
                    ("Range end", range_end),
                    ("Step", step),
                ]:
                    param_type = self.check_types(param)
                    if param_type is None:
                        raise VoidExpressionError(self.program_str, meta)
                    if param_type != NotArrayType(INT):
                        raise MalformedForLoopError(
                            self.program_str,
                            meta,
                            param_name=param_name,
                            param_type=str(param_type.name),
                        )

                for stmt in body:
                    self.check_types(stmt)
            case WhileLoop(scope, meta, cond, body) | RepeatLoop(
                scope, meta, cond, body
            ):
                assert scope is not None

                # condition must be boolean
                cond_type = self.check_types(cond)
                if cond_type is None:
                    raise VoidExpressionError(self.program_str, meta)
                if cond_type != NotArrayType(BOOL):
                    raise InvalidConditionError(
                        self.program_str, meta, cond_type=str(cond_type.name)
                    )

                for stmt in body:
                    self.check_types(stmt)
            case PrintStmt(scope, meta, value):
                assert scope is not None
                value_type = self.check_types(value)
                if value_type is None:
                    raise VoidExpressionError(self.program_str, meta)
            case ScanStmt(scope, meta, lval):
                assert scope is not None
                lval_type = self.check_types(lval)
                assert lval_type is not None

                # lval should not be constant
                if isinstance(lval, Identifier) and scope.var_is_constant(lval.name):
                    raise ImmutableScanTarget(self.program_str, meta)

                # lval should be string
                if lval_type != NotArrayType(STR):
                    raise IncorrectParameterTypeError(
                        self.program_str,
                        meta,
                        func_name="scan",
                        arg_name=None,
                        arg_type=STR,
                        param_type=str(lval_type.name),
                    )
            ###############
            # Expressions
            ###############
            case Identifier(scope, meta, name):  # for identifiers used in expressions
                assert scope is not None
                return scope.get_type(str(name))
            case Literal():
                return node.datatype
            case ArrAccess(scope, meta, _, array_name, indices):
                assert scope is not None
                arr_name = str(array_name)

                # get base type of array (and check that it is actually an array)
                var_type = scope.get_type(arr_name)
                assert var_type is not None
                if not isinstance(var_type, ArrayType):
                    raise InvalidIdentifierTypeError(
                        self.program_str,
                        meta,
                        var_name=arr_name,
                        var_type=str(var_type.name),
                        expected_type="arr",
                    )
                base_type = var_type.base_type

                # check that number of indices matches array dimension
                num_indices = len(indices)
                arr_dim = len(var_type.size)
                if num_indices != arr_dim:
                    raise IncorrectIndexDimensionError(
                        self.program_str,
                        meta,
                        arr_name=arr_name,
                        expected_dim=arr_dim,
                        num_indices=num_indices,
                    )

                # check that indices are ints
                for i, idx in enumerate(indices):
                    idx_type = self.check_types(idx)
                    if idx_type is None:
                        raise VoidExpressionError(self.program_str, meta)
                    if idx_type != NotArrayType(INT):
                        raise InvalidIndexTypeError(
                            self.program_str, meta, i + 1, wrong_type=str(idx_type.name)
                        )

                node.datatype = base_type
                return base_type
            case FieldAccess(scope, _, _, record_name, attribute):
                assert scope is not None

                # get the type of the variable
                var_type = scope.get_type(str(record_name))
                assert var_type is not None
                type_name = str(var_type.name)
                type_dec = self.type_table[type_name]
                assert type_dec is not None

                # return the type of the attribute being referenced
                for field_name, field_type in type_dec.field_list:
                    if str(field_name) == str(attribute):
                        node.datatype = field_type
                        return field_type
            case UnaryOp(_, meta, _, op, arg):
                arg_type = self.check_types(arg)
                if arg_type is None:
                    raise VoidExpressionError(self.program_str, meta)

                # for now, the only unary op is logical negation
                if arg_type != NotArrayType(BOOL):
                    raise OperatorTypeError(
                        self.program_str, meta, op=op, type_names=[str(arg_type.name)]
                    )

                node.datatype = arg_type
                return arg_type
            case BinOp(scope, meta, _, op, left, right):
                BOOL_TYPE = NotArrayType(BOOL)
                INT_TYPE = NotArrayType(INT)
                FLOAT_TYPE = NotArrayType(FLOAT)
                numerical_types = (INT_TYPE, FLOAT_TYPE)

                left_type = self.check_types(left)
                right_type = self.check_types(right)
                if left_type is None or right_type is None:
                    raise VoidExpressionError(self.program_str, meta)
                left_type_name, right_type_name = (
                    str(left_type.name),
                    str(right_type.name),
                )

                match op:
                    case "+" | "-" | "*" | "/":
                        # inputs must be numerical
                        if (
                            left_type not in numerical_types
                            or right_type not in numerical_types
                        ):
                            raise OperatorTypeError(
                                self.program_str,
                                meta,
                                op=op,
                                type_names=[left_type_name, right_type_name],
                            )

                        # type cast to float if at least 1 arg is float
                        if FLOAT_TYPE in (left_type, right_type):
                            op_type = FLOAT_TYPE
                        else:
                            op_type = INT_TYPE

                        node.datatype = op_type
                    case "==" | "!=" | "<" | "<=" | ">" | ">=":
                        # inputs must be numerical
                        if (
                            left_type not in numerical_types
                            or right_type not in numerical_types
                        ):
                            raise OperatorTypeError(
                                self.program_str,
                                meta,
                                op=op,
                                type_names=[left_type_name, right_type_name],
                            )
                        node.datatype = BOOL_TYPE
                    case "||" | "&&":
                        # inputs must be bools
                        if left_type != BOOL_TYPE or right_type != BOOL_TYPE:
                            raise OperatorTypeError(
                                self.program_str,
                                meta,
                                op=op,
                                type_names=[left_type_name, right_type_name],
                            )

                        node.datatype = BOOL_TYPE
                return node.datatype
            case Invocation(scope, meta, _, name, params):
                assert scope is not None
                func_dec = self.func_table[str(name)]

                # check param types
                for i, (arg_name, arg_type) in enumerate(func_dec.args):
                    param_type = self.check_types(params[i])

                    # param is invocation of void function
                    if param_type is None:
                        raise VoidExpressionError(self.program_str, meta)

                    # param otherwise has wrong type
                    if param_type != arg_type:
                        raise IncorrectParameterTypeError(
                            self.program_str,
                            meta,
                            func_name=str(name),
                            arg_name=str(arg_name),
                            arg_type=str(arg_type.name),
                            param_type=str(param_type.name),
                        )

                node.datatype = func_dec.return_type  # may be None if func is void
                return func_dec.return_type
            case _:
                pass

    # checks that return types are correct
    def check_return_stmts(self):
        for func_dec in self.ast.func_decs:
            func_name = str(func_dec.name)
            expected_return_type = func_dec.return_type

            def visit(node: Node):
                match node:
                    case ReturnStmt(_, meta, value):
                        # void functions cannot return a value, non-void funcs must return one
                        match (expected_return_type, value):
                            case (None, t) if t is not None:
                                raise ReturnValueExistenceError(
                                    self.program_str,
                                    meta,
                                    func_name=func_name,
                                    is_void=True,
                                )
                            case (t, None) if t is not None:
                                raise ReturnValueExistenceError(
                                    self.program_str,
                                    meta,
                                    func_name=func_name,
                                    is_void=False,
                                    show_code_block=False,
                                )
                            case (None, None):
                                return
                        assert expected_return_type is not None and value is not None

                        #  check that return types are equal, at this point func is not void and return value exists
                        actual_return_type = self.check_types(value)
                        match (expected_return_type, actual_return_type):
                            # void func was invoked on the right
                            case (_, None):
                                raise VoidExpressionError(self.program_str, meta)
                            # type names are ot equal
                            case (t1, t2) if t1 != t2:
                                assert t1 is not None and t2 is not None
                                raise InvalidReturnValueError(
                                    self.program_str,
                                    meta,
                                    func_name=func_name,
                                    expected_type=str(t1.name),
                                    actual_type=str(t2.name),
                                )
                            # type names are equal but both arrays
                            case (ArrayType() as t1, ArrayType() as t2):
                                t1_base = t1.base_type
                                t2_base = t2.base_type
                                dim1, dim2 = len(t1.size), len(t2.size)
                                formatted_t1 = f"{dim1}-D {t1_base.name} arr"
                                formatted_t2 = f"{dim2}-D {t2_base.name} arr"

                                # check that base types are same and that number of indices matches array dimension
                                if t1_base != t2_base or dim1 != dim2:
                                    raise InvalidReturnValueError(
                                        self.program_str,
                                        meta,
                                        func_name=func_name,
                                        expected_type=formatted_t1,
                                        actual_type=formatted_t2,
                                    )
                    case Conditional():
                        for stmt in node.then_block:
                            visit(stmt)
                        if node.else_block is not None:
                            for stmt in node.else_block:
                                visit(stmt)
                    case ForLoop() | WhileLoop() | RepeatLoop():
                        for stmt in node.body:
                            visit(stmt)
                    case _:
                        pass

            for stmt in func_dec.body:
                visit(stmt)

    # enforces syntax and some semantics
    def analyze(self):
        try:
            self.build_type_table()
            self.build_function_table()
            self.check_misplaced_returns()
            self.build_var_tables(self.ast, Scope(None, dict()))
            self.check_types(self.ast)
            self.check_return_stmts()
        except CustomError as e:
            print("Compilation failed with the following error:")
            print(e)
        except Exception as e:  # if this case is reached there is a bug
            raise e

        for warning in self.warnings:
            print()
            print(warning)


# for testing
if __name__ == "__main__":
    s = """
    record pair {x: float, y: float}
    int arr[5] func(x: float, b: bool) {
        var a: int arr[7];
        return a;
    }
    main: {
    }
    """
    parser = Lark.open(
        "grammar.lark", start="program", parser="lalr", propagate_positions=True
    )
    parse_tree = parser.parse(s)
    ast = ASTConstructor().transform(parse_tree)

    program_analyzer = ProgramAnalyzer(s, ast)
    program_analyzer.analyze()

    # for k, v in ast.scope.var_table.items():
    #     print(k, ": ", v)
