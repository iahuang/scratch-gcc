from core import assembler

asm = assembler.Assembly()
asm.loadSourceFile("test.s")
asm.assemble()
asm.exportAsBinary("test.bin")
asm.exportDebugFile("test.debug")