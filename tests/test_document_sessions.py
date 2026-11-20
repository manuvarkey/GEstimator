import tempfile
import unittest
from pathlib import Path
from modern.backend.runtime import Runtime


class DocumentSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.runtime = Runtime(Path(self.temp.name))
        self.addCleanup(self.runtime.close)

    def call(self, method, session=None, **params):
        state = self.runtime.call("state", session=session) if not method.startswith("session.") else {}
        return self.runtime.call(method, dict(revision=state.get("revision", 0), **params), session=session)

    def test_sessions_hold_independent_projects_and_recovery(self):
        self.call("session.open", session="second")
        self.call("project.new")
        self.call("project.new", session="second")
        self.call("schedule.editor.add", session="second", data=dict(code="X", category="Work"))
        self.runtime.checkpoint_recovery("second")
        self.assertTrue(self.call("state", session="second")["workspace_dirty"])
        self.assertEqual(self.call("schedule.editor.state")["total"], 0)
        # A live document's recovery copy is not offered to the other document.
        self.assertEqual(self.call("recovery.list"), [])
        # MCP requests (no session) follow the active document.
        self.call("session.activate", session="second")
        self.assertTrue(self.runtime.call("state")["workspace_dirty"])
        self.assertEqual(self.call("session.close", session="second")["active"], "main")
        with self.assertRaisesRegex(ValueError, "closed"):
            self.runtime.call("state", session="second")
        with self.assertRaisesRegex(ValueError, "At least one"):
            self.call("session.close", session="main")
        # The closed document's recovery copy is now recoverable elsewhere.
        self.assertEqual(len(self.call("recovery.list")), 1)


class CloseProjectTests(unittest.TestCase):
    def test_close_requires_discard_for_unsaved_work_and_clears_project(self):
        from modern.backend.service import Service
        service = Service()
        self.addCleanup(service.close)
        call = lambda method, **params: service.call(method, dict(revision=service.revision, **params))
        call("project.new")
        call("schedule.editor.add", data=dict(code="X", category="Work"))
        with self.assertRaisesRegex(ValueError, "Unsaved"):
            call("project.close")
        state = call("project.close", discard=True)
        self.assertFalse(state["project_open"])
        self.assertIsNone(service.db)
        call("project.new")
        self.assertTrue(service.state()["project_open"])


class DatabaseNotesTests(unittest.TestCase):
    def test_notes_are_saved_with_project_and_validated(self):
        from modern.backend.service import Service
        service = Service()
        self.addCleanup(service.close)
        call = lambda method, **params: service.call(method, dict(revision=service.revision, **params))
        call("project.new")
        call("project.settings.edit", settings=dict(project_metadata="# DSR\n**2025** rates"))
        self.assertEqual(call("project.settings")["project_metadata"], "# DSR\n**2025** rates")
        self.assertEqual(service.db.get_project_settings()["project_metadata"], "# DSR\n**2025** rates")
        with self.assertRaisesRegex(ValueError, "100,000"):
            call("project.settings.edit", settings=dict(project_metadata="x" * 100_001))
        call("project.undo")
        self.assertEqual(call("project.settings")["project_metadata"], "")
