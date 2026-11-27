"""Shared estimate metadata defaults; optional project JSON preserves legacy files."""

import json

from ..validation import text
from .logo import logo_data

KEY = "project_estimate_fields"
FACING_FIELDS = ("title", "organization", "reference", "office")
TITLES = {
    "abstract": "Abstract of estimate",
    "schedule": "Schedule",
    "signoff": "Signoff",
    "analyses": "Analyses of rates",
    "resources": "Resources",
    "resource_usage": "Resource usage",
    "measurement_abstract": "Measurement abstract",
    "measurements": "Measurements",
    "narrative": "Notes",
}


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
        office="",
        logo="",
        signoff_intro="",
        headings=TITLES.copy(),
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
    """Allow six pages and retain compatibility with long existing source pages."""
    if not isinstance(value, str) or len(value) > 120005:
        raise ValueError("Use up to six notes pages and 120005 characters")
    pages = value.split("\f")
    if len(pages) > 6 or any(len(page) > 60000 for page in pages):
        raise ValueError("Use up to six notes pages with at most 60000 characters per page")
    return value


def validate(value, *, project=False):
    """Normalize program/project metadata with backward-compatible missing fields."""
    base = defaults()
    if not isinstance(value, dict) or set(value) - set(base) - {"issue_date"}:
        raise ValueError("Invalid estimate defaults")
    base.update({key: value[key] for key in base if key in value})
    for key in (*FACING_FIELDS, "signoff_intro"):
        base[key] = text(base[key])
    base["notes"] = notes(base["notes"])
    base["logo"] = logo_data(base["logo"])
    headings = base["headings"]
    if not isinstance(headings, dict) or set(headings) - set(TITLES):
        raise ValueError("Invalid default report headings")
    base["headings"] = {key: text(headings.get(key, title)) for key, title in TITLES.items()}
    if project:
        base["issue_date"] = text(value.get("issue_date", ""))
    base["signoff_blocks"] = blocks(base["signoff_blocks"])
    return base


def project_values(db, fallback=None):
    """Read optional values; never overwrite unreadable future/foreign project data."""
    base = validate(fallback or {}, project=True)
    raw = db.get_project_settings().get(KEY)
    if raw is not None:
        try:
            base = validate(json.loads(raw), project=True)
        except (ValueError, TypeError, RecursionError):
            pass
    return base


def default_specification(db, fallback=None):
    """Compose metadata and initial section order from accepted project values."""
    values = project_values(db, fallback)
    order = (
        "narrative",
        "abstract",
        "schedule",
        "signoff",
        "analyses",
        "resources",
        "resource_usage",
        "measurement_abstract",
        "measurements",
    )
    sections = []
    for kind in order:
        section = dict(
            id=kind, kind=kind, title=values["headings"][kind], enabled=kind in ("abstract", "schedule", "signoff")
        )
        if kind == "narrative":
            section.update(body=values["notes"], enabled=bool(values["notes"].strip()))
        if kind == "signoff":
            section.update(
                new_page=False, signoff_blocks=values["signoff_blocks"], signoff_intro=values["signoff_intro"]
            )
        sections.append(section)
    return dict(
        schema_version=1,
        sections=sections,
        **{key: values[key] for key in (*FACING_FIELDS, "issue_date", "logo")},
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
            settings[KEY] = json.dumps(validate(value, project=True), ensure_ascii=False)
        elif key == "project_metadata":
            if not isinstance(value, str) or len(value) > 100000:
                raise ValueError("Database notes must be text of at most 100,000 characters")
            settings[key] = value
        else:
            settings[key] = text(value)
    db.set_project_settings(settings)
