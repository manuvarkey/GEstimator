"""Standalone, offline HTML from escaped report values and a fixed local layout."""

from decimal import Decimal

from .datasets import resource_description
from .document import ReportDocument
from .fonts import DEFAULT_FONT, bundled_css
from .groups import category_groups
from .html_measurements import measurement_abstract, measurements
from .html_tables import Heading, Total
from .html_tables import table as _table
from .html_tables import text as _text
from .regional import NumberFormat
from .tables import COLUMNS, column_widths, table_values

# Keep the complete fixed layout here so frozen backends need no template assets.
# Resolved values are escaped here; bounded notes templates belong to narrative.py.
STYLE = """
@page { size:A4; margin:20mm;
 @bottom-left { content:element(report-footer); width:80%; border-top:0.5pt solid #729fcf; }
 @bottom-right { content:"Page " counter(page) " of " counter(pages); width:20%; text-align:right; border-top:0.5pt solid #729fcf; }
}
@page:first { @bottom-left { content:none; border:none; } @bottom-right { content:none; border:none; } }
@page report-wide { size:A4 landscape; }
@page report-portrait { size:A4 portrait; }
.wide { page:report-wide; }
.portrait { page:report-portrait; }
h1,h2,h3 { break-after:avoid; }
.keep-together { break-inside:avoid; }
tbody tr:nth-child(even) { background:#fafbfc; }
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
.work-name { font-size:1rem; } .cover .work-name { font-size:1.1rem; }
.cover-logo { display:block; max-width:48mm; max-height:30mm; margin-bottom:1rem; }
.cover-office { white-space:pre-wrap; }
.analysis-item td,.analysis-item th { padding:2px 4px; }
.analysis-item p { margin-block:4px; }
.analysis-parent,.measurement-remarks { font-size:0.9rem; margin-block:4px; }
.measurement-remarks { white-space:pre-wrap; }
.measurement-template { font-size:0.85rem; font-weight:normal; color:#4f6070; }
.measurement-item { margin-block:1rem; }
.table-group th { background:#edf2f5; }
.total-row th,.total-row td { font-weight:bold; background:#f0f4f6; }
tfoot { display:table-row-group; }
.signoff-intro + .signatures { margin-top:16px; }
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
.toc, .toc ul { list-style:none; padding-inline-start:0; }
.toc ul { padding-inline-start:1.2rem; }
.toc a { display:block; border-bottom:0.5pt solid #d8e1e7; padding-block:2px; }
@media print {
  .toc a::after { content:target-counter(attr(href), page); float:right; }
  .page-link::after { content:target-counter(attr(href), page); }
  .page-link span { display:none; }
  body { max-width:none; padding:0; }
  .cover { padding-top:22mm; }
}
"""


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


def render_html(document: ReportDocument, numbers: NumberFormat = NumberFormat()) -> str:
    """Render a fixed cover, linked contents and the enabled ordered sections."""
    spec = document.specification
    sections = [section for section in spec.sections if section.enabled]
    footer_label = spec.organization or document.project or spec.title
    output = [
        '<!doctype html><html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; style-src 'unsafe-inline'; font-src data:; img-src data:\">",
        f"<title>{_text(spec.title)} — {_text(document.project)}</title><style>{STYLE}{_presentation_style(spec)}</style></head><body>",
        f'<div class="report-footer">{_text(footer_label)} · GEstimator</div>',
        '<header class="cover">',
        f'<img class="cover-logo" src="{_text(spec.logo)}" alt="Office logo">' if spec.logo else "",
        f'<p>{_text(spec.organization)}</p><p class="cover-office">{_text(spec.office)}</p>'
        if spec.office
        else f"<p>{_text(spec.organization)}</p>",
        f"<h1>{_text(spec.title)}</h1>",
        f'<h2 class="work-name">{_text(document.project)}</h2>' if document.project else "",
        f"<p>Reference: {_text(spec.reference)}</p>" if spec.reference else "",
        f"<p>Issued: {_text(spec.issue_date)}</p>" if spec.issue_date else "",
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
        output.append(_section_body(document, section, numbers))
        output.append("</section>")
    output.append("</body></html>")
    html = "".join(output)
    if len(html.encode("utf-8")) > 10_000_000:
        raise ValueError("Report HTML exceeds the 10 MB limit; select fewer items")
    return html


def _analyses(document, section, numbers):
    """Keep per-item captions/remarks with their detailed engine-result tables."""
    output = []
    for category_index, (category, items) in enumerate(category_groups(document.analyses)):
        page_class = ' class="item-page"' if category_index and section.each_item_page else ""
        output.append(f'<h2{page_class} id="{section.id}:category:{category_index}">{_text(category)}</h2>')
        for position, (index, analysis) in enumerate(items):
            output.append(_analysis_item(analysis, section, index, position, numbers))
    return "".join(output)


def _analysis_item(analysis, section, index, position, numbers):
    """One item's heading uses body size; its table may continue across pages."""
    output = []
    # Small analyses can stay together. Large blocks must be splittable so
    # a paginator does not push their first table onto an otherwise empty page.
    compact = len(analysis.rows) <= 12 and sum(len(row.description) + len(row.remarks) for row in analysis.rows) <= 1600
    css = "analysis-item keep-together" if compact else "analysis-item"
    if section.each_item_page and position:
        css += " item-page"
    output.append(f'<article class="{css}">')
    parent = f"{analysis.parent_code} — {analysis.parent_description}"
    if analysis.parent_code:
        output.append(f'<p class="analysis-parent">{_text(parent)}</p>')
    output.append(
        f'<h3 class="item-heading" id="{section.id}:analysis:{index}">{_text(analysis.code)} — {_text(analysis.description)}</h3>'
    )
    if analysis.remarks:
        output.append(f'<p class="description">{_text(analysis.remarks)}</p>')
    output.append(
        _table(
            ("Code", "Description", "Unit", "Quantity / factor", "Rate", "Amount"),
            [
                (
                    row.code,
                    _analysis_description(row, numbers) + ("\n" + row.remarks if row.remarks else ""),
                    row.unit,
                    row.quantity,
                    numbers.format(row.rate),
                    numbers.format(row.amount),
                )
                for row in analysis.rows
            ],
            (3, 4, 5),
            (1,),
        )
    )
    output.append(
        f'<p class="total">Stored schedule rate: {_text(numbers.format(analysis.stored_rate))} · '
        f"Calculated analysis rate: {_text(numbers.format(analysis.calculated_rate))}</p>"
    )
    output.append("</article>")
    return "".join(output)


def _analysis_description(row, numbers):
    """Localize the embedded resource adjustments alongside the displayed rates."""
    if row.kind != "Resource" or not row.basic_rate:
        return row.description
    return resource_description(
        row.resource_name, row.basic_rate, Decimal(row.tax), Decimal(row.discount), row.reference, numbers.format
    )


def _section_body(document, section, numbers):
    """Render one dataset without extending the document shell."""
    output = []
    if section.kind in COLUMNS:
        output.append(_fixed_table(document, section, numbers))
        if section.kind in ("abstract", "schedule"):
            output.append(f'<p class="total">Estimate total: {_text(numbers.format(document.total))}</p>')
    elif section.kind == "analyses":
        output.append(_analyses(document, section, numbers))
    elif section.kind == "narrative":
        narrative = next(item for item in document.narratives if item.id == section.id)
        for page in narrative.pages:
            output.append(f'<div class="note-page"><p class="description">{_text(page)}</p></div>')
    elif section.kind == "measurements":
        output.append(measurements(document, section, numbers))
    elif section.kind == "measurement_abstract":
        output.append(measurement_abstract(document, section, numbers))
    else:
        intro = next((item.pages[0] for item in document.narratives if item.id == section.id), "")
        if intro:
            output.append(f'<p class="description signoff-intro">{_text(intro)}</p>')
        output.append('<div class="signatures">')
        for block in section.signoff_blocks:
            output.append(
                f'<div class="signature"><p><strong>{_text(block.caption)}</strong></p><p class="description">{_text(block.body)}</p></div>'
            )
        output.append("</div>")
    return "".join(output)


def _fixed_table(document, section, numbers):
    """Group detail rows by category and keep schedule subtotals in the same columns."""
    grouped = section.kind in ("schedule", "resources", "resource_usage")
    columns, rows = table_values(document, section, group_categories=grouped)
    monetary = {"rate", "amount"}

    def formatted(values):
        return tuple(
            numbers.format(value) if column.key in monetary else value for column, value in zip(columns, values)
        )

    if grouped:
        source = getattr(document, section.kind)
        totals = {row.category_id: row.amount for row in document.abstract} if section.kind == "schedule" else {}
        amounts = next((i for i, col in enumerate(columns) if col.key == "amount"), None)
        label = next((i for i, col in enumerate(columns) if col.key == "description"), 0)
        if label == amounts and len(columns) > 1:
            label = 1
        output = []
        for category, items in category_groups(source):
            output.append(Heading(category))
            output.extend(formatted(rows[i]) for i, _ in items)
            subtotal = totals.get(getattr(items[0][1], "category_id", None))
            if subtotal is not None:
                values = [""] * len(columns)
                values[label] = "Category total"
                if amounts is None or amounts == label:
                    values[label] += ": " + numbers.format(subtotal)
                else:
                    values[amounts] = numbers.format(subtotal)
                output.append(Total(tuple(values)))
    else:
        output = [formatted(row) for row in rows]
    headings = tuple(column.title for column in columns)
    return _table(
        headings,
        output,
        tuple(index for index, column in enumerate(columns) if column.numeric),
        tuple(index for index, column in enumerate(columns) if column.multiline),
        widths=column_widths(headings),
    )


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
