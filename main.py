from core import scratch
from core.scratchpy.parser import SPModuleParser
from core.scratchpy.compiler import SPModuleCompiler
parser = SPModuleParser()
text = """
var a = 0

def main():
    a = 1+a

def add(a, b):
    return a+b
    
"""

module = parser.parseText(text)
print(module.functionBlocks[0].body)

with SPModuleCompiler() as compiler:
    compiler.compileModule(module)
    compiler.exportSB3("test.sb3")
    compiler.exportProjectJSON("test.json")