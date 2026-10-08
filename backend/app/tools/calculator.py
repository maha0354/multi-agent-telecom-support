"""Arithmetic for the analyst, evaluated from a parsed AST so no arbitrary code can run."""

import ast
import operator

_BINARY_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}
_UNARY_OPS = {ast.USub: operator.neg, ast.UAdd: operator.pos}
_FUNCTIONS = {"min": min, "max": max, "round": round}
_MAX_EXPRESSION_LENGTH = 200


class CalculationError(ValueError):
    pass


def _evaluate(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _evaluate(node.body)
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPS:
        return _BINARY_OPS[type(node.op)](_evaluate(node.left), _evaluate(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_evaluate(node.operand))
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _FUNCTIONS
        and not node.keywords
    ):
        return _FUNCTIONS[node.func.id](*(_evaluate(arg) for arg in node.args))
    raise CalculationError(f"Unsupported element in expression: {ast.dump(node)[:60]}")


def calculate(expression: str) -> dict:
    """Evaluate an arithmetic expression using + - * / ( ) and min, max, round."""
    if len(expression) > _MAX_EXPRESSION_LENGTH:
        return {"expression": expression, "error": "Expression too long"}
    try:
        result = _evaluate(ast.parse(expression, mode="eval"))
    except ZeroDivisionError:
        return {"expression": expression, "error": "Division by zero"}
    except (SyntaxError, CalculationError, TypeError) as exc:
        return {"expression": expression, "error": str(exc)}
    return {"expression": expression, "result": round(result, 2)}
