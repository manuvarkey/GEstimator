"""Bounded arithmetic entry without executing Python code or using binary floats."""

import ast
from decimal import Decimal, InvalidOperation, localcontext


def decimal(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        raise ValueError(
            "Enter a decimal or arithmetic expression (maximum 200 characters)"
        )
    try:
        tree = ast.parse(value.strip(), mode="eval")
        if sum(1 for _ in ast.walk(tree)) > 64:
            raise ValueError("Expression is too complex")

        def evaluate(node):
            if isinstance(node, ast.Constant) and type(node.value) in (int, float):
                return Decimal(
                    ast.get_source_segment(value.strip(), node).replace("_", "")
                )
            if isinstance(node, ast.UnaryOp) and isinstance(
                node.op, (ast.UAdd, ast.USub)
            ):
                result = evaluate(node.operand)
                return result if isinstance(node.op, ast.UAdd) else -result
            if isinstance(node, ast.BinOp):
                left, right = evaluate(node.left), evaluate(node.right)
                if isinstance(node.op, ast.Add):
                    return left + right
                if isinstance(node.op, ast.Sub):
                    return left - right
                if isinstance(node.op, ast.Mult):
                    return left * right
                if isinstance(node.op, ast.Div):
                    return left / right
                if (
                    isinstance(node.op, ast.Pow)
                    and abs(right) <= 12
                    and right == int(right)
                ):
                    return left ** int(right)
            raise ValueError(
                "Use numbers, parentheses and +, -, *, / or integer powers only"
            )

        with localcontext() as context:
            context.prec = 40
            result = evaluate(tree.body)
        if not result.is_finite() or abs(result) > Decimal("1e12"):
            raise ValueError("Number outside supported range")
        # Literal inputs retain decimal precision; arithmetic entries follow GTK's six-place entry rounding.
        if any(isinstance(n, ast.BinOp) for n in ast.walk(tree)):
            result = round(result, 6)
        if result.as_tuple().exponent < -12:
            raise ValueError("Number has too many decimal places")
        return result
    except (
        SyntaxError,
        InvalidOperation,
        ArithmeticError,
        OverflowError,
        RecursionError,
    ) as exc:
        raise ValueError("Invalid numeric expression") from exc


def tax_text(value):
    """Tax percentage rounded to four places, shown without padding zeros (18, 2.5, 1.2345)."""
    from estimator.data.schedule import Currency

    text = str(Currency(value or 0, 4))
    return text.rstrip("0").rstrip(".") if "." in text else text
