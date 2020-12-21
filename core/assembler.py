""" A basic two-pass MIPS assembler. Outputs a binary file in a custom format that can then be loaded into Scratch """

import struct
import re

"""
Diagram of the Scratch MIPS VM memory space

+--------------------- <- 0x0000000
| i/o space (see below)
+--------------------- <- 0x0000100
| data segment
+---------------------
| program    
| 
+--------------------- <- everything from here up ^^^ is included in the scratch binary file
|
| stack      ^^^^
+--------------------- <- stack_pointer
| uninitialized/heap
|
|
+--------------------- <- mem_end

Static memory segment for interfacing with the Scratch VM (256 bytes wide)
Definitions for interfacing with this part of memory can be found in "lib/sys.h"

io {
    0x00000 char stdout_buffer      - write to this address to print to the "console"

    0x00004 uint32 mem_end          - pointer to the last address in memory

    0x00008 uint32 stack_start      - pointer to the bottom of the stack

    0x0000C uint8 halt              - set this byte to halt execution of the program
                                      for whatever reason
}

...

Scratch executable binary format (the file outputted by Assembly.outputBinaryFile() )

header (100 bytes) {
    char[4] identifier      - set to "SBIN"

    uint32 program_counter  - the location in memory to begin execution

    uint32 stack_pointer    - initial location of the stack pointer
    
    uint32 alloc_size       - total amount of system memory to allocate
}

vvvv to be loaded in starting at address 0x00000000

program_data (n bytes) {
    byte[256]               - i/o segment data (zero initialized)
    byte[n]                 - program data
}

"""


class AssemblyMessage:
    def __init__(self, message, line=None):
        self.message = message
        self.line = line


class ITypeArgumentFormat:
    """ See InstructionArgument.addITypeFormatInstruction() """
    RS_RT_IMM = 0
    RS_IMM = 1
    RT_RS_IMM = 2
    RT_IMM = 3
    RT_RS_IMM_OFFSET = 4


class InstructionArgument:
    """
    Class that represents an instruction argument

    These are all examples of arguments:
        %hi(a)      # hi value of address of label a
        %lo(a)($2)  # r2 offset by lo value of address of label a
        4($sp)      # stack ptr offset by 4
        $sp         # register 29
        -8          # constant integer -8

    For an argument like 4($sp), the corresponding InstructionArgument returned by InstructionArgument.evaluate()
    would be:

        value: 29 # register number of the stack pointer
        offset: 4

    Not all arguments will have a corresponding offset

    """

    def __init__(self, value):
        self.value = value
        self.offset = None

    def __radd__(self, offset):
        self.offset = offset
        return self

    def __repr__(self):
        return f"<Argument value={self.value} offset={self.offset}>"

    @staticmethod
    def getRegisterNumber(registerName):
        """ Find the register number (0-31) from a mnemonic register name like "$fp" """

        assert registerName[0] == "$", Exception(
            "Register name must start with $")
        registerName = registerName[1:]

        names = {
            "zero": 0,
            "gp": 28,
            "sp": 29,
            "fp": 30,
            "ra": 31
        }

        if registerName in names:
            return names[registerName]
        else:
            return int(registerName)

    @staticmethod
    def evaluate(expr, labels=None):
        """ Evaluate the integer value of this argument.
        Requires a [labels] argument in case this instruction argument references a label.
        If this is the first pass, and we don't know the labels yet, set this to None.
        A placeholder label with at address 0 will be used instead.

        Return the value of this argument plus an AssemblyMessage argument if this operation returned
        an error, otherwise None
        """

        # to evaluate these expressions, we're going to use eval(), since i dont feel like writing a parser
        # to mitigate security risks, we're going to restrict use of builtins and the global scope

        # per https://realpython.com/python-eval-function, panic if the name __class__ is used
        if "__class__" in expr:
            raise Exception("Name in expression not allowed")

        if not labels:  # if we don't know any of the labels yet we're going to have to find them manually
            labels = {}
            # matches a string of characters that starts with a letter or underscore and is not preceded by
            # a $ or %
            for match in re.findall(r'(?<![$%])\b[a-zA-Z_]\w{0,}', string=expr):
                labels[match] = 0

        # replace the % operator prefix with two underscores (%hi -> __hi)
        expr = expr.replace("%", "__")

        # replace instances of stuff like, 4($sp) with 4+($sp)
        def repl(matchObject: re.Match):
            boundary = matchObject.group()
            return boundary[0]+"+"+boundary[1]
        # match boundaries between a symbol and an opening parentheses
        expr = re.sub(r'[\d\)]\(', repl=repl, string=expr)

        # replace $sp, $31, etc. with a getRegisterNumber expression
        def repl(matchObject: re.Match):
            registerName = matchObject.group()
            return '__reg("{}")'.format(registerName)

        expr = re.sub(r'\$\w+', repl=repl, string=expr)

        # build global scope with relevant operator definitions and variables
        globalScope = {
            "__builtins__": {},  # used to prevent security risks
            "__reg": lambda r: InstructionArgument(InstructionArgument.getRegisterNumber(r)),
            "__lo": lambda n: (n << 16) >> 16,  # find low 16 bits of word
            "__hi": lambda n: (n >> 16)       # find high 16 bits of word
        }

        # insert label definitions into global scope

        for labelName, labelAddress in labels.items():
            globalScope[labelName] = labelAddress

        evald = 0  # default to 0 in case there is an error parsing
        err = None

        try:
            evald = eval(expr, globalScope, {})
        except NameError as e:
            nameNotDefined = str(e).split("'")[1]  # parse from the exception
            err = AssemblyMessage(f'Label "{nameNotDefined}" is not defined')
        except SyntaxError as e:
            err = AssemblyMessage(f'Syntax Error')

        if type(evald) == int:
            return InstructionArgument(evald), err
        return evald, err

""" Utility class for loading and packing arguments into a 32-bit instruction """

class MIPSInstructionFormat:
    def __init__(self, name=None):
        self.name = name
        self._args = []

    def argument(self, name, bits):
        self._args.append([name, bits])
        return self

    @property
    def argNames(self):
        return list([a[0] for a in self._args])
    
    def _toBits(self, n, numBits):
        """
        convert [n] into a bit array [numBits] bits long 
        example: _toBits(50, 6) -> [1, 1, 0, 0, 1, 0]
        """
        bitArray = []
        for i in range(0, numBits):
            positionValue = 2**(i)
            bit = (n//positionValue) % 2
            bitArray.insert(0, bit)
        return bitArray

    def _bitsToInt(self, bitArray):
        """
        convert [bitArray] into a single number
        example: _bitArrayToInt([1, 1, 0, 0, 1, 0]) -> 50 (0b110010)
        """
        n = 0
        for i in range(len(bitArray)-1, -1, -1):
            positionValue = 2**(len(bitArray)-i-1)
            bit = bitArray[i]
            n += bit*positionValue
        return n

    def byteCodeFromArgs(self, argValues):
        """ With the provided argument values, create a bytes-like representation of an instruction with this format """
        bits = []

        for argName, argSize in self._args:
            bits += self._toBits(argValues[argName], argSize)
        
        # Use big endian so the order is correct idk man
        return struct.pack(">I", self._bitsToInt(bits))
    
    def buildInstructionCode(self, argFormatString, argStrings, presetArgs={}, labels=None):
        """
        Build a complete sequence of bytes representing the finished instruction
        given unparsed and preset instruction arguments

        Arguments:
        argFormatString - a string dictating how to parse the values provided in argStrings
        argStrings      - a list of strings directly corresponding to the arguments of the instruction
        presetArgs      - other arguments to be set manually (not parsed)
        labels          - assembler label table to assist in parsing (not required for first-pass)

        argFormat examples:
        "rs,rt,imm" // args[0] is rs, args[1] is rt and so on
        "rs,imm+rt" // args[0] is rs, args[1] is rt offset by imm
        """

        # parse argFormat

        argCorresponding = [arg.split("+") for arg in argFormatString.split(",")]

        # parse arg strings
        argValues = {k:v for k,v in presetArgs.items()} # copy presetArgs into argValues to avoid modifying the argument
        errors = [] # any errors that arose from parsing

        for argFormat, argExpr in zip(argCorresponding, argStrings):
            if len(argFormat) == 1: # no offset
                argName = argFormat[0]
                val, err = InstructionArgument.evaluate(argExpr, labels)
                argValues[argName] = val.value

                if err:
                    errors.append(err)
            else: # there is an offset
                offsetArgName, argName = argFormat
                argParsed = InstructionArgument.evaluate(argExpr)
                val, err = argParsed.value
                argValues[argName] = val.value

                offset = 0 # default to 0 if no offset parsable
                
                if argParsed.offset == None: # if there was no offset parsable, add an error
                    errors.append(AssemblyMessage(f'Argument of format "{argFormat}" expected offset, but none was found'))
                else:
                    offset = argParsed.offset

                argValues[offsetArgName] = offset

                if err:
                    errors.append(err)
        
        # check: make sure length of argValues is consistent with the number of expected arguments
        #        specified by this instruction format

        if len(argValues) != len(self._args):
            errors.append(AssemblyMessage(f'Expected {len(self._args)} arguments, but found {len(argValues)}'))

            # invalidade argument values and replace them with zeros to prevent exceptions later on

            argValues = {argName:0 for argName in self.argNames}

        code = InstructionFormats.IType.byteCodeFromArgs(argValues)
        return code, errors

class InstructionFormats:
    IType = (
        MIPSInstructionFormat()
        .argument("op", bits=6)
        .argument("rs", bits=5)
        .argument("rt", bits=5)
        .argument("imm", bits=16)
    )


class Assembly:
    def __init__(self):
        # Stores labels [labelName : codePosition]
        self.labels = {}

        # Stores forward references to labels [codePosition : labelName]
        self.labelReferences = {}

        # Stores forward references to labels in the code [lineNumber : labelName]
        # Sole purpose of outputting error messages for invalid label names
        self.codeLabelReferences = {}

        # Debug:
        self.machCodeLines = []
        self.positionAtLastLine = 0

        # Outputted machine code
        self.machCode = bytearray()

        self.currentPos = 0

        # Current line number in processing
        self.currentLine = 1

        # Any warnings or errors created during assembly
        self.errors: list[AssemblyMessage] = []
        self.warnings: list[AssemblyMessage] = []

        # Contents of current source file (split by line)
        self.sourceLines = []

        # Has this source been processed yet? (Assembly source can only be processed once per Assembly instance)
        self.polluted = False

        # Settings
        self.WARN_UNKNOWN_DIRECTIVE = True
        self.MAX_STACK_SIZE = 1024
        self.MAX_HEAP_SIZE = 0

        # VM Constants
        self._IO_SPACE_SIZE = 256

    def addBytesToCode(self, bytes):
        for b in bytes:
            self.machCode.append(b)
            self.currentPos += 1

    def toWord(self, n: int):  # Converts an int32 to an array of four bytes
        return struct.pack("I", n)

    def createWarning(self, message):  # Creates a new assembler warning at the current line
        self.warnings.append(
            AssemblyMessage(message, self.currentLine)
        )

    def createError(self, message):  # Creates a new assembler error at the current line
        self.errors.append(
            AssemblyMessage(message, self.currentLine)
        )

    def onDirective(self, directive, args, isFirstPass):
        if directive == "word":
            self.addBytesToCode(self.toWord(int(args[0])))
        else:
            if self.WARN_UNKNOWN_DIRECTIVE and isFirstPass:
                msg = 'Unknown assembler directive "{}"'.format(directive)
                self.createWarning(msg)

    def onLabel(self, labelName):
        self.labels[labelName] = self.currentPos

    def trackErrorsToCurrentLine(self, errors):
        """ Add list of errors to current assembly errors. Sets the line number of these errors to the current line number """
        # track errors
        for err in errors:
            # errors that were created by the parsing function
            # did not track the line number
            err.line = self.currentLine

            self.errors.append(err)

    def onInstruction(self, instruction, args, isFirstPass):
        # Process pseudo-instructions

        if instruction == "nop":
            return self.onInstruction("sll", ["$zero", "$zero", "0"], isFirstPass)

        labels = None if isFirstPass else self.labels

        # Process actual instructions
        if instruction == "addiu":
            code, errors = InstructionFormats.IType.buildInstructionCode(
                argFormatString="rt,rs,imm",
                argStrings=args,
                presetArgs={"op": 0b001001},
                labels=labels
            )
            self.trackErrorsToCurrentLine(errors)
            self.addBytesToCode(code)
        else:
            self.createError('Unknown instruction "{}"'.format(instruction))

    def loadSourceFile(self, fl):
        if self.sourceLines:
            raise Exception("Assembly source already loaded")

        with open(fl) as fl:
            flContents = fl.read()

        # Convert windows line endings to unix ones
        flContents = flContents.replace("\r\n", "\n")
        self.sourceLines = flContents.split("\n")

    def runPass(self, isFirstPass=True):
        # adds i/o space to program
        for i in range(self._IO_SPACE_SIZE):
            self.addBytesToCode(bytes([0]))

        for line in self.sourceLines:
            self.processLine(line, isFirstPass=isFirstPass)

            # for debug purposes only
            bytesAddedThisLine = self.machCode[self.positionAtLastLine:]
            self.machCodeLines.append(bytesAddedThisLine)
            self.positionAtLastLine = self.currentPos

    def assemble(self, verbose=True):
        if self.polluted:
            raise Exception(
                "Assembly source can only be processed once per Assembly instance")

        self.runPass()

        # reset variables and whatnot for the second pass
        self.currentPos = 0
        self.currentLine = 1
        self.machCode = bytearray()

        self.runPass(isFirstPass=False)

        self.polluted = True
        if verbose:
            for error in self.errors:
                print("Error:", error.message)
                print('    on line {}: "{}"'.format(
                    error.line, self.sourceLines[error.line-1].strip()))
            print()
            for warn in self.warnings:
                print("Warning:", warn.message)
                print('    on line {}: "{}"'.format(
                    warn.line, self.sourceLines[warn.line-1].strip()))
            print()

            print("Assembly finished with {} errors and {} warnings".format(
                len(self.errors),
                len(self.warnings)
            ))

    def _removeComments(self, line):
        """ return [line] with any comments removed """
        if not "#" in line:
            return line

        # Find the first instance of a # character that isn't enclosed inside a string

        for i, c in enumerate(line):
            if c == "#":
                if not self._isCharEnclosed(i, line):
                    return line[:i]

    def _split(self, string, delimiter):
        """ split [string] on any delimiters that aren't enclosed in strings. delimiter can only be one character """
        segment = ""
        segments = []

        for i, c in enumerate(string):
            if c == delimiter and not self._isCharEnclosed(i, string):
                segments.append(segment)
                segment = ""
            else:
                segment += c

        if segment:
            segments.append(segment)

        return segments

    def _isCharEnclosed(self, charIndex, string):
        """ Return true if the character at charIndex is enclosed in double quotes (a string) """
        numQuotes = 0  # if the number of quotes past this character is odd, than this character lies inside a string
        for i in range(charIndex, len(string)):
            if string[i] == '"':
                numQuotes += 1

        return numQuotes % 2 == 1

    def processLine(self, line, isFirstPass):
        # Determine type of line

        line = line.strip()  # remove trailing and leading whitespace
        line = self._removeComments(line)  # remove comments from line
        # Convert tabs into single spaces (makes parsing easier)
        line = line.replace("\t", " ")

        # Remove comments

        if line == "":  # is line empty?
            return
        elif line.endswith(":"):  # is the line a label?
            if not isFirstPass:
                return  # don't parse labels twice
            self.onLabel(line.rstrip(":"))
        elif line.startswith("."):  # is the line a directive?
            line = line.lstrip(".")  # remove the dot from the directive
            # results in a thing like ["align", "2"]
            parts = self._split(line, " ")

            directive = parts[0]
            argString = ""  # there might not be any arguments

            if len(parts) > 1:
                argString = parts[1]

            args = self._split(argString, ",")
            # remove surrounding whitespace from arguments (usually only applicable if the commas
            args = list([arg.strip() for arg in args])
            # separating the arguments have trailing spaces)

            self.onDirective(directive, args, isFirstPass)
        else:  # it's probably an instruction
            # results in a thing like ["lui", "$2,%hi(a)"]
            parts = self._split(line, " ")

            instruction = parts[0]
            argString = ""  # there might not be any arguments

            if len(parts) > 1:
                argString = parts[1]

            args = self._split(argString, ",")
            # remove surrounding whitespace from arguments (usually only applicable if the commas
            args = list([arg.strip() for arg in args])
            # separating the arguments have trailing spaces)

            self.onInstruction(instruction, args, isFirstPass)

        self.currentLine += 1

    def findEntryPoint(self):
        """ return memory address of main routine """
        return self.labels["main"]

    def getMachineCode(self):
        return bytes(self.machCode)

    def makeHeader(self, programSize, programCounter, stackSize, heapSize):
        # see header format above
        headerFormat = "IIII"

        totalMemorySize = programSize+stackSize+heapSize
        stackPointer = programSize+stackSize

        structData = [0x4E494253, programCounter,
                      stackPointer, totalMemorySize]

        return struct.pack(headerFormat, *structData)

    def exportAsBinary(self, filename):
        # see format above
        with open(filename, 'wb') as fl:
            programData = self.getMachineCode()
            header = self.makeHeader(
                programSize=len(programData),
                programCounter=self.findEntryPoint(),
                stackSize=self.MAX_STACK_SIZE,
                heapSize=self.MAX_HEAP_SIZE
            )

            fl.write(header + programData)

    def exportDebugFile(self, filename):
        with open(filename, "w") as fl:
            for sourceLine, lineCode in zip(self.sourceLines, self.machCodeLines):
                fl.write(sourceLine+"\n")
                if lineCode:
                    codeHex = lineCode.hex(" ")
                    codeBin = ""

                    for i in range(0, len(lineCode)):
                        byte = lineCode[i]
                        codeBin += "{:08b}".format(byte)+" "

                    fl.write(f"    [{codeHex}] {codeBin}\n\n")
