from . import scratch
from .block_builder import makeBlockInput, makeBroadcastInput, makeListField, makeReporterInput, makeValueInput, makeVariableField, makeVariableInput 

""" Base Classes """

class Instruction:
    def __init__(self, name, args):
        self.name = name
        self.args = args

    def convertToBlocks(self, target: scratch.ScratchTarget):
        """ Return a list of blocks to be added after the last one, in order.
        Reporter blocks will be added to the target but not added to the returned list"""
        raise Exception("Cannot convert base Instruction class")

class BinaryBooleanOperation(Instruction):
    def __init__(self, dest, x, y, opcode):
        super().__init__("__boolop", ["dest", "x", "y"])
        self.dest = dest
        self.x = x
        self.y = y
        self.opcode = opcode

    def convertToBlocks(self, target: scratch.ScratchTarget):
        assignBlockTrue = target.createBlock()
        assignBlockTrue.opcode = "data_setvariableto"
        assignBlockTrue.fields = [makeVariableField(target, "VARIABLE", self.dest)]
        assignBlockTrue.inputs = [makeValueInput(target, "VALUE", 1)]

        assignBlockFalse = target.createBlock()
        assignBlockFalse.opcode = "data_setvariableto"
        assignBlockFalse.fields = [makeVariableField(target, "VARIABLE", self.dest)]
        assignBlockFalse.inputs = [makeValueInput(target, "VALUE", 0)]

        ifElseBlock = target.createBlock()
        ifElseBlock.opcode = "control_if_else"

        boolBlock = target.createBlock(parent=assignBlock)
        boolBlock.opcode = self.opcode
        boolBlock.inputs = [
            makeVariableInput(target, inputName="OPERAND1", varName=self.y),
            makeVariableInput(target, inputName="OPERAND2", varName=self.x)
        ]

        ifElseBlock.inputs = [
            makeReporterInput(target, "CONDITION", boolBlock),
            makeBlockInput(target, "SUBSTACK", assignBlockTrue),
            makeBlockInput(target, "SUBSTACK2", assignBlockFalse)
        ]

        return [ifElseBlock]

class BinaryArithmeticOperation(Instruction):
    def __init__(self, dest, x, y, opcode):
        super().__init__("__arithop", ["dest", "x", "y"])
        self.dest = dest
        self.x = x
        self.y = y
        self.opcode = opcode

    def convertToBlocks(self, target: scratch.ScratchTarget):
        assignBlock = target.createBlock()
        assignBlock.opcode = "data_setvariableto"
        assignBlock.fields = [makeVariableField(target, "VARIABLE", self.dest)]

        arithmeticBlock = target.createBlock(parent=assignBlock)
        arithmeticBlock.opcode = self.opcode
        arithmeticBlock.inputs = [
            makeVariableInput(target, inputName="NUM1", varName=self.x),
            makeVariableInput(target, inputName="NUM2", varName=self.y)
        ]

        assignBlock.inputs = [
            makeReporterInput(target, inputName="VALUE",
                              reporter=arithmeticBlock)
        ]

        return [assignBlock]

""" Basic """

class Set(Instruction):
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

""" Memory Manipulation """

class Load(Instruction):
    def __init__(self, dest, addr):
        super().__init__("load", ["dest", "addr"])
        self.dest = dest
        self.listTarget = "mem"
        self.addr = addr

    def convertToBlocks(self, target: scratch.ScratchTarget):
        assignBlock = target.createBlock()
        assignBlock.opcode = "data_setvariableto"

        reporterBlock = target.createBlock(parent=assignBlock)
        indexBlock = target.createBlock(parent=reporterBlock)
        indexBlock.opcode = "operator_add"
        indexBlock.inputs = [
            makeVariableInput(target, "NUM1", self.addr),
            makeValueInput(target, "NUM2", 1)
        ]

        reporterBlock.opcode = "data_itemoflist"
        reporterBlock.inputs = [makeReporterInput(target, "INDEX", indexBlock)]
        reporterBlock.fields = [makeListField(target, "LIST", self.listTarget)]

        assignBlock.inputs = [makeReporterInput(target, "VALUE", reporterBlock)]
        assignBlock.fields = [makeVariableField(target, "VARIABLE", self.dest)]
        return [assignBlock]

class Store(Instruction):
    def __init__(self, addr, x):
        super().__init__("store", ["addr", "x"])
        self.x = x
        self.listTarget = "mem"
        self.addr = addr

    def convertToBlocks(self, target: scratch.ScratchTarget):
        assignBlock = target.createBlock()
        assignBlock.opcode = "data_replaceitemoflist"

        indexBlock = target.createBlock(parent=assignBlock)
        indexBlock.opcode = "operator_add"
        indexBlock.inputs = [
            makeVariableInput(target, "NUM1", self.addr),
            makeValueInput(target, "NUM2", 1)
        ]

        assignBlock.inputs = [
            makeReporterInput(target, "INDEX", indexBlock),
            makeVariableInput(target, "ITEM", self.x)
        ]
        assignBlock.fields = [makeListField(target, "LIST", self.listTarget)]
        return [assignBlock]

""" Arithmetic """


class Add(BinaryArithmeticOperation):
    def __init__(self, dest, x, y):
        super().__init__(dest, x, y, "operator_add")
        self.name = "add"


class Sub(BinaryArithmeticOperation):
    def __init__(self, dest, x, y):
        super().__init__(dest, x, y, "operator_subtract")
        self.name = "sub"


class Mul(BinaryArithmeticOperation):
    def __init__(self, dest, x, y):
        super().__init__(dest, x, y, "operator_multiply")
        self.name = "mul"


class Div(BinaryArithmeticOperation):
    def __init__(self, dest, x, y):
        super().__init__(dest, x, y, "operator_divide")
        self.name = "div"

""" Boolean """

class Gt(BinaryBooleanOperation):
    def __init__(self, dest, x, y):
        super().__init__(dest, x, y, "operator_gt")
        self.name = "gt"


class Lt(BinaryBooleanOperation):
    def __init__(self, dest, x, y):
        super().__init__(dest, x, y, "operator_lt")
        self.name = "lt"


class Eq(BinaryBooleanOperation):
    def __init__(self, dest, x, y):
        super().__init__(dest, x, y, "operator_equals")
        self.name = "eq"

class InstructionRegistry:
    def __init__(self, types: list):
        self.types = types
    
    def getInstructionClass(self, name):
        for instType in self.types:
            if instType.__name__.lower() == name:
                return instType

registry = InstructionRegistry([
    Set,
    Copy,
    Load,
    Store,
    Add,
    Sub,
    Mul,
    Div,
    Gt,
    Lt,
    Eq
])