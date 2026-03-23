from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from lark import Lark, Token
from lark.exceptions import (
    UnexpectedCharacters,
    UnexpectedEOF,
    UnexpectedInput,
    UnexpectedToken,
    VisitError,
)

from abstract_syntax_tree.conditional import Conditional
from abstract_syntax_tree.const_dec import ConstDec
from abstract_syntax_tree.for_loop import ForLoop
from abstract_syntax_tree.func_dec import FuncDec
from abstract_syntax_tree.program import Program
from abstract_syntax_tree.repeat_loop import RepeatLoop
from abstract_syntax_tree.aux_classes import Scope
from abstract_syntax_tree.type_dec import TypeDec
from abstract_syntax_tree.types import ArrayType, Type
from abstract_syntax_tree.var_dec import VarDec
from abstract_syntax_tree.while_loop import WhileLoop
from ast_construction import ASTConstructor
from errors import CustomError
from interpreter import Interpreter
from scanner import build_lexer

GRAMMAR_PATH = Path(__file__).with_name("grammar.lark")
PARSER = Lark.open(
    str(GRAMMAR_PATH), start="program", parser="lalr", propagate_positions=True
)
LEXER = build_lexer(GRAMMAR_PATH)

KEYWORD_TYPES = {
    "LET",
    "VAR",
    "IF",
    "ELSE",
    "FOR",
    "WHILE",
    "REPEAT",
    "UNTIL",
    "RETURN",
    "MAIN",
    "RECORD",
    "ARR",
    "VOID",
    "PRINT",
    "SCAN",
    "CAST",
}
TYPE_TYPES = {"INT_T", "FLOAT_T", "BOOL_T", "CHAR_T", "STR_T"}
LITERAL_TYPES = {"INT", "FLOAT", "BOOLVAL", "CHARVAL", "STRVAL"}
IDENTIFIER_TYPES = {"IDENTIFIER", "CNAME"}
OPERATOR_VALUES = {"+", "-", "*", "/", "=", "==", "!=", "<", "<=", ">", ">=", "!", "&&", "||"}
PUNCTUATION_VALUES = {"(", ")", "{", "}", "[", "]", ":", ";", ",", "."}


@dataclass(slots=True)
class TokenSpan:
    category: str
    value: str
    token_type: str
    start_line: int
    end_line: int
    start_col: int
    end_col: int


@dataclass(slots=True)
class Diagnostic:
    message: str
    start_line: int
    end_line: int
    start_col: int
    end_col: int
    kind: str = "error"


@dataclass(slots=True)
class ValidationResult:
    tokens: list[TokenSpan] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    ast: Optional[Program] = None
    symbols: list["SymbolScopeView"] = field(default_factory=list)


@dataclass(slots=True)
class TraceEntry:
    line: Optional[int]
    snippet: str
    result: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    start_col: Optional[int] = None
    end_col: Optional[int] = None
    snapshot: dict[str, Any] = field(default_factory=dict)
    call_stack: list["CallStackFrame"] = field(default_factory=list)


@dataclass(slots=True)
class CallStackFrame:
    depth: int
    name: str
    locals: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SymbolEntry:
    name: str
    kind: str
    type_name: str
    details: str
    line: Optional[int] = None


@dataclass(slots=True)
class SymbolScopeView:
    label: str
    kind: str
    depth: int
    entries: list[SymbolEntry] = field(default_factory=list)


@dataclass(slots=True)
class ExecutionResult:
    diagnostics: list[Diagnostic] = field(default_factory=list)
    output: list[str] = field(default_factory=list)
    trace: list[TraceEntry] = field(default_factory=list)
    runtime_error: Optional[str] = None
    success: bool = False


def analysis(ast: Program):
    ast.init_scope(Scope(None))
    ast.build_type_table()
    ast.build_func_table()
    ast.check_misplaced_returns()
    ast.build_var_tables()
    ast.check_types()
    ast.check_returns()
    ast.check_null_references()
    ast.ensure_exhaustive_returns()


def format_type_name(datatype: Optional[Type]):
    if datatype is None:
        return "<unresolved>"
    if isinstance(datatype, ArrayType):
        return f"arr[{len(datatype.size)}] of {format_type_name(datatype.base_type)}"
    return str(datatype)


def format_type_fields(type_dec: TypeDec):
    if not type_dec.field_list:
        return "<no fields>"

    return ", ".join(
        f"{field_name}: {format_type_name(field_type)}"
        for field_name, field_type in type_dec.field_list
    )


def format_function_args(args: list[tuple[Any, Type]]):
    if not args:
        return "<no parameters>"

    return ", ".join(
        f"{arg_name}: {format_type_name(arg_type)}" for arg_name, arg_type in args
    )


def get_start_line(node: Any):
    meta_info = getattr(node, "meta_info", None)
    return getattr(meta_info, "start_line", None)


def resolve_symbol_type(
    scope: Optional[Scope],
    name: str,
    fallback: Optional[Type] = None,
):
    if scope is not None:
        var_info = scope.get_var_info(name)
        if var_info is not None and var_info.datatype is not None:
            return format_type_name(var_info.datatype)
    if fallback is not None:
        return format_type_name(fallback)
    return "<unresolved>"


def build_symbol_table(ast: Program):
    scopes: list[SymbolScopeView] = []
    scope_map: dict[int, SymbolScopeView] = {}

    def ensure_scope(scope: Optional[Scope], label: str, kind: str, depth: int):
        if scope is None:
            return None

        scope_id = id(scope)
        if scope_id in scope_map:
            return scope_map[scope_id]

        scope_view = SymbolScopeView(label=label, kind=kind, depth=depth)
        scope_map[scope_id] = scope_view
        scopes.append(scope_view)
        return scope_view

    def add_entry(
        scope: Optional[Scope],
        label: str,
        kind: str,
        depth: int,
        entry: SymbolEntry,
    ):
        scope_view = ensure_scope(scope, label, kind, depth)
        if scope_view is None:
            return
        scope_view.entries.append(entry)

    def walk_statements(
        statements: list[Any],
        scope_label: str,
        scope_kind: str,
        depth: int,
    ):
        for statement in statements:
            if isinstance(statement, VarDec):
                name = str(statement.name)
                details = (
                    "Inferred from initializer"
                    if statement.declared_type is None
                    else "Declared variable"
                )
                add_entry(
                    statement.scope,
                    scope_label,
                    scope_kind,
                    depth,
                    SymbolEntry(
                        name=name,
                        kind="variable",
                        type_name=resolve_symbol_type(
                            statement.scope, name, statement.declared_type
                        ),
                        details=details,
                        line=get_start_line(statement),
                    ),
                )
                continue

            if isinstance(statement, ConstDec):
                name = str(statement.name)
                add_entry(
                    statement.scope,
                    scope_label,
                    scope_kind,
                    depth,
                    SymbolEntry(
                        name=name,
                        kind="constant",
                        type_name=resolve_symbol_type(statement.scope, name),
                        details="Immutable binding",
                        line=get_start_line(statement),
                    ),
                )
                continue

            if isinstance(statement, ForLoop):
                loop_label = f"For Loop (line {get_start_line(statement) or '?'})"
                iterator_name = str(statement.iterator_name)
                add_entry(
                    statement.scope,
                    loop_label,
                    "for loop",
                    depth + 1,
                    SymbolEntry(
                        name=iterator_name,
                        kind="iterator",
                        type_name=resolve_symbol_type(statement.scope, iterator_name),
                        details="Loop iterator",
                        line=get_start_line(statement),
                    ),
                )
                walk_statements(statement.body, loop_label, "for loop", depth + 1)
                continue

            if isinstance(statement, WhileLoop):
                loop_label = f"While Loop (line {get_start_line(statement) or '?'})"
                walk_statements(statement.body, loop_label, "while loop", depth + 1)
                continue

            if isinstance(statement, RepeatLoop):
                loop_label = f"Repeat Loop (line {get_start_line(statement) or '?'})"
                walk_statements(statement.body, loop_label, "repeat loop", depth + 1)
                continue

            if isinstance(statement, Conditional):
                line = get_start_line(statement) or "?"
                walk_statements(
                    statement.then_block,
                    f"Then Block (line {line})",
                    "then block",
                    depth + 1,
                )
                if statement.else_block is not None:
                    walk_statements(
                        statement.else_block,
                        f"Else Block (line {line})",
                        "else block",
                        depth + 1,
                    )

    main_scope = ensure_scope(ast.scope, "Main Scope", "main", 0)
    if main_scope is not None:
        for type_dec in ast.type_decs:
            main_scope.entries.append(
                SymbolEntry(
                    name=str(type_dec.name),
                    kind="type",
                    type_name="record",
                    details=format_type_fields(type_dec),
                    line=get_start_line(type_dec),
                )
            )

        for func_dec in ast.func_decs:
            main_scope.entries.append(
                SymbolEntry(
                    name=str(func_dec.name),
                    kind="function",
                    type_name=format_type_name(func_dec.return_type)
                    if func_dec.return_type is not None
                    else "void",
                    details=f"Args: {format_function_args(func_dec.args)}",
                    line=get_start_line(func_dec),
                )
            )

    walk_statements(ast.main_block, "Main Scope", "main", 0)

    for func_dec in ast.func_decs:
        func_label = f"Function {func_dec.name}"
        func_scope = ensure_scope(func_dec.scope, func_label, "function", 1)
        if func_scope is not None:
            for arg_name, arg_type in func_dec.args:
                func_scope.entries.append(
                    SymbolEntry(
                        name=str(arg_name),
                        kind="parameter",
                        type_name=resolve_symbol_type(
                            func_dec.scope, str(arg_name), arg_type
                        ),
                        details="Function parameter",
                        line=get_start_line(arg_name),
                    )
                )

        walk_statements(func_dec.body, func_label, "function", 1)

    for scope_view in scopes:
        scope_view.entries.sort(
            key=lambda entry: (
                entry.line is None,
                entry.line if entry.line is not None else 0,
                entry.name.lower(),
            )
        )

    return scopes


def classify_token(token: Token):
    if token.type in KEYWORD_TYPES:
        return "keyword"
    if token.type in TYPE_TYPES:
        return "type"
    if token.type in LITERAL_TYPES:
        return "literal"
    if token.type in IDENTIFIER_TYPES:
        return "identifier"
    if token.type == "INVALID_IDENT":
        return "invalid"
    if token.value in OPERATOR_VALUES:
        return "operator"
    if token.value in PUNCTUATION_VALUES:
        return "punctuation"
    return "text"


def token_to_span(token: Token):
    return TokenSpan(
        category=classify_token(token),
        value=token.value,
        token_type=token.type,
        start_line=getattr(token, "line", 1),
        end_line=getattr(token, "end_line", getattr(token, "line", 1)),
        start_col=getattr(token, "column", 1),
        end_col=getattr(token, "end_column", getattr(token, "column", 1) + len(token.value)),
    )


def token_to_invalid_identifier(token: Token):
    return Diagnostic(
        message=f'Invalid identifier "{token.value}"',
        start_line=getattr(token, "line", 1),
        end_line=getattr(token, "end_line", getattr(token, "line", 1)),
        start_col=getattr(token, "column", 1),
        end_col=getattr(token, "end_column", getattr(token, "column", 1) + len(token.value)),
        kind="lexical",
    )


def custom_error_to_diagnostic(error: CustomError):
    meta = error.meta_info
    error_name = getattr(error, "error_name", "COMPILATION ERROR")
    return Diagnostic(
        message=f"{error_name}: {error.error_msg}",
        start_line=meta.start_line,
        end_line=meta.end_line,
        start_col=meta.start_col,
        end_col=max(meta.end_col, meta.start_col + 1),
        kind="semantic",
    )


def lark_error_to_diagnostic(error: UnexpectedInput):
    if isinstance(error, UnexpectedToken) and getattr(error, "token", None) is not None:
        token = error.token
        return Diagnostic(
            message=str(error).strip(),
            start_line=getattr(token, "line", getattr(error, "line", 1)),
            end_line=getattr(token, "end_line", getattr(error, "line", 1)),
            start_col=getattr(token, "column", getattr(error, "column", 1)),
            end_col=max(
                getattr(token, "end_column", getattr(error, "column", 1) + 1),
                getattr(token, "column", getattr(error, "column", 1)) + 1,
            ),
            kind="syntax",
        )

    if isinstance(error, UnexpectedCharacters):
        return Diagnostic(
            message=str(error).strip(),
            start_line=getattr(error, "line", 1),
            end_line=getattr(error, "line", 1),
            start_col=getattr(error, "column", 1),
            end_col=getattr(error, "column", 1) + 1,
            kind="lexical",
        )

    if isinstance(error, UnexpectedEOF):
        return Diagnostic(
            message=str(error).strip(),
            start_line=getattr(error, "line", 1),
            end_line=getattr(error, "line", 1),
            start_col=getattr(error, "column", 1),
            end_col=getattr(error, "column", 1) + 1,
            kind="syntax",
        )

    return Diagnostic(
        message=str(error).strip(),
        start_line=getattr(error, "line", 1),
        end_line=getattr(error, "line", 1),
        start_col=getattr(error, "column", 1),
        end_col=getattr(error, "column", 1) + 1,
        kind="syntax",
    )


def tokenize_source(source: str):
    tokens: list[TokenSpan] = []
    diagnostics: list[Diagnostic] = []

    try:
        for token in LEXER.lex(source):
            if token.type in {"WS", "NEWLINE"}:
                continue
            tokens.append(token_to_span(token))
            if token.type == "INVALID_IDENT":
                diagnostics.append(token_to_invalid_identifier(token))
    except UnexpectedInput as error:
        diagnostics.append(lark_error_to_diagnostic(error))

    return tokens, diagnostics


def validate_source(source: str):
    tokens, diagnostics = tokenize_source(source)
    result = ValidationResult(tokens=tokens, diagnostics=diagnostics)

    if diagnostics:
        return result

    ast: Optional[Program] = None
    try:
        parse_tree = PARSER.parse(source)
        ast = ASTConstructor(source).transform(parse_tree)
        result.ast = ast
        analysis(ast)
        return result
    except CustomError as error:
        result.diagnostics.append(custom_error_to_diagnostic(error))
        return result
    except VisitError as error:
        original = error.orig_exc
        if isinstance(original, CustomError):
            result.diagnostics.append(custom_error_to_diagnostic(original))
        else:
            result.diagnostics.append(
                Diagnostic(
                    message=f"Internal AST construction error: {original}",
                    start_line=1,
                    end_line=1,
                    start_col=1,
                    end_col=2,
                    kind="internal",
                )
            )
        return result
    except UnexpectedInput as error:
        result.diagnostics.append(lark_error_to_diagnostic(error))
        return result
    except Exception as error:
        result.diagnostics.append(
            Diagnostic(
                message=f"Internal compilation error: {error}",
                start_line=1,
                end_line=1,
                start_col=1,
                end_col=2,
                kind="internal",
            )
        )
        return result
    finally:
        if ast is not None:
            try:
                result.symbols = build_symbol_table(ast)
            except Exception:
                result.symbols = []


def execute_validation(
    validation: ValidationResult,
    input_provider: Optional[Callable[[str], str]] = None,
    output_callback: Optional[Callable[[str], None]] = None,
    trace_callback: Optional[Callable[[TraceEntry], None]] = None,
):
    result = ExecutionResult(diagnostics=list(validation.diagnostics))

    if validation.ast is None or validation.diagnostics:
        return result

    def capture_output(text: str):
        result.output.append(text)
        if output_callback is not None:
            output_callback(text)

    def capture_trace(
        meta_info,
        snippet: str,
        statement_result: str,
        snapshot: dict[str, Any],
        call_stack: list[dict[str, Any]],
    ):
        line = meta_info.start_line if meta_info is not None else None
        entry = TraceEntry(
            line=line,
            start_line=meta_info.start_line if meta_info is not None else None,
            end_line=meta_info.end_line if meta_info is not None else None,
            start_col=meta_info.start_col if meta_info is not None else None,
            end_col=meta_info.end_col if meta_info is not None else None,
            snippet=snippet,
            result=statement_result,
            snapshot=dict(snapshot),
            call_stack=[
                CallStackFrame(
                    depth=frame_data["depth"],
                    name=frame_data["name"],
                    locals=dict(frame_data["locals"]),
                )
                for frame_data in call_stack
            ],
        )
        result.trace.append(entry)
        if trace_callback is not None:
            trace_callback(entry)

    interpreter = Interpreter(
        validation.ast,
        debug=False,
        output_callback=capture_output,
        input_provider=input_provider,
        statement_callback=capture_trace,
    )

    try:
        interpreter.run()
        result.success = True
    except RuntimeError as error:
        result.runtime_error = str(error)
        capture_output(result.runtime_error)
    except Exception as error:
        result.runtime_error = f"Internal execution error: {error}"
        capture_output(result.runtime_error)

    return result


def execute_source(
    source: str,
    input_provider: Optional[Callable[[str], str]] = None,
    output_callback: Optional[Callable[[str], None]] = None,
    trace_callback: Optional[Callable[[TraceEntry], None]] = None,
):
    validation = validate_source(source)
    return execute_validation(
        validation,
        input_provider=input_provider,
        output_callback=output_callback,
        trace_callback=trace_callback,
    )
