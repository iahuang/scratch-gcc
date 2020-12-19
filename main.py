from core import assembler

asm = assembler.Assembly()
asm.loadSourceFile("test.s")

asm.WARN_UNKNOWN_DIRECTIVE = False
asm.assemble()
asm.exportAsBinary("test.bin")

print("Machine code output:")
print(asm.getMachineCode().hex(" "))