"""Saved report definitions preserve project compatibility, undo and failure boundaries."""

import copy
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from estimator import misc
from estimator.data.measurement import MeasurementItemCustom
from estimator.data.schedule import ScheduleDatabase, ScheduleItemModel
from estimator.undo import Stack
from modern.backend.reporting.settings import KEY
from modern.backend.service import Service


class ReportSettings(unittest.TestCase):
    """Exercise settings without adding tables, changing versions or saving previews."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "source.eproj"
        db = ScheduleDatabase(Stack())
        db.create_new_database(str(self.source))
        db.insert_item(ScheduleItemModel("A", "Work", "m", category="Work"))
        measurement = db.get_measurement()
        measurement.append_item(MeasurementItemCustom(plugin="_1_NLBH"))
        db.set_measurement(measurement)
        db.close_database()
        self.original = self.source.read_bytes()
        self.service = Service()
        self.addCleanup(self.service.close)
        self.service.call("project.open", dict(path=str(self.source)))
        self.spec = dict(
            schema_version=1,
            title="Saved report",
            organization="Office",
            font_family="DejaVu Serif",
            font_scale=1.25,
            sections=[
                dict(id="notes", kind="narrative", body="=Notes\n<Literal>"),
                dict(id="schedule", kind="schedule", columns=["quantity", "description"], orientation="landscape"),
                dict(id="other", kind="narrative", body="Independent notes", enabled=False),
            ],
        )

    def call(self, method, **params):
        return self.service.call(method, dict(revision=self.service.revision, **params))

    def snapshot(self):
        return copy.deepcopy(
            (
                list(self.service.db.database.connection().iterdump()),
                self.service.revision,
                self.service.workspace_dirty,
                self.service.project_editor.ids,
                self.service.project_editor.record_ids,
                self.service.clipboard,
                len(self.service.project_editor.history),
            )
        )

    def test_apply_is_idempotent_undoable_and_survives_save_reopen(self):
        before = self.snapshot()
        self.assertIsNone(self.call("report.settings")["specification"])
        self.assertEqual(before, self.snapshot())
        result = self.call("report.settings.apply", specification=self.spec)
        self.assertTrue(self.service.workspace_dirty)
        self.assertEqual(self.service.revision, before[1] + 1)
        self.assertEqual(len(self.service.project_editor.history), 1)
        applied = self.snapshot()
        self.call("report.settings.apply", specification=self.spec)
        self.assertEqual(applied, self.snapshot())
        self.call("project.undo")
        self.assertIsNone(self.call("report.settings")["specification"])
        self.call("project.redo")
        self.assertEqual(self.call("report.settings")["specification"], result["specification"])
        target = Path(self.temp.name) / "saved.eproj"
        self.call("project.save_copy", path=str(target))
        self.assertFalse(self.service.workspace_dirty)
        self.call("project.open", path=str(target))
        self.assertEqual(self.call("report.settings")["specification"], result["specification"])
        self.assertEqual(self.service.db.get_project_settings()["file_version"], misc.PROJECT_FILE_VER)
        with closing(sqlite3.connect(target)) as connection:
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone(), ("ok",))
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_write_failure_rolls_back_sql_revision_and_history(self):
        before = self.snapshot()
        write = self.service.db.set_project_settings

        def fail(settings):
            write(settings)
            raise RuntimeError("Simulated failure")

        with patch.object(self.service.db, "set_project_settings", side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, "Simulated failure"):
                self.call("report.settings.apply", specification=self.spec)
        self.assertEqual(before, self.snapshot())

    def test_invalid_or_future_definitions_survive_reads_unrelated_edits_and_saves(self):
        for index, raw in enumerate(("{broken", '{"schema_version":99,"office":"future"}', "null", "x" * 1_000_001)):
            with self.subTest(index=index):
                settings = self.service.db.get_project_settings()
                settings[KEY] = raw
                self.service.db.set_project_settings(settings)
                before = self.snapshot()
                result = self.call("report.settings")
                self.assertIsNone(result["specification"])
                self.assertIn("remain unchanged", result["warning"])
                self.assertEqual(before, self.snapshot())
                self.call("project.settings.edit", settings=dict(project_name=f"Project {index}"))
                # Existing measurement/settings writers retain unknown optional keys.
                self.service.db.set_measurement(self.service.db.get_measurement())
                target = Path(self.temp.name) / f"opaque-{index}.eproj"
                self.call("project.save_copy", path=str(target))
                self.call("project.open", path=str(target))
                self.assertEqual(self.service.db.get_project_settings()[KEY], raw)
        self.call("report.settings.apply", specification=self.spec)
        self.assertEqual(self.call("report.settings")["warning"], "")

    def test_revisions_invalid_inputs_and_filters_leave_state_unchanged(self):
        before = self.snapshot()
        for revision in (None, True, "1", self.service.revision - 1):
            for method in ("report.settings", "report.settings.apply"):
                with self.subTest(method=method, revision=revision), self.assertRaisesRegex(ValueError, "Stale"):
                    self.service.call(method, dict(revision=revision, specification=self.spec))
        for spec in (
            None,
            dict(schema_version=2),
            {**self.spec, "item_ids": []},
            {**self.spec, "category_ids": []},
            dict(
                sections=[dict(id=f"n{i}", kind="narrative", title="😀" * 10000, body="😀" * 10000) for i in range(20)]
            ),
        ):
            with self.subTest(spec_type=type(spec)), self.assertRaises(ValueError):
                self.call("report.settings.apply", specification=spec)
        self.assertEqual(before, self.snapshot())

    def test_dirty_drafts_cannot_be_discarded_by_applying_settings(self):
        self.call("analysis.load", code="A")
        self.call("analysis.edit", field="ana_remarks", value="Pending")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "Unsaved analysis"):
            self.call("report.settings.apply", specification=self.spec, discard=True)
        self.assertIsNone(self.call("report.settings")["specification"])
        self.assertEqual(before, self.snapshot())
        self.call("analysis.load", code="A", discard=True)
        editor = self.service.project_editor
        editor.ensure_ids()
        identity = editor.ids[0]
        self.call("measurement.draft.open", id=identity)
        self.call("measurement.record_add", id=identity)
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "Unsaved measurement"):
            self.call("report.settings.apply", specification=self.spec, discard=True)
        self.assertTrue(editor.measurement_draft.dirty)
        self.assertEqual(before, self.snapshot())

    def test_recovery_retains_applied_settings(self):
        self.service.recovery_dir = Path(self.temp.name) / "recovery"
        self.call("report.settings.apply", specification=self.spec)
        self.service.checkpoint_recovery()
        recovered = Service(self.service.recovery_dir)
        self.addCleanup(recovered.close)
        copies = recovered.call("recovery.list", {})
        self.assertTrue(copies)
        recovered.call("recovery.open", dict(id=copies[0]["id"]))
        self.assertEqual(json.loads(recovered.db.get_project_settings()[KEY])["title"], "Saved report")
