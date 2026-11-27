"""Report snapshots/exports and saved definitions; Service retains revision/draft guards."""

from pathlib import Path

from ..persistence import export_output
from ..validation import text
from . import export_jobs, settings
from .document import build_document
from .html import render_html
from .pdf import find_renderer, render_pdf
from .regional import NumberFormat
from .specification import ReportSpec
from .workbook import write_workbook


def capture(service, params):
    """Validate a report request and capture only accepted working-project data."""
    if service.db is None:
        raise ValueError("Open a project first")
    revision = params.get("revision")
    if type(revision) is not int or revision != service.revision:
        raise ValueError("Stale report request; refresh the view")
    # A report must never silently apply, discard or omit a pending draft.
    service.guard_draft({})
    specification = ReportSpec.parse(params.get("specification", {}))
    return build_document(service.db, revision, specification)


def document(service, params):
    """Return detached JSON report data through the desktop boundary."""
    return capture(service, params).to_dict()


def preview(service, params):
    """Return fixed-layout offline HTML plus the captured revision and definition."""
    snapshot = capture(service, params)
    return dict(
        document=snapshot.to_dict(),
        html=render_html(snapshot, NumberFormat.parse(params.get("number_format"))),
        pdf_available=find_renderer() is not None,
    )


def export(service, params, progress):
    """Render a fresh revision-checked snapshot and publish through the export boundary."""
    arguments = _export_arguments(service, params)
    progress("Rendering report")
    return _render_export(*arguments)


def start_export(service, params):
    """Release the project owner and desktop bridge while the worker renders."""
    return export_jobs.start(_render_export, *_export_arguments(service, params))


def _export_arguments(service, params):
    """Only immutable values cross the thread boundary."""
    snapshot = capture(service, params)
    format = params.get("format")
    if format not in ("html", "xlsx", "pdf"):
        raise ValueError("Choose HTML, Excel or PDF report output")
    destination = Path(text(params.get("path"))).resolve()
    if destination.suffix.lower() != f".{format}":
        raise ValueError(f"Choose a .{format} report filename")
    return (
        snapshot,
        format,
        destination,
        params.get("replace_selected") is True,
        NumberFormat.parse(params.get("number_format")),
    )


def _render_export(snapshot, format, destination, replace_selected, number_format):
    """Publish an immutable snapshot without accessing the project database."""
    warnings = []
    # Complete text/PDF rendering before opening the final destination. Workbook
    # failures are cleaned up by the same existing publication context manager.
    output = None
    if format in ("html", "pdf"):
        html = render_html(snapshot, number_format)
        if format == "pdf":
            renderer = find_renderer()
            if renderer is None:
                raise ValueError("PDF export requires an installed WeasyPrint 70 or newer renderer")
            output, diagnostics = render_pdf(html, renderer)
            if diagnostics:
                warnings.append(diagnostics)
        else:
            output = html.encode("utf-8")
    with export_output(destination, replace_selected) as target:
        if format == "xlsx":
            write_workbook(snapshot, target)
        else:
            target.write_bytes(output)
    return dict(saved=str(destination), revision=snapshot.revision, warnings=warnings)
