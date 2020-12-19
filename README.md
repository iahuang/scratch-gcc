# scratch-gcc

*The world's first (as far as I can tell) C/C++ to Scratch compiler*

### How:
1. Compile C program to MIPS assembly using `mips-linux-gnu-gcc` (you may need to install this first)
2. Assemble assembly program into a simplified binary format
3. Load binary into a Scratch file containing a MIPS assembly VM
