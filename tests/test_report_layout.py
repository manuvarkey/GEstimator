"""Column projection and mixed page layouts preserve authoritative report values."""

import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook

from estimator.data.schedule import ResourceItemModel, ScheduleDatabase, ScheduleItemModel
from estimator.undo import Stack
from modern.backend.reporting import ReportSpec, build_document
from modern.backend.reporting.html import render_html
from modern.backend.reporting.tables import COLUMNS, table_values
from modern.backend.reporting.workbook import write_workbook


class ReportLayout(unittest.TestCase):
    """Check reordered numeric/text cells, independent instances and rejected settings."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = ScheduleDatabase(Stack())
        self.db.create_new_database(str(Path(self.temp.name) / "project.eproj"))
        self.addCleanup(self.db.close_database)
        self.db.insert_item(ScheduleItemModel("H", "Heading", category="Work"))
        item = ScheduleItemModel(
            "A", "=Literal", "m", Decimal("12.34"), Decimal("1.2345"), category="Work", remarks="<Remark>"
        )
        item.resources = {"R": ResourceItemModel("R", "Material", "kg", Decimal("2"), category="Materials")}
        item.add_ana_group("Materials")
        item.add_ana_res(["R", Decimal("2"), ""], 0)
        item.add_ana_sum("Total")
        self.db.insert_item(item)

    def document(self, sections):
        return build_document(self.db, 1, ReportSpec.parse(dict(sections=sections)))

    def workbook(self, document):
        path = Path(self.temp.name) / "report.xlsx"
        write_workbook(document, path)
        workbook = load_workbook(path)
        self.addCleanup(workbook.close)
        return workbook

    def test_ordered_columns_agree_in_html_and_excel_without_changing_snapshot(self):
        before = list(self.db.database.connection().iterdump())
        columns = ["amount", "description", "quantity", "remarks"]
        document = self.document(
            [
                dict(id="custom", kind="schedule", columns=columns, orientation="landscape"),
                dict(id="brief", kind="schedule", columns=["code"], orientation="portrait"),
            ]
        )
        html = render_html(document)
        self.assertIn('class="section wide" id="custom"', html)
        self.assertIn('class="section portrait" id="brief"', html)
        self.assertLess(html.index(">Amount</th>"), html.index(">Description</th>"))
        self.assertIn("&lt;Remark&gt;", html)
        self.assertEqual(document.total, "15.23")
        workbook = self.workbook(document)
        sheet = workbook["Section 1"]
        self.assertEqual([cell.value for cell in sheet[3]], ["Amount", "Description", "Quantity", "Remarks"])
        self.assertIsNone(sheet["A4"].value)
        self.assertEqual(sheet["A5"].value, 15.23)
        self.assertEqual(sheet["B5"].value, "=Literal")
        self.assertEqual(sheet["B5"].data_type, "s")
        self.assertEqual(sheet["C5"].value, 1.2345)
        self.assertEqual(sheet["C5"].number_format, "General")
        self.assertEqual((sheet["A7"].value, sheet["B7"].value), ("Estimate total", "=SUM(A4:A5)"))
        brief = workbook["Section 2"]
        self.assertEqual((brief["A7"].value, brief["B7"].value), ("Estimate total", 15.23))
        self.assertEqual((sheet.page_setup.orientation, brief.page_setup.orientation), ("landscape", "portrait"))
        columns.reverse()
        self.assertEqual(document.specification.sections[0].columns[0], "amount")
        self.assertEqual(before, list(self.db.database.connection().iterdump()))

    def test_every_fixed_table_supports_projection_and_default_columns(self):
        for kind, choices in COLUMNS.items():
            with self.subTest(kind=kind):
                document = self.document(
                    [dict(id="a", kind=kind, columns=[column.key for column in reversed(choices)])]
                )
                columns, rows = table_values(document, document.specification.sections[0])
                self.assertEqual([column.key for column in columns], [column.key for column in reversed(choices)])
                sheet = self.workbook(document)["Section 1"]
                self.assertEqual([cell.value for cell in sheet[3]], [column.title for column in reversed(choices)])
                self.assertTrue(rows)
        default = self.document([dict(id="a", kind="schedule")])
        section = default.specification.sections[0]
        self.assertEqual(len(table_values(default, section)[0]), 6)
        self.assertEqual(len(table_values(default, section, excel=True)[0]), 7)
        self.assertEqual(section.orientation, "auto")

    def test_explicit_orientation_overrides_all_section_defaults(self):
        kinds = [
            "abstract",
            "schedule",
            "analyses",
            "resources",
            "resource_usage",
            "measurements",
            "narrative",
            "signoff",
        ]
        for orientation in ("portrait", "landscape"):
            document = self.document(
                [dict(id=kind, kind=kind, orientation=orientation, new_page=True) for kind in kinds]
            )
            sheets = list(self.workbook(document))[2:]
            self.assertEqual([sheet.page_setup.orientation for sheet in sheets], [orientation] * len(kinds))
            html = render_html(document)
            css = "portrait" if orientation == "portrait" else "wide"
            for kind in kinds:
                self.assertIn(f'class="section {css}" id="{kind}"', html)

    def test_malformed_columns_and_orientations_are_rejected(self):
        for value in ([], "code", ["code", "code"], ["unknown"], [None], [["code"]], ["body"]):
            with self.subTest(columns=value), self.assertRaises(ValueError):
                self.document([dict(id="a", kind="schedule", columns=value)])
        for kind in ("narrative", "measurements", "analyses", "signoff"):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.document([dict(id="a", kind=kind, columns=["code"])])
        for value in (None, 1, True, [], "wide", "@page"):
            with self.subTest(orientation=value), self.assertRaises(ValueError):
                self.document([dict(id="a", kind="schedule", orientation=value)])

    def test_typography_margins_and_column_proportions_match_export_intent(self):
        spec = ReportSpec.parse(
            dict(
                font_family="DejaVu Serif",
                font_scale=1.25,
                organization="Office &P",
                sections=[dict(id="schedule", kind="schedule")],
            )
        )
        document = build_document(self.db, 1, spec)
        html = render_html(document)
        self.assertIn("margin:20mm", html)
        self.assertIn("font-size:12.5pt", html)
        self.assertIn('font-family:"DejaVu Serif",sans-serif', html)
        self.assertIn('class="report-footer">Office &amp;P', html)
        self.assertIn('content:"Page " counter(page) " of " counter(pages)', html)
        self.assertNotIn("@top-left", html)
        self.assertNotIn("@top-right", html)
        self.assertIn("<colgroup>", html)
        workbook = self.workbook(document)
        for sheet in workbook:
            for side in ("left", "right", "top", "bottom"):
                self.assertAlmostEqual(getattr(sheet.page_margins, side) * 25.4, 20)
            self.assertEqual(sheet["A1"].font.name, "DejaVu Serif")
        sheet = workbook["Section 1"]
        self.assertEqual(sheet["A1"].font.sz, 20)
        self.assertEqual(sheet.oddFooter.left.text, "Office &&P · GEstimator")
        self.assertGreater(sheet.column_dimensions["B"].width, sheet.column_dimensions["A"].width * 2)
        self.assertGreater(sheet.column_dimensions["F"].width, sheet.column_dimensions["C"].width)
        self.assertEqual(sheet["E5"].value, 12.34)

    def test_font_input_is_bounded_and_cannot_inject_css_or_html(self):
        for value in (None, True, 0.59, 2.01, float("nan"), float("inf"), "1.2", []):
            with self.subTest(scale=value), self.assertRaises(ValueError):
                ReportSpec.parse(dict(font_scale=value))
        for value in (None, 5, "x" * 201, "Font\nname"):
            with self.subTest(family=value), self.assertRaises(ValueError):
                ReportSpec.parse(dict(font_family=value))
        spec = ReportSpec.parse(dict(font_family='Font";}</style><script>alert(1)</script>', font_scale=2))
        html = render_html(build_document(self.db, 1, spec))
        self.assertNotIn("<script>", html)
        self.assertEqual(html.count("</style>"), 1)
        self.assertEqual(ReportSpec.parse({}).font_scale, 1)
        self.assertEqual(ReportSpec.parse({}).font_family, "")
