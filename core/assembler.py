""" A basic two-pass MIPS assembler. Outputs a binary file in a custom format that can then be loaded into Scratch """

import struct
import re

class AssemblyMessage:
    def __init__(self, message, line):
        self.message = message
        self.line = line

class InstructionArgument:
    """
    Parsing class for instruction arguments

    These are all valid arguments:
        %hi(a)      # hi value of address of label a
        %lo(a)($2)  # r2 offset by lo value of address of label a
        4($sp)      # stack ptr offset by 4
        $sp         # register 29
        -8          # constant integer -8
    
    """
    def __init__(self, expr):
        self.expr = expr
    
    def getRegisterNumber(self, registerName):
        """ Find the register number (0-31) from a mnemonic register name like "$fp" """

        assert registerName[0] == "$", Exception("Register name must start with $")
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
    
    def evaluate(self, labels):
        """ Evaluate the integer value of this argument.
        Requires a [labels] argument in case this instruction argument references a label """

        # to evaluate these expressions, we're going to use eval(), since i dont feel like writing a parser
        # to mitigate security risks, we're going to restrict use of builtins and the global scope

        # per https://realpython.com/python-eval-function, panic if the name __class__ is used
        if "__class__" in self.expr:
            raise Exception("Name in expression not allowed")
            
        # replace the % operator prefix with an underscore (%hi -> _hi)
        expr = self.expr.replace("%", "_") 

        # replace instances of stuff like, 4($sp) with 4+($sp)
        def repl(matchObject: re.Match):
            boundary = matchObject.group()
            return boundary[0]+"+"+boundary[1]
        expr = re.sub(r'[\w\)]\(', repl=repl, string=expr) # match boundaries between a symbol and an opening parentheses 

        # replace $sp, $31, etc. with a getRegisterNumber expression
        def repl(matchObject: re.Match):
            registerName = matchObject.group()
            return 'reg("{}")'.format(registerName)

        expr = re.sub(r'\$\w+', repl=repl, string=expr)
        print(expr)

        # build global scope with relevant operator definitions
        globalScope = {
            "__builtins__": {}, # used to prevent security risks
            "reg": lambda r: self.getRegisterNumber(r)
        }

class Assembly:
    def __init__(self):
        # Stores labels [labelName : codePosition]
        self.labels = {}

        # Stores forward references to labels [codePosition : labelName]
        self.labelReferences = {}

        # Stores forward references to labels in the code [lineNumber : labelName]
        # Sole purpose of outputting error messages for invalid label names
        self.codeLabelReferences = {}

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

    def addBytesToCode(self, bytes):
        for b in bytes:
            self.machCode.append(b)
            self.currentPos += 1

    def toWord(self, n: int):  # Converts an int32 to an array of four bytes
        return struct.pack("I", n)

    def createWarning(self, message): # Creates a new assembler warning at the current line
        self.warnings.append(
            AssemblyMessage(message, self.currentLine)
        )
    
    def createError(self, message): # Creates a new assembler error at the current line
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
    
    def _toBits(self, n, numBits):
        """
        convert [n] into a bit array [numBits] bits long 
        example: _toBits(50, 6) -> [1, 1, 0, 0, 1, 0]
        """
        bitArray = []
        for i in range(0, numBits):
            positionValue = 2**(i)
            bit = (n//positionValue)%2
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
            n+=bit*positionValue
        return n

    def formatIType(self, op, rs, rt, imm):
        """
        rs is a source register—an address for loads and stores, or an operand for branch and immediate arithmetic instructions.
        rt is a source register for branches, but a destination register for the other I-type instructions
        imm is a 16-bit signed two’s-complement value

        op: 6 bits
        rs: 5 bits
        rt: 5 bits
        imm: 16 bits

        total: 32 bits
        """

        args = self._toBits(op, 6) + self._toBits(rs, 5) + self._toBits(rt, 5) + self._toBits(imm, 16)

        # Use big endian so the order is correct idk man
        return struct.pack(">I", self._bitsToInt(args))

    def getRegisterNumber(self, registerName):
        """ Find the register number (0-31) from a mnemonic register name like "$fp" """

        assert registerName[0] == "$", Exception("Register name must start with $")
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

    def onInstruction(self, instruction, args):
        # Process pseudo-instructions

        if instruction == "nop":
            return self.onInstruction("sll", ["$zero", "$zero", "0"])
        
        # Process actual instructions
        if instruction == "addiu":
            rt = args[0]
            rs = args[1]
            imm = int(args[2])

            self.addBytesToCode(self.formatIType(
                9,
                self.getRegisterNumber(rs),
                self.getRegisterNumber(rt),
                imm
            ))
        elif instruction == "sw":
            rt = InstructionArgument(args[0]).evaluate({})
            rt = InstructionArgument(args[1]).evaluate({})

            rt = args[0]
            
            # parse out offset and register from args[1] which will look something like 8($sp)
            rs = re.findall(r'\(.+?\)', args[1])[0]
            rs = rs[1:-1] # remove leading and trailing parentheses

            offset = re.findall(r'-?\d+(?=\()', args[1])[0] # search for a number followed by "(" character

            self.addBytesToCode(self.formatIType(
                43,
                self.getRegisterNumber(rs),
                self.getRegisterNumber(rt),
                int(offset)
            ))

        elif instruction == "move":
            pass
        elif instruction == "lui":
            pass
        elif instruction == "jr":
            pass
        else:
            self.createError('Unknown instruction "{}"'.format(instruction))
    
    def loadSourceFile(self, fl):
        if self.sourceLines:
            raise Error("Assembly source already loaded")

        with open(fl) as fl:
            flContents = fl.read()

        flContents = flContents.replace("\r\n", "\n") # Convert windows line endings to unix ones
        self.sourceLines = flContents.split("\n") 
    
    def runPass(self, isFirstPass=True):

        for line in self.sourceLines:
            self.processLine(line, isFirstPass=isFirstPass)

    def assemble(self, verbose=True):
        if self.polluted:
            raise Error("Assembly source can only be processed once per Assembly instance")
        
        self.runPass()
        
        # reset variables and whatnot for the second pass
        self.currentPos = 0
        self.currentLine = 1
        self.machCode = bytearray()

        self.runPass(isFirstPass=False)

        self.polluted = True
        if verbose:
            for error in self.errors:
                print("Error:",error.message)
                print('    on line {}: "{}"'.format(error.line, self.sourceLines[error.line-1].strip()))
            print()
            for warn in self.warnings:
                print("Warning:",warn.message)
                print('    on line {}: "{}"'.format(warn.line, self.sourceLines[warn.line-1].strip()))
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
        numQuotes = 0 # if the number of quotes past this character is odd, than this character lies inside a string
        for i in range(charIndex, len(string)):
            if string[i] == '"':
                numQuotes += 1
        
        return numQuotes%2 == 1

    def processLine(self, line, isFirstPass):
        # Determine type of line
        
        line = line.strip() # remove trailing and leading whitespace
        line = self._removeComments(line) # remove comments from line
        line = line.replace("\t", " ") # Convert tabs into single spaces (makes parsing easier)

        # Remove comments

        if line == "": # is line empty?
            return
        elif line.endswith(":"): # is the line a label?
            if not isFirstPass: return # don't parse labels twice
            self.onLabel(line.rstrip(":"))
        elif line.startswith("."): # is the line a directive?
            line = line.lstrip(".") # remove the dot from the directive
            parts = self._split(line, " ") # results in a thing like ["align", "2"]

            directive = parts[0]
            argString = "" # there might not be any arguments

            if len(parts) > 1:
                argString = parts[1]
            
            args = self._split(argString, ",")
            args = list([arg.strip() for arg in args])      # remove surrounding whitespace from arguments (usually only applicable if the commas
                                                            # separating the arguments have trailing spaces)

            self.onDirective(directive, args, isFirstPass)
        else: # it's probably an instruction
            parts = self._split(line, " ") # results in a thing like ["lui", "$2,%hi(a)"]

            instruction = parts[0]
            argString = "" # there might not be any arguments

            if len(parts) > 1:
                argString = parts[1]
            
            args = self._split(argString, ",")
            args = list([arg.strip() for arg in args])      # remove surrounding whitespace from arguments (usually only applicable if the commas
                                                            # separating the arguments have trailing spaces)
            
            self.onInstruction(instruction, args)

        self.currentLine+=1
    
    def findEntryPoint(self):
        """ return memory address of main routine """
        return self.labels["main"]
    
    def getMachineCode(self):
        return bytes(self.machCode)
    
    def makeHeader(self, programSize, programCounter, stackSize, heapSize):
        # see header format below
        headerFormat = "IIII"

        """
        Rough diagram of the Scratch MIPS VM memory space

        +--------------------- <- 0x0000000
        | data segment
        +---------------------
        | program    vvvv
        | 
        +---------------------
        |
        | stack      ^^^^
        +---------------------
        | uninitialized/heap
        |
        |
        +---------------------
        """

        totalMemorySize = programSize+stackSize+heapSize
        stackPointer = programSize+stackSize

        structData = [0x4E494253, programCounter, stackPointer, totalMemorySize]

        return struct.pack(headerFormat, *structData)

    def exportAsBinary(self, filename):
        """ Output Binary format

        header (100 bytes) {
            char[4] identifier      - set to "SBIN"

            uint32 program_counter  - the location in memory to begin execution

            uint32 stack_pointer    - initial location of the stack pointer
            
            uint32 alloc_size       - total amount of system memory to allocate
        }

        program_data (n bytes) {
            byte[n]                 - program data to be loaded in starting at address 0x00000000
        }

        """
        with open(filename, 'wb') as fl:
            programData = self.getMachineCode()
            header = self.makeHeader(
                programSize=len(programData),
                programCounter=self.findEntryPoint(),
                stackSize=self.MAX_STACK_SIZE,
                heapSize=self.MAX_HEAP_SIZE
            )

            fl.write(header + programData)

            