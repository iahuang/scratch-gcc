"""
A library for loading and manipluating Scratch project (sb3) files
Basic usage:

with scratch.ScratchProject.fromFile("project.sb3") as proj:
    [do stuff here]

    proj.saveToFile("output.sb3")
"""

import zipfile
import shutil
from pathlib import Path
from glob import glob
import os
import json
import random

TEMPDIR = "tmp/"

def remove_ext(filename):
    return os.path.splitext(filename)[0]

def randomId(size=16):
    return "".join([random.choice("1234567890abcdef") for i in range(size)])

class ScratchAsset:
    def __init__(self, location):
        self.path = Path(location)
        self.name = self.path.name
        with open(location, "rb") as fl:
            self.data = fl.read()

    def __repr__(self):
        return self.data

class BlockInput:
    def __init__(self, inputName: str, value, defaultValue=None):
        """ From the Scratch wiki:

        An object associating names with arrays representing inputs into which reporters may be dropped and C mouths. [?]
        The first element of each array [BlockInput.shadowValue] is 1 if the input is a shadow, 2 if there is no shadow,
        and 3 if there is a shadow but it is obscured by the input.
        The second [BlockInput.value] is either the ID of the input or an array representing it as described below.
        If there is an obscured shadow, the third element is its ID or an array representing it. [third]

        Notes:

        - From my testing, it appears that shadowValue / the first element will never be 2
        - Not entirely sure what the third element (BlockInput.third) does

        """
        self.inputName = inputName
        
        self.value = value
        self.defaultValue = defaultValue

    @property
    def shadow(self):
        return 3 if self.defaultValue else 1
    
    def linkedValue(self, target):
        """ Return the block referenced by self.value, throws an error if self.valueTypeId is not of an id type """
        assert self.valueTypeName == "id", Exception("Type of value does not represent an id type")
        return target.getBlock(self.value)

    @property
    def valueTypeName(self):
        """ Convert self.valueTypeId (an integer) into a more useful description of what type it is
        by looking it up in a table """
        return [
            None,       # 0: undefined
            "id",       # 1: shadow
            None,       # 2: unknown
            "id",       # 3: shadow ("obscured")
            "number",   # 4: number
            "number",   # 5: positive number
            "number",   # 6: positive integer
            "number",   # 7: integer
            "number",   # 8: angle
            "color",    # 9: color
            "string",   # 10: string
            "broadcast",# 11: broadcast
            "variable", # 12: variable
            "list",     # 13: list
        ][self.valueTypeId]
    
    # BlockInput represents a key/value pair, where the key is BlockField.inputName
    def serializeValue(self):
        """ Output a value of type [T, value] where value is either an ID or another, typed value """
        # decide whether value is an ID
        
        if self.defaultValue:
            return [self.shadow, self.value, self.defaultValue]

        return [self.shadow, self.value]
    
    def __repr__(self):
        return f"<Input \"{self.inputName}\">"

class Block:
    def __init__(self, target, id: str):
        self.target = target
        self.id = id
        self.opcode = None
        self.inputs = []
        self.fields = []
        self.shadow = False
        # a kind of redundant variable; set if block.parent != null. don't modify
        self._topLevel = None
        self.parentId = None
        self.nextId = None
        self.x = None
        self.y = None

        self.mutation = None
    
    def loadFromParse(self, blockData):
        self.opcode = blockData["opcode"]
        self.nextId = blockData["next"]
        self.parentId = blockData["parent"]
        self.shadow = blockData["shadow"]
        self._topLevel = blockData["topLevel"]

        for inputName, inputData in blockData["inputs"].items():
            default = None
            if len(inputData) == 3:
                default = inputData[2]

            input = BlockInput(inputName=inputName, value=inputData[1], defaultValue=default)
            self.inputs.append(input)

        for fieldName, fieldData in blockData["fields"].items():
            field = BlockField(fieldName, fieldData[0], fieldData[1] if len(fieldData) > 1 else None)
            self.fields.append(field)
        
        self.x = blockData.get("x", None)
        self.y = blockData.get("y", None)
        return self
    
    def inputByName(self, name):
        for input in self.inputs:
            if input.inputName == name:
                return input
    
    def fieldByName(self, name):
        for field in self.field:
            if field.fieldName == name:
                return field

    
    def getBlock(self, blockId):
        return self.target.getBlock(blockId)

    def getNextBlock(self):
        return self.target.getBlock(self.nextId)

    def getParentBlock(self):
        return self.target.getBlock(self.parentId)

    def _serializeInputs(self):
        return {input.inputName: input.serializeValue() for input in self.inputs}
    
    def _serializeFields(self):
        return {field.fieldName: field.value for field in self.fields}

    def serialize(self):
        baseData = {
            "opcode": self.opcode,
            "inputs": self._serializeInputs(),
            "fields": self._serializeFields(),
            "shadow": self.shadow,
            "topLevel": False if self.parentId else True,
            "parent": self.parentId,
            "next": self.nextId
        }
        # blocks don't necessarily contain x,y data, don't add them if this Block instance doesn't appear to have them
        if self.x != None and self.y != None:
            baseData.update({
                "x": self.x,
                "y": self.y
            })
        if self.mutation:
            baseData.update({
                "mutation": self.mutation
            })
        return baseData

    def __repr__(self):
        return json.dumps(self.serialize(), indent=4)

class BlockField:
    def __init__(self, name, value, varId=None):
        self.fieldName = name
        self.value = value
        self.varId = varId
    def __repr__(self):
        return f"<Field \"{self.fieldName}\": {repr(self.value)}>"

class FunctionDefBlock(Block):
    def __init__(self, target, id):
        super(target, id)
    
    def loadFromParse(self, blockData):
        selfBlock = super().loadFromParse(blockData)
        err = Exception("Cannot create Function definition object from block with opcode", self.opcode)
        assert self.opcode == "procedures_definition", err
        return selfBlock

    @property
    def prototypeBlock(self) -> Block:
        return self.getBlock(self.inputs["custom_block"])

    @property
    def argBlocks(self):
        return self.getBlock()

class Variable:
    def __init__(self, id, name, value=""):
        self.id = id
        self.name = name
        self.value = value

    def __repr__(self):
        return f"<Variable \"{self.name}\": {self.value}>"


class List:
    def __init__(self, id, name, contents=[]):
        self.id = id
        self.name = name
        self.contents = contents

    def __repr__(self):
        return f"<List \"{self.name}\": {self.contents}>"

# represents data for the stage or a scratch sprite (referred to internally as a "target")


class ScratchTarget:
    def __init__(self):
        self.name = "Target"
        self.isStage = False
        self._blocks: dict[str, Block] = {}
        self._variables: dict[str, Variable] = {}
        self._lists: dict[str, List] = {}
        self.comments = {}
        self.currentCostume = 0
        self.costumes = {}
        self.sounds = {}
        self.volume = 100
        self.layerOrder = 0
        self.broadcasts: dict[str, str] = {}

        # stage ony
        self.tempo = 60
        self.videoTransparency = 50
        self.videoState = "on"
        self.textToSpeechLanguage = None

        # non-stage only
        self.visible = True
        self.x = 0
        self.y = 0
        self.size = 0
        self.direction = 90
        self.draggable = False
        self.rotationStyle = "all around"
    
    # Getters and setters

    def findBroadcastId(self, name):
        for id, bname in self.broadcasts.items():
            if bname == name:
                return id

    def getBlocks(self):
        return list(self._blocks.values())
    
    def getVariables(self):
        return list(self._variables.values())

    def findVariableByName(self, name):
        for var in self.getVariables():
            if var.name == name:
                return var
    
    def findListByName(self, name):
        for list in self.getLists():
            if list.name == name:
                return list

    def addVariable(self, name, value=""):
        newId = randomId()
        self._variables[newId] = Variable(newId, name, value)
        return newId
    
    def addList(self, name, value=[]):
        newId = randomId()
        self._lists[newId] = List(newId, name, value)
        return newId
    
    def getLists(self):
        return list(self._lists.values())
    
    def addBlock(self, block: Block, after: Block=None):
        """ Add a block to this target, optionally to be chained after another block (and inserted between it and its original child) if necessary """
        self._blocks[block.id] = block
        
        if after:
            if oldChild := after.getNextBlock():
                oldChild.parentId = block.id
            
            after.nextId = block.id
    
    def createBlock(self, pos=None, parent: Block=None, previous: Block=None):
        newBlock = Block(self, randomId())

        if pos:
            newBlock.x = pos[0]
            newBlock.y = pos[1]
        if parent:
            newBlock.parentId = parent.id
        if previous:
            newBlock.parentId = previous.id
            previous.nextId = newBlock.id
            
        self.addBlock(newBlock)
        return newBlock

    def loadFromParse(self, data: dict):
        self.name = data["name"]
        self.isStage = data["isStage"]
        self.comments = data["comments"]
        self.currentCostume = data["currentCostume"]
        self.costumes = data["costumes"]
        self.sounds = data["sounds"]
        self.volume = data["volume"]
        self.layerOrder = data["layerOrder"]

        # stage only
        self.tempo = data.get("tempo", None)
        self.videoTransparency = data.get("videoTransparency", None)
        self.videoState = data.get("videoState", None)
        self.textToSpeechLanguage = data.get("textToSpeechLanguage", None)

        # non-stage only
        self.visible = data.get("visible", None)
        self.x = data.get("x", None)
        self.y = data.get("y", None)
        self.size = data.get("size", None)
        self.direction = data.get("direction", None)
        self.draggable = data.get("draggable", None)
        self.rotationStyle = data.get("rotationStyle", None)

        # === parse important data: variables, lists, broadcasts, blocks ===

        # parse variables

        self._variables = {}
        for listId, list in data["variables"].items():
            listName, contents = list
            self._variables[listId] = Variable(listId, listName, value=contents)

        # parse lists

        self._lists = {}
        for listId, list in data["lists"].items():
            listName, contents = list
            self._lists[listId] = List(listId, listName, contents=contents)

        # parse broadcasts

        self.broadcasts = data["broadcasts"]  # there's nothing really to parse

        # parse blocks

        self._blocks = {}
        for blockId, blockData in data["blocks"].items():
            newBlock = Block(target=self, id=blockId).loadFromParse(blockData)

            self._blocks[blockId] = newBlock

        return self

    # return json-serializable copy of this target for a project.json file
    def serialize(self):
        baseData = {
            "name": self.name,
            "isStage": self.isStage,
            "variables": {var.id: [var.name, var.value] for var in self._variables.values()},
            "lists": {list.id: [list.name, list.contents] for list in self._lists.values()},
            "broadcasts": self.broadcasts,
            "blocks": {block.id: block.serialize() for block in self._blocks.values()},
            "comments": self.comments,
            "sounds": self.sounds,
            "costumes": self.costumes,
            "currentCostume": self.currentCostume,
            "volume": self.volume,
            "layerOrder": self.layerOrder
        }

        if self.isStage:
            # add stage data to baseData
            baseData.update({
                "tempo": self.tempo,
                "videoTransparency": self.videoTransparency,
                "videoState": self.videoState,
                "textToSpeechLanguage": self.textToSpeechLanguage
            })
        else:
            # add sprite data to baseData
            baseData.update({
                "visible": self.visible,
                "x": self.x,
                "y": self.y,
                "size": self.size,
                "direction": self.direction,
                "draggable": self.draggable,
                "rotationStyle": self.rotationStyle
            })
        

        return baseData

    def __repr__(self):
        return json.dumps(self.serialize(), indent=4)

    def newBlock(self):
        newId = self._randomBlockId()
        newBlock = Block(self, newId)
        self._blocks[newId] = newBlock
        return newBlock

    def getBlock(self, id) -> Block:
        return self._blocks.get(id, None)

    def _randomBlockId(self):
        return "".join([random.choice("1234567890abcdef") for i in range(16)])


class ScratchProject:
    def __init__(self, projectFile):
        if not projectFile.endswith(".sb3"):
            raise Exception("Invalid file type")

        dir = TEMPDIR+remove_ext(projectFile)
        with zipfile.ZipFile(projectFile, 'r') as zip:
            zip.extractall(dir)

        self.dir = dir
        self.deleteDir = True  # Whether to delete the working directory when __exit__ is called
        self.projectFile = projectFile
        self.assets: list = []
        for assetPath in glob(dir+"/*"):
            if assetPath.endswith(".json"):  # Skip the project.json file
                continue

            self.assets.append(ScratchAsset(assetPath))

        self._projectData = None  # JSON-parsed contents of the project.json file
        with open(dir+"/"+"project.json") as projectFile:
            self._projectData = json.load(projectFile)

        # parse information out of self._rawProjectData

        self.targets: list[ScratchTarget] = []
        for targetData in self._projectData["targets"]:
            self.targets.append(ScratchTarget().loadFromParse(targetData))

        self.monitors = self._projectData["monitors"]
        self.extensions = self._projectData["extensions"]
        self.meta = self._projectData["meta"]

    # Return a json-serializable object representing the scratch project.json file
    def serialize(self):
        return {
            "targets": list([target.serialize() for target in self.targets]),
            "monitors": self.monitors,
            "extensions": self.extensions,
            "meta": self.meta

        }

    # return the stage target if it exists
    def getStage(self):
        for target in self.targets:
            if target.isStage:
                return target

    # Read an sb3 file and output a project.json file, don't extract any asset files or return a ScratchProject instance
    @staticmethod
    def decompile(fl, output="project.json"):
        if not fl.endswith(".sb3"):
            raise Exception("Invalid file type")

        # we actually do end up extracting all the files but shhhh we delete them afterwards
        tmpOutputDir = TEMPDIR+remove_ext(fl)
        with zipfile.ZipFile(fl, 'r') as zip:
            zip.extractall(tmpOutputDir)

        with open(output, 'w') as outfl:
            with open(tmpOutputDir+"/project.json") as fl:
                outfl.write(fl.read())

        shutil.rmtree(tmpOutputDir)

    # Patch a string into a existing sb3 file's project.json, overwriting any existing contents
    @staticmethod
    def patchCode(data, projectFile):
        tmpOutputDir = TEMPDIR+remove_ext(projectFile)
        with zipfile.ZipFile(projectFile, 'r') as zip:
            zip.extractall(tmpOutputDir)

        with open(tmpOutputDir+"/project.json", 'w') as patchedFile:
            patchedFile.write(data)

        # remove the old sb3 file
        os.remove(projectFile)
        # make zip file
        shutil.make_archive(remove_ext(projectFile), 'zip', tmpOutputDir)
        # make archive will put the extension .zip on the end; remove it
        os.rename(remove_ext(projectFile)+'.zip', projectFile)

        shutil.rmtree(tmpOutputDir)

    # Patch a new project.json into an existing sb3 file's project.json
    @staticmethod
    def patchFile(file, projectFile):
        with open(file) as fl:
            ScratchProject.patchCode(fl.read(), projectFile)

    # Save the current ScratchProject instance to an sb3 file
    def saveToFile(self, destination, verbose=False, removeTemporary=True, prettyProjectJSON=False):
        # make a directory to write all our files to before compressing it
        cwd = TEMPDIR+"/_saving"  # current working directory for our archive

        if os.path.isdir(cwd):  # if the save directory already exists, delete it
            shutil.rmtree(cwd)

        os.mkdir(cwd)

        # save assets to folder

        for asset in self.assets:
            if verbose:
                print("Saving file", asset.name, "...")

            with open(cwd+"/"+asset.name, "wb") as fl:
                fl.write(asset.data)

        # save project.json

        outputData = self.serialize()

        with open(cwd+"/project.json", "w") as fl:
            if prettyProjectJSON:
                json.dump(outputData, fl, indent=4, sort_keys=True)
            else:
                json.dump(outputData, fl)

        # make zip file
        shutil.make_archive(destination, 'zip', cwd)
        # make archive will put the extension .zip on the end; remove it
        os.rename(destination+'.zip', destination)

        # clean up
        if removeTemporary:
            shutil.rmtree(cwd)
    
    def getTarget(self, name):
        for target in self.targets:
            if target.name == name:
                return target

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if self.deleteDir:
            shutil.rmtree(self.dir)

    def __repr__(self):
        return f'<ScratchProject dir="{self.dir}">'

class Util:
    @staticmethod
    def dumpProjectContents(project: ScratchProject):
        s = ""

        s+=f"=== Scratch Project \"{project.projectFile}\" ===\n"
        s+="\n"
        
        # collect stats
        numStages = len(project.targets)
        numBlocks = 0
        for t in project.targets:
            for b in t._blocks.values():
                numBlocks+=1

        s+=f"Stats: {numStages} stages, {numBlocks} blocks\n"
        s+="\n"

        indent = "    "
        # display targets
        for target in project.targets:
            s+=f"\"{target.name}\" "+("(Stage):\n" if target.isStage else "(Sprite):\n")
            s+=indent+"variables:\n"
            for var in target.getVariables():
                s+=indent*2+f"{var.name} (id: \"{var.id}\")\n"
            s+=indent+"lists:\n"
            for var in target.getLists():
                s+=indent*2+f"{var.name} (id: \"{var.id}\")\n"

            for block in target.getBlocks():
                s+=indent+"Block "+block.opcode+":\n"
                s+=indent*2+"fields:\n"
                for field in block.fields:
                    s+=indent*3+str(field)+"\n"
                s+=indent*2+"inputs:\n"
                for input in block.inputs:
                    s+=indent*3+str(input)+"\n"
                if nextBlock := block.getNextBlock():
                    s+=indent*2+"next: "+nextBlock.opcode+"\n"
            s+="\n"
        
        return s


        