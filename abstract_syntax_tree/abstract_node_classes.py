from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from .aux_classes import MetaInfo, Scope

# prevent circular import
if TYPE_CHECKING:
    from .return_stmt import ReturnStmt
    from .types import Type


@dataclass
class Node:
    # assigned None during AST construction, populated during analysis
    scope: Optional[Scope]
    meta_info: MetaInfo

    def init_scope(self, scope: Scope) -> None:
        """Initializes the scope of this node."""
        self.scope = scope

    # overriden only by Program and TypeDec
    def build_type_table(self) -> None:
        """Builds type symbol tables while enforcing syntax rules in declarations."""
        pass

    # overriden only by Program and FuncDec
    def build_func_table(self) -> None:
        """Builds function symbol tables while enforcing syntax rules in declarations."""
        pass

    # overriden only by Program, ReturnStmt, and nodes with bodies
    def check_misplaced_returns(self) -> None:
        """Checks if a return statement appears outside a function."""
        pass

    def build_var_tables(self) -> None:
        """Builds variable symbol tables while checking for improper use of identifiers."""
        pass

    def check_types(self) -> Optional[Type]:
        """Checks that types of children are appropriate. Returns the type of this expression, or None for void function invocations and non-expressions."""
        return None

    # overriden only by Program and FuncDec
    def check_returns(self) -> None:
        """Checks that return types are correct."""
        pass

    # overriden only by ReturnStmt and nodes with bodies (except Program)
    def _find_returns(self) -> list[ReturnStmt]:
        return []

    def check_null_references(self) -> None:
        """Checks that variables are not referenced before they are initialized."""
        pass

    # only overriden by Program, FuncDec, Conditional, ReturnStmt
    def ensure_exhaustive_returns(self) -> bool:
        """Ensures that in non-void functions, a return statement will always be reached (unless a runtime error occurs)."""
        return False


@dataclass
class Expr(Node):
    # datatype==None means the type has not yet been resolved
    datatype: Optional[Type]
