"""
ScratchPy - A simple Python-based scripting language that compiles to scratch
"""
import ast

class ParsingError(Exception):pass 

class SPVariable:
    def __init__(self, name, initialValue=None):
        self.name = name
        self.value = initialValue
    def __repr__(self):
        return f'<Variable "{self.name}" initialValue={repr(self.value)}>'

class SPList:
    def __init__(self, name, initialValue=[]):
        self.name = name
        self.value = initialValue
    
    def __repr__(self):
        return f'<List "{self.name}" initialValue={repr(self.value)}>'

class SPContainer:
    """
    A top-level container is a event block or myblock (function) declaration. contains a python AST body
    which will eventually be parsed into a scratchpy ast object
    You can think of a container as the stuff that actually contains code
    """
    def __init__(self):
        self.pythonBody: list[ast.AST] = []
        self.body: list[SPNode] = []
        self.lineStart = 0 # source code position of the container header

class SPFunctionArgument:
    def __init__(self, name, isBoolean):
        self.name = name
        self.isBoolean = isBoolean

class SPFunctionDefinition(SPContainer):
    def __init__(self, fname, args):
        super().__init__()

        self.fname = fname
        self.args = args
    
    def getArgument(self, name):
        for arg in self.args:
            if arg.name == name:
                return arg
    
    def hasArgument(self, name):
        return self.getArgument(name) != None 

class SPOnBroadcastDefinition(SPContainer):
    def __init__(self, broadcastName):
        super().__init__()

        self.broadcastName = broadcastName

class SPModule:
    def __init__(self):
        self._variables = {}
        self._lists = {}
        self.imports = []

        self.functionBlocks: list[SPFunctionDefinition] = []
        self.broadcasts = []
        self.eventBlocks = []

    def addVariable(self, name, initialValue=None):
        self._variables[name] = SPVariable(name, initialValue)
    
    def getVariable(self, name):
        return self._variables[name]
    
    def getVariables(self):
        return list(self._variables.values())

    def getLists(self):
        return list(self._lists.values())

    def addList(self, name, initialValue=None):
        self._lists[name] = SPList(name, initialValue)
    
    def getList(self, name):
        return self._lists[name]
                
    def findSymbolType(self, name):
        if name in self._variables:
            return "variable"

        if name in self._lists:
            return "list"

        for v in self.functionBlocks:
            if v.fname == name:
                return "function"
    
    def hasSymbolWithName(self, name):
        return self.findSymbolType(name) != None

""" ScratchPy AST Objects """

class SPNode:
    def __init__(self):
        self._publicProperties = []

    def getChildren(self):
        return []
    
    def _dumpProperties(self):
        return " ".join([f'{prop}={repr(self.__dict__[prop])}' for prop in self._publicProperties])

    def __repr__(self):
        return f'<{type(self).__name__} {self._dumpProperties()}>'

class SPConstant(SPNode):
    def __init__(self, value):
        super().__init__()
        self.value = value
        self._publicProperties = ["value"]
    
    def getChildren(self):
        return []

class SPReturn(SPNode):
    def __init__(self, value):
        super().__init__()
        self.value = value
        self._publicProperties = ["value"]
    
    def getChildren(self):
        return [self.value]

# AST reference to a variable
class SPVariableName(SPNode):
    def __init__(self, var: SPVariable):
        super().__init__()
        self.variableName = var.name

        self._publicProperties = ["variableName"]

# AST reference to a list
class SPListName(SPNode):
    def __init__(self, list: SPVariable):
        super().__init__()
        self.listName = list.name

        self._publicProperties = ["variableName"]

# AST reference to a function
class SPFunctionName(SPNode):
    def __init__(self, fname):
        super().__init__()
        self.fname = fname

        self._publicProperties = ["fname"]

# AST reference to a function argument
class SPArgumentName(SPNode):
    def __init__(self, argname, function: SPFunctionDefinition):
        super().__init__()
        self.argname = argname
        self.function = function

        self._publicProperties = ["argname", "function"]
    
    def getArgumentObject(self):
        return self.function.getArgument(self.argname)

class SPAssign(SPNode):
    def __init__(self, targets, value, modify=0):
        super().__init__()
        self.targets = targets
        self.value = value
        self.modify = modify

        self._publicProperties = ["targets", "value", "modify"]
    
    def getChildren(self):
        return self.targets+[self.value]

class SPExpression(SPNode):
    def __init__(self):
        super().__init__()

class SPArithmetic(SPNode):
    def __init__(self, left, right, op):
        super().__init__()

        self.left = left
        self.right = right
        self.op = op

        self._publicProperties = ["left", "right", "op"]
    
    def getChildren(self):
        return [self.left, self.right]