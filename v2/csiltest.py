from csil import CSILProgram
from csil.build import buildToSB3, VMParameters

buildToSB3(
    exportAs="test.sb3",
    program=CSILProgram(),
    params=VMParameters.mipsVM(memorySize=1024)
)