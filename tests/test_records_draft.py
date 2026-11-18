import copy
import tempfile
import unittest
from pathlib import Path
from modern.backend.service import Service


class RecordsDraftTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.service = Service(recovery_dir=Path(self.temp.name) / "recovery")
        self.addCleanup(self.service.close)
        self.call("project.new")
        self.identity = self.call("measurement.add", template="_1_NLBH", description="Room")["selected"][0]
        self.original = copy.deepcopy(self.service.db.get_measurement().get_model())
        self.call("measurement.draft.open", id=self.identity)
        self.history = len(self.service.project_editor.history)

    def call(self, method, **params):
        return self.service.call(method, dict(revision=self.service.revision, **params))

    def detail(self):
        return self.call("measurement.detail", id=self.identity)["detail"]

    def add_record(self):
        self.call("measurement.record_add", id=self.identity)
        return self.detail()["rows"][-1]["id"]

    def test_records_are_a_draft_with_separate_undo_and_one_project_apply(self):
        record = self.add_record()
        self.call("measurement.record_edit", id=self.identity, record_id=record, field="c3", value="2*3")
        self.assertTrue(self.service.records_dirty)
        self.assertEqual(self.service.db.get_measurement().get_model(), self.original)
        self.assertEqual(len(self.service.project_editor.history), self.history)
        self.call("measurement.draft.undo")
        self.assertEqual(self.detail()["rows"][0]["c3"], "")
        self.call("measurement.draft.redo")
        self.assertEqual(self.detail()["rows"][0]["c3"], "2*3")
        self.call("measurement.draft.apply")
        self.assertFalse(self.service.records_dirty)
        self.assertEqual(len(self.service.project_editor.history), self.history + 1)
        self.assertEqual(len(self.service.db.get_measurement().items[0].records), 1)
        self.call("project.undo")
        self.assertEqual(self.service.db.get_measurement().get_model(), self.original)
        self.assertEqual(self.service.project_editor.record_ids[self.identity], [])
        self.call("project.redo")
        self.assertEqual(self.service.project_editor.record_ids[self.identity], [record])
        self.assertEqual(self.detail()["rows"][0]["c3"], "2*3")

    def test_navigation_and_project_mutations_guard_dirty_records(self):
        self.add_record()
        for method, params in [("project.new", {}), ("schedule.editor.add", dict(data=dict(code="X"))),
                               ("measurement.draft.close", {}), ("project.undo", {}),
                               ("measurement.update_quantities", {})]:
            with self.assertRaisesRegex(ValueError, "measurement records"):
                self.call(method, **params)
        self.call("measurement.draft.discard")
        self.assertFalse(self.service.records_dirty)
        self.assertEqual(self.detail()["rows"], [])
        self.assertEqual(len(self.service.project_editor.history), self.history)
        self.assertEqual(self.service.db.get_measurement().get_model(), self.original)

    def test_properties_clipboard_and_invalid_batches_use_draft(self):
        record = self.add_record()
        self.call("measurement.edit", id=self.identity, value="Edited room")
        data = self.call("clipboard.export", kind="records", id=self.identity, record_ids=[record])
        self.call("clipboard.paste", kind="records", id=self.identity, data=data)
        self.assertEqual(self.detail()["total_records"], 2)
        self.assertEqual(self.detail()["description"], "Edited room")
        before = self.call("measurement.detail", id=self.identity)
        with self.assertRaises(ValueError):
            self.call("measurement.record_edit_many", id=self.identity, edits=[
                dict(id=record, field="c3", value="7"), dict(id=record, field="c4", value="1/0")])
        self.assertEqual(self.call("measurement.detail", id=self.identity), before)
        self.assertEqual(self.service.db.get_measurement().get_model(), self.original)

    def test_save_and_recovery_include_pending_records(self):
        self.add_record()
        self.service.checkpoint_recovery()
        recovery = Path(self.temp.name) / "recovery" / (self.service.recovery_id + ".eproj")
        self.assertTrue(recovery.exists())
        other = Service()
        self.addCleanup(other.close)
        other.call("project.open", dict(path=str(recovery)))
        self.assertEqual(len(other.db.get_measurement().items[0].records), 1)
        self.assertTrue(self.service.records_dirty)
        destination = Path(self.temp.name) / "saved.eproj"
        self.call("project.save_copy", path=str(destination))
        self.assertFalse(self.service.records_dirty)
        self.assertFalse(self.service.workspace_dirty)
        other.call("project.open", dict(path=str(destination), discard=True))
        self.assertEqual(len(other.db.get_measurement().items[0].records), 1)

    def test_failed_save_preserves_the_pending_records(self):
        self.add_record()
        before = self.call("state")
        with self.assertRaises(FileNotFoundError):
            self.call("project.save_copy", path=str(Path(self.temp.name) / "missing" / "saved.eproj"))
        self.assertEqual(self.call("state"), before)
        self.assertEqual(self.detail()["total_records"], 1)
        self.assertEqual(self.service.db.get_measurement().get_model(), self.original)

    def test_mcp_reads_remain_committed_and_writes_report_draft_conflict(self):
        from modern.backend.mcp_query import projection
        from modern.backend.mcp_workspace import Workspace
        from modern.backend.mcp_server import error_result
        original_record = self.add_record()
        self.call("measurement.draft.apply")
        self.call("measurement.record_delete", id=self.identity, record_id=original_record)
        workspace = Workspace(self.service)
        detail = workspace.get_measurements(dict(id=self.identity), [])
        self.assertEqual(len(detail["rows"]), 1)
        self.assertEqual(detail["rows"][0]["id"], original_record)
        self.assertEqual(self.detail()["total_records"], 0)
        data = projection(self.service, self.service.db)
        self.assertEqual(data["v_measurement_records"][0][1], original_record)
        self.assertEqual(self.detail()["total_records"], 0)
        self.assertTrue(workspace.get_state({}, [])["records_dirty"])
        try:
            workspace.edit_measurements(dict(ops=[dict(action="records_add", id=self.identity)]), [])
        except ValueError as error:
            self.assertEqual(error_result(error)["structuredContent"]["error"]["code"], "draft_conflict")
        else:
            self.fail("An agent must not change the human records draft")

    def test_stale_records_and_failed_apply_retain_the_draft_and_history(self):
        from unittest.mock import patch
        self.add_record()
        before = self.call("state")
        with self.assertRaisesRegex(ValueError, "Stale"):
            self.service.call("measurement.draft.apply", dict(revision=self.service.revision - 1))
        with patch.object(self.service.db, "set_measurement", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                self.call("measurement.draft.apply")
        self.assertEqual(self.call("state"), before)
        self.assertEqual(self.service.db.get_measurement().get_model(), self.original)
        self.assertEqual(len(self.service.project_editor.history), self.history)
        self.call("measurement.draft.apply")
        self.assertFalse(self.service.records_dirty)

    def test_every_shipped_template_can_apply_and_discard_records(self):
        self.call("measurement.draft.discard")
        for template in self.call("measurement.templates"):
            identity = self.call("measurement.add", template=template["code"])["selected"][0]
            self.call("measurement.draft.open", id=identity)
            self.call("measurement.record_add", id=identity, count=2)
            self.call("measurement.draft.apply")
            self.call("measurement.record_add", id=identity)
            self.call("measurement.draft.discard")
            detail = self.call("measurement.detail", id=identity)["detail"]
            self.assertEqual(detail["total_records"], 2)

    def test_whole_item_paste_after_apply_creates_a_project_item(self):
        self.add_record()
        self.call("measurement.draft.apply")
        data = self.call("clipboard.export", kind="measurement", ids=[self.identity])
        self.call("clipboard.paste", kind="measurement", id=self.identity, data=data)
        meas = self.service.db.get_measurement()
        self.assertEqual(len(meas.items), 2)
        self.assertEqual([len(item.records) for item in meas.items], [1, 1])
        self.call("project.undo")
        self.assertEqual(len(self.service.db.get_measurement().items), 1)

    def test_clean_draft_closes_before_main_properties_or_agent_edits(self):
        from modern.backend.mcp_workspace import Workspace
        self.call("measurement.draft.close")
        self.call("measurement.edit", id=self.identity, value="Main properties")
        self.assertEqual(self.service.db.get_measurement().items[0].remark, "Main properties")
        self.call("measurement.draft.open", id=self.identity)
        Workspace(self.service).edit_measurements(dict(ops=[dict(action="update", id=self.identity, description="Agent committed")]), [])
        self.assertEqual(self.service.db.get_measurement().items[0].remark, "Agent committed")
        self.assertIsNone(self.service.project_editor.measurement_draft)
        self.assertFalse(self.service.records_dirty)
