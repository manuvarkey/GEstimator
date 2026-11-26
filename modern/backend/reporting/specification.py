"""Strict, immutable specification for the initial estimate report sections."""

import re
from dataclasses import dataclass

from ..validation import text

TITLES = {"abstract": "Abstract of estimate", "schedule": "Schedule", "signoff": "Signoff"}


def _fields(value, allowed, label):
    """Reject unsupported settings rather than silently producing a different report."""
    if not isinstance(value, dict) or set(value) - set(allowed):
        raise ValueError(f"Invalid {label} fields")


def _identities(value):
    """Keep None (all rows) distinct from an explicitly empty selection."""
    if value is None:
        return None
    if not isinstance(value, list) or len(value) > 10000:
        raise ValueError("Choose up to 10000 report row IDs")
    if any(not isinstance(identity, str) or not re.fullmatch(r"[1-9][0-9]{0,18}", identity) for identity in value):
        raise ValueError("Invalid report row ID")
    if len(set(value)) != len(value):
        raise ValueError("Duplicate report row ID")
    return tuple(value)


@dataclass(frozen=True)
class Section:
    """A stable section identity, independent of its display title and position."""

    id: str
    kind: str
    title: str
    enabled: bool

    @classmethod
    def parse(cls, value):
        """Accept only initial supported section kinds and safe anchor identities."""
        _fields(value, ("id", "kind", "title", "enabled"), "report section")
        identity = value.get("id")
        kind = value.get("kind")
        if not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", identity):
            raise ValueError("Invalid report section ID")
        if not isinstance(kind, str) or kind not in TITLES:
            raise ValueError("Unsupported report section")
        enabled = value.get("enabled", True)
        if type(enabled) is not bool:
            raise ValueError("Invalid report section enabled state")
        return cls(identity, kind, text(value.get("title", TITLES[kind])), enabled)


@dataclass(frozen=True)
class ReportSpec:
    """Version-one subset; selections apply to both schedule and abstract totals."""

    sections: tuple[Section, ...]
    item_ids: tuple[str, ...] | None = None
    category_ids: tuple[str, ...] | None = None
    title: str = "Detailed estimate"
    organization: str = ""
    reference: str = ""
    issue_date: str = ""

    @classmethod
    def parse(cls, value):
        """Validate JSON input without retaining mutable request-owned objects."""
        _fields(
            value,
            (
                "schema_version",
                "sections",
                "item_ids",
                "category_ids",
                "title",
                "organization",
                "reference",
                "issue_date",
            ),
            "report specification",
        )
        version = value.get("schema_version", 1)
        if type(version) is not int or version != 1:
            raise ValueError("Unsupported report specification version")
        raw = value.get("sections", [dict(id=kind, kind=kind) for kind in TITLES])
        if not isinstance(raw, list) or len(raw) > 20:
            raise ValueError("Choose up to 20 report sections")
        sections = tuple(Section.parse(section) for section in raw)
        if len({section.id for section in sections}) != len(sections):
            raise ValueError("Duplicate report section ID")
        return cls(
            sections,
            _identities(value.get("item_ids")),
            _identities(value.get("category_ids")),
            text(value.get("title", "Detailed estimate")),
            text(value.get("organization", "")),
            text(value.get("reference", "")),
            text(value.get("issue_date", "")),
        )
