from __future__ import annotations

from dataclasses import dataclass

from .abstract_node_classes import Node
from .aux_classes import Scope
from .func_dec import FuncDec
from .type_dec import TypeDec
from .types import BASIC_TYPES


@dataclass
class Program(Node):
    type_decs: list[TypeDec]
    func_decs: list[FuncDec]
    main_block: list

    def init_scope(self, scope: Scope):
        self.scope = scope
        self.scope.type_table = {k: None for k in BASIC_TYPES}

        for type_dec in self.type_decs:
            type_dec.init_scope(scope)
        for func_dec in self.func_decs:
            new_scope = Scope(self.scope)
            func_dec.init_scope(new_scope)
        for stmt in self.main_block:
            stmt.init_scope(scope)

    def build_type_table(self):
        assert self.scope is not None
        for dec in self.type_decs:
            dec.build_type_table()

    def build_func_table(self):
        for dec in self.func_decs:
            dec.build_func_table()

    def check_misplaced_returns(self):
        for stmt in self.main_block:
            stmt.check_misplaced_returns()

    def build_var_tables(self):
        for func_dec in self.func_decs:
            func_dec.build_var_tables()
        for stmt in self.main_block:
            stmt.build_var_tables()

    def check_returns(self):
        for dec in self.func_decs:
            dec.check_returns()

    def check_types(self):
        for func_dec in self.func_decs:
            func_dec.check_types()
        for stmt in self.main_block:
            stmt.check_types()
