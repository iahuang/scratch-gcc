from os import error, linesep
from .. import scratch
from . import SPContainer, SPModule, SPFunctionDefinition, SPFunctionArgument, ParsingError
from .python_ast import PyASTProcessor
import ast
import re


class SPModuleParser:
    def __init__(self):
        self.module = SPModule()
        self.errors: dict[int,list[str]] = {} # line_number : list[str]
        self.currentLine = 1
        self._parsingSource = []
        self.astProcessor = PyASTProcessor(self.module)
    
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
            self.throwError("Unsupported operation in constant expression", critical=False)
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

        # ok now parse the subsequent indented lines into the container object

        containerBody = []

        lineStart = self.currentLine
        lineNum = self.currentLine+1 # begin parsing into the next block

        while lineNum <= self.lastLineNumber():
            _line = self.getLineByNumber(lineNum)
            _leadingWhitespace = re.findall(r'^\s+', _line)

            if not _line.strip(): # if line is empty, skip it and continue
                lineNum+=1
                containerBody.append(None) # add blank line so the line numbers stay synced
                continue

            if not _leadingWhitespace: # stop once we reach a non-indented block
                break

            # remove block indentation from line
            _line = _line[len(_leadingWhitespace[0]):]

            if _line.endswith(":"):
                _line += " pass"
            
            try:
                containerBody.append(ast.parse(_line).body[0])
            except SyntaxError: # did the python parser throw a hissy fit
                self.throwError("Syntax error", critical=False, lineNumber=lineNum)
                containerBody.append(None)  # add blank line so the line numbers stay synced
            lineNum+=1
        
        self.currentLine = lineNum-1 # skip the lines we just parsed
        # (subtract one because the previous loop ran into the next block and we dont want that)
        
        # don't worry about container being None, if the container type was unable
        # to be determined by this point, a critical error would have been thrown already
        container.pythonBody = containerBody
        container.lineStart = lineStart

        if type(container) == SPFunctionDefinition:
            self.module.functionBlocks.append(container)

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

    def _convertContainerBody(self, container: SPContainer):
        lineNum = container.lineStart
        for astNode in container.pythonBody:
            lineNum+=1
            if astNode == None:
                continue
            spnode = self.astProcessor.processPyAST(astNode)

            self.astProcessor.verifyType(spnode)

            if spnode: # possibly none
                container.body.append(spnode)
            
            for err in self.astProcessor.popErrors():
                self.throwError(err, lineNumber=lineNum, critical=False)
    
    def _parseText(self, text):
        self.currentLine = 1

        # Parse top-level lines
        while self.currentLine <= self.lastLineNumber():
            line = self.getLineByNumber(self.currentLine)
            self._parseTopLevelLine(line)
            self.currentLine+=1
        
        # Process container bodies

        for container in self.module.functionBlocks:
            self.astProcessor.setFunctionContext(container)
            self._convertContainerBody(container)
            self.astProcessor.clearFunctionContext()

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