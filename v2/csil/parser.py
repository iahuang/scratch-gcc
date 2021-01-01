""" Source Parsing Module for CSIL """

from typing import Type
from . import Broadcast, CSILProgram
from . import instructions

class CSILParseError(Exception): pass

def _isCharEnclosed(charIndex, string):
    """ Return true if the character at charIndex is enclosed in double quotes (a string) """
    numQuotes = 0  # if the number of quotes past this character is odd, than this character lies inside a string
    for i in range(charIndex, len(string)):
        if string[i] == '"':
            numQuotes += 1

    return numQuotes % 2 == 1

def _removeComments(line):
    """ return [line] with any comments removed """
    if not "#" in line:
        return line

    # Find the first instance of a # character that isn't enclosed inside a string

    for i, c in enumerate(line):
        if c == "#":
            if not _isCharEnclosed(i, line):
                return line[:i]

def _split(string, delimiter):
    """ split [string] on any delimiters that aren't enclosed in strings. delimiter can only be one character """
    segment = ""
    segments = []

    for i, c in enumerate(string):
        if c == delimiter and not _isCharEnclosed(i, string):
            segments.append(segment)
            segment = ""
        else:
            segment += c

    if segment:
        segments.append(segment)

    return segments

def parseInstruction(line):
    parts = _split(line, " ")

    instruction = parts[0]
    args = parts[1:]

    # this bit uses a lot of weird trickery, don't look too much into it
    # it's also the reason this file isn't several hundred lines long
    instructionType = instructions.registry.getInstructionClass(instruction)

    if not instructionType: raise CSILParseError(f'Unknown instruction "{instruction}"')
    
    try:
        return instructionType(*args)
    except TypeError: # probably invalid num of arguments
        raise CSILParseError("Invalid number of arguments")
    
def parseSource(text):
    broadcasts = []
    lines = text.split("\n")
    i = 0

    currBroadcastBody = []
    currBroadcastName = None

    while i < len(lines):
        line = lines[i]
        line = _removeComments(line).strip()

        if line == "":
            i+=1
            continue
        if line.endswith(":"):
            assert line.startswith("broadcast"), CSILParseError("Unknown label definition type")

            parts = _split(line, " ")
            bname = parts[1]
            currBroadcastName = bname

            if currBroadcastBody:
                # parse previous lines into a new broadcast object
                b = Broadcast(currBroadcastName)
                for l in currBroadcastBody:
                    b.body.append(parseInstruction(l))
                broadcasts.append(b)
                currBroadcastBody = []
                currBroadcastName = None
        else:
            currBroadcastBody.append(line)
        i+=1

    # load parsed broadcasts into a CSIL Program instance
    prgm = CSILProgram()
    prgm.broadcasts = broadcasts

    return prgm