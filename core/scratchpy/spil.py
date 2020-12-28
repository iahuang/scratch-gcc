"""
SPIL: ScratchPy Intermediate Language

An extremely simple assembly-like language that ScratchPy compiles to that can then
be directly converted into real Scratch code

There are no registers, instructions manipulate scratch variables directly.
In place of registers, temporary variables 0-63 are created to evaluate more complex expressions.
These temporary variables are named "__tmp[n]" where [n] is the variable number.

There is also a list "__stack" which acts as the stack. and the variable "__sp" is the pointer (initialized to 1 at the start)

SPIL has no text format. SPIL is not meant to be written by hand and thus
SPIL programs can only be written by manipulating its data classes.

- Scratch draws no distinction between numbers and strings behind the scenes.
- All arithmetic instructions treat variables as strings and so on.
- Setting a variable to a boolean value results in that variable being set to either "true" or "false"
- Temporary variables 0-3 are reserved for use by pseudo operations
- Broadcasts are used as labels

Built-in Lists:

__stack - see above

Built-in Variables:

__sp            - stack pointer
__tmp[0-63]     - temporary
__zero          - always set to 0
__one           - always set to 1


Built-in Broadcasts:

    broadcast "__tmp0_false":   - set __tmp0 to "false"
        load __tmp0 "false"

    broadcast "__tmp0_true":    - set __tmp0 to "true"
        load __tmp0 "true"
    
    broadcast "__nop":          - do nothing
        nop

    broadcast "__stack_grow":   - grow the stack by 1 element
        apd __stack __zero

Instruction Set:

load dest [x]   - load value [x] into dest  
copy dest x     - copy x into dest 

add dest x      - increment dest by x
sub dest x      - decrement dest by x
mul dest x      - multiply dest by x
div dest x      - divide dest by x

get dest list i - load list[i] into dest (zero indexed)
set list i x    - load x into list[i] (zero indexed)
apd list x      - append x to the end of [list]
len list dest   - load length of [list] into dest

gt dest x y     - set dest to the boolean value of whether x > y 
lt dest x y     - set dest to the boolean value of whether x < y
eq dest x y     - set dest to the boolean value of whether x == y  
and dest x y    - set dest to the boolean value of x AND y
or dest x y     - set dest to the boolean value of x OR y

branch cond b1 b2   - broadcast b1 if cond is set to "true" else broadcast b2 
jump b              - broadcast b

call [function] - call my-block defined at compile-time. no arguments

Pseudo instructions:

not dest        - boolean invert variable dest
    load __tmp1 "true"
    eq __tmp0 dest __tmp1

    branch __tmp0 __tmp0_false ___tmp0_true
    copy dest __tmp0

push x          - push x onto __stack
    set __stack __sp x                  # set value at stack pointer to x
    add __sp __one                      # add 1 to __sp
    len __stack __tmp2                  # find size of stack
    eq __tmp1 __sp __tmp2               # check if __sp == len(stack)
    branch __tmp1 __stack_grow __nop    # grow stack if needed

pop dest        - pop off stack into dest
    sub __sp __one
    get dest __stack __sp

neq dest x y    - set dest to the boolean value of whether x != y
    eq dest x y
    load __tmp1 "true"
    eq __tmp0 dest __tmp1

    branch __tmp0 __tmp0_false ___tmp0_true
    copy dest __tmp0

nop             - no operation
    copy __tmp0 __tmp0

cjump cond b:   - conditional jump: broadcast b if cond is set to "true"
    branch cond b __nop

"""

from .. import scratch


class Instruction:
    def convertToBlocks(self, target: scratch.ScratchTarget):
        """ Return a list of blocks to be added after the last one, in order.
        Reporter blocks will be added to the target but not added to the returned list"""
        raise Exception("Cannot convert base Instruction class")

def makeBroadcastInput(target: scratch.ScratchTarget, inputName, broadcastName):
    return scratch.BlockInput(
        inputName,
        [11, broadcastName, target.proj.getStage().findBroadcastId(broadcastName)]
    )

def makeVariableInput(target: scratch.ScratchTarget, inputName, varName, defaultValue="0"):
    return scratch.BlockInput(
        inputName,
        [12, varName, target.findVariableByName(varName).id],
        [4, defaultValue]
    )


def makeReporterInput(target: scratch.ScratchTarget, inputName, reporter: scratch.Block, defaultValue="0"):
    return scratch.BlockInput(
        inputName,
        reporter.id,
        [4, defaultValue]
    )

def makeBlockInput(target: scratch.ScratchTarget, inputName, block: scratch.Block):
    return scratch.BlockInput(
        inputName,
        block.id,
        noShadow=True
    )


def makeValueInput(target: scratch.ScratchTarget, inputName, value, type=4):
    return scratch.BlockInput(
        inputName,
        [type, value]
    )


def makeVariableField(target: scratch.ScratchTarget, fieldName, varName):
    return scratch.BlockField(fieldName, [varName, target.findVariableByName(varName).id])


def makeListField(target: scratch.ScratchTarget, fieldName, varName):
    return scratch.BlockField(fieldName, [varName, target.findListByName(varName).id])

class Load(Instruction):
    def __init__(self, dest, value):
        self.dest = dest
        self.value = value

    def convertToBlocks(self, target: scratch.ScratchTarget):
        block = target.createBlock()
        block.opcode = "data_setvariableto"
        block.inputs = [makeValueInput(target, "VALUE", self.value)]
        block.fields = [makeVariableField(target, "VARIABLE", self.dest)]
        return [block]


class Copy(Instruction):
    def __init__(self, dest, value):
        self.dest = dest
        self.value = value

    def convertToBlocks(self, target: scratch.ScratchTarget):
        block = target.createBlock()
        block.opcode = "data_setvariableto"
        block.inputs = [makeVariableInput(target, "VALUE", self.value)]
        block.fields = [makeVariableField(target, "VARIABLE", self.dest)]
        return [block]


class BinaryBooleanOperation(Instruction):
    def __init__(self, dest, x, y, opcode):
        self.dest = dest
        self.x = x
        self.y = y
        self.opcode = opcode

    def convertToBlocks(self, target: scratch.ScratchTarget):
        assignBlock = target.createBlock()
        assignBlock.opcode = "data_setvariableto"
        assignBlock.fields = [makeVariableField(target, "VARIABLE", self.dest)]

        boolBlock = target.createBlock(parent=assignBlock)
        boolBlock.opcode = self.opcode
        boolBlock.inputs = [
            makeVariableInput(target, inputName="OPERAND1", varName=self.y),
            makeVariableInput(target, inputName="OPERAND2", varName=self.x)
        ]

        assignBlock.inputs = [
            makeReporterInput(target, inputName="VALUE",
                              reporter=boolBlock)
        ]

        return [assignBlock]


class BinaryArithmeticOperation(Instruction):
    def __init__(self, dest, x, opcode):
        self.dest = dest
        self.x = x
        self.opcode = opcode

    def convertToBlocks(self, target: scratch.ScratchTarget):
        assignBlock = target.createBlock()
        assignBlock.opcode = "data_setvariableto"
        assignBlock.fields = [makeVariableField(target, "VARIABLE", self.dest)]

        arithmeticBlock = target.createBlock(parent=assignBlock)
        arithmeticBlock.opcode = self.opcode
        arithmeticBlock.inputs = [
            makeVariableInput(target, inputName="NUM1", varName=self.dest),
            makeVariableInput(target, inputName="NUM2", varName=self.x)
        ]

        assignBlock.inputs = [
            makeReporterInput(target, inputName="VALUE",
                              reporter=arithmeticBlock)
        ]

        return [assignBlock]


class Add(BinaryArithmeticOperation):
    def __init__(self, dest, x):
        super().__init__(dest, x, "operator_add")


class Sub(BinaryArithmeticOperation):
    def __init__(self, dest, x):
        super().__init__(dest, x, "operator_subtract")


class Mul(BinaryArithmeticOperation):
    def __init__(self, dest, x):
        super().__init__(dest, x, "operator_multiply")


class Div(BinaryArithmeticOperation):
    def __init__(self, dest, x):
        super().__init__(dest, x, "operator_divide")


class Gt(BinaryBooleanOperation):
    def __init__(self, dest, x, y):
        super().__init__(dest, x, y, "operator_gt")


class Lt(BinaryBooleanOperation):
    def __init__(self, dest, x, y):
        super().__init__(dest, x, y, "operator_lt")


class Eq(BinaryBooleanOperation):
    def __init__(self, dest, x, y):
        super().__init__(dest, x, y, "operator_equals")


class Broadcast:
    def __init__(self, name):
        self.name = name
        self.body: list[Instruction] = []

class Get(Instruction):
    def __init__(self, dest, list, i):
        self.dest = dest
        self.list = list
        self.i = i

    def convertToBlocks(self, target: scratch.ScratchTarget):
        assignBlock = target.createBlock()
        assignBlock.opcode = "data_setvariableto"

        reporterBlock = target.createBlock(parent=assignBlock)
        indexBlock = target.createBlock(parent=reporterBlock)
        indexBlock.opcode = "operator_add"
        indexBlock.inputs = [
            makeVariableInput(target, "NUM1", self.i),
            makeValueInput(target, "NUM2", 1)
        ]

        reporterBlock.opcode = "data_itemoflist"
        reporterBlock.inputs = [makeReporterInput(target, "INDEX", indexBlock)]
        reporterBlock.fields = [makeListField(target, "LIST", self.list)]

        assignBlock.inputs = [makeReporterInput(target, "VALUE", reporterBlock)]
        assignBlock.fields = [makeVariableField(target, "VARIABLE", self.dest)]
        return [assignBlock]

class Set(Instruction):
    def __init__(self, list, i, x):
        self.x = x
        self.list = list
        self.i = i

    def convertToBlocks(self, target: scratch.ScratchTarget):
        assignBlock = target.createBlock()
        assignBlock.opcode = "data_replaceitemoflist"

        indexBlock = target.createBlock(parent=assignBlock)
        indexBlock.opcode = "operator_add"
        indexBlock.inputs = [
            makeVariableInput(target, "NUM1", self.i),
            makeValueInput(target, "NUM2", 1)
        ]

        assignBlock.inputs = [
            makeReporterInput(target, "INDEX", indexBlock),
            makeVariableInput(target, "ITEM", self.x)
        ]
        assignBlock.fields = [makeListField(target, "LIST", self.list)]
        return [assignBlock]


class Len(Instruction):
    def __init__(self, list, dest):
        self.list = list
        self.dest = dest

    def convertToBlocks(self, target: scratch.ScratchTarget):
        assignBlock = target.createBlock()
        assignBlock.opcode = "data_setvariableto"
        assignBlock.fields = [makeVariableField(target, "VARIABLE", self.dest)]

        reporterBlock = target.createBlock(parent=assignBlock)
        reporterBlock.opcode = "data_lengthoflist"
        reporterBlock.fields = [makeListField(target, "LIST", self.list)]

        assignBlock.inputs = [makeReporterInput(target, "VALUE", reporterBlock)]

        return [assignBlock]

class Apd(Instruction):
    def __init__(self, list, x):
        self.list = list
        self.x = x
    
    def convertToBlocks(self, target: scratch.ScratchTarget):
        block = target.createBlock()
        block.opcode = "data_addtolist"
        block.inputs = [makeVariableInput(target, "ITEM", self.x)]
        block.fields = [makeListField(target, "LIST", self.list)]
        
        return [block]

class Branch(Instruction):
    def __init__(self, cond, b1, b2):
        self.cond = cond
        self.b1 = b1
        self.b2 = b2

    def convertToBlocks(self, target: scratch.ScratchTarget):
        ifelseBlock = target.createBlock()
        ifelseBlock.opcode = "control_if_else"

        condBlock = target.createBlock(parent=ifelseBlock)
        condBlock.opcode = "operator_equals"
        condBlock.inputs = [
            makeVariableInput(target, "OPERAND1", self.cond),
            makeValueInput(target, "OPERAND2", "true", type=10)
        ]

        yesBlock = target.createBlock(parent=ifelseBlock)
        yesBlock.opcode = "event_broadcastandwait"
        yesBlock.inputs = [makeBroadcastInput(target, "BROADCAST_INPUT", self.b1)]
        
        noBlock = target.createBlock(parent=ifelseBlock)
        noBlock.opcode = "event_broadcastandwait"
        noBlock.inputs = [makeBroadcastInput(target, "BROADCAST_INPUT", self.b2)]

        ifelseBlock.inputs = [
            makeReporterInput(target, "CONDITION", condBlock),
            makeBlockInput(target, "SUBSTACK", yesBlock),
            makeBlockInput(target, "SUBSTACK2", noBlock)
        ]

        return [ifelseBlock]

class Jump(Instruction):
    def __init__(self, b):
        self.b = b
    def convertToBlocks(self, target: scratch.ScratchTarget):
        block = target.createBlock()
        block.opcode = "event_broadcastandwait"
        block.inputs = [makeBroadcastInput(target, "BROADCAST_INPUT", self.b)]

        return [block]

""" Pseudo Operations """

class PseudoInstruction(Instruction):
    def expandsTo(self) -> list:
        """ To be overridden """
        raise Exception("yea")

    def convertToBlocks(self, target: scratch.ScratchTarget):
        blocks = []
        for inst in self.expandsTo():
            blocks+=inst.convertToBlocks(target)
        return blocks

class Nop(PseudoInstruction):
    def expandsTo(self) -> list:
        return (Copy("__tmp0", "__tmp0"),)

class Not(PseudoInstruction):
    def __init__(self, dest):
        self.dest = dest
    
    def expandsTo(self):
        return (
            Load("__tmp1", "true"),
            Eq("__tmp0", "dest", "__tmp1"),
            Branch("__tmp0", "__tmp0_false", "__tmp0_true"),
            Copy("dest", "__tmp0")
        )

class Push(PseudoInstruction):
    def __init__(self, x):
        self.x = x
    
    def expandsTo(self):
        return (
            Set("__stack", "__sp", self.x),
            Add("__sp", "__one"),
            Len("__stack", "__tmp2"),
            Eq("__tmp1", "__sp", "__tmp2"),
            Branch("__tmp1", "__stack_grow", "__nop")
        )

class Pop(PseudoInstruction):
    def __init__(self, dest):
        self.dest = dest
    
    def expandsTo(self):
        return (
            Sub("__sp", "__one"),
            Get(self.dest, "__stack", "__sp")
        )

class CompilationContext:
    def __init__(self):
        self.nextAvailableTmp = 4
        self.currentBlock = None

    def reserveTemporary(self):
        tmp = "__tmp"+str(self.nextAvailableTmp)
        self.nextAvailableTmp += 1
        return tmp

    def reset(self):
        self.nextAvailableTmp = 4


def chainBlocks(a: scratch.Block, b: scratch.Block):
    a.nextId = b.id
    b.parentId = a.id

def makeBlockChain(blocks: list):
    currBlock = blocks[0]

    for i in range(1, len(blocks)):
        nextBlock = blocks[i]
        chainBlocks(currBlock, nextBlock)
        currBlock = nextBlock

def makeInstructionChain(target: scratch.ScratchTarget, instructions: list):
    blocks = []
    for inst in instructions:
        blocks += inst.convertToBlocks(target)
    
    makeBlockChain(blocks)
    return blocks

class SPILProgram:
    def __init__(self, target: scratch.ScratchTarget, stage: scratch.ScratchTarget):
        self.variables: list[str] = []
        self.variableIds = {}

        self.lists: list[str] = []
        self.listIds = {}

        self.broadcasts: list[Broadcast] = []
        self.broadcastIds = {}

        self.compileContext = CompilationContext()

        self.target = target
        self.stage = stage

    def getBroadcastId(self, id):
        return self.broadcastIds[id]

    def createVariable(self, name, value=0):
        varId = self.target.addVariable(name, str(value))
        self.variableIds[name] = varId
    
    def createList(self, name, value=[]):
        listId = self.target.addList(name, value)
        self.listIds[name] = listId

    def makeBuiltins(self):
        """ Create built-in variables, broadcasts, etc. """
        self.createVariable("__sp", 0)

        for i in range(64):
            self.createVariable("__tmp"+str(i))

        self.createVariable("__zero", 0)
        self.createVariable("__one", 1)
        self.createList("__stack", [0, 0, 0, 0])

        b = Broadcast("__test")
        b.body.append(Push("__tmp4"))
        self.broadcasts.append(b)

        b = Broadcast("__test2")
        b.body.append(Pop("__tmp4"))
        self.broadcasts.append(b)

        b = Broadcast("__nop")
        b.body.append(Nop())
        self.broadcasts.append(b)

        b = Broadcast("__stack_grow")
        b.body.append(Apd("__stack", "__zero"))
        self.broadcasts.append(b)

        b = Broadcast("__tmp0_false")
        b.body.append(Load("__tmp0", "false"))
        self.broadcasts.append(b)

        b = Broadcast("__tmp0_true")
        b.body.append(Load("__tmp0", "true"))
        self.broadcasts.append(b)

    def compileToTarget(self):
        self.makeBuiltins()

        # make broadcast ids
        for broadcast in self.broadcasts:
            self.broadcastIds[broadcast.name] = "bc"+scratch.randomId()

        # add broadcast ids to stage
        for name, id in self.broadcastIds.items():
            self.stage.broadcasts[id] = name

        # add variables to target
        for varName in self.variables:
            self.createVariable(varName)

        # add lists to target
        for listName in self.lists:
            self.createList(listName)


        # compile
        for broadcast in self.broadcasts:
            # Create top leavel "on broadcast" block to put code after
            broadcastBlock = self.target.createBlock([0, 0])
            broadcastBlock.opcode = "event_whenbroadcastreceived"
            broadcastOpt = [broadcast.name,
                            self.getBroadcastId(broadcast.name)]
            broadcastBlock.fields.append(
                scratch.BlockField("BROADCAST_OPTION", broadcastOpt))

            # begin the chain
            currentBlock = broadcastBlock

            for instruction in broadcast.body:
                newBlocks = instruction.convertToBlocks(self.target)
                for block in newBlocks:
                    chainBlocks(currentBlock, block)
                    currentBlock = block
