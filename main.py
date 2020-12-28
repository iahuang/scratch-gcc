from core import scratch
from core.scratchpy.parser import SPModuleParser
from core.scratchpy.compiler2 import SPModuleCompiler
parser = SPModuleParser()
text = """
var a = 0

def main():
    a = a*a+2

def add(x,y):
    return x+y

# def add(a,b):
#     return a+b
"""

module = parser.parseText(text)
print(module.functionBlocks[0].body)
#print(module.functionBlocks[1].body)

compiler = SPModuleCompiler(module)
compiler.compileModule()
compiler.exportSB3("test.sb3")
compiler.exportProjectJSON("test.json")