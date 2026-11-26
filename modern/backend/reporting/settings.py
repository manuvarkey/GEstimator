"""Optional project report definitions, using the existing project undo/save boundary."""

import json
from dataclasses import asdict

from .specification import ReportSpec

KEY = "project_report_specification"
MAX_BYTES = 1_000_000


def _check(service, params):
    """Reject writes/reads for a replaced project or stale revision."""
    if service.db is None:
        raise ValueError("Open a project first")
    revision = params.get("revision")
    if type(revision) is not int or revision != service.revision:
        raise ValueError("Stale report settings; refresh the view")


def _encode(specification):
    """Normalize a versioned definition without retaining mutable request values."""
    if specification.item_ids is not None or specification.category_ids is not None:
        # SQL keys can be reused after deletion. Persist selections only after
        # their invalidation lifecycle is implemented alongside project edits.
        raise ValueError("Save report settings without item or category filters")
    value = asdict(specification)
    value["schema_version"] = 1
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Report settings exceed the 1 MB limit")
    return encoded


def read(service, params):
    """Ignore invalid optional definitions visibly, preserving their original bytes.

    Reading settings does not inspect analysis/measurement data, activate drafts,
    or change project state. Future definitions survive ordinary open/save cycles.
    """
    _check(service, params)
    raw = service.db.get_project_settings().get(KEY)
    specification, warning = None, ""
    if raw is not None:
        try:
            if not isinstance(raw, str):
                raise ValueError("Invalid report settings text")
            if len(raw.encode("utf-8")) > MAX_BYTES:
                raise ValueError("Report settings exceed the 1 MB limit")
            specification = json.loads(_encode(ReportSpec.parse(json.loads(raw))))
        except (ValueError, TypeError, RecursionError):
            warning = "Saved report settings cannot be read by this version. They remain unchanged until you apply new settings."
    return dict(specification=specification, warning=warning, revision=service.revision)


def apply(service, params):
    """Apply validated settings as one project edit; saving the file is separate."""
    _check(service, params)
    service.guard_draft({})
    encoded = _encode(ReportSpec.parse(params.get("specification")))
    if service.db.get_project_settings().get(KEY) != encoded:

        def update():
            settings = service.db.get_project_settings()
            settings[KEY] = encoded
            service.db.set_project_settings(settings)

        service.project_editor.mutate(update)
    return dict(specification=json.loads(encoded), warning="", revision=service.revision)
