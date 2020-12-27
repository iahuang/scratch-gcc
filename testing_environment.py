from core import scratch

scratch.ScratchProject.decompile("test_environment.sb3", "proj2.json")
scratch.ScratchProject.decompile("test.sb3", "project.json")

# import ast

# m = ast.parse("""
# a += 1
# """)

# print(ast.dump(m))