"""Stable category grouping shared by HTML navigation and workbook renderers."""


def category_groups(items):
    """Group by first category occurrence, retaining original item indices as anchors."""
    grouped = {}
    for index, item in enumerate(items):
        grouped.setdefault(item.category or "UNCATEGORISED", []).append((index, item))
    return tuple((category, tuple(values)) for category, values in grouped.items())
