from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Self

from lark import Token
from lark.tree import Meta

from .types import Type

if TYPE_CHECKING:
    from .func_dec import FuncDec
    from .type_dec import TypeDec


@dataclass
class VarInfo:
    is_constant: bool
    datatype: Optional[Type]  # None for variables declared with assignment


@dataclass
class Scope:
    parent_scope: Optional[Self]
    var_table: dict[str, VarInfo]
    type_table: dict[str, Optional[TypeDec]]
    func_table: dict[str, FuncDec]

    def __init__(self, parent_scope: Optional[Self]):
        self.parent_scope = parent_scope
        self.var_table = dict()
        if parent_scope is not None:
            self.type_table = parent_scope.type_table
            self.func_table = parent_scope.func_table
        else:
            self.type_table = dict()
            self.func_table = dict()

    def var_name_in_scope(self, var_name: str) -> bool:
        if var_name in self.var_table:
            return True
        if self.parent_scope is not None:
            return self.parent_scope.var_name_in_scope(var_name)
        return False

    def type_in_scope(self, type_name: str) -> bool:
        return type_name in self.type_table

    def function_in_scope(self, func_name: str) -> bool:
        return func_name in self.func_table

    def get_type_dec(self, type_name: str) -> Optional[TypeDec]:
        return self.type_table[type_name]

    def get_func_dec(self, func_name: str) -> FuncDec:
        return self.func_table[func_name]

    def insert_varname(self, var_name: str, var_info: VarInfo) -> None:
        self.var_table[var_name] = var_info

    def get_var_info(self, var_name: str) -> Optional[VarInfo]:
        if var_name in self.var_table:
            return self.var_table[var_name]
        if self.parent_scope is not None:
            return self.parent_scope.get_var_info(var_name)
        return None

    def var_is_constant(self, var_name: str) -> bool:
        var_info = self.get_var_info(var_name)
        return var_info.is_constant if var_info is not None else False

    def get_type(self, var_name: str) -> Optional[Type]:
        var_info = self.get_var_info(var_name)
        return var_info.datatype if var_info is not None else None

    # Assumes var_name is already in scope.
    def set_type(self, var_name: str, datatype: Type) -> None:
        cur_info = self.get_var_info(var_name)
        assert cur_info is not None
        self.var_table[var_name] = VarInfo(cur_info.is_constant, datatype)


@dataclass
class MetaInfo:
    program_str: str
    start_line: int
    end_line: int
    start_col: int
    end_col: int
    start_pos: int
    end_pos: int

    @staticmethod
    def from_meta(meta: Meta, program_str: str) -> MetaInfo:
        return MetaInfo(
            program_str,
            meta.line,
            meta.end_line,
            meta.column,
            meta.end_column,
            meta.start_pos,
            meta.end_pos,
        )

    @staticmethod
    def from_token(token: Token, program_str: str) -> MetaInfo:
        return MetaInfo(
            program_str,
            token.line,
            token.end_line,
            token.column,
            token.end_column,
            token.start_pos,
            token.end_pos,
        )
