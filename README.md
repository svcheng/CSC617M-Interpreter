## Project Info
- The project is written purely in Python. The only dependency is the Lark package, used for scanning and parsing.

## Project Structure
- `grammar.py` is the Lark grammar file for the language
- `scanner.py` contains the scanner logic for checking and reporting lexical errors
- `ast_construction.py` contains the AST construction logic (using Lark transform)
- The `abstract_syntax_tree` submodule contains class definitions, each corresopnding to a type of node in the AST, as well as helper classes and functions
- `errors.py` contains custom errors
- `main.py` - the main entry point for the interpreter
