#include <stdint.h>

char* __stdout_buffer = (char*)0x00000000;
void** __mem_end = (void**)0x00000004;
void** __stack_start = (void**)0x0000008;
uint8_t* __halt = (uint8_t*)0x0000000C;

void _write_char(char c) {
    *__stdout_buffer = c;
}

void println(char* string) {
    int i = 0;
    while (1) {
        char c = string[i];
        if (c==0) {
            _write_char('\n');
            return;
        }

        _write_char(c);
    }
}

void _halt() {
    *__halt = 1;
}

/* Very sophisticated heap algorithm */

uint8_t* heap_ptr = 0; // pointer to the next available space on the heap

void* malloc(unsigned int size) {
    // if heap_start variable hasn't been initialized, initialize it

    if (heap_ptr == 0) {
        // stack builds downwards so we can initialize the heap after the stack to grow upwards
        heap_ptr = (uint8_t*)(__stack_start + 1);
    }

    if (heap_ptr >= *(__mem_end)) {
        println("malloc error: out of memory");
        _halt();
    }
    void* new_allocated_space = heap_ptr;

    heap_ptr+=size;
    return new_allocated_space;
}

void free(void* ptr) {
    // get pranked it doesn't do anything, memory can't be reused KEKW
}
