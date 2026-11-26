"""Report selection, calculation parity and read-only snapshot regression tests."""

import copy
import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from decimal import Decimal
from pathlib import Path

from estimator import misc
from estimator.data.schedule import ScheduleDatabase, ScheduleItemModel
from estimator.undo import Stack
from modern.backend.reporting import ReportSpec, build_document
from modern.backend.service import Service


class ReportDocuments(unittest.TestCase):
    """Exercise real project service reads without a renderer dependency."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.source = Path(self.temp.name) / "report.eproj"
        db = ScheduleDatabase(Stack())
        db.create_new_database(str(self.source))
        for code, unit, rate, quantity, category, parent in (
            ("H", "", "999", "99", "Work", None),
            ("A", "m", "0.05", "0.1", "Work", "H"),
            ("B", "m", "0.05", "0.1", "Work", "H"),
            ("C", "kg", "7.13", "2", "Services", None),
            ("D", "kg", "500", "10", misc.SUB_ANA_TITLE, None),
        ):
            item = ScheduleItemModel(
                code, "<Work> " + code, unit, Decimal(rate), Decimal(quantity), category=category, parent=parent
            )
            db.insert_item(item)
        settings = db.get_project_settings()
        settings["project_name"] = "<Real project>"
        db.set_project_settings(settings)
        db.close_database()
        self.original = self.source.read_bytes()
        self.service = Service()
        self.service.call("project.open", dict(path=str(self.source)))

    def tearDown(self):
        self.service.close()
        self.assertEqual(self.source.read_bytes(), self.original)
        self.temp.cleanup()

    def report(self, specification=None, **params):
        return self.service.call(
            "report.document", dict(revision=self.service.revision, specification=specification or {}, **params)
        )

    def identity(self, code):
        table = self.service.db.ScheduleTable
        return str(table.get(table.code == code).id)

    def state(self):
        """Capture SQL and transient state beyond the ordinary public state response."""
        service = self.service
        editor = service.project_editor
        return copy.deepcopy(
            (
                list(service.db.database.connection().iterdump()),
                service.state(),
                service.signature(),
                [vars(model) for model in service.history],
                [vars(model) for model in service.future],
                service.clipboard,
                editor.history,
                editor.future,
                editor.clipboard,
                editor.ids,
                editor.record_ids,
            )
        )

    def test_rounding_stored_rates_heading_and_dependency_exclusion(self):
        before = self.state()
        result = self.report()
        self.assertEqual(result["total"], "14.28")
        self.assertEqual([row["code"] for row in result["schedule"]], ["H", "A", "B", "C"])
        self.assertIsNone(result["schedule"][0]["amount"])
        self.assertEqual([row["amount"] for row in result["abstract"]], ["0.02", "14.26"])
        view = self.service.call("schedule.editor.state", {})
        self.assertEqual(result["total"], view["grand_total"])
        self.assertEqual(before, self.state())
        json.dumps(result, allow_nan=False)

    def test_selection_intersection_order_and_empty_selection(self):
        work = self.service.db.ScheduleCategoryTable.get(description="Work")
        result = self.report(dict(item_ids=[self.identity("C"), self.identity("B")]))
        self.assertEqual([row["code"] for row in result["schedule"]], ["B", "C"])
        self.assertEqual(result["total"], "14.27")
        result = self.report(dict(item_ids=[self.identity("C"), self.identity("B")], category_ids=[str(work.id)]))
        self.assertEqual([row["code"] for row in result["schedule"]], ["B"])
        self.assertEqual(result["total"], "0.01")
        for specification in (dict(item_ids=[]), dict(category_ids=[]), dict(item_ids=[self.identity("D")])):
            result = self.report(specification)
            self.assertEqual(result["schedule"], [])
            self.assertEqual(result["abstract"], [])
            self.assertEqual(result["total"], "0.00")

    def test_sections_and_specification_are_detached_and_immutable(self):
        raw = dict(sections=[dict(id="approval", kind="signoff", title="Approval", enabled=False)])
        spec = ReportSpec.parse(raw)
        raw["sections"][0]["title"] = "Changed"
        snapshot = build_document(self.service.db, self.service.revision, spec)
        with self.assertRaises(FrozenInstanceError):
            snapshot.total = "0"
        with self.assertRaises(FrozenInstanceError):
            snapshot.schedule[0].code = "Changed"
        result = snapshot.to_dict()
        self.assertEqual(result["specification"]["sections"][0]["title"], "Approval")
        result["schedule"][1]["amount"] = "999"
        self.assertEqual(snapshot.schedule[1].amount, "0.01")
        self.service.call(
            "schedule.editor.edit", dict(revision=self.service.revision, id=self.identity("C"), field="qty", value="3")
        )
        self.assertEqual(snapshot.total, "14.28")
        before = self.state()
        self.assertEqual(self.report()["total"], "21.41")
        self.assertEqual(before, self.state())
        self.service.call("project.undo", dict(revision=self.service.revision))
        before = self.state()
        self.assertEqual(self.report()["total"], "14.28")
        self.assertEqual(before, self.state())

    def test_malformed_specifications_and_stale_selections_preserve_state(self):
        before = self.state()
        for spec in (
            None,
            [],
            dict(schema_version=True),
            dict(schema_version=2),
            dict(unknown=True),
            dict(sections="schedule"),
            dict(sections=[dict(id="x", kind="missing")]),
            dict(sections=[dict(id="x", kind="schedule", enabled=1)]),
            dict(sections=[dict(id="bad id", kind="schedule")]),
            dict(sections=[dict(id="x", kind="schedule"), dict(id="x", kind="abstract")]),
            dict(item_ids=["0"]),
            dict(item_ids=[1]),
            dict(item_ids=["1", "1"]),
            dict(item_ids=["999999"]),
            dict(category_ids=["999999"]),
            dict(title=3),
        ):
            with self.subTest(spec=spec), self.assertRaises(ValueError):
                self.service.call("report.document", dict(revision=self.service.revision, specification=spec))
        for revision in (None, True, "1", self.service.revision - 1):
            with self.subTest(revision=revision), self.assertRaisesRegex(ValueError, "Stale report"):
                self.service.call("report.document", dict(revision=revision))
        self.assertEqual(before, self.state())

    def test_dirty_analysis_cannot_be_silently_omitted_or_discarded(self):
        self.service.call("analysis.load", dict(code="C"))
        self.service.call("analysis.edit", dict(revision=self.service.revision, field="ana_remarks", value="Draft"))
        before = self.state()
        with self.assertRaisesRegex(ValueError, "Unsaved analysis"):
            self.report(discard=True)
        self.assertEqual(before, self.state())

    def test_dirty_measurement_draft_is_preserved(self):
        from estimator.data.measurement import MeasurementItemCustom

        measurement = self.service.db.get_measurement()
        measurement.append_item(MeasurementItemCustom(plugin="_1_NLBH"))
        self.service.db.set_measurement(measurement)
        editor = self.service.project_editor
        editor.ensure_ids()
        identity = editor.ids[0]
        self.service.call("measurement.draft.open", dict(revision=self.service.revision, id=identity))
        self.service.call("measurement.record_add", dict(revision=self.service.revision, id=identity))
        before = self.state()
        draft = editor.measurement_draft
        with self.assertRaisesRegex(ValueError, "Unsaved measurement"):
            self.report(discard=True)
        self.assertIs(editor.measurement_draft, draft)
        self.assertTrue(draft.dirty)
        self.assertEqual(before, self.state())

    def test_requires_open_project(self):
        self.service.call("project.close", dict(discard=True))
        with self.assertRaisesRegex(ValueError, "Open a project"):
            self.report()


if __name__ == "__main__":
    unittest.main()
