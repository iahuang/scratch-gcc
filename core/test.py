import ast

try:
    m = ast.parse("""
    if a == 1:
        +
    """)
except SyntaxError as e:
    print(repr(e))

#print(ast.dump(m))