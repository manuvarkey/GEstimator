"""Stable category grouping shared by HTML navigation and workbook renderers."""


def category_groups(items):
    """Group by first category occurrence, retaining original item indices as anchors."""
    grouped = {}
    labels = {}
    for index, item in enumerate(items):
        label = item.category or "UNCATEGORISED"
        identity = getattr(item, "category_id", label)
        labels.setdefault(identity, label)
        grouped.setdefault(identity, []).append((index, item))
    return tuple((labels[identity], tuple(values)) for identity, values in grouped.items())
