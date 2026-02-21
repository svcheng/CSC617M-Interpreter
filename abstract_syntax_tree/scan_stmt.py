from __future__ import annotations

from dataclasses import dataclass

from errors import ImmutableScanTarget, IncorrectParameterTypeError

from .abstract_node_classes import Expr, Node
from .aux_classes import Scope
from .identifier import Identifier
from .types import STR


@dataclass
class ScanStmt(Node):
    lval: Expr

    def init_scope(self, scope: Scope):
        self.scope = scope
        self.lval.init_scope(scope)

    def build_var_tables(self) -> None:
        self.lval.build_var_tables()

    def check_types(self) -> None:
        assert self.scope is not None
        lval_type = self.lval.check_types()
        assert lval_type is not None

        # lval should not be constant
        if isinstance(self.lval, Identifier) and self.scope.var_is_constant(
            self.lval.name
        ):
            raise ImmutableScanTarget(self.meta_info)

        # lval should be string
        if lval_type != STR:
            raise IncorrectParameterTypeError(
                self.meta_info,
                func_name="scan",
                arg_name=None,
                arg_type=str(STR),
                param_type=str(lval_type.name),
            )
