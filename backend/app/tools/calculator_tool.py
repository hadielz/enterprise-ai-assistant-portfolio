"""
Calculator tool.

This is a simple enterprise tool used when the assistant
needs to calculate something.
"""

import ast
import operator


_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}


def _eval(node):
    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.BinOp):
        left = _eval(node.left)
        right = _eval(node.right)
        op = _ALLOWED_OPERATORS[type(node.op)]
        return op(left, right)

    raise ValueError("Unsupported calculation")


def calculate(expression: str) -> str:
    """
    Safely evaluate a simple arithmetic expression.
    """

    tree = ast.parse(expression, mode="eval")
    result = _eval(tree.body)

    return f"The result of {expression} is {result}."