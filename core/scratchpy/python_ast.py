from os import error
from . import SPArgumentName, SPArithmetic, SPConstant, SPFunctionDefinition, SPFunctionName, SPList, SPModule, SPAssign, SPNode, SPReturn, SPVariableName, SPListName
import ast
from typing import Union

class ParsingContext:
    def __init__(self):
        self.enclosingFunction: SPFunctionDefinition = None

class PyASTProcessor:
    def __init__(self, module: SPModule):
        self.module = module
        self.context = ParsingContext()
        self._errorsThisLine = []

    def addError(self, msg):
        self._errorsThisLine.append(msg)
    
    def popErrors(self):
        errors = self._errorsThisLine[:]
        self._errorsThisLine = []
        return errors
    
    def setFunctionContext(self, function: SPFunctionDefinition):
        """ Begin parsing in the context of a function (allow symbols to include function arguments) """
        self.context.enclosingFunction = function
    
    def clearFunctionContext(self):
        self.context.enclosingFunction = None
    
    def processPyAST(self, node: ast.AST):
        """ Converts a Python AST object into a ScratchPy AST object. Returns a list of errors that occurred while parsing """

        spnode = None

        if type(node)==ast.Assign:
            spnode = self.processAssignNode(node)

        elif type(node)==ast.Return:
            spnode = SPReturn(self.processPyAST(node.value))

        elif type(node)==ast.Name:
            spnode = self.processNameNode(node)

        elif type(node)==ast.Constant:
            spnode = SPConstant(node.value)

        elif type(node)==ast.BinOp:
            op = type(node.op)
            opName = ""

            if op == ast.Add:
                opName = "add"
            elif op == ast.Sub:
                opName = "sub"
            elif op == ast.Mult:
                opName = "mul"
            elif op == ast.Div:
                opName = "div"
            else:
                self.addError(f'Unsupported binary operation "{type(node.op).__name__}"')
            
            left = self.processPyAST(node.left)
            right = self.processPyAST(node.right)
            spnode = SPArithmetic(left, right, opName)

        else:
            self.addError(f'Unsupported node type "{type(node).__name__}"')
        
        return spnode

    def processNameNode(self, node: ast.Name):
        symbolName = node.id
        symbolType = self.module.findSymbolType(symbolName)

        # check if symbol is an argument in the current function

        if self.context.enclosingFunction:
            if self.context.enclosingFunction.hasArgument(symbolName):
                return SPArgumentName(symbolName, self.context.enclosingFunction)

        if symbolType == None:
            self.addError(f'Undefined symbol "{symbolName}"')
            return None
        
        if symbolType == "variable":
            return SPVariableName(self.module.getVariable(symbolName))
        
        if symbolType == "list":
            return SPListName(self.module.getList(symbolName))
        
        if symbolType == "function":
            return SPFunctionName(symbolName)
        
        self.addError(f'You shouldn\'t be seeing this error lol')
        return None

    def processAssignNode(self, node: Union[ast.Assign,ast.AugAssign]):
        targets = []
        value = None

        rightHandNode = node.value

        # Process left-hand targets of assignment operator
        for leftHandAssignment in node.targets:
            if type(leftHandAssignment) != ast.Name:
                self.addError(f'Left-hand of assignment operator must be a name constant or list index')
            
            symbolName = leftHandAssignment.id
            symbolType = self.module.findSymbolType(symbolName)

            if symbolType == None:
                self.addError(f'Undefined symbol "{symbolName}"')
            
            # Check to make sure that we're assigning to a variable or list
            if symbolType == "variable":
                targets.append(SPVariableName(self.module.getVariable(symbolName)))
            elif symbolType == "list":
                # can only reassign list variable to a list literal
                if type(rightHandNode) != ast.List:
                    self.addError(f'Cannot assign non-list literal to list variable')
                targets.append(SPListName(self.module.getList(symbolName)))
            else:
                self.addError(f'Cannot assign to symbol of type "{symbolType}"')
        
        # Process right hand value of assignment operator

        value = self.processPyAST(rightHandNode)


        # Process possible assignment augmentation

        modify = None

        if type(node) == ast.AugAssign:
            if node.op == ast.Add:
                modify = "add"
            elif node.op == ast.Sub:
                modify = "sub"
            elif node.op == ast.Mult:
                modify = "mul"
            elif node.op == ast.Div:
                modify = "div"
            else:
                self.addError(f'Unsupported augmented assignment with operation "{type(node.op).__name__}"')
        
        return SPAssign(targets, value, modify)

    def verifyType(self, node: SPNode):
        """ Check types and whatnot, make sure we're not trying to subtract a variable from a list etc. etc. """

        if type(node) == SPArithmetic:
            self._verifyArithmeticArgument(node.left)
            self._verifyArithmeticArgument(node.right)
        if node == None:
            return
        for child in node.getChildren():
            self.verifyType(child)
    
    def _verifyArithmeticArgument(self, node: SPNode):
        if type(node) == SPListName:
            self.addError("Cannot use symbol of type list in arithmetic operation")
            return False
        
        if type(node) == SPFunctionName:
            self.addError("Cannot use symbol of type function in arithmetic operation")
            return False
        
        return True
        