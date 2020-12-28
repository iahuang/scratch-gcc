import os
import json
from . import SPArgumentName, SPArithmetic, SPAssign, SPConstant, SPFunctionDefinition, SPModule, SPNode, SPReturn, SPVariableName
from .. import scratch
from . import spil

class CompilationContext:
    def __init__(self):
        self.nextAvailableTmp = 4
        self.currentBroadcast: spil.Broadcast = None
        self.enclosingFunction: SPFunctionDefinition = None

    def reserveTemporary(self):
        tmp = "__tmp"+str(self.nextAvailableTmp)
        self.nextAvailableTmp += 1
        if self.nextAvailableTmp == 125:
            raise Exception("Temporary variable limit exceeded")
        return tmp

    def resetUsedTemporary(self):
        self.nextAvailableTmp = 4

class SPModuleCompiler:
    def __init__(self, module: SPModule, templateFile=None):
        """
        The SPModule Compiler works by loading an existing sb3 file to use as a template,
        compiling the ScratchPy program into an intermediate language called SPIL and using the SPIL
        compiler to finally create a scratch program.
        """
        if templateFile == None:
            thisPath = os.path.dirname(os.path.realpath(__file__))
            templateFile = thisPath+"/resources/scratchpy_compiler_template.sb3"
        
        self.templateFile = templateFile
        self.module = module

        # The working environment - an instance of a scratch project loaded from the template
        self.scratchProj = scratch.ScratchProject(self.templateFile)
        self.context = CompilationContext()
        self.target = self.scratchProj.getTarget("__main__")
        self.spilProgram = spil.SPILProgram(self.target, self.scratchProj.getStage())
    
    def addInstruction(self, inst: spil.Instruction):
        self.context.currentBroadcast.body.append(inst)
    
    def compileExpression(self, node: SPNode):
        """ Compile a SP Expression into SPIL instructions. Returns variable in which the result of the expresion is stored """
        if type(node) == SPVariableName:
            tmp = self.context.reserveTemporary()
            self.addInstruction(spil.Copy(tmp, node.variableName))
            return tmp
        elif type(node) == SPArgumentName:
            tmp = self.context.reserveTemporary()
            argVar = self.nameMangleArgument(node.argname, self.context.enclosingFunction)
            self.addInstruction(spil.Copy(tmp, argVar))
            return tmp
        elif type(node) == SPConstant:
            tmp = self.context.reserveTemporary()
            self.addInstruction(spil.Load(tmp, node.value))
            return tmp
        
        elif type(node) == SPArithmetic:
            tmpL = self.compileExpression(node.left)
            tmpR = self.compileExpression(node.right)

            if node.op=="add":
                self.addInstruction(spil.Add(tmpL, tmpR))
            if node.op=="sub":
                self.addInstruction(spil.Sub(tmpL, tmpR))
            if node.op=="mul":
                self.addInstruction(spil.Mul(tmpL, tmpR))
            if node.op=="div":
                self.addInstruction(spil.Div(tmpL, tmpR))

            return tmpL
        else:
            print(f'Unsupported SP node type in expression: {type(node).__name__}')

    def compileAssignNode(self, node: SPAssign):
        for assignTargetNode in node.targets:
            assignTarget = assignTargetNode.variableName
            assignVal = self.compileExpression(node.value)
            self.addInstruction(spil.Copy(assignTarget, assignVal))
    
    def compileReturnNode(self, node: SPReturn):
        exprVariable = self.compileExpression(node.value)
        retVariable = self.getReturnVariableName(self.context.enclosingFunction)
        self.addInstruction(spil.Copy(retVariable, exprVariable))
    
    def nameMangleArgument(self, argName, function: SPFunctionDefinition):
        return f"_{function.fname}_arg_{argName}"
    
    def getReturnVariableName(self, function: SPFunctionDefinition):
        return f"_{function.fname}_retval"
    
    def compileModule(self):
        for variable in self.module.getVariables():
            self.spilProgram.createVariable(variable.name, variable.value)
        
        for function in self.module.functionBlocks:            
            self.context.enclosingFunction = function

            # Add global variables for the function arguments and return
            for arg in function.args:
                self.spilProgram.createVariable(self.nameMangleArgument(arg.name, function))

            # add global variable for return value
            self.spilProgram.createVariable(self.getReturnVariableName(function))

            # make broadcast that represents function call
            bc = spil.Broadcast("_call_"+function.fname)
            self.context.currentBroadcast = bc

            # compile function body into broadcast

            for node in function.body:
                if type(node) == SPAssign:
                    self.compileAssignNode(node)
                elif type(node) == SPReturn:
                    self.compileReturnNode(node)
                else:
                    print(f'Unsupported SP node type in statement: {type(node).__name__}')

                self.context.resetUsedTemporary()

            self.spilProgram.broadcasts.append(bc)
        
        self.spilProgram.compileToTarget()
    
    def exportSB3(self, filename):
        self.scratchProj.saveToFile(filename)
    
    def exportProjectJSON(self, filename):
        with open(filename, 'w') as fl:
            json.dump(self.scratchProj.serialize(), fl)

