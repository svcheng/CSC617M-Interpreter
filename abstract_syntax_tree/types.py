from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .abstract_node_classes import Expr
    from .identifier import Identifier


@dataclass
class Type:
    name: str | Identifier

    # Array types may not be equal even when this passes, because their
    # dimensions are unknown until runtime.
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Type):
            return False
        return str(self.name) == str(other.name)

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, Type):
            raise TypeError("Equality comparison between Type obj and non-Type obj")
        return str(self.name) != str(other.name)

    def __str__(self) -> str:
        return str(self.name)


class NotArrayType(Type):
    pass


class ArrayType(Type):
    def __init__(self, base_type: NotArrayType, size: list[Expr]):
        self.name = "arr"
        self.base_type = base_type
        self.size = size


# ---- Constants -----------------------------------------------

INT = NotArrayType("int")
FLOAT = NotArrayType("float")
BOOL = NotArrayType("bool")
CHAR = NotArrayType("char")
STR = NotArrayType("str")

BASIC_TYPES: set[str] = {str(INT), str(FLOAT), str(BOOL), str(CHAR), str(STR)}

RESERVED_WORDS: set[str] = {
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
    "cast",
} | BASIC_TYPES
