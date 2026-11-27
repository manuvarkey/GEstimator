"""Shared estimate metadata defaults; optional project JSON preserves legacy files."""

import json

from ..validation import text

KEY = "project_estimate_fields"
TEXT_FIELDS = ("title", "organization", "reference", "issue_date", "notes")


def signoff_defaults():
    """Return independent editable signature blocks."""
    return [
        dict(caption=caption, body="Name:\nDesignation:\nDate:")
        for caption in ("Prepared by", "Checked by", "Approved by")
    ]


def defaults():
    """Shipped values for new estimates, not a second calculation model."""
    return dict(
        title="Detailed estimate",
        organization="",
        reference="",
        issue_date="",
        notes="",
        signoff_blocks=signoff_defaults(),
    )


def blocks(value):
    """Bound editable captions and body text without interpreting markup."""
    if not isinstance(value, list) or not 1 <= len(value) <= 6:
        raise ValueError("Use one to six signoff blocks")
    result = []
    for block in value:
        if not isinstance(block, dict) or set(block) != {"caption", "body"}:
            raise ValueError("Invalid signoff block")
        result.append(dict(caption=text(block["caption"]), body=text(block["body"])))
    return result


def notes(value):
    """Allow up to three separately authored pages, separated by form feed."""
    if not isinstance(value, str) or len(value) > 60000 or len(value.split("\f")) > 3:
        raise ValueError("Use up to three notes pages and 60000 characters")
    return value


def validate(value):
    """Normalize program/project metadata with backward-compatible missing fields."""
    base = defaults()
    if not isinstance(value, dict) or set(value) - set(base):
        raise ValueError("Invalid estimate defaults")
    base.update(value)
    for key in TEXT_FIELDS:
        base[key] = notes(base[key]) if key == "notes" else text(base[key])
    base["signoff_blocks"] = blocks(base["signoff_blocks"])
    return base


def project_values(db, fallback=None):
    """Read optional values; never overwrite unreadable future/foreign project data."""
    base = validate(fallback or {})
    raw = db.get_project_settings().get(KEY)
    if raw is not None:
        try:
            base = validate(json.loads(raw))
        except (ValueError, TypeError, RecursionError):
            pass
    return base


def default_specification(db, fallback=None):
    """Compose metadata and initial section order from accepted project values."""
    values = project_values(db, fallback)
    # The specification parser reuses our field validators; defer this reverse import.
    from .specification import TITLES

    order = ("narrative", "abstract", "schedule", "signoff", "analyses", "resources", "resource_usage", "measurements")
    sections = []
    for kind in order:
        section = dict(id=kind, kind=kind, title=TITLES[kind], enabled=kind in ("abstract", "schedule", "signoff"))
        if kind == "narrative":
            section.update(body=values["notes"], enabled=bool(values["notes"].strip()))
        if kind == "signoff":
            section.update(new_page=False, signoff_blocks=values["signoff_blocks"])
        sections.append(section)
    return dict(
        schema_version=1,
        sections=sections,
        **{key: values[key] for key in TEXT_FIELDS if key != "notes"},
        font_family="",
        font_scale=1,
    )


def project_settings(db):
    """Expose metadata through the existing project settings read."""
    settings = db.get_project_settings()
    result = {
        key: settings.get(key, "")
        for key in ("project_name", "project_item_code", "project_resource_code", "project_metadata")
    }
    result["estimate"] = project_values(db) if KEY in settings else None
    return result


def update_project(db, changes):
    """Validate the whole edit before the existing ProjectEditor transaction writes it."""
    allowed = {"project_name", "project_item_code", "project_resource_code", "project_metadata", "estimate"}
    if not isinstance(changes, dict) or set(changes) - allowed:
        raise ValueError("Invalid project setting")
    settings = db.get_project_settings()
    for key, value in changes.items():
        if key == "estimate":
            settings[KEY] = json.dumps(validate(value), ensure_ascii=False)
        elif key == "project_metadata":
            if not isinstance(value, str) or len(value) > 100000:
                raise ValueError("Database notes must be text of at most 100,000 characters")
            settings[key] = value
        else:
            settings[key] = text(value)
    db.set_project_settings(settings)
