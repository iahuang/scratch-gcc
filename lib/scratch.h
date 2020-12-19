/* Interfaces for interacting with the scratch-avr vm */

#pragma once

// Global variables so that the assembler knows where to put stuff
int _char_ptr;
char _print_buffer_char_addition;
int _memget_addr;
int _memget_result;

int _memget(int addr) {
    _memget_addr = addr;
    __asm__(".scratch memget");
    // to be interpreted by the scratch-avr assembler as:
    // get item [_memget_addr] of list "memory" and push to the address of the static memory label "_memget_result"
    return _memget_result;
}

void _add_to_print_buffer(char chr) {
    __asm__(".scratch add_to_print_buffer");
}

void print(char* str) {
    int addr = (unsigned int)str; // convert char pointer to address in memory

    while (1) {
        char next_char = _memget(addr);
        addr++;
        if (next_char == 0) { // if reached null character, stop
            return;
        }
        // otherwise add character to buffer
        _add_to_print_buffer(next_char);
    }   
}