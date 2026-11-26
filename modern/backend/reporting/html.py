"""Standalone, offline HTML from escaped report values and a fixed local layout."""

from html import escape

from .document import ReportDocument

# Keep the complete fixed layout here so frozen backends need no template assets.
# No project text is interpreted as template source, markup, CSS or script.
STYLE = """
@page { size:A4; margin:20mm 15mm;
 @top-left { content:"GEstimator · Estimate report"; font-size:8pt; }
 @top-right { content:string(section-heading); font-size:8pt; }
 @bottom-right { content:"Page " counter(page) " of " counter(pages); font-size:8pt; }
}
@page:first { @top-left { content:none; } @top-right { content:string(section-heading); font-size:8pt; }
 @bottom-right { content:none; } }
@page report-wide { size:A4 landscape; }
.wide { page:report-wide; }
.section > h1 { string-set:section-heading content(); }
h1,h2,h3 { break-after:avoid; }
.keep-together { break-inside:avoid; }
tbody tr:nth-child(even) { background:#f5f8fa; }
* { box-sizing:border-box; }
body { font:10pt/1.45 "DejaVu Sans",sans-serif; color:#243247; margin:0 auto; max-width:1100px; padding:24px; }
h1 { color:#174e67; font-size:22pt; } h2 { font-size:17pt; }
a { color:#174e67; } .cover { padding:60px 0; }
.section { break-before:page; margin-top:32px; }
table { border-collapse:collapse; width:100%; font-size:9pt; }
thead { display:table-header-group; }
th,td { border-bottom:1px solid #ccd6dc; padding:8px; text-align:left; vertical-align:top; overflow-wrap:anywhere; }
th { background:#e4eef2; overflow-wrap:normal; } tr { break-inside:avoid; }
.number { text-align:right; white-space:nowrap; overflow-wrap:normal; }
.description { white-space:pre-wrap; } .total { font-weight:bold; text-align:right; }
.signatures { display:flex; gap:24px; margin-top:60px; }
.signature { flex:1; border-top:1px solid; padding-top:8px; }
.toc a::after { content:""; }
@media print { .toc a::after { content:" … " target-counter(attr(href), page); } body { max-width:none; padding:0; } .cover { padding-top:22mm; } }
"""


def _text(value):
    """Escape a plain text value at the one HTML output boundary."""
    return escape(str(value), quote=True)


def _table(headings, rows, numeric=(), descriptions=(), widths=()):
    """Build accessible table markup without interpolating arbitrary attributes."""
    output = ["<table>"]
    if widths:
        output.append("<colgroup>" + "".join(f'<col style="width:{width}%">' for width in widths) + "</colgroup>")
    output.append("<thead><tr>")
    for index, label in enumerate(headings):
        css = "number" if index in numeric else ""
        output.append(f'<th scope="col" class="{css}">{_text(label)}</th>')
    output.append("</tr></thead><tbody>")
    for row in rows:
        output.append("<tr>")
        for index, value in enumerate(row):
            css = "number" if index in numeric else "description" if index in descriptions else ""
            output.append(f'<td class="{css}">{_text(value)}</td>')
        output.append("</tr>")
    output.append("</tbody></table>")
    return "".join(output)


def render_html(document: ReportDocument) -> str:
    """Render a fixed cover, linked contents and the enabled ordered sections."""
    spec = document.specification
    sections = [section for section in spec.sections if section.enabled]
    output = [
        '<!doctype html><html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; style-src 'unsafe-inline'\">",
        f"<title>{_text(spec.title)} — {_text(document.project)}</title><style>{STYLE}</style></head><body>",
        '<header class="cover">',
        f"<p>{_text(spec.organization)}</p><h1>{_text(spec.title)}</h1><h2>{_text(document.project)}</h2>",
        f"<p>Reference: {_text(spec.reference)}</p><p>Issued: {_text(spec.issue_date)}</p>",
        '</header><nav class="section" aria-label="Contents"><h1>Contents</h1><ol class=toc>',
    ]
    for section in sections:
        output.append(f'<li><a href="#{section.id}">{_text(section.title)}</a>')
        if section.kind == "analyses":
            output.append("<ul>")
            for index, analysis in enumerate(document.analyses):
                output.append(f'<li><a href="#{section.id}:analysis:{index}">{_text(analysis.code)}</a></li>')
            output.append("</ul>")
        output.append("</li>")
    output.append("</ol></nav>")
    # Each renderer consumes the same captured amounts; rendering never calculates.
    for section in sections:
        css = "section wide" if section.kind in ("resources", "resource_usage", "measurements") else "section"
        output.append(f'<section class="{css}" id="{section.id}"><h1>{_text(section.title)}</h1>')
        output.append(_section_body(document, section))
        output.append("</section>")
    output.append("</body></html>")
    html = "".join(output)
    if len(html.encode("utf-8")) > 10_000_000:
        raise ValueError("Report HTML exceeds the 10 MB limit; select fewer items")
    return html


def _analyses(document, section_id):
    """Keep per-item captions/remarks with their detailed engine-result tables."""
    output = []
    for index, analysis in enumerate(document.analyses):
        # Small analyses can stay together. Large blocks must be splittable so
        # a paginator does not push their first table onto an otherwise empty page.
        compact = (
            len(analysis.rows) <= 12 and sum(len(row.description) + len(row.remarks) for row in analysis.rows) <= 1600
        )
        css = "analysis-item keep-together" if compact else "analysis-item"
        output.append(f'<article class="{css}">')
        output.append(
            f'<h2 id="{section_id}:analysis:{index}">{_text(analysis.code)} — {_text(analysis.description)}</h2>'
        )
        output.append(f'<p class="description">{_text(analysis.remarks)}</p>')
        output.append(
            _table(
                ("Code", "Description", "Unit", "Quantity / factor", "Rate", "Amount"),
                [
                    (
                        row.code,
                        row.description + ("\n" + row.remarks if row.remarks else ""),
                        row.unit,
                        row.quantity,
                        row.rate,
                        row.amount,
                    )
                    for row in analysis.rows
                ],
                (3, 4, 5),
                (1,),
                widths=(8, 44, 8, 14, 13, 13),
            )
        )
        output.append(
            f'<p class="total">Stored schedule rate: {_text(analysis.stored_rate)} · '
            f"Calculated analysis rate: {_text(analysis.calculated_rate)}</p>"
        )
        output.append("</article>")
    return "".join(output)


def _section_body(document, section):
    """Render one dataset without extending the document shell."""
    output = []
    if section.kind == "abstract":
        output.append(_table(("Category", "Amount"), [(row.category, row.amount) for row in document.abstract], (1,)))
        output.append(f'<p class="total">Estimate total: {_text(document.total)}</p>')
    elif section.kind == "schedule":
        output.append(
            _table(
                ("Code", "Description", "Unit", "Quantity", "Rate", "Amount"),
                [
                    (
                        row.code,
                        row.description,
                        row.unit,
                        row.quantity if row.unit else "",
                        row.rate if row.unit else "",
                        row.amount or "",
                    )
                    for row in document.schedule
                ],
                (3, 4, 5),
                (1,),
            )
        )
        output.append(f'<p class="total">Estimate total: {_text(document.total)}</p>')
    elif section.kind == "analyses":
        output.append(_analyses(document, section.id))
    elif section.kind == "narrative":
        output.append(f'<p class="description">{_text(section.body)}</p>')
    elif section.kind == "measurements":
        output.append(_measurements(document))
    elif section.kind == "resources":
        output.append(
            _table(
                ("Code", "Description", "Unit", "Basic rate", "Tax %", "Discount %", "Reference", "Category"),
                [
                    (row.code, row.description, row.unit, row.rate, row.tax, row.discount, row.reference, row.category)
                    for row in document.resources
                ],
                (3, 4, 5),
                (1,),
            )
        )
    elif section.kind == "resource_usage":
        output.append(
            "<p>Direct resource usage for selected schedule items; dependency resources are not expanded.</p>"
        )
        output.append(
            _table(
                ("Code", "Description", "Unit", "Quantity", "Adjusted rate", "Amount", "Category"),
                [
                    (row.code, row.description, row.unit, row.quantity, row.rate, row.amount, row.category)
                    for row in document.resource_usage
                ],
                (3, 4, 5),
                (1,),
            )
        )
    else:
        output.append('<div class="signatures">')
        for role in ("Prepared by", "Checked by", "Approved by"):
            output.append(f'<div class="signature"><p>{role}</p><p>Name:</p><p>Designation:</p><p>Date:</p></div>')
        output.append("</div>")
    return "".join(output)


def _measurements(document):
    """Render template records and each independent output with its link and unit."""
    output = ["<p>Complete measurement sheets; totals are separate template outputs, not schedule quantities.</p>"]
    for sheet in document.measurements:
        compact = (
            len(sheet.records) + len(sheet.outputs) <= 15
            and sum(len(value) for record in sheet.records for value in record) <= 1600
        )
        output.append('<article class="keep-together">' if compact else "<article>")
        output.append(f"<h2>{sheet.number}. {_text(sheet.description or sheet.template)}</h2>")
        output.append(f"<p>{_text(sheet.category)} · {_text(sheet.template)}</p>")
        output.append(_table(sheet.columns, sheet.records, descriptions=tuple(range(len(sheet.columns)))))
        if sheet.properties:
            output.append(_table(("Property", "Value"), sheet.properties))
        output.append(
            _table(
                ("Output", "Code", "Description", "Unit", "Quantity", "Remarks"),
                [(row.label, row.code, row.description, row.unit, row.quantity, row.remarks) for row in sheet.outputs],
                (4,),
                (2, 5),
            )
        )
        output.append("</article>")
    return "".join(output)
