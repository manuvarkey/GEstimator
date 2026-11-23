"""Shared validation for project and analysis requests."""

from typing import Any


def text(value, *, error="Invalid text"):
    if not isinstance(value, str) or len(value) > 10000:
        raise ValueError(error)
    return value


def request_text(value: Any) -> str:
    """Validate command text with its existing transport error message."""
    return text(value, error="Expected text of at most 10000 characters")
