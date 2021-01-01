""" A set of utility functions for creating Scratch blocks """

from . import scratch

def makeBroadcastInput(target: scratch.ScratchTarget, inputName, broadcastName):
    return scratch.BlockInput(
        inputName,
        [11, broadcastName, target.proj.getStage().findBroadcastId(broadcastName)]
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

def makeBlockInput(target: scratch.ScratchTarget, inputName, block: scratch.Block):
    return scratch.BlockInput(
        inputName,
        block.id,
        noShadow=True
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