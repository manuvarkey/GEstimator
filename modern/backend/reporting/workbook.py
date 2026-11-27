"""Excel presentation of the same immutable data used by HTML/PDF reports."""

from copy import copy
from decimal import Decimal

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins
from openpyxl.worksheet.pagebreak import Break

from .document import ReportDocument
from .fonts import DEFAULT_FONT
from .groups import category_groups
from .tables import COLUMNS, column_widths, table_values


def _text(sheet, row, column, value):
    """Store user text literally, including values beginning with an equals sign."""
    cell = sheet.cell(row, column, str(value))
    cell.font = Font(size=10)
    cell.data_type = "s"
    cell.alignment = Alignment(vertical="top", wrap_text=True)
    return cell


def _table(sheet, headings, rows, numeric=(), start_row=3):
    """Style a printable worksheet with repeated headings and numeric money cells."""
    for column, heading in enumerate(headings, 1):
        cell = _text(sheet, start_row, column, heading)
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="E4EEF2")
    for index, values in enumerate(rows, start_row + 1):
        for column, value in enumerate(values, 1):
            if column in numeric and value not in (None, ""):
                cell = sheet.cell(index, column, Decimal(value))
                cell.font = Font(size=10)
                cell.number_format = "General" if headings[column - 1] == "Quantity" else "0.00"
                cell.alignment = Alignment(horizontal="right", vertical="top")
            else:
                _text(sheet, index, column, value or "")
    for column, width in enumerate(column_widths(headings), 1):
        # One full report table is about 120 Excel character units before print fitting.
        letter = get_column_letter(column)
        sheet.column_dimensions[letter].width = max(8, width * 1.2)
    sheet.print_title_rows = "1:3"
    sheet.freeze_panes = "A4"
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_setup.orientation = "landscape" if len(headings) > 3 else "portrait"
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.print_options.horizontalCentered = True


def write_workbook(document: ReportDocument, destination):
    """Write sections in order; contents links are sheet links, never PDF page claims."""
    workbook = Workbook()
    cover = workbook.active
    cover.title = "Cover"
    spec = document.specification
    for index, value in enumerate(
        (spec.title, document.project, spec.organization, spec.reference, spec.issue_date), 1
    ):
        _text(cover, index, 1, value)
    cover.column_dimensions["A"].width = 80
    contents = workbook.create_sheet("Contents")
    _text(contents, 1, 1, "Contents")
    for index, section in enumerate((section for section in spec.sections if section.enabled), 1):
        # Generated worksheet names avoid collisions, forbidden characters and formulas.
        inline = section.kind == "signoff" and not section.new_page and len(workbook.worksheets) > 2
        sheet = workbook.worksheets[-1] if inline else workbook.create_sheet(f"Section {index}")
        start = sheet.max_row + 3 if inline else 1
        _text(sheet, start, 1, section.title).font = Font(bold=True, size=16)
        if not inline:
            _text(
                sheet,
                2,
                1,
                document.project if section.show_name_of_work or section.kind not in ("abstract", "schedule") else "",
            )
        link = _text(contents, index + 1, 1, section.title)
        link.hyperlink = f"#'{sheet.title}'!A{start}"
        link.style = "Hyperlink"
        if section.kind == "signoff":
            _write_signoff(sheet, section, start + 2, inline)
        else:
            _write_section(document, sheet, section)
        if section.orientation != "auto" and not inline:
            sheet.page_setup.orientation = section.orientation
    contents.column_dimensions["A"].width = 60
    for sheet in workbook:
        _presentation(sheet, document)
    workbook.save(destination)


def _write_section(document, sheet, section):
    """Fill one section worksheet from immutable presentation values."""
    kind = section.kind
    if kind == "narrative":
        narrative = next(item for item in document.narratives if item.id == section.id)
        position = 3
        for index, body in enumerate(narrative.pages):
            if index:
                sheet.row_breaks.append(Break(id=position - 1))
            # Separate short literal rows avoid Excel's 32767-character cell limit
            # and maximum wrapped-row height silently hiding a long notes page.
            values = [
                (line[start : start + 100],) for line in body.split("\n") for start in range(0, max(1, len(line)), 100)
            ]
            _table(sheet, ("Notes",), values, start_row=position)
            for row in range(position + 1, position + len(values) + 1):
                sheet.row_dimensions[row].height = 28
            position += len(values) + 2
        sheet.column_dimensions["A"].width = 100
    elif kind == "measurements":
        _write_measurements(document, sheet, section)
    elif kind in COLUMNS:
        _write_fixed_table(document, sheet, section)
    elif kind == "analyses":
        _write_analyses(document, sheet, section)


def _write_signoff(sheet, section, start, inline=False):
    """Append editable signatures to the preceding sheet unless a page is requested."""
    sheet.row_dimensions[start].height = 20
    sheet.row_dimensions[start + 1].height = (
        max(3, max(block.body.count("\n") + 1 for block in section.signoff_blocks)) * 14
    )
    if inline:
        # Preserve the schedule's column geometry, orientation and repeated rows.
        columns = max(sheet.max_column, len(section.signoff_blocks))
        count = len(section.signoff_blocks)
        for index, block in enumerate(section.signoff_blocks):
            first = index * columns // count + 1
            last = (index + 1) * columns // count
            _text(sheet, start, first, block.caption).font = Font(bold=True, size=10)
            _text(sheet, start + 1, first, block.body)
            if last > first:
                sheet.merge_cells(start_row=start, start_column=first, end_row=start, end_column=last)
                sheet.merge_cells(start_row=start + 1, start_column=first, end_row=start + 1, end_column=last)
    else:
        _table(
            sheet,
            tuple(block.caption for block in section.signoff_blocks),
            [tuple(block.body for block in section.signoff_blocks)],
            start_row=start,
        )


def _write_analyses(document, sheet, section):
    """Retain category and item headings while assigning explicit per-item page breaks."""
    position = 3
    count = 0
    for category, items in category_groups(document.analyses):
        if count and section.each_item_page:
            sheet.row_breaks.append(Break(id=position - 1))
        _text(sheet, position, 1, category).font = Font(bold=True, size=12)
        position += 1
        for offset, (_, item) in enumerate(items):
            if offset and section.each_item_page:
                sheet.row_breaks.append(Break(id=position - 1))
            _text(sheet, position, 1, f"{item.code} — {item.description}").font = Font(bold=True, size=10)
            rows = [(row.code, row.description, row.unit, row.quantity, row.rate, row.amount) for row in item.rows]
            _table(
                sheet,
                ("Code", "Description", "Unit", "Quantity / factor", "Rate", "Amount"),
                rows,
                (4, 5, 6),
                start_row=position + 1,
            )
            position += len(rows) + 3
            _text(
                sheet,
                position,
                1,
                f"Stored schedule rate: {item.stored_rate}; calculated analysis rate: {item.calculated_rate}",
            )
            position += 2
            count += 1
    sheet.print_title_rows = "1:2"


def _write_measurements(document, sheet, section):
    """Keep each variable-width template table and its independent outputs together."""
    position = 3
    count = 0
    for category, items in category_groups(document.measurements):
        if count and section.each_item_page:
            sheet.row_breaks.append(Break(id=position - 1))
        _text(sheet, position, 1, category).font = Font(bold=True, size=12)
        position += 1
        for offset, (_, measurement) in enumerate(items):
            if offset and section.each_item_page:
                sheet.row_breaks.append(Break(id=position - 1))
            _text(
                sheet, position, 1, f"{measurement.number}. {measurement.description or measurement.template}"
            ).font = Font(bold=True, size=10)
            _text(sheet, position + 1, 1, f"{measurement.category} · {measurement.template}")
            _table(sheet, measurement.columns, measurement.records, start_row=position + 2)
            position += len(measurement.records) + 4
            if measurement.properties:
                _table(sheet, ("Property", "Value"), measurement.properties, start_row=position)
                position += len(measurement.properties) + 2
            _table(
                sheet,
                ("Output", "Code", "Description", "Unit", "Quantity", "Remarks"),
                [
                    (row.label, row.code, row.description, row.unit, row.quantity, row.remarks)
                    for row in measurement.outputs
                ],
                (5,),
                start_row=position,
            )
            position += len(measurement.outputs) + 3
            count += 1
    sheet.print_title_rows = "1:2"
    sheet.page_setup.orientation = "landscape"


def _write_fixed_table(document, sheet, section):
    """Keep numeric types and totals correct when columns move or are omitted."""
    columns, rows = table_values(document, section, excel=True)
    _table(
        sheet,
        tuple(column.title for column in columns),
        rows,
        tuple(index for index, column in enumerate(columns, 1) if column.numeric),
    )
    if section.kind not in ("abstract", "schedule"):
        return
    # The total remains a separate summary even when Amount is hidden or first.
    keys = [column.key for column in columns]
    amount_column = max(2, keys.index("amount") + 1) if "amount" in keys else 2
    label_column = 2 if section.kind == "schedule" and section.columns is None else 1
    _text(sheet, len(rows) + 5, label_column, "Estimate total")
    sheet.cell(len(rows) + 5, amount_column, Decimal(document.total)).number_format = "0.00"


def _presentation(sheet, document):
    """Apply document typography and 20 mm print margins to every worksheet."""
    spec = document.specification
    for row in sheet:
        for cell in row:
            font = copy(cell.font)
            font.name = spec.font_family or DEFAULT_FONT
            font.sz = (10 if cell.style == "Hyperlink" else (font.sz or 10)) * spec.font_scale
            cell.font = font
    for dimension in sheet.row_dimensions.values():
        if dimension.height is not None:
            dimension.height *= spec.font_scale
    margin = 20 / 25.4
    sheet.page_margins = PageMargins(
        left=margin, right=margin, top=margin, bottom=margin, header=8 / 25.4, footer=8 / 25.4
    )
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A4

    # Double ampersands keep project strings literal in Excel's header/footer syntax.
    def literal(value):
        return value.replace("&", "&&").replace("\n", " ").replace("\r", " ")[:240]

    sheet.oddHeader.left.text = "&P"
    sheet.oddHeader.right.text = literal(str(sheet["A1"].value or spec.title))
    sheet.oddFooter.left.text = literal(spec.organization or document.project or spec.title) + " · GEstimator"
    sheet.oddFooter.right.text = "Page &P of &N"
    for region in (sheet.oddHeader.left, sheet.oddHeader.right, sheet.oddFooter.left, sheet.oddFooter.right):
        region.size = 8 * spec.font_scale
        region.font = spec.font_family or DEFAULT_FONT
    sheet.HeaderFooter.differentFirst = sheet.title == "Cover"
