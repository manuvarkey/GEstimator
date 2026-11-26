"""Accepted analysis/catalog/usage datasets retain engine semantics and snapshot safety."""

import copy
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from openpyxl import load_workbook

from estimator import misc
from estimator.data.schedule import ResourceItemModel, ScheduleDatabase, ScheduleItemModel
from estimator.undo import Stack
from modern.backend.reporting import ReportSpec, build_document
from modern.backend.service import Service


class ReportDatasets(unittest.TestCase):
    """Exercise adjustments, row kinds, selection and untouched project state."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "project.eproj"
        db = ScheduleDatabase(Stack())
        db.create_new_database(str(self.source))
        resource = ResourceItemModel(
            "R", "<Material>", "kg", Decimal("10.05"), Decimal("18"), Decimal("5"), "=Quote", "Materials"
        )
        db.insert_resource(ResourceItemModel("UNUSED", "Unused", "m", Decimal("3"), category="Other"))
        for code, qty, category in (("A", "2", "Work"), ("B", "3", "Services"), ("DEP", "10", misc.SUB_ANA_TITLE)):
            model = ScheduleItemModel(
                code, "Work " + code, "m", Decimal("99"), Decimal(qty), category=category, ana_remarks="<Notes>"
            )
            model.resources = {"R": resource}
            model.add_ana_group("Materials", code="M")
            model.add_ana_res(["R", Decimal("2.5"), "=Entry remark"], 0)
            model.add_ana_weight("10%", Decimal(".1"))
            model.add_ana_weight("20% of group", Decimal(".2"))
            model.add_ana_sum("Subtotal")
            model.add_ana_times("Half", Decimal(".5"))
            model.add_ana_round("Say", Decimal("0"))
            db.insert_item(model)
        db.close_database()
        self.original = self.source.read_bytes()
        self.service = Service()
        self.addCleanup(self.service.close)
        self.service.call("project.open", dict(path=str(self.source)))
        self.spec = dict(sections=[dict(id=kind, kind=kind) for kind in ("analyses", "resources", "resource_usage")])

    def report(self, **settings):
        return self.service.call(
            "report.document", dict(revision=self.service.revision, specification={**self.spec, **settings})
        )

    def test_analysis_parity_adjustments_and_project_preservation(self):
        db = self.service.db
        before = list(db.database.connection().iterdump())
        history = copy.deepcopy(self.service.project_editor.history)
        result = self.report()
        self.assertEqual(result["total"], "495.00")
        self.assertEqual([row["code"] for row in result["analyses"]], ["A", "B"])
        for analysis in result["analyses"]:
            model = db.get_item(analysis["code"], modify_res_code=False)
            self.assertEqual(analysis["stored_rate"], "99")
            self.assertEqual(analysis["calculated_rate"], str(model.get_ana_rate()))
            self.assertEqual(analysis["calculated_rate"], "18")
            self.assertEqual(
                [row["amount"] for row in analysis["rows"]],
                ["", "28.18", "28.18", "2.82", "5.64", "36.64", "18.32", "18"],
            )
            resource = analysis["rows"][1]
            self.assertEqual(resource["rate"], "11.27")
            self.assertIn("[=Quote]", resource["description"])
            self.assertEqual(resource["remarks"], "=Entry remark")
        self.assertEqual(before, list(db.database.connection().iterdump()))
        self.assertEqual(history, self.service.project_editor.history)
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_usage_engine_filter_rounding_and_catalog_selection(self):
        report = self.report()
        self.assertEqual({row["code"] for row in report["resources"]}, {"R", "UNUSED"})
        usage = report["resource_usage"][0]
        self.assertEqual((usage["quantity"], usage["rate"], usage["amount"]), ("6.2500", "11.27", "70.44"))
        db = self.service.db
        identity = str(db.ScheduleTable.get(code="A").id)
        selected = self.report(item_ids=[identity])
        self.assertEqual([row["code"] for row in selected["analyses"]], ["A"])
        self.assertEqual([row["code"] for row in selected["resources"]], ["R"])
        self.assertEqual(selected["resource_usage"][0]["quantity"], "2.5000")
        self.assertEqual(db.get_res_usage(codes=["A"])["Materials"]["R"][3], Decimal("2.5000"))
        self.assertEqual(db.get_res_usage()["Materials"]["R"][3], Decimal("18.7500"))
        self.assertTrue(all(not rows for rows in db.get_res_usage(codes=[]).values()))
        for field in ("item_ids", "category_ids"):
            empty = self.report(**{field: []})
            self.assertEqual([empty[name] for name in ("analyses", "resources", "resource_usage")], [[], [], []])

    def test_disabled_sections_skip_extra_reads_and_nested_values_are_frozen(self):
        db = self.service.db
        with patch.object(db, "get_res_usage", side_effect=AssertionError("unused dataset")):
            default = self.service.call("report.document", dict(revision=self.service.revision))
        self.assertEqual(default["analyses"], [])
        snapshot = build_document(db, self.service.revision, ReportSpec.parse(self.spec))
        with self.assertRaises(FrozenInstanceError):
            snapshot.analyses[0].rows[0].amount = "0"
        data = snapshot.to_dict()
        data["analyses"][0]["rows"][1]["amount"] = "0"
        self.assertEqual(snapshot.analyses[0].rows[1].amount, "28.18")

    def test_all_formats_share_new_sections_and_literal_text(self):
        preview = self.service.call("report.preview", dict(revision=self.service.revision, specification=self.spec))
        html = preview["html"]
        self.assertIn("&lt;Material&gt;", html)
        self.assertIn("&lt;Notes&gt;", html)
        self.assertIn("Calculated analysis rate: 18", html)
        self.assertIn('href="#analyses:analysis:0"', html)
        self.assertIn('class="section wide" id="resources"', html)
        path = Path(self.temp.name) / "report.xlsx"
        self.service.call(
            "report.export",
            dict(revision=self.service.revision, specification=self.spec, format="xlsx", path=str(path)),
        )
        workbook = load_workbook(path)
        self.addCleanup(workbook.close)
        analysis, catalog, usage = (workbook[f"Section {index}"] for index in (1, 2, 3))
        self.assertEqual(analysis["A4"].value, "Stored rate")
        self.assertEqual(analysis["F4"].value, 99)
        self.assertEqual(analysis["G6"].value, 28.18)
        resource_row = next(row for row in catalog if row[0].value == "R")
        self.assertEqual(resource_row[6].value, "=Quote")
        self.assertEqual(resource_row[6].data_type, "s")
        self.assertEqual(usage["D4"].value, 6.25)
        self.assertEqual(usage["F4"].value, 70.44)
        self.assertEqual(catalog.page_setup.orientation, "landscape")
        self.assertFalse(any(cell.data_type == "f" for sheet in workbook for row in sheet for cell in row))
