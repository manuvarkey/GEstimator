import hashlib
from contextlib import closing
from pathlib import Path
import tempfile
import unittest
from decimal import Decimal
from estimator.data.schedule import (
    ScheduleDatabase,
    ScheduleItemModel,
    ResourceItemModel,
)
from estimator.data.measurement import MeasurementItemCustom
from estimator.undo import Stack
from modern.backend.service import Service


class ProjectEditors(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.source = Path(self.temp.name) / "project.eproj"
        db = ScheduleDatabase(Stack())
        db.create_new_database(str(self.source))
        resource = ResourceItemModel(
            "R",
            "Material",
            "kg",
            Decimal("10"),
            Decimal("0"),
            Decimal("0"),
            category="Materials",
        )
        for code, qty in [("A", "2"), ("B", "3")]:
            item = ScheduleItemModel(
                code, "Work " + code, "m3", Decimal("0"), Decimal("1"), category="Work"
            )
            item.resources = {"R": resource}
            item.add_ana_group("Materials", code="M")
            item.add_ana_res(["R", Decimal(qty), ""], 0)
            item.add_ana_sum("Total")
            item.evaluate_results()
            item.update_rate()
            db.insert_item(item)
        db.close_database()
        self.original = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.s = Service()
        self.s.call("project.open", dict(path=str(self.source)))

    def tearDown(self):
        self.s.close()
        self.temp.cleanup()

    def call(self, method, **p):
        return self.s.call(method, dict(revision=self.s.revision, **p))

    def test_schedule_resource_edit_undo_dependency_and_roundtrip(self):
        state = self.call("schedule.editor.state")
        self.assertEqual(state["total"], 2)
        self.call(
            "schedule.editor.add",
            data=dict(
                code="C",
                description="Child\nwork",
                unit="m",
                rate="12.5",
                qty="2",
                parent="A",
                category="Work",
            ),
        )
        row = self.s.db.ScheduleTable.get(self.s.db.ScheduleTable.code == "C")
        self.assertEqual(row.parent.code, "A")
        self.call("schedule.editor.edit", id=str(row.id), field="qty", value="2*3")
        self.assertEqual(self.s.db.ScheduleTable.get_by_id(row.id).qty, Decimal("6"))
        self.call("project.undo")
        self.assertEqual(self.s.db.ScheduleTable.get_by_id(row.id).qty, Decimal("2"))
        self.call("project.redo")
        self.assertEqual(self.s.db.ScheduleTable.get_by_id(row.id).qty, Decimal("6"))
        resource = self.s.db.ResourceTable.get()
        self.call(
            "resources.editor.edit", id=str(resource.id), field="rate", value="20"
        )
        self.assertEqual(self.s.db.get_item("A").rate, Decimal("40"))
        self.assertEqual(self.s.db.get_item("B").rate, Decimal("60"))
        with self.assertRaises(ValueError):
            self.call("resources.editor.delete", id=str(resource.id))
        self.call("project.save_copy", path=str(Path(self.temp.name) / "saved.eproj"))
        self.assertEqual(
            hashlib.sha256(self.source.read_bytes()).hexdigest(), self.original
        )
        self.assertFalse(self.s.state()["workspace_dirty"])

    def test_category_duplicate_and_invalid_edit_are_atomic(self):
        self.call("resources.editor.category_add", description="Labour")
        row = self.s.db.ResourceTable.get()
        self.call("resources.editor.duplicate", id=str(row.id), data=dict(code="R2"))
        self.assertEqual(self.s.db.ResourceTable.select().count(), 2)
        self.call(
            "resources.editor.edit", id=str(row.id), field="category", value="Labour"
        )
        self.assertEqual(self.s.db.get_resource("R").category, "Labour")
        count = len(self.s.project_editor.history)
        with self.assertRaises(ValueError):
            self.call("resources.editor.edit", id=str(row.id), field="code", value="R2")
        self.assertEqual(self.s.db.get_resource("R").category, "Labour")
        self.assertEqual(len(self.s.project_editor.history), count)

    def test_add_from_selected_category_and_duplicate_preserve_parent(self):
        table = self.s.db.ScheduleTable
        parent = table.get(code="A")
        self.call("schedule.editor.add", id="cat:" + str(parent.category_id), data=dict(
            code="A.1", description="Child", parent="A", category="Different category",
        ))
        child = table.get(code="A.1")
        self.assertEqual((child.parent_id, child.category_id), (parent.id, parent.category_id))
        self.call("schedule.editor.duplicate", id=str(child.id), data=dict(code="A.2"))
        duplicate = table.get(code="A.2")
        self.assertEqual((duplicate.parent_id, duplicate.category_id), (parent.id, parent.category_id))
        self.call("project.undo")
        self.assertFalse(table.select().where(table.code == "A.2").exists())
        category = self.s.db.ResourceCategoryTable.get(description="Materials")
        self.call("resources.editor.add", id="cat:" + str(category.id), data=dict(code="NEW", category="Materials", rate="5"))
        self.assertEqual(self.s.db.get_resource("NEW").category, "Materials")

    def test_measurement_template_records_links_and_quantities(self):
        templates = self.call("measurement.templates")
        self.assertEqual(len(templates), 8)
        self.call("measurement.add", template="_1_NLBH", description="Dimensions")
        state = self.call("measurement.state")
        identity = state["rows"][0]["id"]
        self.call("measurement.record_add", id=identity)
        state = self.call("measurement.state", id=identity)
        record = state["detail"]["rows"][0]["id"]
        for field, value in [
            ("c0", "Column\nfooting"),
            ("c2", "2"),
            ("c3", "3"),
            ("c4", "4"),
            ("c5", "5"),
        ]:
            self.call(
                "measurement.record_edit",
                id=identity,
                record_id=record,
                field=field,
                value=value,
            )
        state = self.call("measurement.state", id=identity)
        self.assertEqual(state["detail"]["totals"], ["120"])
        self.call("measurement.link", id=identity, slot=0, code="A", remark="Footing")
        self.call("measurement.update_quantities", rounding="Round to .000")
        self.assertEqual(self.s.db.get_item("A").qty, Decimal("120"))
        self.call("measurement.record_duplicate", id=identity, record_id=record)
        self.assertEqual(
            self.call("measurement.state", id=identity)["detail"]["totals"], ["240"]
        )
        self.call("project.undo")
        self.assertEqual(
            self.call("measurement.state", id=identity)["detail"]["totals"], ["120"]
        )
        with self.assertRaises(ValueError):
            self.call(
                "measurement.record_edit",
                id=identity,
                record_id=record,
                field="c2",
                value='__import__("os")',
            )
        model = self.s.db.get_measurement().get_model()
        self.call(
            "project.save_copy", path=str(Path(self.temp.name) / "measurements.eproj")
        )
        restored = ScheduleDatabase(Stack())
        restored.open_database(str(Path(self.temp.name) / "measurements.eproj"))
        self.assertEqual(restored.get_measurement().get_model(), model)
        restored.close_database()

    def test_schedule_colour_only_marks_selected_items_and_round_trips(self):
        table = self.s.db.ScheduleTable
        parent = table.get(code="A")
        other = table.get(code="B")
        self.call("schedule.editor.add", data=dict(
            code="A.1", description="Child", parent="A", category="Work",
        ))
        child = table.get(code="A.1")
        ids = [f"cat:{parent.category_id}", str(parent.id), str(other.id)]
        with self.assertRaises(ValueError):
            self.call("schedule.editor.colour", ids=ids, colour="red")
        self.assertIsNone(table.get(code="A").colour)
        self.call("schedule.editor.colour", ids=ids, colour="#aabbcc")
        self.assertEqual(table.get(code="A").colour, "#AABBCC")
        self.assertEqual(table.get(code="B").colour, "#AABBCC")
        self.assertIsNone(table.get_by_id(child.id).colour)
        self.call("schedule.editor.colour", ids=[str(parent.id)], colour="#ffffff")
        self.assertIsNone(table.get(code="A").colour)
        self.call("project.undo")
        self.assertEqual(table.get(code="A").colour, "#AABBCC")
        saved = Path(self.temp.name) / "coloured.eproj"
        self.call("project.save_copy", path=str(saved))
        self.call("project.open", path=str(saved))
        items = self.call("schedule.editor.state")["rows"][0]["_children"]
        self.assertEqual(items[0]["colour"], "#AABBCC")
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), self.original)

    def test_schedule_quantity_update_uses_only_selected_measurement_links(self):
        self.call("measurement.add", template="_1_NLBH")
        self.call("measurement.add", template="_1_NLBH")
        rows = self.call("measurement.state")["rows"]
        for item, code in zip(rows, ("A", "B")):
            identity = item["id"]
            self.call("measurement.record_add", id=identity)
            record = self.call("measurement.state", id=identity)["detail"]["rows"][0]["id"]
            for field in ("c2", "c3", "c4", "c5"):
                self.call("measurement.record_edit", id=identity, record_id=record,
                          field=field, value="1.5" if field == "c3" else "2")
            self.call("measurement.link", id=identity, slot=0, code=code)
        item = self.s.db.ScheduleTable.get(code="A")
        self.call("schedule.editor.update_quantities",
                  ids=[str(item.id), f"cat:{item.category_id}"], rounding="Round to 10")
        self.assertEqual(self.s.db.get_item("A").qty, Decimal("10"))
        self.assertEqual(self.s.db.get_item("B").qty, Decimal("1"))
        self.call("project.undo")
        self.assertEqual(self.s.db.get_item("A").qty, Decimal("1"))

    def test_schedule_relocation_renumbering_and_undo_preserve_links(self):
        table = self.s.db.ScheduleTable
        a, b = table.get(code="A"), table.get(code="B")
        self.call("schedule.editor.edit", id=str(b.id), field="category", value="Second")
        self.call("schedule.editor.edit", id=str(a.id), field="parent", value="B")
        self.assertEqual(table.get_by_id(a.id).category.description, "Second")
        self.assertEqual(table.get_by_id(a.id).parent_id, b.id)
        with self.assertRaisesRegex(ValueError, "cycle"):
            self.call("schedule.editor.edit", id=str(b.id), field="parent", value="A")
        self.call("schedule.editor.add", data=dict(
            code="LIB:SUB", description="Sub-analysis", category="SUB ANALYSIS",
        ))
        self.call("measurement.add", template="_1_NLBH")
        measurement = self.call("measurement.state")["rows"][0]["id"]
        self.call("measurement.link", id=measurement, slot=0, code="A")
        self.call("analysis.load", code="A")
        self.call("schedule.editor.renumber")
        self.assertEqual(table.get_by_id(b.id).code, "2.1")
        self.assertEqual(table.get_by_id(a.id).code, "2.1.1")
        self.assertTrue(table.get(code="LIB:SUB"))
        self.assertEqual(self.s.db.get_measurement().items[0].itemnos[0], a.id)
        self.assertEqual(self.s.state()["code"], "2.1.1")
        self.call("project.undo")
        self.assertEqual(self.s.state()["code"], "A")
        self.call("project.redo")
        self.assertEqual(self.s.state()["code"], "2.1.1")
        self.call("schedule.editor.edit", id=str(b.id), field="category", value="Work")
        self.assertEqual(table.get_by_id(a.id).category.description, "Work")
        self.assertEqual(table.get_by_id(a.id).parent_id, b.id)
        self.assertEqual(self.s.db.get_item("2.1.1").rate, Decimal("20"))

    def test_import_schedule_adds_prefixed_sub_analysis_and_preserves_source(self):
        library = Path(self.temp.name) / "sub-analysis.eproj"
        external = ScheduleDatabase(Stack())
        external.create_new_database(str(library))
        settings = external.get_project_settings()
        settings["project_resource_code"] = "LIB"
        external.set_project_settings(settings)
        for code, resource_code, rate, category in (
            ("MIX", "SAND", "4", "SUB ANALYSIS"),
            ("TOP", "MIX", "8", "Road"),
        ):
            item = ScheduleItemModel(code, code, "m3", Decimal(rate), category=category)
            item.resources = {
                resource_code: ResourceItemModel(resource_code, resource_code, "kg", Decimal(rate) / 2, category="Materials")
            }
            item.add_ana_group("Materials")
            item.add_ana_res([resource_code, Decimal("2"), ""], 0)
            external.insert_item(item)
        external.close_database()
        digest = hashlib.sha256(library.read_bytes()).hexdigest()
        source = self.call("library.attach", path=str(library))[0]["id"]
        rows = self.call("schedule.editor.state", source=source, query="TOP")["rows"]
        selected = rows[0]["_children"][0]["id"]
        self.call("schedule.editor.add_from_library", source=source, ids=[selected])
        self.assertEqual(self.s.db.get_item("LIB:MIX").category, "SUB ANALYSIS")
        self.assertEqual(self.s.db.get_item("LIB:MIX").rate, Decimal("4"))
        self.assertEqual(self.s.db.get_item("TOP").rate, Decimal("8"))
        self.assertIn("LIB:MIX", self.s.db.get_item("TOP", modify_res_code=False).resources)
        self.call("project.undo")
        self.assertIsNone(self.s.db.get_item("LIB:MIX"))
        self.assertIsNone(self.s.db.get_item("TOP"))
        self.assertEqual(hashlib.sha256(library.read_bytes()).hexdigest(), digest)

    def test_in_place_save_backs_up_original_and_rejects_external_changes(self):
        self.call("analysis.load", code="A")
        self.call("analysis.edit", field="ana_remarks", value="First save")
        result = self.call("project.save")
        backup = Path(result["backup"])
        self.assertEqual(hashlib.sha256(backup.read_bytes()).hexdigest(), self.original)
        self.assertFalse(self.s.dirty)
        self.assertFalse(self.s.workspace_dirty)
        other = Service()
        self.addCleanup(other.close)
        other.call("project.open", dict(path=str(self.source)))
        self.assertEqual(other.db.get_item("A").ana_remarks, "First save")
        other.call("project.settings.edit", dict(
            revision=other.revision, settings=dict(project_name="Externally edited"),
        ))
        second = other.call("project.save", {})
        self.assertNotEqual(second["backup"], result["backup"])
        external_bytes = self.source.read_bytes()
        self.call("analysis.edit", field="ana_remarks", value="Conflicting draft")
        with self.assertRaisesRegex(ValueError, "changed on disk"):
            self.call("project.save")
        self.assertEqual(self.source.read_bytes(), external_bytes)
        self.assertTrue(self.s.dirty)
        self.assertEqual(self.s.db.get_item("A").ana_remarks, "First save")
        self.call("project.save_copy", path=str(Path(self.temp.name) / "alternate.eproj"))

    def test_failed_save_preserves_source_draft_and_cleans_staging(self):
        from unittest.mock import patch
        self.call("analysis.load", code="A")
        self.call("analysis.edit", field="ana_remarks", value="Unsaved after failure")
        original = self.source.read_bytes()
        before = self.s.state()
        def fail_write(path):
            path.write_bytes(b"interrupted snapshot")
            raise OSError("Snapshot interrupted")
        faults = [
            patch.object(self.s, "write_project_snapshot", side_effect=fail_write),
            patch("modern.backend.persistence.shutil.copyfile", side_effect=OSError("Backup failed")),
            patch("pathlib.Path.replace", side_effect=PermissionError("Destination held open")),
        ]
        for fault in faults:
            with fault, self.assertRaises(OSError):
                self.call("project.save")
            self.assertEqual(self.source.read_bytes(), original)
            self.assertEqual(self.s.state(), before)
            self.assertFalse(list(self.source.parent.glob(".gestimator-*.tmp")))
        result = self.call("project.save")
        self.assertEqual(Path(result["backup"]).read_bytes(), original)
        self.assertFalse(self.s.dirty)

    def test_concurrent_save_lock_and_stale_second_window_preserve_drafts(self):
        from modern.backend.persistence import save_lock
        other = Service()
        self.addCleanup(other.close)
        other.call("project.open", dict(path=str(self.source)))
        self.call("analysis.load", code="A")
        self.call("analysis.edit", field="ana_remarks", value="First window")
        other.call("analysis.load", dict(code="B"))
        other.call("analysis.edit", dict(revision=other.revision, field="ana_remarks", value="Second window"))
        before = other.state()
        original = self.source.read_bytes()
        with save_lock(self.source):
            with self.assertRaisesRegex(ValueError, "Another GEstimator window"):
                other.call("project.save", {})
        self.assertEqual(other.state(), before)
        self.assertEqual(self.source.read_bytes(), original)
        self.call("project.save")
        saved = self.source.read_bytes()
        with self.assertRaisesRegex(ValueError, "changed on disk"):
            other.call("project.save", {})
        self.assertEqual(self.source.read_bytes(), saved)
        self.assertEqual(other.state(), before)

    def test_interrupted_recovery_keeps_last_complete_checkpoint(self):
        from unittest.mock import patch
        from modern.backend.persistence import write_recovery
        checkpoint = Path(self.temp.name) / "last.eproj"
        checkpoint.write_bytes(self.source.read_bytes())
        original = checkpoint.read_bytes()
        def partial(path):
            path.write_bytes(b"partial checkpoint")
            raise OSError("Interrupted")
        with self.assertRaises(OSError):
            write_recovery(checkpoint, partial)
        self.assertEqual(checkpoint.read_bytes(), original)
        with patch("pathlib.Path.replace", side_effect=PermissionError("Publish failed")), self.assertRaises(OSError):
            write_recovery(checkpoint, lambda path: path.write_bytes(b"complete new checkpoint"))
        self.assertEqual(checkpoint.read_bytes(), original)
        self.assertFalse(list(checkpoint.parent.glob(".gestimator-*.tmp")))

    def test_recovery_restores_workspace_and_pending_analysis_to_new_file(self):
        recovery = Path(self.temp.name) / "recovery"
        self.s.recovery_dir = recovery
        self.call("analysis.load", code="A")
        self.call("analysis.edit", field="ana_remarks", value="Recovered draft")
        self.s.checkpoint_recovery()
        self.assertEqual(self.s.db.get_item("A").ana_remarks, None)
        reopened = Service(recovery)
        try:
            copies = reopened.call("recovery.list", {})
            self.assertEqual(len(copies), 1)
            state = reopened.call("recovery.open", dict(id=copies[0]["id"]))
            self.assertTrue(state["workspace_dirty"])
            self.assertIsNone(state["source_path"])
            self.assertEqual(reopened.db.get_item("A").ana_remarks, "Recovered draft")
            output = Path(self.temp.name) / "recovered.eproj"
            reopened.call("project.save_copy", dict(path=str(output)))
            self.assertTrue(output.exists())
            self.assertFalse(reopened.call("recovery.list", {}))
        finally:
            reopened.close()
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), self.original)

    def test_new_project_settings_are_undoable_and_savable_without_analysis(self):
        self.call("project.new")
        self.assertTrue(self.s.state()["workspace_dirty"])
        self.call(
            "project.settings.edit",
            settings={"project_name": "New estimate", "project_resource_code": "NEW"},
        )
        self.assertEqual(self.call("project.settings")["project_name"], "New estimate")
        self.call("project.undo")
        self.assertEqual(self.call("project.settings")["project_name"], "")
        self.call("project.redo")
        self.call("project.save_copy", path=str(Path(self.temp.name) / "empty.eproj"))
        self.assertFalse(self.s.state()["workspace_dirty"])

    def test_version_one_migrates_only_the_isolated_copy(self):
        import sqlite3

        legacy = Path(self.temp.name) / "legacy.eproj"
        with closing(sqlite3.connect(self.source)) as source, closing(
            sqlite3.connect(legacy)
        ) as target:
            source.backup(target)
        with sqlite3.connect(legacy) as target:
            target.execute("ALTER TABLE scheduletable DROP COLUMN colour")
            target.execute(
                "UPDATE projecttable SET value='GESTIMATOR_FILE_REFERENCE_VER_1' WHERE key='file_version'"
            )
        target.close()
        digest = hashlib.sha256(legacy.read_bytes()).hexdigest()
        self.call("project.open", path=str(legacy))
        self.assertEqual(
            self.s.db.get_project_settings()["file_version"],
            "GESTIMATOR_FILE_REFERENCE_VER_2",
        )
        self.assertEqual(self.s.db.get_item("A").rate, Decimal("20"))
        self.assertEqual(hashlib.sha256(legacy.read_bytes()).hexdigest(), digest)

    def test_project_clipboards_reordering_and_single_transaction_undo(self):
        rows = list(
            self.s.db.ScheduleTable.select().order_by(self.s.db.ScheduleTable.id)
        )
        self.call("schedule.editor.copy", ids=[str(rows[0].id)])
        self.call("schedule.editor.paste")
        self.assertIsNotNone(self.s.db.get_item("A-copy"))
        self.call("project.undo")
        self.assertIsNone(self.s.db.get_item("A-copy"))
        self.call("schedule.editor.move", id=str(rows[1].id), delta=-1)
        self.assertEqual(self.s.db.ScheduleTable.get_by_id(rows[1].id).order, 0)
        self.call("project.undo")
        self.assertEqual(self.s.db.ScheduleTable.get_by_id(rows[1].id).order, 1)
        self.call("measurement.add", template="_1_NLBH")
        identity = self.call("measurement.state")["rows"][0]["id"]
        self.call("measurement.record_add", id=identity)
        record = self.call("measurement.state", id=identity)["detail"]["rows"][0]["id"]
        self.call(
            "measurement.record_edit",
            id=identity,
            record_id=record,
            field="c2",
            value="2",
        )
        self.call("measurement.record_copy", id=identity, record_id=record)
        self.call("measurement.record_paste", id=identity, record_id=record)
        self.assertEqual(
            self.call("measurement.state", id=identity)["detail"]["totals"], ["4"]
        )

    def test_mapped_excel_import_rolls_back_all_rows_and_preserves_analysis(self):
        from openpyxl import Workbook

        book = Workbook()
        sheet = book.active
        sheet.append(["Code", "Description", "Unit", "Rate", "Qty", "Category"])
        sheet.append(["C", "New work", "m", "12.50", "2*3", "Work"])
        sheet.append(["A", "Updated existing", "m3", "20", "4", "Work"])
        path = Path(self.temp.name) / "import.xlsx"
        book.save(path)
        book.close()
        preview = self.call("project.import_preview", path=str(path))
        mapping = preview["mapping"]
        with self.assertRaises(ValueError):
            self.call(
                "project.import_apply", path=str(path), kind="schedule", mapping=mapping
            )
        self.assertIsNone(self.s.db.get_item("C"))
        result = self.call(
            "project.import_apply",
            path=str(path),
            kind="schedule",
            mapping=mapping,
            duplicates="update",
        )
        self.assertEqual((result["added"], result["updated"]), (1, 1))
        self.assertEqual(self.s.db.get_item("C").qty, Decimal("6"))
        self.assertEqual(len(self.s.db.get_item("A").ana_items), 2)
        self.call("project.undo")
        self.assertIsNone(self.s.db.get_item("C"))
        self.assertEqual(self.s.db.get_item("A").qty, Decimal("1"))

    def test_library_browsing_import_and_analysis_use_isolated_sources(self):
        import sqlite3

        library = Path(self.temp.name) / "library.eproj"
        with closing(sqlite3.connect(self.source)) as src, closing(
            sqlite3.connect(library)
        ) as dst:
            src.backup(dst)
        external = ScheduleDatabase(Stack())
        external.open_database(str(library))
        settings = external.get_project_settings()
        settings["project_name"] = "Reference library"
        settings["project_resource_code"] = "LIB"
        external.set_project_settings(settings)
        external.insert_resource(
            ResourceItemModel(
                "X",
                "External",
                "kg",
                Decimal("7"),
                Decimal("0"),
                Decimal("0"),
                category="Materials",
            )
        )
        external.close_database()
        digest = hashlib.sha256(library.read_bytes()).hexdigest()
        libraries = self.call("library.attach", path=str(library))
        source = libraries[0]["id"]
        state = self.call("resources.editor.state", source=source, query="X")
        row = state["rows"][0]["_children"][0]
        with self.assertRaises(ValueError):
            self.call(
                "resources.editor.edit",
                source=source,
                id=row["id"],
                field="rate",
                value="99",
            )
        self.call("resources.editor.add_from_library", source=source, ids=[row["id"]])
        self.assertEqual(self.s.db.get_resource("LIB:X").rate, Decimal("7"))
        self.call("analysis.load", code="A")
        group = self.s.state()["rows"][0]["id"]
        self.call(
            "resource.add", id=group, source=source, library=True, code="X", qty="2"
        )
        self.assertEqual(self.s.state()["rows"][0]["_children"][0]["code"], "LIB:X")
        self.assertEqual(hashlib.sha256(library.read_bytes()).hexdigest(), digest)

    def test_selected_library_price_update_preserves_definitions_and_undo(self):
        library = Path(self.temp.name) / "prices.eproj"
        external = ScheduleDatabase(Stack())
        external.create_new_database(str(library))
        settings = external.get_project_settings()
        settings["project_resource_code"] = "LIB"
        external.set_project_settings(settings)
        for code in ("R", "X"):
            external.insert_resource(
                ResourceItemModel(
                    code, "Library description", "t",
                    Decimal("20"), Decimal("10"), Decimal("5"),
                    "Updated reference", "Library materials",
                )
            )
        external.close_database()
        digest = hashlib.sha256(library.read_bytes()).hexdigest()
        source = self.call("library.attach", path=str(library))[0]["id"]
        row = self.s.db.ResourceTable.get()
        self.call("resources.editor.edit", id=str(row.id), field="code", value="LIB:R")
        self.call("resources.editor.duplicate", id=str(row.id), data=dict(code="LIB:X"))
        other = self.s.db.ResourceTable.get(code="LIB:X")
        self.call("resources.editor.edit", id=str(other.id), field="category", value="Other")
        self.call("resources.editor.duplicate", id=str(row.id), data=dict(code="Unmatched"))
        category = self.s.db.get_resource("LIB:R").category
        category_id = self.s.db.ResourceCategoryTable.get(description=category).id
        params = dict(library=source, ids=[f"cat:{category_id}", str(row.id)])
        expected = dict(changed=1, unchanged=0, unmatched=1)
        revision = self.s.revision
        self.assertEqual(self.call("resources.editor.price_preview", **params), expected)
        self.assertEqual(self.s.revision, revision)
        self.assertEqual(self.call("resources.editor.price_update", **params), expected)
        current = self.s.db.get_resource("LIB:R")
        self.assertEqual((current.rate, current.vat, current.discount, current.reference),
                         (Decimal("20"), Decimal("10"), Decimal("5"), "Updated reference"))
        self.assertEqual((current.description, current.unit, current.category),
                         ("Material", "kg", category))
        self.assertEqual(self.s.db.get_resource("LIB:X").rate, Decimal("10"))
        self.assertEqual(self.s.db.get_item("A").rate, Decimal("41.80"))
        revision = self.s.revision
        self.assertEqual(self.call("resources.editor.price_update", **params),
                         dict(changed=0, unchanged=1, unmatched=1))
        self.assertEqual(self.s.revision, revision)
        self.call("project.undo")
        self.assertEqual(self.s.db.get_resource("LIB:R").rate, Decimal("10"))
        self.assertEqual(self.s.db.get_item("A").rate, Decimal("20"))
        self.call("project.redo")
        self.assertEqual(self.s.db.get_item("A").rate, Decimal("41.80"))
        self.assertEqual(hashlib.sha256(library.read_bytes()).hexdigest(), digest)

    def test_resource_usage_totals_and_direct_analysis_links(self):
        self.call("analysis.load", code="A")
        last = self.s.state()["rows"][-1]["id"]
        self.call("add", kind="Multiply", value="2", id=last)
        self.call("analysis.apply")
        row = self.s.db.ResourceTable.get()
        self.call("resources.editor.edit", id=str(row.id), field="vat", value="10")
        self.call("resources.editor.edit", id=str(row.id), field="discount", value="5")
        revision = self.s.revision
        total = self.call("resources.editor.usage", query="material KG")
        self.assertEqual(total["total"], 1)
        self.assertEqual(total["rows"][0]["code"], "R")
        self.assertEqual(Decimal(total["rows"][0]["quantity"]), Decimal("7"))
        self.assertEqual(total["rows"][0]["rate"], "10.45")
        self.assertEqual(total["rows"][0]["amount"], "73.15")
        self.assertEqual(self.call("resources.editor.usage", query="other")["total"], 0)
        self.assertEqual(self.call("resources.editor.usage", offset=1)["rows"], [])
        matches = self.call("resources.editor.dependents", code="R")
        self.assertEqual([row["code"] for row in matches["rows"]], ["A", "B"])
        self.assertEqual(self.call("resources.editor.dependents", code="R", offset=1)["rows"],
                         [dict(code="B", description="Work B", indirect=False)])
        self.assertEqual(self.call("resources.editor.dependents", code="missing")["total"], 0)
        self.assertEqual(self.s.revision, revision)

    def test_resource_dependents_follow_nested_analyses_without_duplicates(self):
        for code, resource in (("SUB1", "R"), ("SUB2", "SUB1"), ("MAIN", "SUB2")):
            model = ScheduleItemModel(code, code, "m3", category="SUB ANALYSIS")
            model.resources = {
                resource: ResourceItemModel(resource, resource, "kg", Decimal("10"), category="Materials")
            }
            model.add_ana_group("Materials")
            model.add_ana_res([resource, Decimal("1"), ""], 0)
            self.assertTrue(self.s.db.insert_item(model))
        matches = self.call("resources.editor.dependents", code="R")
        self.assertEqual(
            {row["code"]: row["indirect"] for row in matches["rows"]},
            {"A": False, "B": False, "SUB1": False, "SUB2": True, "MAIN": True},
        )

    def test_matrix_paste_is_atomic_and_uses_backend_calculation(self):
        records = list(
            self.s.db.ScheduleTable.select().order_by(self.s.db.ScheduleTable.id)
        )
        edits = [
            dict(id=str(row.id), field="qty", value=str(index + 3))
            for index, row in enumerate(records)
        ]
        self.call("schedule.editor.edit_many", edits=edits)
        self.assertEqual(
            [self.s.db.get_item(code).qty for code in ("A", "B")],
            [Decimal("3"), Decimal("4")],
        )
        self.call("project.undo")
        self.assertEqual(
            [self.s.db.get_item(code).qty for code in ("A", "B")],
            [Decimal("1"), Decimal("1")],
        )
        edits[1]["value"] = "not a number"
        with self.assertRaises(ValueError):
            self.call("schedule.editor.edit_many", edits=edits)
        self.assertEqual(self.s.db.get_item("A").qty, Decimal("1"))

    def test_all_shipped_measurement_templates_preserve_calculations_and_export(self):
        from estimator.data.measurement import RecordCustom
        from estimator import misc

        for template in self.call("measurement.templates"):
            expected = MeasurementItemCustom(plugin=template["code"])
            values = [
                (
                    "1"
                    if kind in (misc.MEAS_L, misc.MEAS_NO)
                    else "Reference" if kind == misc.MEAS_DESC else ""
                )
                for kind in expected.columntypes
            ]
            expected.append_record(
                RecordCustom(
                    values,
                    expected.cust_funcs,
                    expected.total_func_item,
                    expected.columntypes,
                )
            )
            self.call(
                "measurement.add",
                template=template["code"],
                description=template["name"],
            )
            identity = self.call("measurement.state")["rows"][0]["id"]
            self.call("measurement.record_add", id=identity)
            state = self.call("measurement.state", id=identity)
            self.assertEqual([column["width"] for column in state["detail"]["columns"]], expected.dimensions[0])
            self.assertEqual([column["expand"] for column in state["detail"]["columns"]], expected.dimensions[1])
            self.assertEqual([column["numeric"] for column in state["detail"]["columns"]], [kind in (misc.MEAS_L, misc.MEAS_NO) for kind in expected.columntypes])
            record = state["detail"]["rows"][0]["id"]
            edits = [
                dict(id=record, field="c" + str(index), value=value)
                for index, value in enumerate(values)
                if expected.columntypes[index] != misc.MEAS_CUST
            ]
            self.call("measurement.record_edit_many", id=identity, edits=edits)
            actual = self.call("measurement.state", id=identity)
            self.assertEqual(
                actual["detail"]["totals"],
                [str(v) for v in expected.get_total()],
                template["code"],
            )
            self.assertEqual(
                self.s.db.get_measurement().items[0].records[0].data_string, values
            )
        output = Path(self.temp.name) / "all-measurements.xlsx"
        self.call("project.export_xlsx", path=str(output))
        from openpyxl import load_workbook

        workbook = load_workbook(output)
        self.assertIn("DOM", workbook.sheetnames)
        self.assertTrue(
            any(cell.value == "Reference" for row in workbook["DOM"] for cell in row)
        )
        def signature(book):
            return [(
                sheet.title,
                [(cell.coordinate, cell.value, cell.data_type, cell.number_format, str(cell._style)) for row in sheet for cell in row],
                str(sheet.merged_cells), str(sheet.page_setup), str(sheet.page_margins),
                str(sheet.print_options), str(sheet.print_area), sheet.print_title_rows, sheet.print_title_cols,
                [(key, str(value)) for key, value in sheet.column_dimensions.items()],
                [(key, str(value)) for key, value in sheet.row_dimensions.items()],
            ) for sheet in book]
        expected_signature = signature(workbook)
        workbook.close()
        class Progress:
            def add_message(self, message): pass
            def set_fraction(self, value): pass
            def pulse(self, *args, **kwargs): pass
        reference = Path(self.temp.name) / "legacy-reference.xlsx"
        spreadsheet = misc.Spreadsheet()
        self.s.db.export_sch_spreadsheet(spreadsheet, False)
        self.s.db.export_res_spreadsheet(spreadsheet)
        self.s.db.export_meas_spreadsheet(spreadsheet, False)
        self.s.db.export_res_usage_spreadsheet(spreadsheet)
        self.s.db.export_ana_spreadsheet(spreadsheet, Progress(), [0.3, 0.9])
        spreadsheet.save(reference)
        legacy = load_workbook(reference)
        self.assertEqual(signature(legacy), expected_signature)
        names = legacy.sheetnames
        legacy.close()
        # Optional real-office check, using an isolated profile and disposable output.
        import shutil
        import subprocess
        if office := shutil.which("libreoffice"):
            folder = Path(self.temp.name) / "recalculated"
            folder.mkdir()
            profile = (Path(self.temp.name) / "office-profile").as_uri()
            result = subprocess.run([office, "-env:UserInstallation=" + profile, "--headless", "--convert-to", "xlsx", "--outdir", str(folder), str(output)], capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            recalculated = load_workbook(folder / output.name, data_only=True)
            self.assertEqual(recalculated.sheetnames, names)
            errors = [(sheet.title, cell.coordinate, cell.value) for sheet in recalculated for row in sheet for cell in row if cell.data_type == "e"]
            self.assertEqual(errors, [])
            recalculated.close()

    def test_empty_categories_are_visible_renamable_and_ordered(self):
        self.call("schedule.editor.category_add", description="Empty category")
        state = self.call("schedule.editor.state")
        category = next(
            row for row in state["rows"] if row["description"] == "Empty category"
        )
        self.assertEqual(category["_children"], [])
        self.call(
            "schedule.editor.edit",
            id=category["id"],
            field="description",
            value="Renamed category",
        )
        self.call("schedule.editor.move", id=category["id"], delta=1)
        self.assertEqual(
            self.call("schedule.editor.state")["rows"][-1]["description"],
            "Renamed category",
        )
        self.call("project.undo")
        self.call("project.undo")
        self.assertEqual(
            self.call("schedule.editor.state")["rows"][0]["description"],
            "Empty category",
        )

    def test_category_delete_preserves_measurements_and_undo_restores_links(self):
        self.call("measurement.add", template="_1_NLBH")
        identity = self.call("measurement.state")["rows"][0]["id"]
        self.call(
            "measurement.link", id=identity, slot=0, code="A", remark="Linked item"
        )
        category = self.call("schedule.editor.state")["rows"][0]
        preview = self.call("schedule.editor.delete_preview", ids=[category["id"]])
        self.assertEqual(preview["measurement_references"], 1)
        self.call("schedule.editor.delete_many", ids=[category["id"]])
        detail = self.call("measurement.state", id=identity)["detail"]
        self.assertEqual(detail["links"][0]["code"], "")
        self.assertIsNone(self.s.db.get_measurement().items[0].itemnos[0])
        self.assertEqual(detail["links"][0]["remark"], "Linked item")
        self.call(
            "schedule.editor.add",
            data=dict(code="NEW", description="New work", category="Work"),
        )
        self.assertIsNone(self.s.db.get_measurement().items[0].itemnos[0])
        self.call("project.undo")
        self.call("project.undo")
        self.assertFalse(
            self.call("measurement.state", id=identity)["detail"]["links"][0]["missing"]
        )
        self.assertEqual(self.s.db.get_item("A").rate, Decimal("20"))

    def test_resource_category_delete_unused_or_all_is_atomic_and_undoable(self):
        self.call(
            "resources.editor.add",
            data=dict(code="UNUSED", description="Unused", category="Materials"),
        )
        category = self.call("resources.editor.state")["rows"][0]
        preview = self.call("resources.editor.delete_preview", ids=[category["id"]])
        self.assertEqual(preview["used_resources"], ["R"])
        with self.assertRaises(ValueError):
            self.call("resources.editor.delete_many", ids=[category["id"]])
        self.call("resources.editor.delete_many", ids=[category["id"]], policy="unused")
        self.assertIsNone(self.s.db.get_resource("UNUSED"))
        self.assertIsNotNone(self.s.db.get_resource("R"))
        self.call("project.undo")
        self.call("resources.editor.delete_many", ids=[category["id"]], policy="all")
        self.assertEqual(self.s.db.ResourceTable.select().count(), 0)
        self.assertEqual(self.s.db.get_item("A").rate, Decimal("0"))
        self.call("project.undo")
        self.assertEqual(self.s.db.get_item("A").rate, Decimal("20"))
        self.assertIsNotNone(self.s.db.get_resource("UNUSED"))

    def test_import_whole_library_categories_preserves_hierarchy_and_prefixes(self):
        # Persist a real hierarchy and prefix before attaching the read-only snapshot.
        external = ScheduleDatabase(Stack())
        external.open_database(str(self.source))
        settings = external.get_project_settings()
        settings["project_resource_code"] = "LIB"
        external.set_project_settings(settings)
        self.call(
            "schedule.editor.add",
            data=dict(code="HEAD", description="Heading", category="Work"),
        )
        external.insert_item(ScheduleItemModel("HEAD", "Heading", "", category="Work"))
        external.insert_item(
            ScheduleItemModel(
                "CHILD",
                "Child work",
                "m",
                Decimal("7"),
                Decimal("2"),
                category="Work",
                parent="HEAD",
            )
        )
        external.close_database()
        digest = hashlib.sha256(self.source.read_bytes()).hexdigest()
        source = self.call("library.attach", path=str(self.source))[0]["id"]
        category = self.call("schedule.editor.state", source=source)["rows"][0]
        result = self.call(
            "schedule.editor.add_from_library", source=source, ids=[category["id"]]
        )
        self.assertEqual(result["imported"], 4)
        self.assertIsNotNone(self.s.db.get_item("A-copy"))
        self.assertEqual(self.s.db.get_item("A-copy").rate, Decimal("20"))
        self.assertEqual(self.s.db.get_item("CHILD").parent, "HEAD-copy")
        self.assertIn(
            "LIB:R", self.s.db.get_item("A-copy", modify_res_code=False).resources
        )
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), digest)
        self.call("project.undo")
        self.assertIsNone(self.s.db.get_item("A-copy"))
        self.assertIsNone(self.s.db.get_resource("LIB:R"))

    def test_category_selection_expands_beyond_page_and_deduplicates(self):
        self.call("resources.editor.category_add", description="Bulk")
        db = self.s.db
        with db.database.atomic():
            for index in range(205):
                db.insert_resource_atomic(
                    ResourceItemModel(
                        "BULK" + str(index),
                        "Resource",
                        "kg",
                        Decimal("1"),
                        category="Bulk",
                    )
                )
        state = self.call("resources.editor.state", limit=1)
        category = state["rows"][0]
        child = category["_children"][0]
        before = len(self.s.project_editor.history)
        revision = self.s.revision
        preview = self.call(
            "resources.editor.delete_preview", ids=[category["id"], child["id"]]
        )
        self.assertEqual(preview["items"], 205)
        self.assertEqual(self.s.revision, revision)
        self.assertEqual(len(self.s.project_editor.history), before)
        with self.assertRaises(ValueError):
            self.call("resources.editor.delete_many", ids=[child["id"], "999999"])
        self.assertEqual(db.ResourceTable.select().count(), 206)
        self.assertEqual(len(self.s.project_editor.history), before)
        self.call("resources.editor.delete_many", ids=[category["id"], child["id"]])
        self.assertEqual(db.ResourceTable.select().count(), 1)
        self.call("project.undo")
        self.assertEqual(db.ResourceTable.select().count(), 206)

    def test_measurement_multiselect_operations_preserve_order_and_undo(self):
        for label in reversed(("One", "Two", "Three", "Four")):
            self.call("measurement.add", description=label)
        def rows():
            return self.call("measurement.state")["rows"]
        ids = [row["id"] for row in rows()]
        self.call("measurement.move", ids=[ids[1], ids[2]], delta=-1)
        self.assertEqual([row["id"] for row in rows()], [ids[1], ids[2], ids[0], ids[3]])
        self.call("measurement.copy", ids=[ids[2], ids[1]])
        self.call("measurement.paste", id=ids[3])
        self.assertEqual([row["description"] for row in rows()],
                         ["Two", "Three", "One", "Four", "Two", "Three"])
        self.call("measurement.delete", ids=[ids[1], ids[2]])
        self.assertEqual(len(rows()), 4)
        self.call("project.undo")
        self.assertEqual([row["id"] for row in rows()][:2], [ids[1], ids[2]])
        self.call("measurement.duplicate", ids=[ids[0], ids[3]])
        self.assertEqual([row["description"] for row in rows()][4:6], ["One", "Four"])
        with self.assertRaises(ValueError):
            self.call("measurement.delete", ids=[ids[0], "stale"])
        self.assertEqual(len(rows()), 8)

    def test_default_analysis_rows_and_selected_rate_refresh(self):
        self.call("analysis.load", code="A")
        original = self.s.state()
        self.call("analysis.insert_template", id=original["rows"][-1]["id"])
        self.assertEqual(len(self.s.state()["rows"]), len(original["rows"]) + 11)
        self.call("undo")
        self.assertEqual(self.s.state()["rows"], original["rows"])
        table = self.s.db.ScheduleTable
        a, b = table.get(code="A"), table.get(code="B")
        for item in (a, b):
            self.call("schedule.editor.edit", id=str(item.id), field="rate", value="1")
        self.call("schedule.editor.update_rates", ids=[str(a.id)])
        self.assertEqual(table.get_by_id(a.id).rate, Decimal("20"))
        self.assertEqual(table.get_by_id(b.id).rate, Decimal("1"))
        self.call("project.undo")
        self.assertEqual(table.get_by_id(a.id).rate, Decimal("1"))

    def test_spreadsheet_analysis_preview_and_import_are_undoable(self):
        from openpyxl import Workbook

        path = Path(self.temp.name) / "analysis.xlsx"
        book = Workbook()
        sheet = book.active
        for row in (
            ["EXTERNAL", "Original item"],
            [None, "Cost of concrete"],
            ["Code", "Description", "Unit", "Qty", "Rate", "Amount"],
            [None, "MATERIALS"],
            ["X", "Cement", "kg", 3, 7, 21],
            [None, "TOTAL MATERIALS", None, None, None, 21],
            [None, "TOTAL", None, None, None, 21],
        ):
            sheet.append(row)
        book.save(path)
        self.call("analysis.load", code="A")
        preview = self.call("analysis.import_preview", path=str(path))
        items = preview.pop("items")
        self.assertEqual(preview, dict(rows=2, resources=1, rate="21.00", warnings=[]))
        self.assertEqual((items[0]["kind"], items[1]["kind"], items[1]["code"], items[1]["amount"]), ("Group", "Resource", "X", "21.00"))
        self.assertFalse(self.s.dirty)
        self.call("analysis.import_xlsx", path=str(path))
        self.assertEqual(self.s.state()["code"], "A")
        self.assertEqual(self.s.state()["rate"], "21.00")
        self.assertTrue(self.s.dirty)
        self.assertEqual(self.s.db.get_item("A").rate, Decimal("20"))
        self.call("undo")
        self.assertEqual(self.s.state()["rate"], "20.00")

    def test_measurement_record_workbook_import_is_atomic(self):
        from openpyxl import Workbook

        path = Path(self.temp.name) / "records.xlsx"
        book = Workbook()
        sheet = book.active
        sheet.append(["Description", "Number", "Length", "Breadth", "Height"])
        sheet.append(["Footing", 2, 3, 4, 5])
        sheet.append(["Invalid", "invalid", 1, 1, 1])
        book.save(path)
        self.call("measurement.add", template="_1_NLBH")
        identity = self.call("measurement.state")["rows"][0]["id"]
        params = dict(id=identity, path=str(path), first_row=2)
        with self.assertRaises(ValueError):
            self.call("measurement.record_import", **params)
        self.assertEqual(self.call("measurement.state", id=identity)["detail"]["rows"], [])
        self.assertEqual(self.call("measurement.record_import", last_row=2, **params), dict(imported=1))
        detail = self.call("measurement.state", id=identity)["detail"]
        self.assertEqual(detail["rows"][0]["c0"], "Footing")
        self.assertEqual(detail["totals"], ["120"])
        self.call("project.undo")
        self.assertEqual(self.call("measurement.state", id=identity)["detail"]["rows"], [])

    def test_measurement_record_order_preserves_ids_values_totals_and_undo(self):
        self.call("measurement.add", template="_1_NLBH")
        identity = self.call("measurement.state")["rows"][0]["id"]
        self.call("measurement.record_add", id=identity)
        first = self.call("measurement.state", id=identity)["detail"]["rows"][0]["id"]
        self.call(
            "measurement.record_edit_many",
            id=identity,
            edits=[
                dict(id=first, field="c0", value="First\nrecord"),
                dict(id=first, field="c2", value="2*3"),
            ],
        )
        self.call("measurement.record_duplicate", id=identity, record_id=first)
        original = self.call("measurement.state", id=identity)["detail"]
        second = original["rows"][1]["id"]
        self.call("measurement.record_move", id=identity, record_id=second, delta=-1)
        moved = self.call("measurement.state", id=identity)["detail"]
        self.assertEqual([row["id"] for row in moved["rows"]], [second, first])
        self.assertEqual(moved["totals"], original["totals"])
        self.assertEqual(moved["rows"][0]["c0"], "First\nrecord")
        self.call("project.undo")
        self.assertEqual(
            self.call("measurement.state", id=identity)["detail"], original
        )
        self.call("project.redo")
        self.assertEqual(self.call("measurement.state", id=identity)["detail"], moved)

    def test_existing_export_worksheets_formulas_and_page_settings(self):
        path = Path(self.temp.name) / "report.xlsx"
        self.call("project.export_xlsx", path=str(path))
        from openpyxl import load_workbook

        book = load_workbook(path)
        self.assertEqual(
            book.sheetnames, ["Schedule", "Resources", "DOM", "Res Usage", "Analysis"]
        )
        self.assertTrue(book["Schedule"].merged_cells.ranges)
        self.assertEqual(book["Analysis"].page_setup.paperSize, 9)
        self.assertTrue(
            any(c.data_type == "f" for row in book["Analysis"] for c in row)
        )
        book.close()


class LenientMappedImportTests(unittest.TestCase):
    def test_formulas_text_numbers_and_row_range(self):
        import tempfile
        from pathlib import Path
        from openpyxl import Workbook
        from modern.backend.service import Service
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / "lenient.xlsx"
        book = Workbook()
        sheet = book.active
        sheet.append(["Title row"])
        sheet.append(["Item No.", "Description of item", "Unit", "Rate (Rs.)", "Qty."])
        sheet.append(["1.1", "Formula qty", "m", "1,234.50", "=2*3"])
        sheet.append(["1.2", "Text rate", "LS", "Rs. 50", "-"])
        sheet.append(["1.3", "Bad rate", "m", "lump sum", "2*3"])
        sheet.append(["1.4", "Outside range", "m", "1", "1"])
        book.save(path)
        service = Service()
        self.addCleanup(service.close)
        call = lambda method, **params: service.call(method, dict(revision=service.revision, **params))
        call("project.new")
        preview = call("project.import_preview", path=str(path), header_row=2)
        self.assertEqual(preview["mapping"], dict(code=0, description=1, unit=2, rate=3, qty=4))
        result = call("project.import_apply", kind="schedule", path=str(path), header_row=2, first_row=3, last_row=5, mapping=preview["mapping"])
        self.assertEqual((result["added"], result["warning_count"]), (3, 1))
        self.assertIn("1.3", result["warnings"][0])
        db = service.db
        self.assertEqual((db.get_item("1.1").rate, db.get_item("1.1").qty), (Decimal("1234.50"), Decimal("6")))
        self.assertEqual((db.get_item("1.2").rate, db.get_item("1.2").qty), (Decimal("50"), Decimal("0")))
        self.assertIsNone(db.get_item("1.4"))


class StructuredScheduleImportTests(unittest.TestCase):
    def test_codes_categories_and_multiline_headings_like_gtk(self):
        import tempfile
        from pathlib import Path
        from openpyxl import Workbook
        from modern.backend.service import Service
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / "structured.xlsx"
        book = Workbook()
        for row in [["Code", "Description", "Unit", "Rate", "Qty"],
                    [None, "EARTH WORK"],
                    ["1.1", "Excavation in all kinds of soil"], [None, "including disposal"],
                    ["1.1.1", "Depth up to 1.5 m", "cum", 100, 2], ["1.1.2", "Depth 1.5 to 3 m", "cum", 120, 3],
                    ["1.2", "Filling", "cum", 50, 4],
                    [None, "CONCRETE"], ["2.1", "PCC 1:4:8", "cum", 5000, 1]]:
            book.active.append(row)
        book.save(path)
        service = Service()
        self.addCleanup(service.close)
        call = lambda method, **params: service.call(method, dict(revision=service.revision, **params))
        call("project.new")
        mapping = dict(code=0, description=1, unit=2, rate=3, qty=4)
        result = call("project.import_apply", kind="schedule", path=str(path), mapping=mapping, hierarchy=True)
        self.assertEqual(result["added"], 5)
        db = service.db
        heading = db.get_item("1.1")
        self.assertEqual((heading.unit, heading.description, heading.category), ("", "Excavation in all kinds of soil\nincluding disposal", "EARTH WORK"))
        self.assertEqual([db.get_item(code).parent for code in ("1.1.1", "1.1.2", "1.2", "2.1")], ["1.1", "1.1", None, None])
        self.assertEqual(db.get_item("2.1").category, "CONCRETE")
        self.assertEqual(db.get_item("1.1.2").qty, Decimal("3"))
        call("project.undo")
        flat = call("project.import_apply", kind="schedule", path=str(path), mapping=mapping)
        self.assertEqual(flat["added"], 5)
        self.assertIsNone(db.get_item("1.1.1").parent)
