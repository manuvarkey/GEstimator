"""Standalone, offline HTML from escaped report values and a fixed local layout."""

from html import escape

from .document import ReportDocument
from .fonts import DEFAULT_FONT, bundled_css
from .groups import category_groups
from .tables import COLUMNS, column_widths, table_values

# Keep the complete fixed layout here so frozen backends need no template assets.
# Resolved values are escaped here; bounded notes templates belong to narrative.py.
STYLE = """
@page { size:A4; margin:20mm;
 @top-left { content:counter(page); background:#729fcf; color:#172b3a; font-style:italic;
   width:6%; height:10mm; text-align:center; vertical-align:middle; border-bottom:0.5pt solid #729fcf; }
 @top-right { content:string(section-heading); font-style:italic; vertical-align:middle;
   width:94%; height:10mm; text-align:right; border-bottom:0.5pt solid #729fcf; }
 @bottom-left { content:element(report-footer); width:80%; border-top:0.5pt solid #729fcf; }
 @bottom-right { content:"Page " counter(page) " of " counter(pages); width:20%; text-align:right; border-top:0.5pt solid #729fcf; }
}
@page:first { @top-left { content:none; background:none; border:none; }
 @top-right { content:none; border:none; } @bottom-left { content:none; border:none; }
 @bottom-right { content:none; border:none; } }
@page report-wide { size:A4 landscape; }
@page report-portrait { size:A4 portrait; }
.wide { page:report-wide; }
.portrait { page:report-portrait; }
.section > h1 { string-set:section-heading content(); }
h1,h2,h3 { break-after:avoid; }
.keep-together { break-inside:avoid; }
tbody tr:nth-child(even) { background:#f5f8fa; }
* { box-sizing:border-box; }
html { font-size:10pt; }
body { font:1rem/1.45 "Iosevka",monospace; color:#243247; margin:0 auto; max-width:1100px; padding:24px; }
h1 { color:#174e67; font-size:2.2rem; } h2 { font-size:1.7rem; }
a { color:#174e67; } .cover { padding:60px 0; }
.section { break-before:page; margin-top:32px; }
.section.inline { break-before:auto; break-inside:avoid; }
.item-heading { font-size:1rem; font-weight:bold; }
.item-page { break-before:page; }
.note-page + .note-page { break-before:page; }
.work-name { font-weight:bold; }
table { border-collapse:collapse; width:100%; font-size:0.9rem; table-layout:fixed; }
thead { display:table-header-group; }
th,td { border-bottom:1px solid #ccd6dc; padding:6px 5px; text-align:left; vertical-align:top; overflow-wrap:anywhere; }
th,th.number { background:#e4eef2; overflow-wrap:anywhere; hyphens:auto; } tr { break-inside:avoid; }
.number { text-align:right; font-variant-numeric:tabular-nums; overflow-wrap:anywhere; }
.report-footer { position:running(report-footer); font-size:0.8rem; white-space:nowrap; overflow:hidden; }
@media screen { .report-footer { position:static; border-bottom:1px solid #729fcf; padding-bottom:8px; } }
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
    widths = widths or column_widths(headings)
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


def _css_string(value):
    """Quote text as a CSS string, including HTML raw-text terminators and controls."""
    return '"' + "".join(char if char.isalnum() or char in " -_." else f"\\{ord(char):x} " for char in value) + '"'


def _presentation_style(spec):
    """Scale every typographic role together without changing physical page margins."""
    family = _css_string(spec.font_family or "Iosevka")
    fallback = "monospace" if not spec.font_family or spec.font_family == DEFAULT_FONT else "sans-serif"
    return (
        (bundled_css() if not spec.font_family or spec.font_family == DEFAULT_FONT else "")
        + f"html {{ font-size:{10 * spec.font_scale:g}pt; }} body {{ font-family:{family},{fallback}; }}"
        f" @page {{ font-family:{family},{fallback}; font-size:{8 * spec.font_scale:g}pt; }}"
    )


def render_html(document: ReportDocument) -> str:
    """Render a fixed cover, linked contents and the enabled ordered sections."""
    spec = document.specification
    sections = [section for section in spec.sections if section.enabled]
    footer_label = spec.organization or document.project or spec.title
    output = [
        '<!doctype html><html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; style-src 'unsafe-inline'; font-src data:\">",
        f"<title>{_text(spec.title)} — {_text(document.project)}</title><style>{STYLE}{_presentation_style(spec)}</style></head><body>",
        f'<div class="report-footer">{_text(footer_label)} · GEstimator</div>',
        '<header class="cover">',
        f"<p>{_text(spec.organization)}</p><h1>{_text(spec.title)}</h1><h2>{_text(document.project)}</h2>",
        f"<p>Reference: {_text(spec.reference)}</p><p>Issued: {_text(spec.issue_date)}</p>",
        '</header><nav class="section" aria-label="Contents"><h1>Contents</h1><ol class=toc>',
    ]
    for section in sections:
        output.append(f'<li><a href="#{section.id}">{_text(section.title)}</a>')
        if section.kind in ("analyses", "measurements"):
            output.append(_item_contents(document, section))
        output.append("</li>")
    output.append("</ol></nav>")
    # Each renderer consumes the same captured amounts; rendering never calculates.
    for section in sections:
        orientation = section.orientation
        if orientation == "auto":
            orientation = "landscape" if section.kind in ("resources", "resource_usage", "measurements") else "auto"
        css = (
            "section wide"
            if orientation == "landscape"
            else "section portrait"
            if orientation == "portrait"
            else "section"
        )
        if not section.new_page:
            css = "section inline"
        output.append(f'<section class="{css}" id="{section.id}"><h1>{_text(section.title)}</h1>')
        if section.show_name_of_work:
            output.append(f'<p class="work-name">Name of work: {_text(document.project)}</p>')
        output.append(_section_body(document, section))
        output.append("</section>")
    output.append("</body></html>")
    html = "".join(output)
    if len(html.encode("utf-8")) > 10_000_000:
        raise ValueError("Report HTML exceeds the 10 MB limit; select fewer items")
    return html


def _analyses(document, section):
    """Keep per-item captions/remarks with their detailed engine-result tables."""
    output = []
    for category_index, (category, items) in enumerate(category_groups(document.analyses)):
        page_class = ' class="item-page"' if category_index and section.each_item_page else ""
        output.append(f'<h2{page_class} id="{section.id}:category:{category_index}">{_text(category)}</h2>')
        for position, (index, analysis) in enumerate(items):
            output.append(_analysis_item(analysis, section, index, position))
    return "".join(output)


def _analysis_item(analysis, section, index, position):
    """One item's heading uses body size; its table may continue across pages."""
    output = []
    # Small analyses can stay together. Large blocks must be splittable so
    # a paginator does not push their first table onto an otherwise empty page.
    compact = len(analysis.rows) <= 12 and sum(len(row.description) + len(row.remarks) for row in analysis.rows) <= 1600
    css = "analysis-item keep-together" if compact else "analysis-item"
    if section.each_item_page and position:
        css += " item-page"
    output.append(f'<article class="{css}">')
    output.append(
        f'<h3 class="item-heading" id="{section.id}:analysis:{index}">{_text(analysis.code)} — {_text(analysis.description)}</h3>'
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
    if section.kind in COLUMNS:
        columns, rows = table_values(document, section)
        if section.kind == "resource_usage":
            output.append(
                "<p>Direct resource usage for selected schedule items; dependency resources are not expanded.</p>"
            )
        output.append(
            _table(
                tuple(column.title for column in columns),
                rows,
                tuple(index for index, column in enumerate(columns) if column.numeric),
                tuple(index for index, column in enumerate(columns) if column.multiline),
                widths=column_widths(tuple(column.title for column in columns)),
            )
        )
        if section.kind in ("abstract", "schedule"):
            output.append(f'<p class="total">Estimate total: {_text(document.total)}</p>')
    elif section.kind == "analyses":
        output.append(_analyses(document, section))
    elif section.kind == "narrative":
        narrative = next(item for item in document.narratives if item.id == section.id)
        for page in narrative.pages:
            output.append(f'<div class="note-page"><p class="description">{_text(page)}</p></div>')
    elif section.kind == "measurements":
        output.append(_measurements(document, section))
    else:
        output.append('<div class="signatures">')
        for block in section.signoff_blocks:
            output.append(
                f'<div class="signature"><p><strong>{_text(block.caption)}</strong></p><p class="description">{_text(block.body)}</p></div>'
            )
        output.append("</div>")
    return "".join(output)


def _measurements(document, section):
    """Render template records and each independent output with its link and unit."""
    output = ["<p>Complete measurement sheets; totals are separate template outputs, not schedule quantities.</p>"]
    for category_index, (category, items) in enumerate(category_groups(document.measurements)):
        page_class = ' class="item-page"' if category_index and section.each_item_page else ""
        output.append(f'<h2{page_class} id="{section.id}:category:{category_index}">{_text(category)}</h2>')
        for position, (index, sheet) in enumerate(items):
            output.append(_measurement_item(sheet, section, index, position))
    return "".join(output)


def _measurement_item(sheet, section, index, position):
    """Render a complete measurement sheet under its category and nested contents target."""
    output = []
    compact = (
        len(sheet.records) + len(sheet.outputs) <= 15
        and sum(len(value) for record in sheet.records for value in record) <= 1600
    )
    css = "keep-together" if compact else ""
    if position and section.each_item_page:
        css += " item-page"
    output.append(f'<article class="{css}">')
    output.append(
        f'<h3 class="item-heading" id="{section.id}:measurement:{index}">{sheet.number}. {_text(sheet.description or sheet.template)}</h3>'
    )
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


def _item_contents(document, section):
    """Link category headings and each analysis/measurement item in a nested outline."""
    items = document.analyses if section.kind == "analyses" else document.measurements
    kind = "analysis" if section.kind == "analyses" else "measurement"
    output = ["<ul>"]
    for group_index, (category, values) in enumerate(category_groups(items)):
        output.append(f'<li><a href="#{section.id}:category:{group_index}">{_text(category)}</a><ul>')
        for index, item in values:
            label = item.code if kind == "analysis" else f"{item.number}. {item.description or item.template}"
            output.append(f'<li><a href="#{section.id}:{kind}:{index}">{_text(label)}</a></li>')
        output.append("</ul></li>")
    output.append("</ul>")
    return "".join(output)
