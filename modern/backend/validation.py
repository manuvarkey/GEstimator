"""Shared validation for project and analysis requests."""

from typing import Any

MAX_TEXT_LENGTH = 10000


def text(value, *, error="Invalid text"):
    if not isinstance(value, str) or len(value) > MAX_TEXT_LENGTH:
        raise ValueError(error)
    return value


def request_text(value: Any) -> str:
    """Validate command text with its existing transport error message."""
    return text(value, error=f"Expected text of at most {MAX_TEXT_LENGTH} characters")
