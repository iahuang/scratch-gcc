import sys

from pycparser import c_parser

text = r"""
typedef int var;
typedef int list;

var a = a+3;

var bruh(void)
{
    ooga.append(1);
    ooga[0] = 1;
}
"""

if __name__ == '__main__':
    parser = c_parser.CParser()
    ast = parser.parse(text)
    print("Before:")
    ast.show(offset=2)

    print(ast.ext[0].body)
    assign = ast.ext[0].body.block_items[0]
    assign.lvalue.name = "y"
    assign.rvalue.value = 2

    print("After:")
    #ast.show(offset=2)