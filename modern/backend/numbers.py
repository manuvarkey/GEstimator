"""Bounded numeric entry with Decimal arithmetic and shared mathematical syntax."""

from decimal import localcontext

from estimator.arithmetic import NumericExpression


def decimal(value):
    """Retain literal precision and round computed entries to six decimal places."""
    # Step 1: share syntax and safety limits with stored measurement expressions.
    expression = NumericExpression(value)
    with localcontext() as context:
        context.prec = 40
        result = expression.evaluate(decimal_mode=True)
        # Step 2: round computed entries without changing literal precision rules.
        if expression.computed:
            result = round(result, 6)
    if result.as_tuple().exponent < -12:
        raise ValueError("Number has too many decimal places")
    return result


def tax_text(value):
    """Tax percentage rounded to four places, shown without padding zeros (18, 2.5, 1.2345)."""
    from estimator.data.schedule import Currency

    text = str(Currency(value or 0, 4))
    return text.rstrip("0").rstrip(".") if "." in text else text
