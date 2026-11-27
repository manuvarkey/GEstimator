"""HTML/PDF measurement details and bidirectional printable page references."""

from decimal import Decimal, InvalidOperation

from .groups import category_groups
from .html_tables import Anchor, Heading, PageLink, Total, table, text
from .measurement_abstract import first_enabled, item_description, measured_items


def measurement_abstract(document, section, numbers):
    """Show one brought-forward quantity per accepted link and a total per item."""
    destination = first_enabled(document, "measurements")
    entries = []
    for category, items in category_groups(measured_items(document)):
        entries.append(Heading(category))
        for index, measured in items:
            item = measured.item
            description = item_description(item.description, section)
            entries.append((Anchor(f"{section.id}:item:{index}", item.code), description, item.unit, ""))
            for entry in measured.entries:
                target = f"{destination.id}:measurement:{entry.index}" if destination else ""
                label = f"Measurement {entry.number}"
                value = PageLink(target, label, "Qty B/F [", "]") if target else f"Qty B/F [{label}]"
                entries.append(("", value, entry.output.unit, numbers.format(entry.output.quantity)))
            entries.append(Total(("", "Total", item.unit, numbers.format(measured.total))))
    if not entries:
        return "<p>No selected schedule items have linked measurements.</p>"
    return table(("Code", "Description", "Unit", "Quantity"), entries, (3,), (1,))


def measurements(document, section, numbers):
    """Retain numbered template records, separate totals and optional carry-over links."""
    destination = first_enabled(document, "measurement_abstract")
    targets = (
        {value.item.code: f"{destination.id}:item:{index}" for index, value in enumerate(measured_items(document))}
        if destination
        else {}
    )
    output = []
    for category_index, (category, items) in enumerate(category_groups(document.measurements)):
        page_class = ' class="item-page"' if category_index and section.each_item_page else ""
        output.append(f'<h2{page_class} id="{section.id}:category:{category_index}">{text(category)}</h2>')
        for position, (index, sheet) in enumerate(items):
            page_break = bool(position and section.each_item_page)
            output.append(_measurement_item(sheet, f"{section.id}:measurement:{index}", page_break, numbers, targets))
    return "".join(output)


def _measurement_item(sheet, anchor, page_break, numbers, targets):
    """Keep the caption and remarks with the first record while allowing long tables to flow."""
    css = "measurement-item item-page" if page_break else "measurement-item"
    caption = f"{sheet.number}. {sheet.description or sheet.template}"
    template = f' <span class="measurement-template">· {text(sheet.template)}</span>' if sheet.description else ""
    output = [f'<article class="{css}">', f'<h3 class="item-heading" id="{anchor}">{text(caption)}{template}</h3>']
    remarks = [f"{row.code} — {row.remarks}" if row.code else row.remarks for row in sheet.outputs if row.remarks]
    if remarks:
        output.append(f'<p class="measurement-remarks"><em>{text(chr(10).join(remarks))}</em></p>')
    headings = ("Sl. No.", *sheet.columns)
    records = [
        (
            index,
            *(
                numbers.format(value) if column in sheet.numeric_columns and _numeric(value) else value
                for column, value in enumerate(record)
            ),
        )
        for index, record in enumerate(sheet.records, 1)
    ]
    if sheet.properties:
        output.append(table(("Property", "Value"), sheet.properties))
    totals = [
        (f"Total · {row.label}" if len(sheet.outputs) > 1 else "Total", numbers.format(row.quantity))
        for row in sheet.outputs
    ]
    output.append(table(headings, records, (0,), tuple(range(1, len(headings))), totals=totals))
    codes = tuple(dict.fromkeys(row.code for row in sheet.outputs if row.code in targets))
    if codes:
        links = ", ".join(PageLink(targets[code], "Measurement abstract").html() for code in codes)
        output.append(f'<p class="quantity-carry">Quantity C/o [{links}]<br>{text(", ".join(codes))}</p>')
    output.append("</article>")
    return "".join(output)


def _numeric(value):
    """Template custom columns may emit both text and finite numbers."""
    try:
        return Decimal(value).is_finite()
    except InvalidOperation:
        return False
