# MIPS Assembly VM written in ScratchPy, a subset of the Python programming language

list memory = []
var memsize = 0

# to be loaded in externally
list programBinary = []
var stackPointer = 0
var prgmCounter = 0

# for performing bit operations
list breg8 = makeArray(8)
list breg16 = makeArray(16)
list breg32 = makeArray(32)

var bitValue = 0
var i = 0

def pow(a,b):
    return tentothe(log(a)*b)

def toBin8(x):
    i=8
    while i>0:
        bitValue = pow(2, 8-i)
        breg8[i] = floor(x/bitValue) % 2
        i-=1

def toBin16(x):
    i=16
    while i>0:
        bitValue = pow(2, 16-i)
        breg8[i] = floor(x/bitValue) % 2
        i-=1

def toBin32(x):
    i=32
    while i>0:
        bitValue = pow(2, 32-i)
        breg8[i] = floor(x/bitValue) % 2
        i-=1

var instructionWord = 0
def main():
    while True:
        instructionWord = memory[prgmCounter+3]
        instructionWord += memory[prgmCounter+2]*256
        instructionWord += memory[prgmCounter+1]*65536
        instructionWord += memory[prgmCounter]*16777216

        