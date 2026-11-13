import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from decimal import Decimal
from estimator import misc
from estimator.data.schedule import ScheduleDatabase
from estimator.undo import Stack
from modern.backend.service import Service

FIXTURE = Path("estimator/database/DSREM2022.eproj")


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.s = Service()

    def tearDown(self):
        self.s.close()

    def command(self, method, **params):
        return self.s.call(method, dict(revision=self.s.revision, **params))

    def test_edits_copy_move_undo_validation(self):
        group = self.s.state()["rows"][0]["id"]
        self.command(
            "resource.add",
            id=group,
            code="R",
            description="Long\nresource",
            unit="kg",
            rate="10.05",
            vat="18",
            discount="5",
            qty="2.5",
        )
        row = self.s.state()["rows"][0]["_children"][0]
        self.assertEqual(row["amount"], "28.18")
        self.command("copy", ids=[row["id"]])
        self.command("paste", id=group)
        self.assertEqual(self.s.state()["rate"], "56.36")
        self.command("undo")
        self.assertEqual(self.s.state()["rate"], "28.18")
        self.command("redo")
        self.assertEqual(self.s.state()["rate"], "56.36")
        self.command("move", id=group, delta=1)
        self.assertEqual(self.s.state()["rows"][1]["id"], group)
        before = self.s.state()
        for bad in ("NaN", "Infinity", "1e999", "0.00000000000001"):
            with self.assertRaises(ValueError):
                self.command("edit", id=row["id"], field="value", value=bad)
            self.assertEqual(self.s.state(), before)
        with self.assertRaises(ValueError):
            self.s.call("edit", dict(revision=-1))
        self.command("delete", ids=[group])
        self.command("undo")
        self.assertEqual(self.s.state()["rows"][1]["id"], group)

    def test_project_roundtrip_original_untouched_and_export(self):
        original = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
        self.s.call("project.open", dict(path=str(FIXTURE)))
        db = self.s.db
        code = db.ScheduleTable.select().join(db.SequenceTable).get().code
        state = self.s.call("analysis.load", dict(code=code))
        self.assertTrue(state["rows"])
        self.command(
            "edit",
            id=state["rows"][0]["id"],
            field="description",
            value="Edited\nMaterials",
        )
        resource_row = next(r for g in state["rows"] for r in g.get("_children", []))
        self.command("edit", id=resource_row["id"], field="rate", value="123.45")
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "copy.eproj"
            self.s.call("project.save_copy", dict(path=str(target)))
            self.assertFalse(self.s.state()["dirty"])
            with self.assertRaises(FileExistsError):
                self.s.call("project.save_copy", dict(path=str(target)))
            other = ScheduleDatabase(Stack())
            other.open_database(str(target))
            self.assertEqual(
                other.get_item(code, modify_res_code=False).ana_items[0]["description"],
                "Edited\nMaterials",
            )
            self.assertEqual(
                other.get_resource(resource_row["code"]).rate, Decimal("123.45")
            )
            saved_item = other.get_item(code, modify_res_code=False)
            self.assertEqual(saved_item.rate, saved_item.get_ana_rate())
            self.assertEqual(
                dict(other.ProjectTable.select().tuples()),
                dict(db.ProjectTable.select().tuples()),
            )
            sheet = misc.Spreadsheet()
            other.export_ana_item_spreadsheet(code, sheet)
            sheet.save(Path(d) / "analysis.xlsx")
            loaded = misc.Spreadsheet(Path(d) / "analysis.xlsx")
            self.assertTrue(
                any(str(c.value).startswith("=") for row in loaded.sheet for c in row)
            )
            other.close_database()
        self.assertEqual(hashlib.sha256(FIXTURE.read_bytes()).hexdigest(), original)

    def test_transaction_rollback_and_resource_paging(self):
        self.s.call("project.open", dict(path=str(FIXTURE)))
        db = self.s.db
        row = db.ResourceTable.select().get()
        original = row.rate
        with self.assertRaises(RuntimeError):
            with db.database.atomic():
                db.ResourceTable.update(rate=999).where(
                    db.ResourceTable.id == row.id
                ).execute()
                raise RuntimeError()
        self.assertEqual(db.ResourceTable.get_by_id(row.id).rate, original)
        page = self.s.call("resources.search", dict(limit=2, offset=0))
        second = self.s.call("resources.search", dict(limit=2, offset=2))
        self.assertEqual(len(page), 2)
        self.assertNotEqual(page[0]["code"], second[0]["code"])

    def test_dirty_guard_and_workspace_metadata(self):
        initial = self.s.state()
        self.assertFalse(initial["dirty"])
        self.command("add", kind="Weight", value="0.1")
        self.assertTrue(self.s.state()["dirty"])
        self.command("undo")
        self.assertFalse(self.s.state()["dirty"])
        self.command("redo")
        before = self.s.state()
        with self.assertRaisesRegex(ValueError, "Unsaved analysis"):
            self.s.call("project.open", dict(path=str(FIXTURE)))
        self.assertEqual(self.s.state(), before)
        self.s.call("project.open", dict(path=str(FIXTURE), discard=True))
        state = self.s.state()
        self.assertFalse(state["dirty"])
        self.assertTrue(state["project_open"])
        self.assertFalse(state["project"])
        self.assertEqual(state["source_path"], str(FIXTURE.resolve()))
        code = self.s.db.ScheduleTable.select().join(self.s.db.SequenceTable).get().code
        state = self.s.call("analysis.load", dict(code=code))
        self.assertTrue(state["unit"])
        self.command(
            "edit", id=state["rows"][0]["id"], field="description", value="Dirty group"
        )
        with self.assertRaisesRegex(ValueError, "Unsaved analysis"):
            self.s.call("analysis.load", dict(code=code))
        self.s.call("analysis.load", dict(code=code, discard=True))
        self.assertFalse(self.s.state()["dirty"])

    def test_no_gtk_and_protocol_recovery(self):
        script = 'from modern.backend.service import Service; import sys; s=Service(); assert "gi" not in sys.modules; s.close()'
        subprocess.run([sys.executable, "-c", script], check=True)
        requests = (
            "bad json\n"
            + json.dumps(dict(id="1", method="state"))
            + "\n"
            + json.dumps(dict(id="2", method="shutdown"))
            + "\n"
        )
        result = subprocess.run(
            [sys.executable, "-m", "modern.backend"],
            input=requests,
            text=True,
            capture_output=True,
            check=True,
        )
        lines = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(lines[0]["error"]["code"], "INVALID_REQUEST")
        self.assertEqual(lines[1]["id"], "1")
        self.assertTrue(lines[2]["result"])


if __name__ == "__main__":
    unittest.main()
