from core.scratchpy import spil
from core import scratch
templateProj = scratch.ScratchProject("core/scratchpy/resources/scratchpy_compiler_template.sb3")

target = templateProj.getTarget("__main__")
p = spil.SPILProgram(target)
p.compileToTarget()

templateProj.saveToFile("test.sb3")
