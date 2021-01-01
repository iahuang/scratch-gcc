"""
ScratchPy - A simple Python-based scripting language that compiles to scratch
"""

from core.scratch import ScratchProject
import core.scratch as scratch
import re
import ast
import os
import json

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

STATEMENT_ASSIGN = 0
STATEMENT_IF = 1
STATEMENT_ELSE = 2
STATEMENT_ELIF = 3
STATEMENT_WHILE = 4
STATEMENT_BREAK = 5
STATEMENT_RETURN = 6
STATEMENT_CALL = 7

class SPStatement:
    """ A statement is a line of code enclosed in a code body such as a function or a loop """
    def __init__(self, type, params, body=None):
        """
        Parameters for the various statement types:
        *parameter list should contain python ast.AST instances

        assign  - [lefthand: list, righthand: expr, mutation: int]  # mutation describes a += or -= assignment
                                                                    # 1 if +=
                                                                    # -1 if -=
                                                                    # 0 otherwise
        if      - [condition]
        else    - [] (none)
        elif    - [condition]
        while   - [condition]
        break   - [] (none)
        return  - [expr]

        Body: a SPCodeBlock instance if relevant

        """
        self.type = type
        self.params = params
        self.body = body

class SPCodeBlock:
    """ A CodeBlock is a list of instructions, such as that following a function definition or the body of a loop """
    def __init__(self):
        self.statements = []

class SPContainer:
    """
    A top-level container is a event block or myblock (function) declaration. contains a SPCodeBlock body.
    You can think of a container as the stuff that actually contains code
    """
    def __init__(self):
        self.body = None

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

class SPOnBroadcastDefinition(SPContainer):
    def __init__(self, broadcastName):
        super().__init__()

        self.broadcastName = broadcastName

class SPModule:
    def __init__(self):
        self._variables = {}
        self._lists = {}
        self.imports = []

        self.functionBlocks = []
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

class ParsingError(Exception):pass 

class SPModuleParser:
    def __init__(self):
        self.module = SPModule()
        self.errors: dict[int,list[str]] = {} # line_number : list[str]
        self.currentLine = 1
        self._parsingSource = []
    
    def getLineByNumber(self, num):
        return self._parsingSource[num-1]
    
    def lastLineNumber(self):
        return len(self._parsingSource)

    def throwError(self, errorText, critical=True, lineNumber=None):
        """ Add an error message to the current (or specified) line """
        at = self.currentLine if lineNumber == None else lineNumber

        if not self.currentLine in self.errors:
            self.errors[at] = []
        
        self.errors[at].append(errorText)

        if critical:
            raise ParsingError("An error occurred while parsing")
    
    def _isCharEnclosed(self, charIndex, string):
        """ Return true if the character at charIndex is enclosed in double quotes (a string) """
        numQuotes = 0  # if the number of quotes past this character is odd, than this character lies inside a string
        for i in range(charIndex, len(string)):
            if string[i] == '"':
                numQuotes += 1

        return numQuotes % 2 == 1

    def _removeComments(self, line):
        """ return [line] with any comments removed """
        if not "#" in line:
            return line

        # Find the first instance of a # character that isn't enclosed inside a string

        for i, c in enumerate(line):
            if c == "#":
                if not self._isCharEnclosed(i, line):
                    return line[:i]
    
    def _isValidName(self, name):
        """
        Enforces valid function/variable/etc names--name cannot start with a number and must contain only alphanumeric characters
        and underscores
        """

        if name[0] in "1234567890":
            return False
        
        for c in name:
            if not c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890_":
                return False
        
        return True

    def _astParseExpr(self, expr):
        """ Parse expression using python's ast module. creates an error on the current line if there was a syntax error """

        try:
            return ast.parse(expr)
        except SyntaxError as e:
            self.throwError(repr(e), critical=False)
            return ast.parse("None") # Return "None" as default

    def _astParseConstantExpr(self, expr):
        """ Parse constant expression using python's ast module. creates an error on the current line if there was a syntax error """
       
        try:
            value = ast.literal_eval(expr)
            return value
        except ValueError as e:
            self.throwError("Unsupported operation in constant expression")
        except SyntaxError:
            self.throwError("Syntax Error", critical=False)
            return 0
    
    def _parseVariableOrListDefinition(self, line):
        # line should look something like "var foo = expr"

        # split string on first instance of an "=" character
        left, right = line.split("=", maxsplit=1) # left="var foo ", right=" expr"

        varName = left.split(" ")[1].strip() # "foo"

        if not self._isValidName(varName):
            self.throwError(f'Invalid variable name "{varName}"')
        
        right = right.strip()

        # top-level variable definitions must be constant expressions
        varInitialValue = self._astParseConstantExpr(right)

        # check to see if symbol with this name already exists in module
        if self.module.hasSymbolWithName(varName):
            self.throwError(f'Duplicate symbol "{varName}"')

        # add variable/list
        symbolType = left.split(" ")[0]
        if symbolType=="var":
            self.module.addVariable(varName, varInitialValue)
        else:
            self.module.addList(varName, varInitialValue)

    def _parseContainerDefinition(self, line: str):
        # line is the header for a top-level container definition
        # such as a function definition or event handler

        # find indentation of subsequent line, if it's zero than we have a problem
        leadingWhitespace = re.findall(r'^\s+', self.getLineByNumber(self.currentLine+1))

        if not leadingWhitespace:
            self.throwError("Missing code block definition", lineNumber=self.currentLine+1)
            
        leadingWhitespace = leadingWhitespace[0] # get first (and only) match

        # we need to package the subsequent code block into an SPContainer
        # and add it to the module. First, let's figure out what kind of container this is

        container = None

        if line.startswith("def "): # it's a function definition, so we can parse it as python
            funcDefNode = ast.parse(line+" pass").body[0]   # add a function body stub to the parser argument so python
                                                            # doesn't get mad that we have an incomplete function definition
            print(ast.dump(funcDefNode))
            functionName = funcDefNode.name
            functionArgNodes = funcDefNode.args.args

            if funcDefNode.args.vararg:
                self.throwError("Variadic arguments are not supported")

            if funcDefNode.args.kwarg:
                self.throwError("Keyword arguments are not supported")
            
            if functionName == "main" and functionArgNodes:
                self.throwError("main function should not have arguments")
            
            functionArgs = []
            for argNode in functionArgNodes:
                isBoolean = False

                if type(argNode.annotation) == ast.Name:
                    if argNode.annotation.id == "bool":
                        isBoolean = True
                
                functionArgs.append(SPFunctionArgument(argNode.arg, isBoolean))
            
            container = SPFunctionDefinition(functionName, functionArgs)
        
        else:
            self.throwError(f'Unexpected symbol "{line.split(" ")[0]}"')
        
        # Collect the contents of this container to be parsed later,
        # once the rest of the top-level lines of this program
        # have been parsed

        # ok now parse the subsequent indented lines (statements) into a code block
        # but actually increment the global line counter
        codeBlock = SPCodeBlock()

        self.currentLine+=1 # begin parsing into the next block

        while self.currentLine <= self.lastLineNumber():
            _line = self.getLineByNumber(self.currentLine)
            _leadingWhitespace = re.findall(r'^\s+', _line)

            if not _line.strip(): # if line is empty, skip it and continue
                self.currentLine+=1
                continue

            if not _leadingWhitespace: # stop once we reach a non-indented block
                self.currentLine-=1 # we've gone too far (into the next bit of code), back up so it can be parsed
                break

            # remove block indentation from line
            _line = _line[len(_leadingWhitespace[0]):]

            # if the code block exists inside a function definition, we need to specify
            # information about the function arguments otherwise they will be considered
            # undefined symbols

            functionContext = None
            if type(container) == SPFunctionDefinition:
                functionContext = container.args

            statement = self._parseStatementLine(_line, functionContext)

            codeBlock.statements.append(statement)
            self.currentLine+=1
        
        # don't worry about container being None, if the container type was unable
        # to be determined by this point, a critical error would have been thrown already
        container.body = codeBlock
        return container

    def _parseTopLevelLine(self, line: str):
        line = self._removeComments(line).rstrip() # remove comments and trailing whitespace 

        if line == "":
            return
        # enforce indentation (top-level lines cannot be indented)
        if line.lstrip() != line:
            self.throwError("Indentation error")
        
        if line.startswith("var ") or line.startswith("list "):
            """ Variable/list definition """

            self._parseVariableOrListDefinition(line)
            return
        
        if line.endswith(":"):
            """ Container definition """

            self._parseContainerDefinition(line)
            return
    
    def _parseStatementLine(self, line, functionArgs=None):
        """
        Parse a codeblock line into a SPStatement object. Returns None if a non-critical error occurred.

        If this statement line exists inside of a function definition body, pass the SBFunctionDefinition.args list as well
        so that symbolic definitions for its arguments can be included as well
        """
        # codeblock statements should all be valid python code
        # use ast.parse to parse them in this case

        node = ast.parse(line).body[0]

        # STATEMENT_ASSIGN = 0
        # STATEMENT_IF = 1
        # STATEMENT_ELSE = 2
        # STATEMENT_ELIF = 3
        # STATEMENT_WHILE = 4
        # STATEMENT_BREAK = 5
        # STATEMENT_RETURN = 6
        print(ast.dump(node))
        if type(node)==ast.Assign:
            param_leftHand = []
            param_rightHand = None
            param_mut = 0

            rightHandNode = node.value

            # Process left-hand targets of assignment operator
            for leftHandAssignment in node.targets:
                if type(leftHandAssignment) != ast.Name:
                    self.throwError(f'Left-hand of assignment operator must be a name constant or list index', critical=False)
                
                symbolName = leftHandAssignment.id
                symbolType = self.module.findSymbolType(symbolName)

                if symbolType == None:
                    self.throwError(f'Undefined symbol "{symbolName}"', critical=False)
                
                # Check to make sure that we're assigning to a variable or list
                if symbolType == "variable":
                    param_leftHand.append(self.module.getVariable(symbolName))
                elif symbolType == "list":
                    # can only reassign list variable to a list literal
                    if type(rightHandNode) != ast.List:
                        self.throwError(f'Cannot assign non-list literal to list variable', critical=False)
                    param_leftHand.append(self.module.getList(symbolName))
                else:
                    self.throwError(f'Cannot assign to symbol of type "{symbolType}"', critical=False)

            # build statement object

            return SPStatement(
                type=STATEMENT_ASSIGN,
                params=[param_leftHand, param_rightHand, param_mut]
            )
        elif type(node) == ast.Return:
            return SPStatement(
                type=STATEMENT_RETURN,
                params=[node.value]
            )

        else:
            self.throwError(f'Unsupported statement type "{type(node).__name__}"', critical=False)
        
            
    def _parseText(self, text):
        self.currentLine = 1

        while self.currentLine <= self.lastLineNumber():
            line = self.getLineByNumber(self.currentLine)
            self._parseTopLevelLine(line)
            self.currentLine+=1

    def parseText(self, text):
        self._parsingSource = text.split("\n")

        try:
            self._parseText(text)
        except ParsingError:
            pass

        if self.errors:
            errorLineNums = list(self.errors.keys())
            errorLineNums.sort() # sort by line number

            for lineNum in errorLineNums:
                errorsOnThisLine = self.errors[lineNum]
                badLine = self.getLineByNumber(lineNum).strip()

                for err in errorsOnThisLine:
                    print(f'line {lineNum}: error: {err}')
                    print(f'    '+badLine)
                print()
        
        return self.module

class SPModuleCompiler:
    def __init__(self, templateFile=None, templateTarget=None):
        """
        The SPModule Compiler works by loading an existing sb3 file to use as a template,
        building the necessary code blocks, and loading them into an existing sprite in that template file.

        templateFile specifies the file to use, if none is specified, then it defaults to using the built-in template

        templateTarget specifies the sprite to load the program blocks into
        """
        if templateFile == None:
            thisPath = os.path.dirname(os.path.realpath(__file__))
            templateFile = thisPath+"/scratchpy_compiler_template.sb3"
            templateTarget = "__main__"
        
        self.templateFile = templateFile
        self.templateTarget = templateTarget
        self.module: SPModule = None

        # The working environment - an instance of a scratch project loaded from the template
        self.scratchProj = scratch.ScratchProject(self.templateFile)
    
    def compileModule(self, module):
        self.module = module

        # Start by creating an scratch project instance to work with

        codeTarget = self.scratchProj.getTarget(self.templateTarget)
        stage = self.scratchProj.getStage()

        # add variables to stage
        
        for variable in self.module.getVariables():
            stage.addVariable(variable.name, variable.value)

    def exportSB3(self, filename):
        self.scratchProj.saveToFile(filename)
    
    def exportProjectJSON(self, filename):
        with open(filename, 'w') as fl:
            json.dump(self.scratchProj.serialize(), fl)
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.scratchProj.__exit__()