"""
CScratch Intermediate Language

An extremely simple assembly-like language that compiles to Scratch.
There are no registers in a traditional sense, instructions manipulate Scratch variables directly in place of registers. Due to the dynamic nature of Scratch, registers can technically hold any type of data, including integers, strings, and floats.
CSIL code is not represented in program memory, and there are no opcodes. Instead instructions are represented directly through Scratch blocks, and control flow is directed by use of broadcasts. This means that the program itself cannot arbitrarily jump to different parts of the program.


Current Specification

https://docs.google.com/document/d/1qnO-grzpq-OGZvvym4R8JGqC_dIo9-sqCrF-uoIeZIA

█████████████████████████████████████████████
█████████████████████████████████████████████
████ ▄▄▄▄▄ █▄▄▄ ▀   █   █ ▀█▀█▄█▄█ ▄▄▄▄▄ ████
████ █   █ ██▄▀ █▄ ▀█▀█▄█ ▄▄█ ▄▄██ █   █ ████
████ █▄▄▄█ ██▀▄ ▄ ▀▄█▄▀▄▀█ ▀▀█ █ █ █▄▄▄█ ████
████▄▄▄▄▄▄▄█ ▀▄█ █ █▄█ █ █ ▀ ▀ ▀ █▄▄▄▄▄▄▄████
████▄▄█▄▄▀▄▀▀▄▀█▄▄ ▄▄█▀ ▄▀▀▄█▀▀▀▄█▄▀▀██▀▄████
████▄▄ ▀▀ ▄▄██ █▄█ ▀█▀▀█▀▄▄▄█▄▀▄▄█ ▀ ▄ ▄▄████
████ ▄▀▀ ▄▄▄ ▀ █▀▄▄██▀ █ █ ▄▄▀▄  ▄▄▄▀ ▀ ▄████
████▀█ █ █▄ █▄██▀▀ ▄▀██▄ ▄▀▀█▄█▄█▄█▀ █▀▄ ████
████▄ █▄▀ ▄▀▀██ ▄██▄█▀█ █▄▄▀▄▄▀▀█▀▄▀█ ▄▄▄████
████▄▀▀█▀▀▄█▄▄▀▀▄ ▄▀ ▄█▄██▄▄█ ▄▄▀ ▄██▀██ ████
████ ██▀▄ ▄▄▄ █▄▀ ██▀ ▀▀█▀▄  ▀  █▄▄   ▀ ▄████
████▄▀▀▀▄ ▄█  █ ▀ █▄ ▀███▄▀ ▀▄█  ██ ▀ ▀▀ ████
████▀ ▀▀█▀▄▀██▀▄▄ ▀▄  ▀▀▄ █ █▄▀  █▄▄▀ ▀▀▄████
████ ▄▀ █▀▄▄ █▀ ▄▄█▀▄█▄▄██ █ █▄ █ ▀▀ ▀▀▄ ████
████▄█▄▄▄▄▄█  ▀▀▀▀ █▀▀▀▀ ▄ ▄█ ▄█ ▄▄▄ ▄  █████
████ ▄▄▄▄▄ ██▀▀▄▀█▀▄█▄█▄██▀   █▀ █▄█ ▀█▀▄████
████ █   █ █ ▄██▄▄ ▄▄▀██▄██ ██ ▄ ▄ ▄▄█▀▄▀████
████ █▄▄▄█ █▀▀ █▄█ ▄ ▀ ▀█▄█▄ ▄▀██▄█▄ █ ▀ ████
████▄▄▄▄▄▄▄█▄▄███▄▄█▄▄█▄▄▄█▄████▄████▄██▄████
█████████████████████████████████████████████
█████████████████████████████████████████████
"""

from . import scratch
from .instructions import Instruction

class Broadcast:
    def __init__(self, name):
        self.name = name
        self.body: list[Instruction] = []

class CSILProgram:
    def __init__(self):
        self.broadcasts: list[Broadcast] = []
