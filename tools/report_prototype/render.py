"""Offline report rendering experiment; no desktop commands or project writes.

Run from the repository root with ``python -m tools.report_prototype.render``.
Custom templates are explicitly selected, trusted local authoring inputs. Project
text is always passed as data, never used as template source.
"""

import argparse
import base64
import sys
from decimal import Decimal
from pathlib import Path

from jinja2 import FileSystemLoader, StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

from estimator.data.schedule import Currency

from .executable import render_pdf

TEMPLATES = Path(__file__).parent / "templates"
SECTIONS = ("abstract", "schedule", "signoff")


def context(rows, *, project, organization, logo=None, sections=SECTIONS):
    """Build an independent presentation context from already selected rows.

    Prototype rows have category, code, description, unit, quantity and rate.
    Decimal amounts retain the engine's per-item Currency rounding. An eventual
    project adapter must supply engine-selected payable rows, excluding headings
    and dependency-only subanalyses, rather than querying every schedule record.
    """
    if len(set(sections)) != len(sections) or any(section not in SECTIONS for section in sections):
        raise ValueError("Invalid or duplicate report section")
    totals = {}
    schedule = []
    for row in rows:
        amount = Currency(Decimal(row["quantity"]) * Decimal(row["rate"]))
        totals[row["category"]] = totals.get(row["category"], Decimal(0)) + amount
        schedule.append({**row, "amount": str(amount)})
    return dict(
        project=project,
        organization=organization,
        logo=logo,
        title="Detailed estimate",
        reference="DEMO / 2026 / 01",
        revision="P1 — demonstration",
        date="24 November 2026",
        sections=list(sections),
        schedule=schedule,
        abstract=[dict(category=category, amount=str(Currency(amount))) for category, amount in totals.items()],
        total=str(Currency(sum(totals.values(), Decimal(0)))),
        signatories=["Prepared by", "Checked by", "Approved by"],
    )


def logo_uri(path):
    """Embed an explicitly selected PNG/JPEG; no filesystem URLs in output."""
    path = Path(path)
    if path.stat().st_size > 2_000_000:
        raise ValueError("Logo exceeds 2 MB")
    data = path.read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "image/png"
    elif data.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    else:
        raise ValueError("Choose a PNG or JPEG logo")
    return f"data:{mime};base64," + base64.b64encode(data).decode("ascii")


def render_html(data, template_directory=TEMPLATES):
    """Render default or trusted custom facing/abstract templates with escaping."""
    environment = SandboxedEnvironment(
        loader=FileSystemLoader([str(Path(template_directory).resolve()), str(TEMPLATES.resolve())]),
        autoescape=True,
        undefined=StrictUndefined,
    )
    return environment.get_template("report.html").render(**data)


def sample_rows():
    """Provide deterministic multi-page data, including long and non-ASCII text."""
    return [
        dict(
            category="Civil works" if index < 26 else "Building services",
            code=f"{index + 1}.1",
            description=(
                "Supply and installation, including all fixings, testing and making good. "
                "Café wing — area measured in m². " + "Detailed specification and workmanship requirements. " * 4
            ),
            unit="m²",
            quantity="2.125",
            rate="123.45",
        )
        for index in range(52)
    ]


def main():
    """Write sample artifacts to a new directory, without replacing existing files."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--templates", type=Path, default=TEMPLATES)
    parser.add_argument("--logo", type=Path)
    parser.add_argument(
        "--executable", type=Path, help="Use a trusted WeasyPrint CLI executable instead of the library"
    )
    parser.add_argument("--timeout", type=float, default=60, help="CLI renderer deadline in seconds")
    parser.add_argument("--sections", nargs="*", choices=SECTIONS, default=list(SECTIONS))
    args = parser.parse_args()
    data = context(
        sample_rows(),
        project="Community building refurbishment",
        organization="Example Engineering Office",
        logo=logo_uri(args.logo) if args.logo else None,
        sections=args.sections,
    )
    # Step 1: complete both renders before publishing the experiment's outputs.
    html = render_html(data, args.templates)
    if args.executable:
        pdf, diagnostics = render_pdf(html, args.executable, args.timeout)
        if diagnostics:
            print(diagnostics, file=sys.stderr)
    else:
        # Loading native text libraries is unnecessary when using the executable.
        from .library import render_pdf as render_library_pdf

        pdf = render_library_pdf(html)
    # Step 2: require a fresh directory so existing reports cannot be overwritten.
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "estimate.html").write_text(html, encoding="utf-8")
    (args.output / "estimate.pdf").write_bytes(pdf)
    print(f"Generated {args.output}; total {data['total']}")


if __name__ == "__main__":
    main()
