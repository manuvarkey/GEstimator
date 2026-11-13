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
        workbook.close()

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
