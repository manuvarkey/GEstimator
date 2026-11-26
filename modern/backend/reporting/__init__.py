"""Read-only report assembly; project revisions and drafts stay with Service."""

from .document import build_document
from .specification import ReportSpec


def document(service, params):
    """Validate a report request and capture only accepted working-project data."""
    if service.db is None:
        raise ValueError("Open a project first")
    revision = params.get("revision")
    if type(revision) is not int or revision != service.revision:
        raise ValueError("Stale report request; refresh the view")
    # A report must never silently apply, discard or omit a pending draft.
    service.guard_draft({})
    specification = ReportSpec.parse(params.get("specification", {}))
    return build_document(service.db, revision, specification).to_dict()
