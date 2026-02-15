from dataclasses import dataclass
from typing import Any, Optional, Self

from lark import Token
from lark.tree import Meta

# =====================
# Auxialliary info useful for syntax and semantic checking
# =====================


@dataclass
class VarInfo:
    is_constant: bool
    # quotations below so that IDE does not complain that Type is not defined
    datatype: Optional["Type"]  # type: ignore # datatype=None for variables declared with assignment


@dataclass
class Scope:
    parent_scope: Optional[Self]  # has type Scope or None
    var_table: dict[str, VarInfo]

    def var_name_in_scope(self, var_name: str) -> bool:
        if var_name in self.var_table:
            return True
        elif self.parent_scope is not None and self.parent_scope.var_name_in_scope(
            var_name
        ):
            return True

        return False

    def insert_varname(self, var_name: str, var_info: VarInfo) -> None:
        self.var_table[var_name] = var_info

    def get_var_info(self, var_name: str) -> Optional[VarInfo]:
        if var_name in self.var_table:
            return self.var_table[var_name]
        elif self.parent_scope is not None:
            return self.parent_scope.get_var_info(var_name)
        else:
            return None

    def var_is_constant(self, var_name: str) -> bool:
        var_info = self.get_var_info(var_name)
        if var_info is None:
            return False

        return var_info.is_constant

    def get_type(self, var_name: str) -> Optional["Type"]:
        var_info = self.get_var_info(var_name)
        return var_info.datatype if var_info is not None else None

    # assumes var_name is in scope
    def set_type(self, var_name: str, datatype: "Type") -> None:
        cur_info = self.get_var_info(var_name)
        assert cur_info is not None
        self.var_table[var_name] = VarInfo(cur_info.is_constant, datatype)


@dataclass
class MetaInfo:
    start_line: int
    end_line: int
    start_col: int
    end_col: int
    start_pos: int
    end_pos: int

    @staticmethod
    def from_meta(meta: Meta):
        return MetaInfo(
            meta.line,
            meta.end_line,
            meta.column,
            meta.end_column,
            meta.start_pos,
            meta.end_pos,
        )

    @staticmethod
    def from_token(token: Token):
        return MetaInfo(
            token.line,
            token.end_line,
            token.column,
            token.end_column,
            token.start_pos,
            token.end_pos,
        )


# =====================
# Types
# =====================


@dataclass
class Type:
    name: "str | Identifier"

    # note that array types may not be equal even when this passes due to dimensions being unkown until runtime
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Type):
            raise TypeError("Equality comparison between Type obj and non-Type obj")
        return str(self.name) == str(other.name)

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, Type):
            raise TypeError("Equality comparison between Type obj and non-Type obj")
        return str(self.name) != str(other.name)

    def __str__(self) -> str:
        return str(self.name)


@dataclass
class NotArrayType(Type):
    pass


@dataclass
class ArrayType(Type):
    base_type: NotArrayType
    size: list["Expr"]

    def __init__(self, base_type: NotArrayType, size: list["Expr"]):
        self.name = "arr"
        self.base_type = base_type
        self.size = size


# =====================
# Program Structure
# =====================


@dataclass
class Node:
    # will always be assigned None during ast construction, to be determined during syntax checking
    scope: Optional[Scope]
    meta_info: MetaInfo  # contains info about the rule matched like the line number, col number, etc.


@dataclass
class Identifier(Node):
    name: str

    def __str__(self):
        return self.name


@dataclass
class Program(Node):
    type_decs: list["TypeDec"]
    func_decs: list["FuncDec"]
    main_block: list


# =====================
# Declarations
# =====================


@dataclass
class ConstDec(Node):
    name: Identifier
    value: "Expr"


@dataclass
class VarDec(Node):
    name: Identifier
    declared_type: Optional[Type]
    init_value: Optional["Expr"]


@dataclass
class TypeDec(Node):
    name: Identifier
    field_list: list[tuple[Identifier, Type]]


@dataclass
class FuncDec(Node):
    name: Identifier
    args: list[tuple[Identifier, Type]]
    return_type: Optional[Type]
    body: list


# =====================
# Statements
# =====================


@dataclass
class Assignment(Node):
    lval: "Expr"
    rval: "Expr"


@dataclass
class Conditional(Node):
    condition: "Expr"
    then_block: list
    else_block: Optional[list]


@dataclass
class ForLoop(Node):
    iterator_name: Identifier
    range_start: "Expr"
    range_end: "Expr"
    step: "Expr"
    body: list


@dataclass
class WhileLoop(Node):
    cond: "Expr"
    body: list


@dataclass
class RepeatLoop(Node):
    cond: "Expr"
    body: list


@dataclass
class ReturnStmt(Node):
    value: Optional["Expr"]


@dataclass
class PrintStmt(Node):
    value: "Expr"


@dataclass
class ScanStmt(Node):
    lval: "Expr"


# =====================
# Expressions
# =====================


@dataclass
class Expr(Node):
    datatype: Optional[Type]  # type of None means type is still unknown


@dataclass
class Literal(Expr):
    value: Any


@dataclass
class ArrAccess(Expr):
    array_name: Identifier
    indices: list["Expr"]


@dataclass
class FieldAccess(Expr):
    record_name: Identifier
    attribute: Identifier


@dataclass
class UnaryOp(Expr):
    op: str
    arg: Expr


@dataclass
class BinOp(Expr):
    op: str
    left: Expr
    right: Expr


@dataclass
class Invocation(Expr):
    name: Identifier
    args: list[Expr]


#################### Base Types

INT = NotArrayType("int")
FLOAT = NotArrayType("float")
BOOL = NotArrayType("bool")
CHAR = NotArrayType("char")
STR = NotArrayType("str")
