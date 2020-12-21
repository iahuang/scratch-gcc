from core import assembler

asm = assembler.Assembly()
asm.loadSourceFile("test/test.s")
asm.assemble()
asm.exportAsBinary("test/test.bin")
asm.exportDebugFile("test/test.debug")