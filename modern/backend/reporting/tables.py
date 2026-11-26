"""Fixed table columns shared by specification validation and document renderers."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Column:
    """A known immutable document field, never an author-supplied expression."""

    key: str
    title: str
    numeric: bool = False
    multiline: bool = False


COLUMNS = {
    "abstract": (Column("category", "Category"), Column("amount", "Amount", True)),
    "schedule": (
        Column("code", "Code"),
        Column("description", "Description", multiline=True),
        Column("unit", "Unit"),
        Column("quantity", "Quantity", True),
        Column("rate", "Rate", True),
        Column("amount", "Amount", True),
        Column("remarks", "Remarks", multiline=True),
    ),
    "resources": (
        Column("code", "Code"),
        Column("description", "Description", multiline=True),
        Column("unit", "Unit"),
        Column("rate", "Basic rate", True),
        Column("tax", "Tax %", True),
        Column("discount", "Discount %", True),
        Column("reference", "Reference"),
        Column("category", "Category"),
    ),
    "resource_usage": (
        Column("code", "Code"),
        Column("description", "Description", multiline=True),
        Column("unit", "Unit"),
        Column("quantity", "Quantity", True),
        Column("rate", "Adjusted rate", True),
        Column("amount", "Amount", True),
        Column("category", "Category"),
    ),
}


def parse_columns(kind, value):
    """Accept only a nonempty ordered subset; None retains renderer defaults."""
    if value is None:
        return None
    allowed = {column.key for column in COLUMNS.get(kind, ())}
    if not isinstance(value, list) or not value or len(value) > len(allowed):
        raise ValueError("Choose at least one supported report column")
    if any(not isinstance(key, str) or key not in allowed for key in value):
        raise ValueError("Unsupported report column")
    if len(set(value)) != len(value):
        raise ValueError("Duplicate report column")
    return tuple(value)


def table_values(document, section, *, excel=False):
    """Project accepted values in the chosen order without recalculating totals.

    Default HTML omits schedule remarks, while default Excel retains its existing
    remarks column. An explicit selection has the same columns in every format.
    """
    available = COLUMNS[section.kind]
    if section.columns is not None:
        by_key = {column.key: column for column in available}
        columns = tuple(by_key[key] for key in section.columns)
    else:
        columns = available[:-1] if section.kind == "schedule" and not excel else available
    rows = getattr(document, section.kind)
    values = []
    for row in rows:
        values.append(
            tuple(
                ""
                if section.kind == "schedule" and not row.unit and column.key in ("quantity", "rate", "amount")
                else getattr(row, column.key) or ""
                for column in columns
            )
        )
    return columns, values


# Relative space follows the meaning of the field, so hiding or moving a column
# redistributes the available page width without losing the description's share.
WIDTH_WEIGHTS = {
    "Code": 13,
    "Description": 48,
    "Unit": 10,
    "Quantity": 14,
    "Quantity / factor": 18,
    "Rate": 13,
    "Basic rate": 13,
    "Adjusted rate": 13,
    "Amount": 15,
    "Remarks": 24,
    "Category": 28,
    "Reference": 20,
    "Tax %": 8,
    "Discount %": 14,
    "Kind": 16,
    "Output": 20,
    "Property": 28,
    "Value": 48,
    "Notes": 80,
}


def column_widths(headings):
    """Return proportional percentages for known fields and variable template labels."""
    weights = [WIDTH_WEIGHTS.get(heading, 16) for heading in headings]
    total = sum(weights)
    return tuple(round(weight * 100 / total, 4) for weight in weights) if total else ()
