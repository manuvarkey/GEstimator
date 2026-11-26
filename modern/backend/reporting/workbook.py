"""Excel presentation of the same immutable data used by HTML/PDF reports."""

from decimal import Decimal

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .document import ReportDocument


def _text(sheet, row, column, value):
    """Store user text literally, including values beginning with an equals sign."""
    cell = sheet.cell(row, column, str(value))
    cell.data_type = "s"
    cell.alignment = Alignment(vertical="top", wrap_text=True)
    return cell


def _table(sheet, headings, rows, numeric=()):
    """Style a printable worksheet with repeated headings and numeric money cells."""
    for column, heading in enumerate(headings, 1):
        cell = _text(sheet, 3, column, heading)
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="E4EEF2")
    for index, values in enumerate(rows, 4):
        for column, value in enumerate(values, 1):
            if column in numeric and value not in (None, ""):
                cell = sheet.cell(index, column, Decimal(value))
                cell.number_format = "General" if headings[column - 1] == "Quantity" else "0.00"
                cell.alignment = Alignment(horizontal="right", vertical="top")
            else:
                _text(sheet, index, column, value or "")
    for column in range(1, len(headings) + 1):
        sheet.column_dimensions[get_column_letter(column)].width = 54 if column == 2 else 20
    sheet.print_title_rows = "1:3"
    sheet.freeze_panes = "A4"
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_setup.orientation = "landscape" if len(headings) > 3 else "portrait"
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.print_options.horizontalCentered = True
    sheet.oddFooter.right.text = "Page &P of &N"
    sheet.oddHeader.left.text = "GEstimator"


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
        sheet = workbook.create_sheet(f"Section {index}")
        _text(sheet, 1, 1, section.title).font = Font(bold=True, size=16)
        _text(sheet, 2, 1, document.project)
        link = _text(contents, index + 1, 1, section.title)
        link.hyperlink = f"#'{sheet.title}'!A1"
        link.style = "Hyperlink"
        if section.kind == "abstract":
            _table(sheet, ("Category", "Amount"), [(row.category, row.amount) for row in document.abstract], (2,))
            _text(sheet, len(document.abstract) + 5, 1, "Estimate total")
            sheet.cell(len(document.abstract) + 5, 2, Decimal(document.total)).number_format = "0.00"
        elif section.kind == "schedule":
            _table(
                sheet,
                ("Code", "Description", "Unit", "Quantity", "Rate", "Amount", "Remarks"),
                [
                    (
                        row.code,
                        row.description,
                        row.unit,
                        row.quantity if row.unit else "",
                        row.rate if row.unit else "",
                        row.amount,
                        row.remarks,
                    )
                    for row in document.schedule
                ],
                (4, 5, 6),
            )
            _text(sheet, len(document.schedule) + 5, 2, "Estimate total")
            sheet.cell(len(document.schedule) + 5, 6, Decimal(document.total)).number_format = "0.00"
        else:
            _table(
                sheet,
                ("Prepared by", "Checked by", "Approved by"),
                [("Name:",) * 3, ("Designation:",) * 3, ("Date:",) * 3],
            )
    contents.column_dimensions["A"].width = 60
    workbook.save(destination)
