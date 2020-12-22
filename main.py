from core import scratch
from core.scratchpy import SPModuleParser, ParsingError, SPModuleCompiler

parser = SPModuleParser()
text = """
var a = 0

def main():
    a = 1+2

def add(a: int, b: int):
    return a+b
    
"""

module = parser.parseText(text)

with SPModuleCompiler() as compiler:
    compiler.compileModule(module)
    compiler.exportSB3("test.sb3")
    compiler.exportProjectJSON("test.json")