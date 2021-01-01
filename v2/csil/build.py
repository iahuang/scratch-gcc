""" CSIL Compilation and Build Module """

from . import Broadcast, CSILProgram
from .parser import parseSource
from .scratch import ScratchProject, randomId
import os

class BuildContext:
    def __init__(self, template):
        self.template = template

        self.target = template.getTarget("__main__")
        self.stage = template.getStage()

        self.broadcastIds = {}
    
    def addRegister(self, name, value=0):
        self.target.addVariable(name, str(value))
    
    def initMemoryList(self, memSize):
        # Create a list for the memory
        self.target.addList("mem", list([0 for i in range(memSize)]))
    
    def getBroadcastId(self, name):
        return self.broadcastIds[name]

    def registerBroadcast(self, broadcast: Broadcast):
        id = randomId()
        self.broadcastIds[broadcast.name] = id
        self.stage.broadcasts[id] = name

class VMParameters:
    """ Parameters for the CSIL runtime """
    def __init__(self, memorySize: int, stackPointerInit: int):
        self.memorySize = memorySize
        self.stackPointerInit = stackPointerInit
    
    @staticmethod
    def mipsVM(memorySize: int):
        """ Create a parameter list preset for emulating a MIPS CPU """
        return VMParameters(memorySize, stackPointerInit=memorySize-1)

def buildToSB3(exportAs: str, program: CSILProgram, params: VMParameters):
    """ To build a CSIL Program, we compile the CSIL code into blocks and add them to an existing 
    Scratch project template """
    currDirectory = os.path.dirname(os.path.realpath(__file__))
    template = ScratchProject(currDirectory+"/resources/template.sb3")
    
    context = BuildContext(template)

    # Add variables to the target to represent registers

    for i in range(64):
        context.addRegister("tmp"+str(i))

    for i in range(4):
        context.addRegister("arg"+str(i))
    
    for i in range(4):
        context.addRegister("res"+str(i))

    context.addRegister("ZERO")
    context.addRegister("ONE", 1)
    context.addRegister("rv")
    context.addRegister("null")
    context.addRegister("STACK_END", 0)
    context.addRegister("err", "")
    context.addRegister("fp")

    context.addRegister("sp", params.stackPointerInit)

    # Initialize memory
    context.initMemoryList(params.memorySize)

    # Add CSIL Header

    with open(currDirectory+"/resources/header.csil") as fl:
        headerPrgm = parseSource(fl.read())
    
    for broadcast in program.broadcasts:
        context.registerBroadcast(broadcast)
    
    row = 0
    col = 0
    rowSpacing = 1000
    colSpacing = 500
    maxCols = 5

    # compile
    for broadcast in program.broadcasts:
        # Create top leavel "on broadcast" block to put code after
        broadcastBlock = context.target.createBlock([col*colSpacing, row*rowSpacing])
        broadcastBlock.opcode = "event_whenbroadcastreceived"
        broadcastOpt = [broadcast.name,
                        context.getBroadcastId(broadcast.name)]
        broadcastBlock.fields.append(
            scratch.BlockField("BROADCAST_OPTION", broadcastOpt))

        # begin the chain
        currentBlock = broadcastBlock

        for instruction in broadcast.body:
            newBlocks = instruction.convertToBlocks(context.target)
            for block in newBlocks:
                chainBlocks(currentBlock, block)
                currentBlock = block
        
        col+=1
        if col>maxCols:
            col = 0
            row+=1
    template.saveToFile(exportAs)