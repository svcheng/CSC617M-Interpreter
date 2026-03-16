# interpreter.py

from __future__ import annotations
from typing import Any, Optional

from abstract_syntax_tree.program import Program
from abstract_syntax_tree.aux_classes import Scope
from abstract_syntax_tree.assignment import Assignment
from abstract_syntax_tree.var_dec import VarDec
from abstract_syntax_tree.const_dec import ConstDec
from abstract_syntax_tree.print_stmt import PrintStmt
from abstract_syntax_tree.scan_stmt import ScanStmt
from abstract_syntax_tree.conditional import Conditional
from abstract_syntax_tree.while_loop import WhileLoop
from abstract_syntax_tree.for_loop import ForLoop
from abstract_syntax_tree.repeat_loop import RepeatLoop
from abstract_syntax_tree.return_stmt import ReturnStmt
from abstract_syntax_tree.func_dec import FuncDec
from abstract_syntax_tree.invocation import Invocation
from abstract_syntax_tree.bin_op import BinOp
from abstract_syntax_tree.unary_op import UnaryOp
from abstract_syntax_tree.literal import Literal
from abstract_syntax_tree.identifier import Identifier
from abstract_syntax_tree.arr_access import ArrAccess
from abstract_syntax_tree.field_access import FieldAccess
from abstract_syntax_tree.cast import Cast
from abstract_syntax_tree.types import (
    BOOL,
    CHAR,
    FLOAT,
    INT,
    STR,
    ArrayType,
    NotArrayType,
)


class Frame:
    def __init__(self, parent: Optional["Frame"] = None):
        self.parent = parent
        self.values: dict[str, Any] = {}
        self.constants: set[str] = set()
        self.initialized: set[str] = set()

    def lookup(self, name: str):
        if name in self.values:
            return self.values[name]
        if self.parent:
            return self.parent.lookup(name)
        raise RuntimeError(f"Variable '{name}' not found")

    def assign(self, name: str, value: Any, constant: bool = False):
        if name in self.constants and name in self.values:
            raise RuntimeError(f"Cannot reassign constant '{name}'")
        self.values[name] = value
        if constant:
            self.constants.add(name)
        self.initialized.add(name)

    def is_initialized(self, name: str):
        if name in self.initialized:
            return True
        if self.parent:
            return self.parent.is_initialized(name)
        return False


class ReturnSignal(Exception):
    def __init__(self, value: Any):
        self.value = value


class Interpreter:
    def __init__(self, ast: Program, debug: bool = False):
        self.ast = ast
        self.global_frame = Frame(None)
        self.global_scope: Scope = ast.scope
        self.funcs = {str(f.name): f for f in self.ast.func_decs}
        self.debug = debug

    def snippet(self, node):
        mi = getattr(node, "meta_info", None)
        if mi is None:
            return repr(node)
        return mi.program_str[mi.start_pos : mi.end_pos].strip()

    def trace(self, msg: str):
        if self.debug:
            print(msg)

    def run(self):
        self.exec_block(self.ast.main_block, self.global_frame)

    # -------- statement execution --------
    def exec_block(self, stmts: list, frame: Frame):
        for stmt in stmts:
            self.exec_stmt(stmt, frame)

    def exec_stmt(self, stmt, frame: Frame):
        self.trace(f"EXEC {type(stmt).__name__}: {self.snippet(stmt)}")
        match stmt:
            case VarDec():
                self.exec_var_dec(stmt, frame)
            case ConstDec():
                self.exec_const_dec(stmt, frame)
            case Assignment():
                self.exec_assignment(stmt, frame)
            case PrintStmt():
                self.exec_print(stmt, frame)
            case ScanStmt():
                self.exec_scan(stmt, frame)
            case Conditional():
                self.exec_conditional(stmt, frame)
            case WhileLoop():
                self.exec_while(stmt, frame)
            case ForLoop():
                self.exec_for(stmt, frame)
            case RepeatLoop():
                self.exec_repeat(stmt, frame)
            case ReturnStmt():
                raise ReturnSignal(
                    self.eval_expr(stmt.value, frame) if stmt.value else None
                )
            case _:
                raise NotImplementedError(f"Exec not implemented for {type(stmt)}")

    def exec_var_dec(self, stmt: VarDec, frame: Frame):
        name = str(stmt.name)
        if stmt.declared_type is not None:
            typ = stmt.declared_type
            if isinstance(typ, ArrayType):
                value = self.make_array_value(typ, frame)
                frame.assign(name, value, constant=False)
                return
            if str(typ) not in {str(INT), str(FLOAT), str(BOOL), str(CHAR), str(STR)}:
                # record type: auto-initialize with defaults
                value = self.make_record_value(str(typ))
                frame.assign(name, value, constant=False)
                return
        if stmt.init_value is not None:
            value = self.eval_expr(stmt.init_value, frame)
            frame.assign(name, value, constant=False)
            return
        # uninitialized basic variable:
        frame.assign(name, None, constant=False)

    def exec_const_dec(self, stmt: ConstDec, frame: Frame):
        name = str(stmt.name)
        value = self.eval_expr(stmt.value, frame)
        frame.assign(name, value, constant=True)

    def exec_assignment(self, stmt: Assignment, frame: Frame):
        value = self.eval_expr(stmt.rval, frame)

        # lval can be Identifier, FieldAccess, or ArrAccess
        match stmt.lval:
            case Identifier():
                name = str(stmt.lval.name)
                frame.assign(name, value, constant=False)
            case FieldAccess():
                self.set_field(stmt.lval, value, frame)
            case ArrAccess():
                self.set_array_element(stmt.lval, value, frame)
            case _:
                raise RuntimeError("Unsupported l-value")

    def exec_print(self, stmt: PrintStmt, frame: Frame):
        value = self.eval_expr(stmt.value, frame)
        print(value)

    def exec_scan(self, stmt: ScanStmt, frame: Frame):
        target = stmt.lval
        value = input()
        if isinstance(target, Identifier):
            name = str(target.name)
            frame.assign(name, value, constant=False)
        else:
            raise RuntimeError("scan() only supports identifiers")

    def exec_conditional(self, stmt: Conditional, frame: Frame):
        cond = self.eval_expr(stmt.condition, frame)
        if cond:
            self.exec_block(stmt.then_block, Frame(frame))
        elif stmt.else_block is not None:
            self.exec_block(stmt.else_block, Frame(frame))

    def exec_while(self, stmt: WhileLoop, frame: Frame):
        while self.eval_expr(stmt.cond, frame):
            try:
                self.exec_block(stmt.body, Frame(frame))
            except ReturnSignal as r:
                raise r

    def exec_for(self, stmt: ForLoop, frame: Frame):
        start = self.eval_expr(stmt.range_start, frame)
        end = self.eval_expr(stmt.range_end, frame)
        step = self.eval_expr(stmt.step, frame)

        loop_frame = Frame(frame)
        loop_frame.assign(str(stmt.iterator_name.name), start, constant=False)

        def condition(v):
            return v <= end if step >= 0 else v >= end

        while condition(loop_frame.lookup(str(stmt.iterator_name.name))):
            try:
                self.exec_block(stmt.body, loop_frame)
            except ReturnSignal as r:
                raise r
            cur = loop_frame.lookup(str(stmt.iterator_name.name))
            loop_frame.assign(str(stmt.iterator_name.name), cur + step, constant=False)

    def exec_repeat(self, stmt: RepeatLoop, frame: Frame):
        while True:
            try:
                self.exec_block(stmt.body, frame)   
            except ReturnSignal as r:
                raise r
            if self.eval_expr(stmt.cond, frame):
                break

    # -------- expression evaluation --------
    def eval_expr(self, expr, frame: Frame):
        self.trace(f"EVAL {type(expr).__name__}: {self.snippet(expr)}")
        match expr:
            case Literal():
                return expr.value
            case Identifier():
                name = str(expr.name)
                if not frame.is_initialized(name):
                    raise RuntimeError(f"Uninitialized variable {name}")
                return frame.lookup(name)
            case BinOp():
                l = self.eval_expr(expr.left, frame)
                r = self.eval_expr(expr.right, frame)
                result = self.eval_binop(expr.op, l, r)
                self.trace(f"EVAL {l} {expr.op} {r} = {result}")
                return result
            case UnaryOp():
                v = self.eval_expr(expr.arg, frame)
                result = self.eval_unary(expr.op, v)
                self.trace(f"EVAL {expr.op}{v} = {result}")
                return result
            case Invocation():
                return self.eval_call(expr, frame)
            case ArrAccess():
                return self.eval_arr_access(expr, frame)
            case FieldAccess():
                return self.eval_field_access(expr, frame)
            case Cast():
                v = self.eval_expr(expr.arg, frame)
                result = self.eval_cast(expr.target_type.value, v)
                self.trace(f"EVAL Cast ({expr.target_type.value}) {v} = {result}")
                return result
            case _:
                raise NotImplementedError(f"Eval not implemented for {type(expr)}")

    def eval_binop(self, op: str, l: Any, r: Any):
        match op:
            case "+":
                return l + r
            case "-":
                return l - r
            case "*":
                return l * r
            case "/":
                return l / r
            case "==":
                return l == r
            case "!=":
                return l != r
            case "<":
                return l < r
            case "<=":
                return l <= r
            case ">":
                return l > r
            case ">=":
                return l >= r
            case "&&":
                return bool(l) and bool(r)
            case "||":
                return bool(l) or bool(r)
            case _:
                raise RuntimeError(f"Unknown operator {op}")

    def eval_unary(self, op: str, v: Any):
        if op == "!":
            return not bool(v)
        raise RuntimeError(f"Unknown unary operator {op}")

    def eval_call(self, expr: Invocation, frame: Frame):
        name = str(expr.name.name)
        if name not in self.funcs:
            raise RuntimeError(f"Function '{name}' not found")

        func = self.funcs[name]
        fn_frame = Frame(self.global_frame)

        # evaluate args in caller frame
        for (arg_name, _), arg_expr in zip(func.args, expr.args):
            fn_frame.assign(str(arg_name.name), self.eval_expr(arg_expr, frame), constant=False)

        try:
            self.exec_block(func.body, fn_frame)
        except ReturnSignal as r:
            return r.value
        return None

    def eval_arr_access(self, expr: ArrAccess, frame: Frame):
        arr = self.eval_expr(expr.array_name, frame)
        for idx_expr in expr.indices:
            idx = self.eval_expr(idx_expr, frame)
            if not isinstance(idx, int):
                raise RuntimeError("Array index must be integer")
            if idx < 0 or idx >= len(arr):
                raise RuntimeError("Array index out of bounds")
            arr = arr[idx]
        return arr

    def set_array_element(self, expr: ArrAccess, value: Any, frame: Frame):
        arr = self.eval_expr(expr.array_name, frame)
        indices = [self.eval_expr(i, frame) for i in expr.indices]
        sub = arr
        for idx in indices[:-1]:
            sub = sub[idx]
        last = indices[-1]
        sub[last] = value

    def eval_field_access(self, expr: FieldAccess, frame: Frame):
        record = self.eval_expr(expr.record_name, frame)
        for attr in expr.attributes:
            record = record[str(attr.name)]
        return record

    def set_field(self, expr: FieldAccess, value: Any, frame: Frame):
        record = self.eval_expr(expr.record_name, frame)
        for attr in expr.attributes[:-1]:
            record = record[str(attr.name)]
        record[str(expr.attributes[-1].name)] = value

    def eval_cast(self, target: str, value: Any):
        if target == "int":
            return int(value)
        if target == "float":
            return float(value)

        if target == "bool":
            # Handle string input explicitly
            if isinstance(value, str):
                v = value.strip().lower()
                if v in ("true", "1"):
                    return True
                if v in ("false", "0"):
                    return False
                raise RuntimeError(f'Cannot cast "{value}" to bool')
            # For numeric conversions, preserve language-style behavior
            if isinstance(value, (int, float)):
                return value != 0
            return bool(value)

        if target == "char":
            return str(value)[0]
        if target == "str":
            return str(value)

        raise RuntimeError(f"Invalid cast target {target}")

    # -------- helpers for default values --------
    def make_record_value(self, typename: str):
        type_dec = self.global_scope.get_type_dec(typename)
        if type_dec is None:
            raise RuntimeError(f"Unknown record type {typename}")
        result: dict[str, Any] = {}
        for field_id, field_type in type_dec.field_list:
            fname = str(field_id.name)
            if isinstance(field_type, ArrayType):
                result[fname] = self.make_array_value(field_type, self.global_frame)
            elif str(field_type) in {str(INT), str(FLOAT), str(BOOL), str(CHAR), str(STR)}:
                result[fname] = self.default_for_basic(str(field_type))
            else:
                # nested record
                result[fname] = self.make_record_value(str(field_type))
        return result

    def make_array_value(self, typ: ArrayType, frame: Frame):
        sizes = [self.eval_expr(dim, frame) for dim in typ.size]
        if any(not isinstance(s, int) or s < 0 for s in sizes):
            raise RuntimeError("Array size must be non-negative integer(s)")

        def build(dim: int):
            if dim == 1:
                return [self.default_for_basic(str(typ.base_type)) for _ in range(sizes[-1])]
            return [build(dim - 1) for _ in range(sizes[-dim])]

        return build(len(sizes))

    def default_for_basic(self, typename: str):
        if typename == str(INT):
            return 0
        if typename == str(FLOAT):
            return 0.0
        if typename == str(BOOL):
            return False
        if typename == str(CHAR):
            return ""
        if typename == str(STR):
            return ""
        return None