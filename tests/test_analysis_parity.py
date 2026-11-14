import copy
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from modern.backend.service import Service
from modern.backend.numbers import decimal

FIXTURE = Path("estimator/database/DSREM2022.eproj")


class AnalysisParity(unittest.TestCase):
    def setUp(self):
        self.s = Service()

    def tearDown(self):
        self.s.close()

    def command(self, method, **p):
        return self.s.call(method, dict(revision=self.s.revision, **p))

    def resource(self, group, code="R", **extra):
        return self.command(
            "resource.add",
            id=group,
            code=code,
            description="Resource",
            unit="kg",
            rate="10",
            **extra
        )

    def test_selection_insertion_and_entry_metadata(self):
        group = self.s.state()["rows"][0]["id"]
        self.command("add", id=group, kind="Weight", value="1/100")
        self.assertEqual(self.s.state()["rows"][1]["kind"], "Weight")
        self.command("edit", id=group, field="code", value="A1")
        self.resource(
            group,
            qty="2*3",
            remarks="First entry",
            reference="Quotation",
            category="Materials",
        )
        first = self.s.state()["rows"][0]["_children"][0]
        self.resource(first["id"], code="R2")
        children = self.s.state()["rows"][0]["_children"]
        self.assertEqual([r["code"] for r in children], ["R", "R2"])
        self.assertEqual(children[1]["value"], "0")
        self.assertEqual(children[0]["remarks"], "First entry")
        self.assertEqual(children[0]["reference"], "Quotation")
        self.command("analysis.edit", field="ana_remarks", value="Analysis\nnotes")
        self.assertEqual(self.s.state()["ana_remarks"], "Analysis\nnotes")
        self.command("undo")
        self.assertEqual(self.s.state()["ana_remarks"], "")

    def test_batch_preview_apply_atomic_undo_and_validation(self):
        group = self.s.state()["rows"][0]["id"]
        self.resource(group, qty="2")
        row = self.s.state()["rows"][0]["_children"][0]
        original = self.s.state()
        history = len(self.s.history)
        operations = [dict(method="edit", id=row["id"], field="value", value="3*2"), dict(method="edit", id=row["id"], field="rate", value="15.555")]
        preview = self.command("analysis.batch.preview", operations=operations)
        self.assertEqual(preview["rows"][0]["_children"][0]["amount"], "93.36")
        self.assertEqual(self.s.state(), original)
        self.assertEqual(len(self.s.history), history)
        applied = self.command("analysis.batch", operations=operations)
        self.assertEqual(applied["rate"], preview["rate"])
        self.assertEqual(len(self.s.history), history + 1)
        self.command("undo")
        self.assertEqual(self.s.state()["rows"], original["rows"])
        self.command("redo")
        before = self.s.state()
        for method in ("analysis.batch", "analysis.batch.preview"):
            with self.assertRaises(ValueError):
                self.command(method, operations=[dict(method="edit", id=row["id"], field="value", value="9"), dict(method="edit", id=row["id"], field="rate", value="1/0")])
            self.assertEqual(self.s.state(), before)
        with self.assertRaises(ValueError):
            self.command("analysis.batch", operations=[dict(method="project.save")])
        with self.assertRaises(ValueError):
            self.s.call("analysis.batch", dict(revision=original["revision"], operations=operations))

    def test_configurable_template_uses_existing_rows_and_one_undo(self):
        rows = self.s.call("analysis.template_rows", {})
        group = self.s.state()["rows"][0]["id"]
        original = self.s.state()["rows"]
        operations = [dict(method="add", **row) for row in rows]
        preview = self.command("analysis.batch.preview", id=group, operations=operations)
        result = self.command("analysis.batch", id=group, operations=operations)
        self.assertEqual([r["description"] for r in result["rows"][1:1+len(rows)]], [r["description"] for r in rows])
        self.assertEqual(result["rate"], preview["rate"])
        self.command("undo")
        self.assertEqual(self.s.state()["rows"], original)

    def test_independent_duplicate_and_resource_replacement(self):
        group = self.s.state()["rows"][0]["id"]
        self.resource(group, qty="2")
        row = self.s.state()["rows"][0]["_children"][0]
        self.command("resource.duplicate", id=row["id"], code="COPY")
        children = self.s.state()["rows"][0]["_children"]
        self.assertEqual([r["code"] for r in children], ["R", "COPY"])
        self.assertEqual(children[1]["value"], "0")
        self.command("edit", id=children[1]["id"], field="rate", value="20")
        self.assertEqual(self.s.model.resources["R"].rate, Decimal("10"))
        self.command("edit", id=row["id"], field="code", value="COPY")
        self.assertEqual(self.s.state()["rows"][0]["_children"][0]["value"], "2")
        self.command("undo")
        self.assertEqual(self.s.state()["rows"][0]["_children"][0]["code"], "R")

    def test_copy_paste_position_and_definitions_are_not_overwritten(self):
        group = self.s.state()["rows"][0]["id"]
        self.resource(group, qty="2")
        row = self.s.state()["rows"][0]["_children"][0]
        self.command("copy", ids=[row["id"]])
        self.command("edit", id=row["id"], field="rate", value="15")
        self.command("paste", id=row["id"])
        self.assertEqual(self.s.model.resources["R"].rate, Decimal("15"))
        self.assertEqual(len(self.s.model.ana_items[0]["resource_list"]), 2)
        self.command("copy", ids=[group, row["id"]])
        self.command("paste", id=self.s.state()["rows"][-1]["id"])
        self.assertEqual(len(self.s.model.ana_items[-1]["resource_list"]), 1)
        self.command("undo")
        self.assertEqual(len(self.s.model.ana_items), 3)

    def test_apply_multiple_items_and_export_without_changing_draft(self):
        self.s.call("project.open", dict(path=str(FIXTURE)))
        codes = [
            r.code
            for r in self.s.db.ScheduleTable.select()
            .join(self.s.db.SequenceTable)
            .distinct()
            .limit(2)
        ]
        self.s.call("analysis.load", dict(code=codes[0]))
        self.command("analysis.edit", field="ana_remarks", value="Applied first item")
        self.command("analysis.apply")
        self.assertFalse(self.s.state()["dirty"])
        self.assertTrue(self.s.state()["workspace_dirty"])
        self.s.call("analysis.load", dict(code=codes[1]))
        self.command("analysis.edit", field="ana_remarks", value="Unsaved second item")
        before = copy.deepcopy(self.s.state())
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / "analysis.xlsx"
            self.s.call("analysis.export_xlsx", dict(path=str(output)))
            self.assertTrue(output.exists())
            self.assertEqual(self.s.state(), before)
            with self.assertRaises(FileExistsError):
                self.s.call("analysis.export_xlsx", dict(path=str(output)))
            self.s.call("project.save_copy", dict(path=str(Path(d) / "project.eproj")))
            self.assertFalse(self.s.state()["workspace_dirty"])
        self.assertEqual(
            self.s.db.get_item(codes[0], modify_res_code=False).ana_remarks,
            "Applied first item",
        )
        self.assertEqual(
            self.s.db.get_item(codes[1], modify_res_code=False).ana_remarks,
            "Unsaved second item",
        )

    def test_resource_entry_rounding_matches_gtk_currency(self):
        group = self.s.state()["rows"][0]["id"]
        self.command(
            "resource.add",
            id=group,
            code="R",
            description="Taxed",
            unit="kg",
            rate="10.055",
            vat="18",
            discount="0",
            qty="1",
        )
        resource = self.s.state()["rows"][0]["_children"][0]
        self.assertEqual(resource["rate"], "10.06")
        self.assertEqual(resource["effective_rate"], "11.87")
        self.command("add", id=group, kind="Round", value="1.3")
        self.assertEqual(self.s.state()["rows"][1]["value"], "1.3")

    def test_bounded_arithmetic(self):
        self.assertEqual(decimal("0.1 + 0.2"), Decimal(".3"))
        self.assertEqual(decimal("(2.5 * 4) / 3"), Decimal("3.333333"))
        for bad in (
            '__import__("os")',
            "True",
            "1/0",
            "2**100",
            "[1][0]",
            "1e999",
            "NaN",
        ):
            with self.assertRaises(ValueError):
                decimal(bad)
