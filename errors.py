from typing import Optional

from ast_constructor import MetaInfo
from ast_definition import Type


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


class InvalidIdentifierTypeError(CustomError):
    error_name = "INVALID-IDENTIFIER-TYPE ERROR"

    def __init__(
        self,
        program_str: str,
        meta_info: MetaInfo,
        var_name: str,
        var_type: str,
        expected_type: str,
    ):
        msg_prefix = self.error_name + " found in "
        error_msg = f'Expected "{var_name}" to have type "{expected_type}" but has type "{var_type}"'
        super().__init__(
            msg_prefix=msg_prefix,
            error_msg=error_msg,
            program_str=program_str,
            meta_info=meta_info,
        )


class InvalidIndexTypeError(CustomError):
    error_name = "INVALID-INDEX-TYPE Error"

    def __init__(
        self, program_str: str, meta_info: MetaInfo, order: int, wrong_type: str
    ):
        msg_prefix = self.error_name + " found in "
        match order:
            case 1:
                ord_str = "1st"
            case 2:
                ord_str = "2nd"
            case 3:
                ord_str = "3rd"
            case _:
                ord_str = str(order) + "th"

        error_msg = f'"Array indices should be integers but {ord_str} index has type "{wrong_type}"'
        super().__init__(
            msg_prefix=msg_prefix,
            error_msg=error_msg,
            program_str=program_str,
            meta_info=meta_info,
        )


class IncorrectIndexDimensionError(CustomError):
    error_name = "INCORRECT-INDEX-DIMENSION ERROR"

    def __init__(
        self,
        program_str: str,
        meta_info: MetaInfo,
        arr_name: str,
        expected_dim: int,
        num_indices: int,
    ):
        msg_prefix = self.error_name + " found in "
        error_msg = f'"{arr_name}" has dimension {expected_dim} but {num_indices} {"index" if num_indices == 1 else "indices"} given'
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
        self,
        program_str: str,
        meta_info: MetaInfo,
        func_name: str,
        is_void: bool,
        show_code_block: bool = True,
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
            show_code_block=show_code_block,
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


class OperatorTypeError(CustomError):
    error_name = "OPERATOR-TYPE ERROR"

    def __init__(
        self, program_str: str, meta_info: MetaInfo, op: str, type_names: list[str]
    ):
        msg_prefix = self.error_name + " found in "

        if len(type_names) == 1:
            error_msg = (
                f'Input of type "{type_names[0]}" is not valid for operator "{op}"'
            )
        else:
            type1, type2 = type_names
            error_msg = f'Inputs of type "{type1}" and "{type2}" are not valid for operator "{op}"'

        super().__init__(
            msg_prefix=msg_prefix,
            error_msg=error_msg,
            program_str=program_str,
            meta_info=meta_info,
        )


class VoidExpressionError(CustomError):
    error_name = "VOID-EXPRESSION ERROR"
    error_msg = "Void function cannot be invoked where a value is expected"

    def __init__(self, program_str: str, meta_info: MetaInfo):
        msg_prefix = self.error_name + " found in "

        super().__init__(
            msg_prefix=msg_prefix,
            error_msg=self.error_msg,
            program_str=program_str,
            meta_info=meta_info,
        )


class IncorrectParameterTypeError(CustomError):
    error_name = "INCORRECT-PARAMETER-TYPE ERROR"

    def __init__(
        self,
        program_str: str,
        meta_info: MetaInfo,
        func_name: str,
        arg_name: Optional[str],
        arg_type: str,
        param_type: str,
    ):
        msg_prefix = self.error_name + " found in "
        if arg_name is not None:
            error_msg = f'"{func_name}" expects parameter of type "{arg_type}" to be passed to "{arg_name}" but "{param_type} was received'
        else:
            error_msg = f'"{func_name}" expects parameter of type "{arg_type}" to be passed but "{param_type} was received'
        super().__init__(
            msg_prefix=msg_prefix,
            error_msg=error_msg,
            program_str=program_str,
            meta_info=meta_info,
        )


class TypeMismatchError(CustomError):
    error_name = "TYPE-MISMATCH ERROR"

    def __init__(self, program_str: str, meta_info: MetaInfo, ltype: str, rtype: str):
        msg_prefix = self.error_name + " found in assignment, "
        error_msg = f'"{rtype}" given but "{ltype}" expected'
        super().__init__(
            msg_prefix=msg_prefix,
            error_msg=error_msg,
            program_str=program_str,
            meta_info=meta_info,
        )


class InvalidConditionError(CustomError):
    error_name = "INVALID-CONDITION ERROR"

    def __init__(self, program_str: str, meta_info: MetaInfo, cond_type: str):
        msg_prefix = self.error_name + " found in "
        error_msg = f'Conditions should be boolean but "{cond_type}" given'
        super().__init__(
            msg_prefix=msg_prefix,
            error_msg=error_msg,
            program_str=program_str,
            meta_info=meta_info,
        )


class MalformedForLoopError(CustomError):
    error_name = "MALFORMED-FOR-LOOP ERROR"

    def __init__(
        self, program_str: str, meta_info: MetaInfo, param_name: str, param_type: str
    ):
        msg_prefix = self.error_name + " found in "
        error_msg = f'{param_name} should be integer but "{param_type}" was given'
        super().__init__(
            msg_prefix=msg_prefix,
            error_msg=error_msg,
            program_str=program_str,
            meta_info=meta_info,
        )


class ImmutableScanTarget(CustomError):
    error_name = "INVALID-SCAN-TARGET ERROR"
    error_msg = 'Input to "scan" must not be a constant'

    def __init__(self, program_str: str, meta_info: MetaInfo):
        msg_prefix = self.error_name + " found in "

        super().__init__(
            msg_prefix=msg_prefix,
            error_msg=self.error_msg,
            program_str=program_str,
            meta_info=meta_info,
        )


class InvalidReturnValueError(CustomError):
    error_name = "INVALID-RETURN-VALUE ERROR"

    def __init__(
        self,
        program_str: str,
        meta_info: MetaInfo,
        func_name: str,
        expected_type: str,
        actual_type: str,
    ):
        msg_prefix = self.error_name + f' found in definition of "{func_name}", '
        error_msg = f'Returning value of type "{actual_type}" but function has return type "{expected_type}"'
        super().__init__(
            msg_prefix=msg_prefix,
            error_msg=error_msg,
            program_str=program_str,
            meta_info=meta_info,
        )
