import copy
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from estimator.data.schedule import ScheduleDatabase, ScheduleItemModel, ResourceItemModel
from estimator.undo import Stack
from modern.backend.service import Service


class ProgramSettingsTests(unittest.TestCase):
    def setUp(self):
        self.service = Service()
        self.addCleanup(self.service.close)

    def call(self, method, **params):
        return self.service.call(method, dict(revision=self.service.revision, **params))

    def test_defaults_and_validation_do_not_change_draft_or_project(self):
        before = self.call("state")
        result = self.call("program.settings")
        settings = result["settings"]
        self.assertTrue(settings["export_break_items"])
        self.assertTrue(Path(result["library_directory"]).is_absolute())
        self.assertEqual(settings["ana_copy_delete_rows"], 0)
        settings["sch_rate_mult_factor"] = "1 + 1/3"
        validated = self.call("program.settings.validate", settings=settings)
        self.assertEqual(validated["sch_rate_mult_factor"], "1.33333")
        self.assertEqual(self.call("state"), before)
        self.assertFalse(self.service.history)
        for change in [dict(ana_copy_delete_rows=True), dict(ana_copy_delete_rows=6), dict(sch_rate_mult_factor="__import__('os')"), dict(export_break_items="True"), dict(ana_default_rows=[dict(kind="Round", description="Round", value="2.01")])]:
            with self.assertRaises(ValueError):
                self.call("program.settings.validate", settings=dict(settings, **change))
            self.assertEqual(self.call("state"), before)

    def test_configured_default_template_preserves_codes_and_undo(self):
        before = self.call("state")
        rows = [dict(kind="Group", code="LAB", description="Labour", value=""), dict(kind="Weight", description="Overheads", value="1/10")]
        after = self.call("analysis.insert_template", rows=rows)
        self.assertEqual(after["rows"][0]["code"], "LAB")
        self.assertEqual(after["rows"][1]["value"], "0.100000")
        self.call("undo")
        self.assertEqual(self.call("state")["rows"], before["rows"])
        before = self.call("state")
        with self.assertRaises(ValueError):
            self.call("analysis.insert_template", rows=rows + [dict(kind="Weight", value="1/0")])
        self.assertEqual(self.call("state"), before)

    def test_library_catalog_and_stable_bundled_identifiers(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "custom"
            with patch("modern.backend.program_settings.library_directory", return_value=folder):
                self.call("program.settings")
                self.assertFalse(folder.exists())
                self.assertEqual(self.call("program.library_directory"), str(folder))
                (folder / "Custom.EPROJ").write_bytes(b"metadata discovery does not open files")
                (folder / "ignored.txt").write_text("ignored")
                catalog = self.call("program.libraries")
                self.assertFalse(catalog["warnings"])
                custom = [entry for entry in catalog["rows"] if not entry["bundled"]]
                self.assertEqual([entry["name"] for entry in custom], ["Custom"])
                self.assertTrue(Path(custom[0]["path"]).is_absolute())
                self.assertIn("bundled:DSREM2022.eproj", [entry["path"] for entry in catalog["rows"]])
        self.call("project.new")
        sources = self.call("library.attach", path="bundled:DSREM2022.eproj")
        from estimator import misc
        repeated = self.call("library.attach", path=misc.abs_path("database", "DSREM2022.eproj"))
        self.assertEqual(len(repeated), 1)
        self.assertEqual(repeated[0]["id"], sources[0]["id"])
        state = self.call("schedule.editor.state", source=sources[0]["id"], query="1.1.1")
        self.assertGreater(state["total"], 0)
        for path in ("bundled:../DSREM2022.eproj", "bundled:folder\\DSREM2022.eproj", "bundled:/DSREM2022.eproj", "bundled:script.py"):
            with self.assertRaises(ValueError):
                self.call("library.attach", path=path)

    def test_modify_add_matches_gtk_rate_template_reference_and_atomic_undo(self):
        with tempfile.TemporaryDirectory() as directory:
            library = Path(directory) / "library.eproj"
            db = ScheduleDatabase(Stack())
            db.create_new_database(str(library))
            settings = db.get_project_settings()
            settings["project_item_code"] = "REF"
            db.set_project_settings(settings)
            resource = ResourceItemModel("R", "Resource", "kg", Decimal("10"), category="Materials")
            item = ScheduleItemModel("A", "Library work", "m", Decimal("20"), Decimal("1"), category="Work")
            item.resources = {"R": resource}
            item.add_ana_group("Materials")
            item.add_ana_res(["R", Decimal("2"), ""], 0)
            item.add_ana_sum("Original total")
            db.insert_item(item)
            db.close_database()
            source_bytes = library.read_bytes()
            self.call("project.new")
            source = self.call("library.attach", path=str(library))[0]["id"]
            state = self.call("schedule.editor.state", source=source)
            identity = state["rows"][0]["_children"][0]["id"]
            self.call("schedule.editor.add_from_library", source=source, ids=[identity])
            config = self.call("program.settings")["settings"]
            config.update(sch_rate_mult_factor="2", ana_copy_delete_rows=1,
                          ana_copy_rows=[dict(kind="Multiply", description="Triple base", value="3")])
            self.call("schedule.editor.add_from_library", source=source, ids=[identity], modify=True, settings=config)
            modified = self.service.db.get_item("A-copy", modify_res_code=False)
            self.assertEqual(modified.rate, Decimal("40"))
            self.assertEqual(modified.remarks, "REF A")
            self.assertEqual(modified.ana_items[-1]["description"], "Triple base")
            modified.evaluate_results()
            self.assertEqual(modified.get_ana_rate(), Decimal("60"))
            self.assertEqual(self.service.db.get_item("A").rate, Decimal("20"))
            self.call("project.undo")
            self.assertIsNone(self.service.db.get_item("A-copy"))
            self.call("project.redo")
            self.assertEqual(self.service.db.get_item("A-copy").rate, Decimal("40"))
            for count, rows in [(0, config["ana_copy_rows"]), (2, config["ana_copy_rows"]), (1, [])]:
                options = dict(config, ana_copy_delete_rows=count, ana_copy_rows=rows)
                self.call("schedule.editor.add_from_library", source=source, ids=[identity], modify=True, settings=options)
                values = self.service.db.get_item("A-copy2", modify_res_code=False)
                self.assertEqual(values.ana_items[-1]["description"], "Original total")
                self.call("project.undo")
            before = self.call("state")
            bad = copy.deepcopy(config)
            bad["ana_copy_rows"][0]["value"] = "1/0"
            with self.assertRaises(ValueError):
                self.call("schedule.editor.add_from_library", source=source, ids=[identity], modify=True, settings=bad)
            self.assertEqual(self.call("state"), before)
            self.assertIsNone(self.service.db.get_item("A-copy2"))
            self.assertEqual(library.read_bytes(), source_bytes)
