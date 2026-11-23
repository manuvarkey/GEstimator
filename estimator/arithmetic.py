"""Bounded mathematical expressions for measurements and Decimal numeric entry.

Only named constants and explicitly listed functions are callable. Both numeric
modes share syntax and limits; measurement templates retain integer/float results.
"""

import ast
import math
import operator
from decimal import Decimal

_BINARY = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_FUNCTIONS = {
    name: getattr(math, name)
    for name in (
        "sqrt",
        "cbrt",
        "ceil",
        "floor",
        "trunc",
        "sin",
        "cos",
        "tan",
        "asin",
        "acos",
        "atan",
        "exp",
        "log",
        "log10",
        "degrees",
        "radians",
    )
}
_FUNCTION_NAMES = frozenset(_FUNCTIONS) | {"abs", "max", "min", "round"}
_DECIMAL_CONSTANTS = {
    "pi": Decimal("3.141592653589793238462643383279502884197"),
    "e": Decimal("2.718281828459045235360287471352662497757"),
}


class NumericExpression:
    """Parse once, then evaluate with template numbers or the caller's Decimal context."""

    def __init__(self, source):
        if not isinstance(source, str) or not source.strip() or len(source) > 200:
            raise ValueError("Enter a numeric expression of at most 200 characters")
        self.source = source.strip()
        try:
            self.tree = ast.parse(self.source, mode="eval")
        except (SyntaxError, RecursionError) as exc:
            raise ValueError("Invalid numeric expression") from exc
        nodes = list(ast.walk(self.tree))
        if len(nodes) > 64:
            raise ValueError("Expression is too complex")
        # Plain literals retain their precision; computed entries use entry rounding.
        self.computed = any(isinstance(node, (ast.BinOp, ast.Call, ast.Name)) for node in nodes)

    def evaluate(self, *, decimal_mode=False):
        """Evaluate only the allowed AST nodes; never execute source as Python code."""
        try:
            return _Evaluator(self.source, decimal_mode).evaluate(self.tree.body)
        except (ArithmeticError, TypeError, RecursionError) as exc:
            raise ValueError("Invalid numeric expression") from exc


class _Evaluator:
    def __init__(self, source, decimal_mode):
        self.source = source
        self.decimal_mode = decimal_mode
        self.constants = _DECIMAL_CONSTANTS if decimal_mode else {"pi": math.pi, "e": math.e}

    def checked(self, value):
        """Bound intermediate results as well as the final value."""
        if self.decimal_mode and type(value) in (int, float):
            value = Decimal(str(value))
        if type(value) not in (int, float, Decimal):
            raise ValueError("Invalid numeric expression: result must be real")
        finite = value.is_finite() if isinstance(value, Decimal) else math.isfinite(value)
        if not finite or abs(value) > 1e12:
            raise ValueError("Number outside supported range")
        return value

    def evaluate(self, node):
        # Step 1: resolve literals and the two constants without a Python namespace.
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            result = (
                Decimal(ast.get_source_segment(self.source, node).replace("_", "")) if self.decimal_mode else node.value
            )
        elif isinstance(node, ast.Name) and node.id in self.constants:
            result = self.constants[node.id]
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = self.evaluate(node.operand)
            result = value if isinstance(node.op, ast.UAdd) else -value
        # Step 2: evaluate bounded operands before applying an operator or named function.
        elif isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
            left, right = self.evaluate(node.left), self.evaluate(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 12:
                raise ValueError("Use powers between -12 and 12")
            # Decimal's // truncates; expression syntax uses Python's floor semantics.
            if self.decimal_mode and isinstance(node.op, (ast.FloorDiv, ast.Mod)):
                quotient = math.floor(self.checked(left / right))
                result = quotient if isinstance(node.op, ast.FloorDiv) else left - right * quotient
            else:
                result = _BINARY[type(node.op)](left, right)
        elif isinstance(node, ast.Call):
            result = self.call(node)
        else:
            raise ValueError("Invalid numeric expression: use numbers, pi, e and supported math functions")
        if isinstance(result, complex):
            raise ValueError("Invalid numeric expression: result must be real")
        return self.checked(result)

    def call(self, node):
        """Validate call syntax and argument counts before invoking a listed function."""
        if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCTION_NAMES or node.keywords:
            raise ValueError("Invalid numeric expression: unsupported function or call syntax")
        name = node.func.id
        count = len(node.args)
        if name in ("min", "max"):
            valid = count >= 1
        elif name in ("round", "log"):
            valid = count in (1, 2)
        else:
            valid = count == 1
        if not valid:
            raise ValueError("Invalid numeric expression: wrong number of arguments for " + name)
        args = [self.evaluate(arg) for arg in node.args]
        if name == "log" and (args[0] <= 0 or count == 2 and (args[1] <= 0 or args[1] == 1)):
            raise ValueError("Invalid numeric expression: log requires a positive value and valid base")
        if name in ("asin", "acos") and not -1 <= args[0] <= 1:
            raise ValueError("Invalid numeric expression: inverse sine and cosine require values between -1 and 1")
        if name == "round" and count == 2:
            if args[1] != int(args[1]) or abs(args[1]) > 12:
                raise ValueError("Invalid numeric expression: round digits must be an integer between -12 and 12")
            args[1] = int(args[1])
        try:
            if name == "abs":
                return abs(args[0])
            if name in ("min", "max"):
                return min(args) if name == "min" else max(args)
            if name == "round":
                return round(*args)
            if self.decimal_mode:
                return self.decimal_function(name, args)
            return _FUNCTIONS[name](*args)
        except ValueError as exc:
            raise ValueError("Invalid numeric expression: function argument outside its domain") from exc

    def decimal_function(self, name, args):
        """Keep exact Decimal operations where available; trig uses bounded math results."""
        value = args[0]
        if name == "sqrt":
            return value.sqrt()
        if name == "cbrt":
            return -((-value) ** (Decimal(1) / 3)) if value < 0 else value ** (Decimal(1) / 3)
        if name == "exp":
            return value.exp()
        if name == "log":
            return value.ln() if len(args) == 1 else value.ln() / args[1].ln()
        if name == "log10":
            return value.log10()
        if name == "degrees":
            return value * 180 / self.constants["pi"]
        if name == "radians":
            return value * self.constants["pi"] / 180
        return _FUNCTIONS[name](*args)


def evaluate_number(source):
    """Evaluate an expression with the integer/float semantics used by templates."""
    return NumericExpression(source).evaluate()
