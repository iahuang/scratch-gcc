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

Instruction Set:

load dest [x]   - load value [x] into dest  
copy dest x     - copy x into dest 

add dest x      - increment dest by x
sub dest x      - decrement dest by x
mul dest x      - multiply dest by x
div dest x      - divide dest by x

get dest list i - load list[i] into dest (zero indexed)
set list i x    - load x into list[i] (zero indexed)

gt dest x y     - set dest to the boolean value of whether x > y 
lt dest x y     - set dest to the boolean value of whether x < y
eq dest x y     - set dest to the boolean value of whether x == y  
and dest x y    - set dest to the boolean value of x AND y
or dest x y     - set dest to the boolean value of x OR y

branch cond b1 b2   - broadcast b1 if cond is set to "true" else broadcast b2 

call [function] - call my-block defined at compile-time. no arguments

Pseudo instructions:

not dest        - boolean invert variable dest
    load __tmp1 "true"
    eq __tmp0 dest __tmp1

    branch __tmp0 __tmp0_false ___tmp1_true
    copy dest __tmp0

push x          - push x onto __stack
    set __stack __sp x
    load __tmp0 1
    add __sp __tmp0

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
        [11, broadcastName, target.findBroadcastId(broadcastName)]
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
        reporterBlock.opcode = "data_itemoflist"
        reporterBlock.inputs = [makeVariableInput(target, "INDEX", self.i)]
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

        assignBlock.inputs = [
            makeVariableInput(target, "INDEX", self.i),
            makeVariableInput(target, "ITEM", self.x)
        ]
        assignBlock.fields = [makeListField(target, "LIST", self.list)]
        return [assignBlock]

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
            makeReporterInput(target, "SUBSTACK", yesBlock),
            makeReporterInput(target, "SUBSTACK2", noBlock)
        ]

        return [ifelseBlock]


""" Pseudo Operations """

class Nop(Instruction):
    def convertToBlocks(self, target: scratch.ScratchTarget):
        return Copy("__tmp0", "__tmp0").convertToBlocks(target)

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
    def __init__(self, target: scratch.ScratchTarget):
        self.variables: list[str] = []
        self.variableIds = {}

        self.lists: list[str] = []
        self.listIds = {}

        self.broadcasts: list[Broadcast] = []
        self.broadcastIds = {}

        self.compileContext = CompilationContext()

        self.target = target

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
        self.createVariable("__sp")

        for i in range(64):
            self.createVariable("__tmp"+str(i))

        self.createVariable("__zero", 0)
        self.createVariable("__one", 1)
        self.createList("__testlist", [1,2,3,4])

        b = Broadcast("__test")
        b.body.append(Load("__tmp1", "__tmp0"))
        b.body.append(Add("__tmp1", "__tmp0"))
        b.body.append(Copy("__tmp1", "__tmp0"))
        b.body.append(Gt("__tmp2", "__tmp0", "__tmp1"))
        b.body.append(Get("__tmp0", "__testlist", "__tmp1"))
        b.body.append(Branch("__tmp2", "__nop", "__nop"))
        self.broadcasts.append(b)

        b = Broadcast("__nop")
        b.body.append(Nop())

        self.broadcasts.append(b)

    def compileToTarget(self):
        self.makeBuiltins()

        # make broadcast ids
        for broadcast in self.broadcasts:
            self.broadcastIds[broadcast.name] = "broadcast"+scratch.randomId()

        # add broadcast ids to target
        for name, id in self.broadcastIds.items():
            self.target.broadcasts[id] = name

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
