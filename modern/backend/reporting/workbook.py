"""Excel presentation of the same immutable data used by HTML/PDF reports."""

from copy import copy
from decimal import Decimal, InvalidOperation

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins
from openpyxl.worksheet.pagebreak import Break

from .document import ReportDocument
from .fonts import DEFAULT_FONT
from .groups import category_groups
from .measurement_abstract import item_description, measured_items
from .tables import COLUMNS, column_widths, table_values
from .workbook_formulas import AnalysisFormulas, WorkbookLinks, adjusted_rate, sheet_ref
from .workbook_formulas import formula as _formula


def _text(sheet, row, column, value):
    """Store user text literally, including values beginning with an equals sign."""
    cell = sheet.cell(row, column, str(value))
    cell.font = Font(size=10)
    cell.data_type = "s"
    cell.alignment = Alignment(vertical="top", wrap_text=True)
    return cell


def _table(sheet, headings, rows, numeric=(), start_row=3, numeric_format=None):
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
                cell.number_format = numeric_format or (
                    "General" if headings[column - 1] in ("Quantity", "Quantity / factor", "Sl. No.") else "#,##0.00"
                )
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
    if spec.office:
        _text(cover, 6, 1, spec.office)
    cover.column_dimensions["A"].width = 80
    contents = workbook.create_sheet("Contents")
    _text(contents, 1, 1, "Contents")
    sections = [section for section in spec.sections if section.enabled]
    # Allocate every destination before filling tables so formulas can reference
    # a sheet regardless of the order of report sections.
    destinations = []
    for index, section in enumerate(sections, 1):
        inline = section.kind == "signoff" and not section.new_page and len(workbook.worksheets) > 2
        sheet = workbook.worksheets[-1] if inline else workbook.create_sheet(f"Section {index}")
        destinations.append((section, sheet, inline))
    links = _workbook_links(document, destinations)
    for index, (section, sheet, inline) in enumerate(destinations, 1):
        # Generated worksheet names avoid collisions, forbidden characters and formulas.
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
            intro = next((item.pages[0] for item in document.narratives if item.id == section.id), "")
            visible_width = links.measurement_input_start - 2 if sheet in links.measurement_sheets else sheet.max_column
            position = _write_intro(sheet, start + 2, intro, visible_width) if intro else start + 2
            _write_signoff(sheet, section, position, inline, visible_width)
            links.print_widths[sheet] = max(visible_width, len(section.signoff_blocks))
        else:
            _write_section(document, sheet, section, links)
        if section.orientation != "auto" and not inline:
            sheet.page_setup.orientation = section.orientation
    links.finish()
    contents.column_dimensions["A"].width = 60
    for sheet in workbook:
        if sheet in links.measurement_sheets:
            end = max(links.measurement_input_start - 2, links.print_widths.get(sheet, 0))
            sheet.print_area = f"A1:{get_column_letter(end)}{sheet.max_row}"
        _presentation(sheet, document)
    workbook.save(destination)


def _write_section(document, sheet, section, links):
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
        _write_measurements(document, sheet, section, links)
    elif kind == "measurement_abstract":
        _write_measurement_abstract(document, sheet, section, links)
    elif kind in COLUMNS:
        _write_fixed_table(document, sheet, section, links)
    elif kind == "analyses":
        _write_analyses(document, sheet, section, links)


def _write_intro(sheet, start, intro, visible_width):
    """Wrap a resolved signoff introduction above its signature columns."""
    position = start
    span = max(visible_width, 3)
    for line in intro.splitlines():
        for offset in range(0, max(1, len(line)), 100):
            _text(sheet, position, 1, line[offset : offset + 100])
            sheet.merge_cells(start_row=position, start_column=1, end_row=position, end_column=span)
            sheet.row_dimensions[position].height = 26
            position += 1
    return position + 1


def _write_signoff(sheet, section, start, inline, visible_width):
    """Append editable signatures to the preceding sheet unless a page is requested."""
    sheet.row_dimensions[start].height = 20
    sheet.row_dimensions[start + 1].height = (
        max(3, max(block.body.count("\n") + 1 for block in section.signoff_blocks)) * 14
    )
    if inline:
        # Preserve the schedule's column geometry, orientation and repeated rows.
        columns = max(visible_width, len(section.signoff_blocks))
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


def _write_analyses(document, sheet, section, links):
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
            if item.parent_code:
                _text(sheet, position, 1, f"{item.parent_code} — {item.parent_description}")
                position += 1
            _text(sheet, position, 1, f"{item.code} — {item.description}").font = Font(bold=True, size=10)
            rows = [
                (
                    row.code,
                    row.description + ("\n" + row.remarks if row.remarks else ""),
                    row.unit,
                    row.quantity,
                    row.rate,
                    row.amount,
                )
                for row in item.rows
            ]
            _table(
                sheet,
                ("Code", "Description", "Unit", "Quantity / factor", "Rate", "Amount"),
                rows,
                (4, 5, 6),
                start_row=position + 1,
            )
            formulas = AnalysisFormulas()
            for row_index, row in enumerate(item.rows, position + 2):
                if row.kind == "Resource":
                    _formula(sheet, row_index, 5, adjusted_rate(row.code, row, links.resources))
                amount = formulas.amount(row.kind, row_index, row.quantity)
                if amount is not None:
                    _formula(sheet, row_index, 6, amount)
            links.analyses.setdefault(
                item.code, (sheet_ref(sheet, f"F{position + 1 + len(rows)}"), item.calculated_rate)
            )
            position += len(rows) + 3
            _text(sheet, position, 1, "Stored schedule rate")
            sheet.cell(position, 2, Decimal(item.stored_rate)).number_format = "#,##0.00"
            _text(sheet, position, 3, "Calculated analysis rate")
            _formula(sheet, position, 4, f"F{position - 2}")
            position += 2
            count += 1
    sheet.print_title_rows = "1:2"


def _write_measurements(document, sheet, section, links):
    """Keep each variable-width template table and its independent outputs together."""
    position = 3
    count = 0
    for category, items in category_groups(document.measurements):
        if count and section.each_item_page:
            sheet.row_breaks.append(Break(id=position - 1))
        _text(sheet, position, 1, category).font = Font(bold=True, size=12)
        position += 1
        for offset, (index, measurement) in enumerate(items):
            if offset and section.each_item_page:
                sheet.row_breaks.append(Break(id=position - 1))
            links.measurement_headings.setdefault(index, sheet_ref(sheet, f"A{position}"))
            _text(
                sheet, position, 1, f"{measurement.number}. {measurement.description or measurement.template}"
            ).font = Font(bold=True, size=10)
            _text(sheet, position + 1, 1, f"{measurement.category} · {measurement.template}")
            numeric = tuple(
                i + 2
                for i in measurement.numeric_columns
                if all(_is_number(record[i]) for record in measurement.records)
            )
            records = [(number, *record) for number, record in enumerate(measurement.records, 1)]
            _table(
                sheet,
                ("Sl. No.", *measurement.columns),
                records,
                (1, *numeric),
                start_row=position + 2,
                numeric_format="General",
            )
            records_header = position + 2
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
            _measurement_totals(sheet, position, records_header, measurement, index, links)
            for code in dict.fromkeys(
                output.code for output in measurement.outputs if output.code in links.measured_codes
            ):
                cell = _text(sheet, position + len(measurement.outputs) + 1, 2, "Quantity C/o " + code)
                links.carry.append((cell, code))
                position += 1
            links.measurement_sheets.add(sheet)
            position += len(measurement.outputs) + 3
            count += 1
    sheet.print_title_rows = "1:2"
    sheet.page_setup.orientation = "portrait"


def _write_fixed_table(document, sheet, section, links):
    """Keep numeric types and totals correct when columns move or are omitted."""
    columns, rows = table_values(document, section, excel=True)
    _table(
        sheet,
        tuple(column.title for column in columns),
        rows,
        tuple(index for index, column in enumerate(columns, 1) if column.numeric),
    )
    column_by_key = {column.key: index for index, column in enumerate(columns, 1)}
    _fixed_formulas(document, sheet, section.kind, column_by_key, links)
    if section.kind not in ("abstract", "schedule"):
        if section.kind in ("resources", "resource_usage"):
            sheet.page_setup.orientation = "portrait"
        return
    # The total remains a separate summary even when Amount is hidden or first.
    keys = [column.key for column in columns]
    amount_column = max(2, keys.index("amount") + 1) if "amount" in keys else 2
    label_column = 2 if section.kind == "schedule" and section.columns is None else 1
    _text(sheet, len(rows) + 5, label_column, "Estimate total")
    sum_column = column_by_key.get("amount")
    total_row = len(rows) + 5
    if sum_column and rows:
        letter = get_column_letter(sum_column)
        _formula(sheet, total_row, amount_column, f"SUM({letter}4:{letter}{len(rows) + 3})")
    else:
        sheet.cell(total_row, amount_column, Decimal(document.total)).number_format = "#,##0.00"


def _workbook_links(document, destinations):
    """Index known catalog cells and reserve room beside measurement tables."""
    has_abstract = any(section.kind == "measurement_abstract" for section, _, _ in destinations)
    links = WorkbookLinks(
        measured_codes={value.item.code for value in measured_items(document)} if has_abstract else set(),
        measurement_input_start=max([6, *(len(item.columns) + 1 for item in document.measurements)]) + 2,
    )
    for section, sheet, _ in destinations:
        if section.kind != "resources":
            continue
        columns, _ = table_values(document, section, excel=True)
        for row_index, resource in enumerate(document.resources, 4):
            for column, choice in enumerate(columns, 1):
                if choice.key in ("rate", "tax", "discount"):
                    address = f"{get_column_letter(column)}{row_index}"
                    links.resources.setdefault((resource.code, choice.key), sheet_ref(sheet, address))
    return links


def _fixed_formulas(document, sheet, kind, columns, links):
    """Keep accepted overrides and cross-reference compatible rate cells."""
    amount, rate, quantity = (columns.get(key) for key in ("amount", "rate", "quantity"))
    if kind == "abstract" and amount:
        for index, row in enumerate(document.abstract, 4):
            links.category_amounts.append((sheet.cell(index, amount), row.category_id))
    if kind not in ("schedule", "resource_usage"):
        return
    categories = {}
    for index, row in enumerate(getattr(document, kind), 4):
        if kind == "schedule":
            if not row.unit:
                continue
            if rate:
                links.analysis_rates.append((sheet.cell(index, rate), row.code, row.rate))
            if amount:
                first, _ = categories.get(row.category_id, (index, index))
                categories[row.category_id] = (first, index)
        if kind == "resource_usage" and rate and (row.code, "rate") in links.resources:
            _formula(sheet, index, rate, adjusted_rate(row.code, row, links.resources))
        if quantity and rate and amount:
            _formula(
                sheet, index, amount, f"ROUND({get_column_letter(quantity)}{index}*{get_column_letter(rate)}{index},2)"
            )
    if kind == "schedule" and amount:
        letter = get_column_letter(amount)
        for category, (first, last) in categories.items():
            links.schedule_amounts.setdefault(category, sheet_ref(sheet, f"{letter}{first}:{letter}{last}"))


def _is_number(value):
    """Custom record columns can contain both blank and numeric values."""
    if value == "":
        return True
    try:
        return Decimal(value).is_finite()
    except InvalidOperation:
        return False


def _measurement_totals(sheet, header, records_header, measurement, index, links):
    """Sum independently captured record contributions for each installed template."""
    weights = measurement.total_weights
    for output_index, _ in enumerate(measurement.outputs):
        row = header + output_index + 1
        links.measurement_quantities.setdefault((index, output_index), sheet_ref(sheet, f"E{row}"))
        if not measurement.sum_records:
            continue
        if not measurement.record_totals:
            _formula(sheet, row, 5, "SUM(0)", "General")
            continue
        terms = []
        for component in range(len(weights)) if weights else (output_index,):
            column = _contribution_column(sheet, records_header, measurement, component, links)
            letter = get_column_letter(column)
            first = records_header + 1
            last = records_header + len(measurement.record_totals)
            term = f"SUM({letter}{first}:{letter}{last})"
            if weights:
                weight = sheet.cell(records_header - 1, column, Decimal(weights[component])).coordinate
                term = f"{term}*{weight}"
            terms.append(term)
        _formula(sheet, row, 5, "ROUND(" + "+".join(terms) + ",3)", "General")


def _contribution_column(sheet, header, measurement, component, links):
    """Link to a visible output when it agrees with the engine's contribution."""
    values = [Decimal(record[component]) for record in measurement.record_totals]
    if measurement.output_columns:
        visible = measurement.output_columns[component] + 2
        cells = [sheet.cell(row, visible) for row in range(header + 1, header + 1 + len(values))]
        if all(cell.data_type == "n" and cell.value == value for cell, value in zip(cells, values)):
            return visible
    # Steel and templates whose display precision differs keep exact, editable
    # contributions beside the printed table.
    column = links.measurement_input_start + component
    caption = f"Length {component + 1}" if measurement.total_weights else measurement.outputs[component].label
    _text(sheet, header, column, caption + " contribution")
    sheet.column_dimensions[get_column_letter(column)].width = 19
    for row, value in enumerate(values, header + 1):
        sheet.cell(row, column, value)
    return column


def _write_measurement_abstract(document, sheet, section, links):
    """Write brought-forward entries, their worksheet links and formula totals."""
    rows, pending, totals = [], [], []
    for category, items in category_groups(measured_items(document)):
        rows.append(("", category, "", ""))
        for _, measured in items:
            item = measured.item
            rows.append((item.code, item_description(item.description, section), item.unit, ""))
            links.abstract_headings.setdefault(item.code, sheet_ref(sheet, f"A{len(rows) + 3}"))
            start = len(rows) + 4
            for entry in measured.entries:
                rows.append(("", f"Qty B/F [Measurement {entry.number}]", entry.output.unit, entry.output.quantity))
                pending.append((len(rows) + 3, entry.index, entry.output_index))
            totals.append((len(rows) + 4, start, len(rows) + 3))
            rows.append(("", "Total", item.unit, measured.total))
    _table(sheet, ("Code", "Description", "Unit", "Quantity"), rows, (4,))
    for row, index, output in pending:
        links.forward.append((sheet.cell(row, 2), sheet.cell(row, 4), index, output))
    for row, first, last in totals:
        _formula(sheet, row, 4, f"SUM(D{first}:D{last})", "General")
    sheet.page_setup.orientation = "portrait"


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
