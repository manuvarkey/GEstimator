import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from openpyxl import Workbook
from estimator.data.schedule import ScheduleItemModel
from modern.backend.analysis_import import parse_analyses, read_rows
from modern.backend.importing import import_analysis


class AnalysisImportResilienceTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "analysis.xlsx"

    def write(self, rows):
        book = Workbook()
        for row in rows:
            book.active.append(row)
        book.save(self.path)
        book.close()
        return dict(path=str(self.path))

    def parse(self, rows, settings=(1, -1)):
        return parse_analyses(read_rows(self.write(rows)), settings)

    def test_free_form_layout(self):
        drafts, warnings = self.parse([
            ["Item No. 4.1", None],
            ["4.1", "Brick work in cement mortar"],
            ["", "Details of cost for 10 cum"],
            ["Sl", "Particulars", "UOM", "Qty", "Rate", "Amount"],
            ["", "Materials"],
            ["", "Bricks", "1000 Nos", 5, "5,000.00", "25,000.00"],
            ["", "Cement", "bag", 12, None, 4800],
            ["", "  sourced locally"],
            ["", "Total of materials", None, None, None, 29800],
            ["", "Labour"],
            ["L1", "Mason", "day", 10, 800, 8000],
            ["", "Total", None, None, None, 8000],
            ["", "Total", None, None, None, 37800],
            ["", "Add 1% water charges", None, None, None, 378],
            ["", "Contractor's profit @ 15%", None, None, None, 5670],
            ["", "Total", None, None, None, 43848],
            ["", "Rate per cum", None, None, None, 4384.80],
            ["", "Say", None, None, None, 4385],
        ])
        self.assertEqual(list(drafts), ["4.1"])
        item = drafts["4.1"]
        self.assertEqual(item.ana_remarks, "Details of cost for 10 cum")
        groups = [row for row in item.ana_items if row["itemtype"] == 0]
        self.assertEqual([row["description"] for row in groups], ["Materials", "Labour"])
        cement = groups[0]["resource_list"][1]
        self.assertEqual(item.resources[cement[0]].rate, Decimal("400"))  # rate = amount / qty
        self.assertEqual(cement[2], "sourced locally")
        self.assertTrue(cement[0].startswith("R"))  # generated code for a code-less resource
        kinds = [row["itemtype"] for row in item.ana_items]
        self.assertEqual(kinds, [0, 0, 1, 2, 2, 1, 3, 4])
        self.assertEqual(item.get_ana_rate(), Decimal("4385"))
        self.assertEqual(warnings, [])

    def test_formulas_without_saved_values_are_evaluated(self):
        drafts, warnings = self.parse([
            ["X1", "Formula analysis"],
            ["Code", "Description", "Unit", "Qty", "Rate", "Amount"],
            ["", "MATERIALS"],
            ["M1", "Sand", "cum", 2, 1500.5, "=ROUND(D4*E4,2)"],
            ["M2", "Cement", "bag", "=1+2", 400, "=ROUND(D5*E5,2)"],
            ["", "TOTAL of MATERIALS", None, None, None, "=SUM(F4:F5)"],
            ["", "Add water @ 1%", None, None, None, "=ROUND(0.01*F6,2)"],
            ["", "Say", None, None, None, "=MROUND(F6+F7,0.05)"],
        ])
        item = drafts["X1"]
        self.assertEqual(item.ana_items[0]["resource_list"][1][1], Decimal("3"))
        self.assertEqual(item.ana_items[1]["value"], Decimal("0.01"))
        self.assertEqual(item.get_ana_rate(), Decimal("4243"))
        self.assertEqual(warnings, [])

    def test_gestimator_export_details_restore_tax_and_discount(self):
        drafts, _ = self.parse([
            ["E1", "Exported"],
            [None, "remark"],
            ["Code", "Description", "Unit", "Qty", "Rate", "Amount"],
            [None, "MATERIALS"],
            ["R1", "Steel\n(Basic rate 100 [Vendor] + Tax @18% - Discount @5%)", "kg", 2, 112.1, 224.2],
            [None, "TOTAL of MATERIALS", None, None, None, 224.2],
        ])
        resource = drafts["E1"].resources["R1"]
        self.assertEqual((resource.description, resource.rate, resource.vat, resource.discount, resource.reference),
                         ("Steel", Decimal("100"), Decimal("18"), Decimal("5"), "Vendor"))
        self.assertEqual(drafts["E1"].ana_remarks, "remark")

    def test_unusable_rows_are_reported_not_fatal(self):
        drafts, warnings = self.parse([
            ["Q1", "Item"],
            ["Code", "Description", "Unit", "Qty", "Rate", "Amount"],
            ["", "MATERIALS"],
            ["M1", "Sand", "cum", 2, 100, 200],
            ["", "TOTAL", None, None, None, 200],
            ["", "Mystery adjustment", None, None, None, 5000],
            ["", "Say", None, None, None, 200],
            ["", "Description", "Unit"],
        ])
        self.assertEqual(drafts["Q1"].get_ana_rate(), Decimal("200"))
        self.assertTrue(any("Mystery adjustment" in warning for warning in warnings))
        self.assertTrue(any("without an item code" in warning for warning in warnings))

    def test_single_import_uses_first_analysis(self):
        params = self.write([
            ["A", "First"], ["Code", "Description", "Unit", "Qty", "Rate", "Amount"],
            ["", "MATERIALS"], ["M1", "Sand", "cum", 2, 100, 200], ["", "Say", None, None, None, 200],
        ])
        warnings = []
        draft = import_analysis(ScheduleItemModel("TARGET", "Target", "m"), params, warnings)
        self.assertEqual((draft.code, draft.get_ana_rate(), warnings), ("TARGET", Decimal("200"), []))
