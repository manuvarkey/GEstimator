"""Shared validation for project editor input."""


def text(value):
    if not isinstance(value, str) or len(value) > 10000:
        raise ValueError("Invalid text")
    return value
