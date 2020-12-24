import os
import json
from . import SPModule
from .. import scratch


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
            templateFile = thisPath+"/resources/scratchpy_compiler_template.sb3"
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
        
        # create blocks for functions

        for function in self.module.functionBlocks:
            defBlock = stage.createBlock([0, 0])
            defBlock.opcode = "procedures_definition"
            
            protoBlock = stage.createBlock()
            protoBlock.opcode = "procedures_prototype"
            


    def exportSB3(self, filename):
        self.scratchProj.saveToFile(filename)
    
    def exportProjectJSON(self, filename):
        with open(filename, 'w') as fl:
            json.dump(self.scratchProj.serialize(), fl)
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.scratchProj.__exit__()