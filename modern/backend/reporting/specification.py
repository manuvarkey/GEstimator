"""Strict, immutable specification for the initial estimate report sections."""

import re
from dataclasses import dataclass

from ..validation import text
from .estimate_fields import blocks, notes, signoff_defaults
from .tables import parse_columns


@dataclass(frozen=True)
class SignoffBlock:
    """Editable literal caption and signature text."""

    caption: str
    body: str


TITLES = {
    "abstract": "Abstract of estimate",
    "schedule": "Schedule",
    "signoff": "Signoff",
    "analyses": "Analyses of rates",
    "resources": "Resources",
    "resource_usage": "Resource usage",
    "measurements": "Measurements",
    "narrative": "Notes",
}


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
    body: str = ""
    columns: tuple[str, ...] | None = None
    orientation: str = "auto"

    new_page: bool = True
    each_item_page: bool = False
    show_name_of_work: bool = False
    signoff_blocks: tuple[SignoffBlock, ...] = ()

    @classmethod
    def parse(cls, value):
        """Accept only initial supported section kinds and safe anchor identities."""
        _fields(
            value,
            (
                "id",
                "kind",
                "title",
                "enabled",
                "body",
                "columns",
                "orientation",
                "new_page",
                "each_item_page",
                "show_name_of_work",
                "signoff_blocks",
            ),
            "report section",
        )
        identity = value.get("id")
        kind = value.get("kind")
        if not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", identity):
            raise ValueError("Invalid report section ID")
        if not isinstance(kind, str) or kind not in TITLES:
            raise ValueError("Unsupported report section")
        enabled = value.get("enabled", True)
        if type(enabled) is not bool:
            raise ValueError("Invalid report section enabled state")
        body = notes(value.get("body", ""))
        if body and kind != "narrative":
            raise ValueError("Only narrative sections accept body text")
        columns = parse_columns(kind, value.get("columns"))
        orientation = value.get("orientation", "auto")
        if not isinstance(orientation, str) or orientation not in ("auto", "portrait", "landscape"):
            raise ValueError("Unsupported report page orientation")
        options = [
            value.get("new_page", kind != "signoff"),
            value.get("each_item_page", False),
            value.get("show_name_of_work", False),
        ]
        if any(type(option) is not bool for option in options):
            raise ValueError("Invalid report pagination option")
        if options[1] and kind not in ("analyses", "measurements"):
            raise ValueError("Per-item pages apply to analyses and measurements")
        if options[2] and kind not in ("abstract", "schedule"):
            raise ValueError("Name of work applies to abstract and schedule")
        raw_blocks = value.get("signoff_blocks")
        if raw_blocks not in (None, []) and kind != "signoff":
            raise ValueError("Only signoff sections accept signature blocks")
        signatures = (
            tuple(
                SignoffBlock(**block) for block in blocks(raw_blocks if raw_blocks is not None else signoff_defaults())
            )
            if kind == "signoff"
            else ()
        )
        return cls(
            identity,
            kind,
            text(value.get("title", TITLES[kind])),
            enabled,
            body,
            columns,
            orientation,
            *options,
            signatures,
        )


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
    font_family: str = ""
    font_scale: float = 1.0

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
                "font_family",
                "font_scale",
            ),
            "report specification",
        )
        version = value.get("schema_version", 1)
        if type(version) is not int or version != 1:
            raise ValueError("Unsupported report specification version")
        raw = value.get("sections", [dict(id=kind, kind=kind) for kind in ("abstract", "schedule", "signoff")])
        if not isinstance(raw, list) or len(raw) > 20:
            raise ValueError("Choose up to 20 report sections")
        sections = tuple(Section.parse(section) for section in raw)
        if len({section.id for section in sections}) != len(sections):
            raise ValueError("Duplicate report section ID")
        family = value.get("font_family", "")
        if not isinstance(family, str) or len(family) > 200 or any(ord(char) < 32 for char in family):
            raise ValueError("Invalid report font family")
        scale = value.get("font_scale", 1.0)
        if type(scale) not in (int, float) or not 0.6 <= scale <= 2:
            raise ValueError("Choose a report font scale between 60% and 200%")
        return cls(
            sections,
            _identities(value.get("item_ids")),
            _identities(value.get("category_ids")),
            text(value.get("title", "Detailed estimate")),
            text(value.get("organization", "")),
            text(value.get("reference", "")),
            text(value.get("issue_date", "")),
            family.strip(),
            float(scale),
        )
