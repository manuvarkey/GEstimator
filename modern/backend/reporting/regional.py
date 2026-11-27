"""Apply the desktop regional grouping profile without converting Decimal values to float."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class NumberFormat:
    """A bounded Intl grouping profile from the desktop's selected or system region."""

    group: str = ","
    decimal: str = "."
    primary: int = 3
    secondary: int = 3
    minimum: int = 4
    digits: str = "0123456789"

    @classmethod
    def parse(cls, value):
        """Validate all strings and grouping widths before rendering."""
        if value is None:
            return cls()
        if not isinstance(value, dict) or set(value) != {
            "group",
            "decimal",
            "primary",
            "secondary",
            "minimum",
            "digits",
        }:
            raise ValueError("Invalid report number format")
        if type(value["minimum"]) is not int or not 1 <= value["minimum"] <= 16:
            raise ValueError("Invalid report number grouping threshold")
        if any(type(value[key]) is not int or not 1 <= value[key] <= 8 for key in ("primary", "secondary")):
            raise ValueError("Invalid report number grouping")
        if any(not isinstance(value[key], str) or not 1 <= len(value[key]) <= 4 for key in ("group", "decimal")):
            raise ValueError("Invalid report number separator")
        digits = value["digits"]
        if not isinstance(digits, str) or len(digits) != 10 or len(set(digits)) != 10 or not digits.isdecimal():
            raise ValueError("Invalid report digits")
        return cls(**value)

    def format(self, value):
        """Group integers by the locale pattern while retaining captured precision."""
        if value in (None, ""):
            return ""
        whole, dot, fraction = format(Decimal(value), "f").partition(".")
        sign = "-" if whole.startswith("-") else ""
        whole = whole.removeprefix("-")
        if len(whole) >= self.minimum:
            width = self.primary
            groups = []
            while len(whole) > width:
                groups.append(whole[-width:])
                whole = whole[:-width]
                width = self.secondary
            whole = self.group.join((whole, *reversed(groups)))
        return (sign + whole + (self.decimal + fraction if dot else "")).translate(
            str.maketrans("0123456789", self.digits)
        )
