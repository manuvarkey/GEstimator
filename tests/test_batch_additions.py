import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from estimator.data.schedule import ScheduleDatabase, ScheduleItemModel, ResourceItemModel
from estimator.undo import Stack
from modern.backend.service import Service


class BatchAdditionsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.service = Service()
        self.addCleanup(self.service.close)
        path = Path(self.temp.name) / "library.eproj"
        db = ScheduleDatabase(Stack())
        db.create_new_database(str(path))
        db.insert_resource_multiple_atomic([ResourceItemModel(code, code, "kg", Decimal("5"), category="Materials") for code in ("R1", "R2")], preserve_structure=True)
        db.insert_item_multiple_atomic([ScheduleItemModel(code, code, "" if code == "A" else "m", Decimal("10"), category="Work", parent=parent) for code, parent in [("A", None), ("A.1", "A"), ("B", None)]], preserve_structure=True)
        db.close_database()
        self.original = path.read_bytes()
        self.path = path
        self.call("project.new")
        self.source = self.call("library.attach", path=str(path))[0]["id"]

    def call(self, method, **params):
        return self.service.call(method, dict(revision=self.service.revision, **params))

    def selection(self, kind):
        return [row["id"] for row in self.call(kind + ".editor.state", source=self.source)["rows"]]

    def test_schedule_and_resource_imports_call_legacy_batches_once(self):
        for kind, batch, individual in [("schedule", "insert_item_multiple_atomic", "insert_item"), ("resources", "insert_resource_multiple_atomic", "insert_resource")]:
            db = self.service.db
            before = len(self.service.project_editor.history)
            with patch.object(db, individual, side_effect=AssertionError("Individual add must not be used")), patch.object(db, batch, wraps=getattr(db, batch)) as spy:
                result = self.call(kind + ".editor.add_from_library", source=self.source, ids=self.selection(kind))
                self.assertEqual(spy.call_count, 1)
            self.assertEqual(len(self.service.project_editor.history), before + 1)
            self.assertEqual(result["imported"], 3 if kind == "schedule" else 2)
            if kind == "schedule":
                self.assertEqual(db.get_item("A.1").parent, "A")
            self.call("project.undo")
            table = db.ScheduleTable if kind == "schedule" else db.ResourceTable
            self.assertEqual(table.select().count(), 0)
            self.call("project.redo")
            self.assertEqual(table.select().count(), result["imported"])
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_batch_failure_rolls_back_items_categories_and_history(self):
        db = self.service.db
        original = db.insert_item_atomic
        count = 0
        def fail_second(*args, **kwargs):
            nonlocal count
            count += 1
            if count == 2:
                raise ValueError("Injected batch failure")
            return original(*args, **kwargs)
        before = self.call("state")
        with patch.object(db, "insert_item_atomic", side_effect=fail_second):
            with self.assertRaisesRegex(ValueError, "Injected"):
                self.call("schedule.editor.add_from_library", source=self.source, ids=self.selection("schedule"))
        self.assertEqual(self.call("state"), before)
        self.assertEqual(db.ScheduleTable.select().count(), 0)
        self.assertEqual(db.ScheduleCategoryTable.select().count(), 0)
        self.assertFalse(self.service.project_editor.history)

    def test_analysis_resources_insert_in_order_as_one_draft_operation(self):
        self.call("schedule.editor.add", data=dict(code="WORK"))
        self.call("analysis.load", code="WORK")
        group = self.call("add", kind="Group")["rows"][0]["id"]
        before = self.call("state")
        with patch.object(self.service, "edit", wraps=self.service.edit) as spy:
            self.call("analysis.resources_add", source=self.source, ids=self.selection("resources"), id=group)
            self.assertNotIn("resource.add", [args.args[0] for args in spy.call_args_list])
        children = self.call("state")["rows"][0]["_children"]
        self.assertEqual([row["code"] for row in children], ["R1", "R2"])
        self.assertEqual(len(self.service.history), 2)
        self.call("undo")
        self.assertEqual(self.call("state")["rows"], before["rows"])


class LibraryRateTests(unittest.TestCase):
    def test_import_keeps_stored_library_rate_like_gtk(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / "rates.eproj"
        db = ScheduleDatabase(Stack())
        db.create_new_database(str(path))
        resource = ResourceItemModel("R", "R", "kg", Decimal("5"), category="Materials")
        db.insert_resource(resource)
        item = ScheduleItemModel("X", "X", "m", Decimal("99"), category="Work")
        item.resources = {"R": resource}
        item.add_ana_group("Materials")
        item.add_ana_res(["R", Decimal("1"), ""], 0)
        db.insert_item(item)
        db.close_database()
        service = Service()
        self.addCleanup(service.close)
        call = lambda method, **params: service.call(method, dict(revision=service.revision, **params))
        call("project.new")
        source = call("library.attach", path=str(path))[0]["id"]
        rows = call("schedule.editor.state", source=source)["rows"]
        ids = [child["id"] for row in rows for child in row.get("_children", [])]
        call("schedule.editor.add_from_library", source=source, ids=ids)
        self.assertEqual(service.db.get_item("X").rate, Decimal("99"))
        call("project.undo")
        call("schedule.editor.add_from_library", source=source, ids=ids, recalculate=True)
        self.assertEqual(service.db.get_item("X").rate, Decimal("5"))


class LibraryGTKPlacementTests(unittest.TestCase):
    def test_selection_numbering_subitems_and_sub_analysis_codes(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / "lib.eproj"
        db = ScheduleDatabase(Stack())
        db.create_new_database(str(path))
        db.set_project_settings(dict(db.get_project_settings(), project_item_code="DSR", project_resource_code="DSR"))
        resource = ResourceItemModel("R", "R", "kg", Decimal("5"), category="Materials")
        db.insert_resource(resource)
        sub = ScheduleItemModel("9.9", "Sub", "m", Decimal("5"), category="Work")
        sub.resources = {"R": resource}
        sub.add_ana_group("M")
        sub.add_ana_res(["R", Decimal("1"), ""], 0)
        db.insert_item(sub)
        db.insert_resource(ResourceItemModel("9.9", "Sub", "m", Decimal("5"), category="Sub"))
        item = ScheduleItemModel("1.1", "Uses sub", "m", Decimal("10"), category="Work", parent=None)
        item.resources = {"9.9": db.get_resource("9.9")}
        item.add_ana_group("S")
        item.add_ana_res(["9.9", Decimal("2"), ""], 0)
        db.insert_item(item)
        db.close_database()
        service = Service()
        self.addCleanup(service.close)
        call = lambda method, **params: service.call(method, dict(revision=service.revision, **params))
        call("project.new")
        call("schedule.editor.add", data=dict(code="3", description="Heading", unit="", category="Work"))["selected"][0]
        main = call("schedule.editor.add", data=dict(code="4", description="Priced", unit="m", category="Work"))["selected"][0]
        source = call("library.attach", path=str(path))[0]["id"]
        rows = call("schedule.editor.state", source=source)["rows"]
        ids = {child["code"]: child["id"] for row in rows for child in row.get("_children", [])}
        call("schedule.editor.add_from_library", source=source, ids=[ids["1.1"]], target_ids=[main])
        imported = service.db.get_item("5", modify_res_code=False)
        self.assertEqual(imported.remarks, "DSR 1.1")
        # The sub-analysis keeps its (prefixed) code and the analysis still links it.
        self.assertIsNotNone(service.db.get_item("DSR:9.9"))
        self.assertIn("DSR:9.9", imported.resources)
        self.assertIsNone(service.db.get_item("1.1"))
