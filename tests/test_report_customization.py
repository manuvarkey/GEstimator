"""Measurement and narrative reports preserve accepted template data and plain text."""

import copy
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from openpyxl import load_workbook

from estimator.data.measurement import MeasurementItemCustom, MeasurementItemHeading, RecordCustom
from estimator.data.schedule import ScheduleDatabase, ScheduleItemModel
from estimator.undo import Stack
from modern.backend.reporting import ReportSpec, build_document
from modern.backend.reporting.html import render_html
from modern.backend.reporting.workbook import write_workbook
from modern.backend.service import Service


class ReportCustomization(unittest.TestCase):
    """Use a multi-output template so filtering cannot silently combine units."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "project.eproj"
        db = ScheduleDatabase(Stack())
        db.create_new_database(str(self.source))
        for code, unit in (("A", "m"), ("B", "m2")):
            db.insert_item(ScheduleItemModel(code, "Work " + code, unit, category="Work"))
        ids = {row.code: row.id for row in db.ScheduleTable.select()}
        meas = db.get_measurement()
        meas.append_item(MeasurementItemHeading(["<Category>"]))
        item = MeasurementItemCustom(plugin="_2_LLLLL")
        item.remark = "<Linked sheet>"
        item.itemnos[:2] = [ids["A"], ids["B"]]
        item.item_remarks[:2] = ["Length", "Area"]
        item.append_record(
            RecordCustom(
                ["=Literal", "", "1/3", "2.3456", "", "", ""], item.cust_funcs, item.total_func_item, item.columntypes
            )
        )
        meas.append_item(item)
        meas.append_item(MeasurementItemCustom(plugin="_1_NLBH"))
        db.set_measurement(meas)
        db.close_database()
        self.original = self.source.read_bytes()
        self.service = Service()
        self.addCleanup(self.service.close)
        self.service.call("project.open", dict(path=str(self.source)))
        self.spec = dict(
            sections=[
                dict(id="measurements", kind="measurements"),
                dict(id="notes", kind="narrative", body="=Notes\n<script>alert(1)</script>"),
                dict(id="other", kind="narrative", body="Other notes"),
            ]
        )

    def document(self, **settings):
        return build_document(self.service.db, self.service.revision, ReportSpec.parse({**self.spec, **settings}))

    def test_template_results_filtering_and_read_only_snapshot(self):
        db = self.service.db
        before = list(db.database.connection().iterdump())
        editor = self.service.project_editor
        ids, history = copy.deepcopy(editor.ids), copy.deepcopy(editor.history)
        document = self.document()
        sheet = document.measurements[0]
        self.assertEqual(sheet.category, "<Category>")
        self.assertEqual(sheet.records[0][0], "=Literal")
        self.assertEqual(sheet.records[0][2:4], ("0.333", "2.346"))
        self.assertEqual(
            [(r.code, r.unit, r.quantity) for r in sheet.outputs[:2]], [("A", "m", "0.333"), ("B", "m2", "2.346")]
        )
        identity = str(db.ScheduleTable.get(code="A").id)
        filtered = self.document(item_ids=[identity])
        self.assertEqual(len(filtered.measurements), 1)
        self.assertEqual(len(filtered.measurements[0].outputs), 5)
        self.assertEqual(len(document.measurements), 2)
        for field in ("item_ids", "category_ids"):
            self.assertEqual(self.document(**{field: []}).measurements, ())
        with patch.object(db, "get_measurement", side_effect=AssertionError("disabled dataset")):
            self.assertEqual(self.document(sections=[]).measurements, ())
        detached = document.to_dict()
        detached["measurements"][0]["records"][0][0] = "changed"
        self.assertEqual(sheet.records[0][0], "=Literal")
        self.assertEqual(before, list(db.database.connection().iterdump()))
        self.assertEqual((ids, history), (editor.ids, editor.history))
        self.assertEqual(self.original, self.source.read_bytes())

    def test_html_and_workbook_keep_text_literal_and_outputs_separate(self):
        document = self.document()
        html = render_html(document)
        self.assertIn("&lt;Linked sheet&gt;", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertNotIn("<script>", html)
        self.assertIn('id="other"><h1>Notes</h1><div class="note-page"><p class="description">Other notes', html)
        self.assertIn('class="section" id="measurements"', html)
        self.assertIn(">Sl. No.</th>", html)
        self.assertIn("<em>A — Length\nB — Area</em>", html)
        path = Path(self.temp.name) / "report.xlsx"
        write_workbook(document, path)
        workbook = load_workbook(path)
        self.addCleanup(workbook.close)
        self.assertEqual(
            [workbook["Section 2"][f"A{row}"].value for row in (4, 5)], ["=Notes", "<script>alert(1)</script>"]
        )
        self.assertEqual(workbook["Section 2"]["A4"].data_type, "s")
        self.assertEqual(workbook["Section 3"]["A4"].value, "Other notes")
        cells = [cell for sheet in workbook for row in sheet for cell in row]
        self.assertTrue(any(cell.data_type == "f" and "SUM(" in cell.value for cell in cells))
        self.assertTrue(any(cell.value == "=Literal" for cell in cells))
        self.assertTrue(any(cell.value == 2.346 and cell.data_type == "n" for cell in cells))
        self.assertEqual(workbook["Section 1"].page_setup.orientation, "portrait")

    def test_measurement_abstract_links_each_output_and_sums_matching_units(self):
        document = self.document(
            sections=[
                dict(id="billed", kind="measurement_abstract", description_words=1),
                dict(id="detail", kind="measurements"),
            ]
        )
        html = render_html(document)
        for target in ("detail:measurement:0", "billed:item:0", "billed:item:1"):
            self.assertIn(f'href="#{target}"', html)
        self.assertIn("Qty B/F [", html)
        self.assertIn("Quantity C/o [", html)
        self.assertIn("Work …", html)
        self.assertEqual(html.count(">Sl. No.</th>"), 2)
        self.assertNotIn("<script>", html)
        path = Path(self.temp.name) / "linked.xlsx"
        write_workbook(document, path)
        with closing(load_workbook(path)) as workbook:
            abstract, details = workbook["Section 1"], workbook["Section 2"]
            self.assertEqual(abstract["D6"].data_type, "f")
            self.assertTrue(abstract["D6"].value.startswith("='Section 2'!E"))
            self.assertEqual(abstract["C6"].value, "m")
            self.assertEqual(abstract["D7"].value, "=SUM(D6:D6)")
            self.assertEqual(abstract["C9"].value, "m2")
            self.assertTrue(abstract["B6"].hyperlink.target.startswith("#'Section 2'!"))
            self.assertTrue(
                any(
                    cell.hyperlink and cell.hyperlink.target.startswith("#'Section 1'!")
                    for row in details
                    for cell in row
                )
            )

    def test_template_constants_and_wide_columns_are_retained(self):
        db = self.service.db
        measurement = db.get_measurement()
        steel = MeasurementItemCustom(plugin="civil_steel_table")
        measurement.append_item(steel)
        db.set_measurement(measurement)
        sheet = self.document().measurements[-1]
        self.assertEqual(
            sheet.properties,
            tuple((caption, str(value)) for caption, value in zip(steel.captions_udata, steel.user_data)),
        )
        self.assertEqual(sheet.columns[10], steel.captions[10] + " · " + str(steel.user_data[0]))
        self.assertEqual([row.quantity for row in sheet.outputs], [str(value) for value in steel.get_total()])
        html = render_html(self.document())
        self.assertIn("Property", html)
        self.assertIn(str(steel.user_data[-1]), html)

    def test_body_validation_and_dirty_draft_protection(self):
        for body in (None, 1, "x" * 60001):
            with self.subTest(body_type=type(body)), self.assertRaises(ValueError):
                ReportSpec.parse(dict(sections=[dict(id="notes", kind="narrative", body=body)]))
        with self.assertRaisesRegex(ValueError, "Only narrative"):
            ReportSpec.parse(dict(sections=[dict(id="s", kind="schedule", body="Text")]))
        editor = self.service.project_editor
        editor.ensure_ids()
        identity = editor.ids[1]
        self.service.call("measurement.draft.open", dict(revision=self.service.revision, id=identity))
        self.service.call("measurement.record_add", dict(revision=self.service.revision, id=identity))
        with self.assertRaisesRegex(ValueError, "Unsaved measurement"):
            self.service.call("report.document", dict(revision=self.service.revision, specification=self.spec))
        self.assertTrue(editor.measurement_draft.dirty)
