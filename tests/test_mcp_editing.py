import hashlib
import http.client
import json
import socket
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler
from modern.backend.mcp_operations import OPERATIONS
from modern.backend.service import Service
import test_mcp_server as transport


class MCPEditingTests(transport.MCPServerTests):
    # Reuse the real HTTP/runtime fixture, without repeating its transport tests.
    test_protocol_discovery_notifications_and_invalid_transport = None
    test_bearer_host_and_origin_guards = None
    test_live_project_and_measurements_are_read_only = None
    test_parallel_http_and_desktop_reads_share_owner_thread = None
    test_configuration_conflict_rotation_and_shutdown_release_socket = None

    def writable(self):
        self.runtime.call("mcp.configure", dict(access="read-write"))
        self.start()

    def agent(self, name, **arguments):
        if OPERATIONS[name]["write"] or "revision" in OPERATIONS[name]["definition"]["inputSchema"]["required"]:
            arguments.setdefault("revision", self.runtime.call("state")["revision"])
        response = self.tool(name, arguments)
        self.assertFalse(response["isError"], response)
        return json.loads(response["content"][0]["text"])

    def test_agent_prepares_calculates_measures_exports_saves_and_reopens(self):
        self.writable()
        definitions = {tool["name"]: tool for tool in self.status["tools"]}
        self.assertTrue(definitions["schedule.editor.edit"]["annotations"]["destructiveHint"])
        self.assertFalse(definitions["schedule.editor.edit"]["annotations"]["readOnlyHint"])
        self.assertTrue(definitions["database.inspect"]["annotations"]["readOnlyHint"])
        self.agent("project.new")
        self.agent("project.settings.edit", settings=dict(project_name="Agent estimate"))
        self.agent("resources.editor.add", data=dict(code="R", description="Material", unit="kg", rate="10", category="Materials"))
        schedule = self.agent("schedule.editor.add", data=dict(code="A", description="Work", unit="m3", category="Civil"))["data"]["selected"][0]
        self.agent("analysis.load", code="A")
        group = self.agent("analysis.add_row", kind="Group", description="Materials")["data"]["rows"][0]["id"]
        analysis = self.agent("analysis.resource_add", id=group, code="R", library=True, qty="2*3")["data"]
        self.assertEqual(Decimal(analysis["rate"]), 60)
        resource = analysis["rows"][0]["_children"][0]["id"]
        before = self.runtime.call("state")
        edits = [dict(method="edit", id=resource, field="value", value="4")]
        preview = self.agent("analysis.batch.preview", operations=edits)
        self.assertEqual(Decimal(preview["data"]["rate"]), 40)
        self.assertEqual(self.runtime.call("state"), before)
        self.agent("analysis.batch", operations=edits)
        self.assertEqual(Decimal(self.agent("analysis.undo")["data"]["rate"]), 60)
        self.assertEqual(Decimal(self.agent("analysis.redo")["data"]["rate"]), 40)
        self.agent("analysis.apply")
        self.assertEqual(Decimal(self.agent("database.analysis", code="A")["data"]["rate"]), 40)
        templates = self.agent("measurement.templates")["data"]
        self.assertEqual({value["group"] for value in templates}, {"General", "Civil", "E&M"})
        identity = self.agent("measurement.add", template="_1_NLBH", description="Dimensions")["data"]["selected"][0]
        self.agent("measurement.record_add", id=identity, count=2)
        detail = self.agent("measurement.detail", id=identity)["data"]["detail"]
        records = detail["rows"]
        self.agent("measurement.record_edit_many", id=identity, edits=[
            dict(id=records[0]["id"], field="c2", value="2*3"), dict(id=records[0]["id"], field="c3", value="2+2"),
            dict(id=records[1]["id"], field="c3", value="2")])
        self.agent("measurement.link", id=identity, slot=0, code="A", remark="Measured")
        self.agent("measurement.update_quantities", rounding="No rounding")
        rows = self.agent("schedule.editor.state")["data"]["rows"][0]["_children"]
        self.assertEqual(Decimal(rows[0]["qty"]), 26)
        self.assertEqual(Decimal(rows[0]["amount"]), 1040)
        metadata = self.agent("database.inspect")["data"]
        self.assertEqual(metadata["metadata"]["project_name"], "Agent estimate")
        self.assertEqual((metadata["schedule_items"], metadata["resources"]), (1, 1))
        with tempfile.TemporaryDirectory() as directory:
            path, book = Path(directory) / "estimate.eproj", Path(directory) / "estimate.xlsx"
            self.agent("project.export_xlsx", path=str(book))
            self.assertGreater(book.stat().st_size, 0)
            self.agent("project.save_copy", path=str(path))
            original = path.read_bytes()
            self.agent("schedule.editor.edit", id=schedule, field="qty", value="27")
            self.assertEqual(path.read_bytes(), original)
            saved = self.agent("project.save")["data"]
            self.assertEqual(Path(saved["backup"]).read_bytes(), original)
            self.agent("project.open", path=str(path), discard=True)
            measured = self.agent("measurement.state")["data"]["rows"][0]["id"]
            row = self.agent("measurement.detail", id=measured)["data"]["detail"]["rows"][0]
            self.assertEqual((row["c2"], row["_display"]["c2"], row["_display"]["c1"]), ("2*3", "6", "[2*3,2+2,,]"))

    def test_attached_database_metadata_read_import_and_source_preservation(self):
        self.writable()
        self.agent("project.new")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "library.eproj"
            source = Service()
            try:
                source.call("project.new", {})
                source.call("resources.editor.add", dict(revision=source.revision, data=dict(code="R", rate="8", unit="kg", category="Materials")))
                source.call("schedule.editor.add", dict(revision=source.revision, data=dict(code="DB", rate="25", category="Work")))
                source.call("project.save_copy", dict(path=str(path)))
            finally:
                source.close()
            original = hashlib.sha256(path.read_bytes()).digest()
            library = self.agent("library.attach", path=str(path))["data"][0]["id"]
            self.assertEqual(self.agent("database.inspect", source=library)["data"]["resources"], 1)
            self.assertEqual(Decimal(self.agent("database.resource", source=library, code="R")["data"]["rate"]), 8)
            self.assertEqual(Decimal(self.agent("database.analysis", source=library, code="DB")["data"]["rate"]), 25)
            for kind in ("schedule", "resources"):
                row = self.agent(kind + ".editor.state", source=library)["data"]["rows"][0]["_children"][0]
                self.agent(kind + ".editor.add_from_library", source=library, ids=[row["id"]])
            before = self.runtime.call("state")
            self.agent("database.analysis", source=library, code="DB")
            self.assertEqual(self.runtime.call("state"), before)
            self.assertEqual(hashlib.sha256(path.read_bytes()).digest(), original)

    def test_read_mode_revision_races_atomic_failure_and_access_boundaries(self):
        self.start()
        self.assertTrue(self.tool("project.new", dict(revision=0))["isError"])
        self.assertNotIn("project.new", {item["name"] for item in self.status["tools"]})
        self.runtime.call("mcp.stop")
        self.writable()
        self.agent("project.new")
        identity = self.agent("schedule.editor.add", data=dict(code="A", description="Original", rate="3", category="Work"))["data"]["selected"][0]
        before = self.agent("schedule.editor.state")
        failure = self.tool("schedule.editor.edit_many", dict(revision=before["revision"], edits=[dict(id=identity, field="description", value="Changed"), dict(id=identity, field="rate", value="1/0")]))
        self.assertTrue(failure["isError"])
        self.assertEqual(self.agent("schedule.editor.state"), before)
        self.assertTrue(self.tool("schedule.editor.edit", dict(revision=True, id=identity, field="qty", value="2"))["isError"])
        self.assertTrue(self.tool("schedule.editor.edit", dict(revision=before["revision"], id=identity, field="qty", value="2", source="external"))["isError"])
        def edit(value):
            return self.tool("schedule.editor.edit", dict(revision=before["revision"], id=identity, field="qty", value=value))
        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(edit, ["4", "5"]))
        self.assertEqual(sorted(result["isError"] for result in results), [False, True])
        self.assertEqual(self.runtime.call("state")["revision"], before["revision"] + 1)
        self.assertTrue(self.tool("mcp.stop")["isError"])
        self.assertTrue(self.runtime.call("mcp.status")["running"])

    def test_failed_recovery_checkpoint_reports_committed_operation(self):
        self.writable()
        self.agent("project.new")
        with patch.object(Service, "checkpoint_recovery", side_effect=OSError("Unavailable")):
            result = self.agent("schedule.editor.add", data=dict(code="A", category="Work"))
        self.assertIn("Operation applied", result["warning"])
        self.assertEqual(self.agent("schedule.editor.state")["data"]["total"], 1)

    def test_stopped_listener_rejects_an_already_accepted_incomplete_write(self):
        self.writable()
        revision = self.agent("project.new")["revision"]
        body = json.dumps(dict(jsonrpc="2.0", id=100, method="tools/call", params=dict(name="schedule.editor.add", arguments=dict(revision=revision, data=dict(code="LATE", category="Work"))))).encode()
        parsed = threading.Event()
        original = BaseHTTPRequestHandler.parse_request
        def parse(handler):
            accepted = original(handler)
            if handler.headers.get("X-Test-Held-Body"):
                parsed.set()
            return accepted
        with patch.object(BaseHTTPRequestHandler, "parse_request", parse), socket.create_connection(("127.0.0.1", self.port), timeout=5) as client:
            headers = f"POST /mcp HTTP/1.1\r\nHost: 127.0.0.1:{self.port}\r\nAuthorization: Bearer {self.token}\r\nContent-Type: application/json\r\nAccept: application/json, text/event-stream\r\nX-Test-Held-Body: true\r\nContent-Length: {len(body)}\r\n\r\n"
            client.sendall(headers.encode())
            self.assertTrue(parsed.wait(timeout=3))
            self.runtime.call("mcp.stop")
            self.runtime.call("mcp.start")
            client.sendall(body)
            response = http.client.HTTPResponse(client)
            response.begin()
            result = json.loads(response.read())
            self.assertTrue(result["result"]["isError"])
        self.assertEqual(self.runtime.call("schedule.editor.state")["total"], 0)
