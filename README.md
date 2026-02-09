- ast_definition.py contains class definitions for the abstract syntax tree
- ast_constructor.py uses Lark transform to create AST from the parse tree created by Lark
- errors.py contains custom errors
- ast_analysis.py contains a class that analyzes the code (in AST form) and reports errors
- semantics.txt is just a todo list i made for myself, might not be complete

HOW TO RUN:
```
python scanner.py path/to/source.txt
python scanner.py path/to/source.txt -o scanner_output.txt
```