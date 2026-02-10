from lark import Lark
from lark.exceptions import UnexpectedInput
import argparse
import time
from pathlib import Path

GRAMMAR_PATH = Path(__file__).with_name("grammar.lark")

CLASS_MAP = {
    "IDENTIFIER": "Identifier",
    "INT": "Integer constant",
    "FLOAT": "Float constant",
    "STRVAL": "String constant",
    "CHARVAL": "Character constant",
    "BOOLVAL": "Boolean constant",
    # keywords / type names
    "LET": "Keyword",
    "VAR": "Keyword",
    "IF": "Keyword",
    "ELSE": "Keyword",
    "FOR": "Keyword",
    "WHILE": "Keyword",
    "REPEAT": "Keyword",
    "UNTIL": "Keyword",
    "RETURN": "Keyword",
    "MAIN": "Keyword",
    "RECORD": "Keyword",
    "INT_T": "Type",
    "FLOAT_T": "Type",
    "BOOL_T": "Type",
    "CHAR_T": "Type",
    "STR_T": "Type",
    "ARR": "Keyword",
    "VOID": "Keyword",
    "PRINT": "Keyword",
    "SCAN": "Keyword",
    # errors
    "INVALID_IDENT": "Invalid Identifier",
}

def classify(tok):
    return CLASS_MAP.get(tok.type, tok.type)

def build_lexer(grammar_path=GRAMMAR_PATH):
    text = grammar_path.read_text(encoding="utf-8")
    # create a Lark instance in lexer-only mode (no parser)
    return Lark(text, parser=None, lexer="basic")

def scan_text(text, lexer, output_file=None):
    start = time.time()
    out_lines = []
    try:
        tokens = lexer.lex(text)
        for tok in tokens:
            # skip whitespace-like tokens if present
            if tok.type in ("WS", "NEWLINE"):
                continue
            label = classify(tok)
            line = getattr(tok, "line", "?")
            col = getattr(tok, "column", "?")
            if label == "UNKNOWN" or tok.type == "UNKNOWN":
                out_lines.append(f"Error found in line {line} column {col}: Unknown symbol '{tok.value}'")
            else:
                out_lines.append(f'{label} Token "{tok.value}" found in line {line} column {col}')
    except UnexpectedInput as e:
        out_lines.append(f"Lexer error: {e}")
    elapsed = time.time() - start
    out_lines.append(f"\nScanner time: {elapsed:.6f} seconds")

    if output_file:
        Path(output_file).write_text("\n".join(out_lines), encoding="utf-8")
        print(f"Output dumped to {output_file}")
    else:
        print("\n".join(out_lines))

def main():
    parser = argparse.ArgumentParser(description="Scanner using grammar.lark")
    parser.add_argument("filename", help="Source file to scan")
    parser.add_argument("-o", "--output", help="Write scanner output to file")
    args = parser.parse_args()

    lexer = build_lexer()
    src = Path(args.filename).read_text(encoding="utf-8")
    scan_text(src, lexer, args.output)

if __name__ == "__main__":
    main()