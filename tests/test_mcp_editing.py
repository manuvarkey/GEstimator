import copy
import hashlib
import http.client
import json
import socket
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from unittest.mock import patch

from test_mcp_server import MCPFixture

from modern.backend.mcp_operations import OPERATIONS
from modern.backend.service import Service


class MCPEditingTests(MCPFixture):
    def writable(self):
        self.runtime.call("mcp.configure", dict(access="read-write"))
        self.start()

    def test_adapt_bundled_analysis_and_reuse_a_library_resource(self):
        self.writable()
        self.agent("project", action="new")
        source = "bundled:DSR2023.eproj"
        matches = self.agent("search_items", source=source, kind="schedule", query="demolishing rcc")["data"]["items"]
        self.assertEqual([row["code"] for row in matches[:2]], ["15.3", "15.58"])
        library_code = matches[0]["code"]
        imported = self.agent("import_items", source=source, kind="schedule", codes=[library_code])["data"]
        base = imported["code_map"][library_code]
        include = ["analysis", "resources"]
        original = self.agent("get_items", kind="schedule", codes=[base], include=include)["data"]["items"][0]

        self.agent(
            "upsert_items",
            kind="schedule",
            items=[dict(code="DEM", duplicate_from=base, description="Adapted concrete demolition", qty="2")],
        )
        equipment = self.agent("search_items", source=source, kind="resource", query="hydraulic excavator")["data"][
            "items"
        ][0]
        self.agent(
            "edit_analysis",
            code="DEM",
            ops=[
                dict(action="add", id="r0", kind="Group", description="Plant", ref="plant"),
                dict(action="add", target="resource", id="plant", source=source, code=equipment["code"], qty="1"),
            ],
        )
        retained, adapted = self.agent("get_items", kind="schedule", codes=[base, "DEM"], include=include)["data"][
            "items"
        ]
        self.assertEqual(retained, original)
        self.assertEqual(adapted["description"], "Adapted concrete demolition")
        self.assertEqual(Decimal(adapted["qty"]), 2)
        self.assertEqual(adapted["analysis"][:1] + adapted["analysis"][2:], original["analysis"])
        resource_code, qty, _ = adapted["analysis"][1]["resources"][0]
        resource = next(row for row in adapted["resources"] if row["code"] == resource_code)
        self.assertEqual(resource_code, f"DC23:{equipment['code']}")
        self.assertEqual((Decimal(resource["rate"]), Decimal(qty)), (Decimal(equipment["rate"]), 1))
        self.assertGreater(Decimal(adapted["rate"]), Decimal(original["rate"]))

    def agent(self, name, **arguments):
        response = self.tool(name, arguments)
        self.assertFalse(response["isError"], response)
        self.assertEqual(json.loads(response["content"][0]["text"]), response["structuredContent"])
        return response["structuredContent"]

    def setup_estimate(self):
        self.agent("project", action="new")
        self.agent(
            "batch",
            ops=[
                dict(
                    tool="upsert_items",
                    args=dict(
                        kind="resource",
                        items=[dict(code="R", description="Material", unit="kg", rate="10", category="Materials")],
                    ),
                ),
                dict(
                    tool="upsert_items",
                    args=dict(kind="schedule", items=[dict(code="A", description="Work", unit="m3", category="Civil")]),
                ),
                dict(
                    tool="edit_analysis",
                    args=dict(
                        code="A",
                        ops=[
                            dict(action="add", kind="Group", ref="materials"),
                            dict(action="add", target="resource", id="materials", code="R", qty="4"),
                        ],
                    ),
                ),
            ],
        )

    def test_agent_prepares_calculates_measures_exports_saves_and_reopens(self):
        self.writable()
        self.setup_estimate()
        definition = self.agent("get_items", kind="schedule", codes=["A"], include=["analysis", "resources"])["data"][
            "items"
        ][0]
        self.assertEqual(Decimal(definition["rate"]), 40)
        self.assertEqual(definition["analysis"][0]["resources"][0][1], "4")
        templates = self.agent("get_measurements", section="templates")["data"]["templates"]
        self.assertEqual({value["group"] for value in templates}, {"General", "Civil", "E&M"})
        nlb = next(t for t in templates if t["code"] == "_1_NLBH")
        self.assertEqual(nlb["columns"][1]["field"], "c1")
        self.assertFalse(nlb["columns"][1]["editable"])
        identity = self.agent(
            "edit_measurements",
            ops=[
                dict(
                    action="create",
                    template="_1_NLBH",
                    description="Dimensions",
                    links=[dict(code="A", remark="Measured")],
                    records=[{"No": "2*3", "L": "2+2"}, {"L": "2"}],
                )
            ],
        )["data"]["results"][0]["id"]
        self.assertEqual(self.agent("recalculate", what="quantities", rounding="No rounding")["data"]["changed"], 1)
        self.assertEqual(self.agent("recalculate", what="quantities", rounding="No rounding")["data"]["changed"], 0)
        self.assertEqual(Decimal(self.agent("get_summary")["data"]["grand_total"]), 1040)
        self.assertEqual(Decimal(self.agent("get_items", kind="schedule", codes=["A"])["data"]["items"][0]["qty"]), 26)
        with tempfile.TemporaryDirectory() as directory:
            path, book = Path(directory) / "estimate.eproj", Path(directory) / "estimate.xlsx"
            self.agent("project", action="export_xlsx", path=str(book))
            self.assertGreater(book.stat().st_size, 0)
            self.agent("project", action="save_copy", path=str(path))
            original = path.read_bytes()
            self.agent("upsert_items", kind="schedule", items=[dict(code="A", qty="27")])
            self.assertEqual(path.read_bytes(), original)
            saved = self.agent("project", action="save")["data"]
            self.assertEqual(Path(saved["backup"]).read_bytes(), original)
            self.agent("project", action="open", path=str(path), discard=True)
            measured = self.agent("get_measurements")["data"]["items"][0]["id"]
            row = self.agent("get_measurements", id=measured)["data"]["rows"][0]
            self.assertEqual((row["c2"], row["_display"]["c2"], row["_display"]["c1"]), ("2*3", "6", "[2*3,2+2,,]"))

    def test_source_parent_import_placement_conflicts_and_source_preservation(self):
        self.writable()
        self.agent("project", action="new")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "library.eproj"
            source = Service()
            try:
                source.call("project.new", {})
                for code, parent in (("1.2", ""), ("1.2.1", "1.2"), ("1.2.2", "1.2")):
                    source.call(
                        "schedule.editor.add",
                        dict(revision=source.revision, data=dict(code=code, parent=parent, rate="25", category="Work")),
                    )
                source.call(
                    "resources.editor.add",
                    dict(revision=source.revision, data=dict(code="R", rate="8", unit="kg", category="Materials")),
                )
                source.call(
                    "project.settings.edit",
                    dict(revision=source.revision, settings=dict(project_metadata="# Test library\nRates as on 2025.")),
                )
                source.call("project.save_copy", dict(path=str(path)))
            finally:
                source.close()
            original = hashlib.sha256(path.read_bytes()).digest()
            data = self.agent("describe_source", source=str(path))["data"]
            self.assertIn("categories", data)
            # Author notes reach MCP clients separately from technical settings.
            self.assertEqual(data["metadata"], "# Test library\nRates as on 2025.")
            self.assertNotIn("project_metadata", data["settings"])
            imported = self.agent(
                "import_items", source=str(path), kind="schedule", codes=["1.2.1"], qty={"1.2.1": "3"}
            )["data"]
            self.assertEqual(imported["parents"], 1)
            self.assertEqual(imported["code_map"], {"1.2": "1.2", "1.2.1": "1.2.1"})
            self.agent(
                "upsert_items",
                kind="schedule",
                items=[dict(code="1.10", category="Work"), dict(code="1.1", category="Work")],
            )
            self.assertEqual(
                [r["code"] for r in self.agent("browse", kind="schedule", under="Work")["data"]["items"]],
                ["1.1", "1.2", "1.10"],
            )
            self.assertEqual(
                self.agent("get_items", kind="schedule", codes=["1.2.1"])["data"]["items"][0]["parent_code"], "1.2"
            )
            self.agent("import_items", source=str(path), kind="resource", codes=["R"])
            self.assertEqual(
                Decimal(
                    self.agent("get_items", source=str(path), kind="resource", codes=["R"])["data"]["items"][0]["rate"]
                ),
                8,
            )
            self.assertTrue(
                self.tool("import_items", dict(source=str(path), kind="resource", codes=["R"], on_conflict="error"))[
                    "isError"
                ]
            )
            self.agent("import_items", source=str(path), kind="resource", codes=["R"], on_conflict="update")
            self.assertEqual(hashlib.sha256(path.read_bytes()).digest(), original)

    def test_revision_races_atomic_failure_and_access_boundaries(self):
        self.start()
        self.assertEqual(self.tool("project", dict(action="new"))["structuredContent"]["error"]["code"], "read_only")
        self.assertEqual(len(self.status["tools"]), 8)
        self.runtime.call("mcp.stop")
        self.writable()
        self.agent("project", action="new")
        self.agent(
            "upsert_items", kind="schedule", items=[dict(code="A", description="Original", rate="3", category="Work")]
        )
        before = self.runtime.call("state")
        failure = self.tool(
            "batch",
            dict(
                ops=[
                    dict(
                        tool="upsert_items", args=dict(kind="schedule", items=[dict(code="A", description="Changed")])
                    ),
                    dict(tool="upsert_items", args=dict(kind="schedule", items=[dict(code="A", rate="1/0")])),
                ]
            ),
        )
        self.assertTrue(failure["isError"])
        self.assertEqual(self.runtime.call("state"), before)
        self.assertEqual(
            self.agent("get_items", kind="schedule", codes=["A"])["data"]["items"][0]["description"], "Original"
        )
        self.assertTrue(self.tool("upsert_items", dict(if_revision=True, kind="schedule", items=[]))["isError"])
        self.assertTrue(self.tool("upsert_items", dict(kind="schedule", items=[], source="external"))["isError"])

        def edit(value):
            return self.tool(
                "upsert_items", dict(if_revision=before["revision"], kind="schedule", items=[dict(code="A", qty=value)])
            )

        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(edit, ["4", "5"]))
        self.assertEqual(sorted(result["isError"] for result in results), [False, True])
        self.assertEqual(self.runtime.call("state")["revision"], before["revision"] + 1)
        self.assertEqual(self.tool("state")["structuredContent"]["error"]["code"], "unknown_tool")
        self.assertTrue(self.tool("mcp.stop")["isError"])
        self.assertTrue(self.runtime.call("mcp.status")["running"])

    def test_batch_one_undo_and_failure_preserves_redo_measurement_ids(self):
        self.writable()
        self.setup_estimate()
        self.agent("history", action="undo")
        self.assertEqual(self.agent("get_state")["data"]["counts"]["schedule"], 0)
        self.agent("history", action="redo")
        before = self.runtime.call("state")
        result = self.tool(
            "batch",
            dict(
                ops=[
                    dict(
                        tool="edit_measurements",
                        args=dict(ops=[dict(action="create", template="_1_NLBH", records=[{"L": "2"}])]),
                    ),
                    dict(tool="upsert_items", args=dict(kind="schedule", items=[dict(code="A", rate="1/0")])),
                ]
            ),
        )
        self.assertTrue(result["isError"])
        self.assertEqual(self.runtime.call("state"), before)
        self.assertEqual(self.agent("get_measurements")["data"]["total"], 0)
        self.agent("history", action="undo")
        self.assertEqual(self.agent("get_state")["data"]["counts"]["schedule"], 0)
        self.agent("history", action="redo")
        self.assertEqual(Decimal(self.agent("get_items", kind="schedule", codes=["A"])["data"]["items"][0]["rate"]), 40)

    def test_draft_protection_preview_and_computed_column_errors(self):
        self.writable()
        self.setup_estimate()
        self.runtime.call("analysis.load", dict(code="A"))
        row = self.runtime.call("state")["rows"][0]["_children"][0]
        self.runtime.call(
            "edit", dict(revision=self.runtime.call("state")["revision"], id=row["id"], field="value", value="8")
        )
        draft = self.runtime.call("state")
        self.assertEqual(
            self.tool("edit_analysis", dict(code="A", ops=[]))["structuredContent"]["error"]["code"], "draft_conflict"
        )
        self.assertEqual(self.runtime.call("state"), draft)
        preview = self.agent(
            "edit_analysis",
            code="A",
            ops=[dict(action="edit", id="r0:0", field="value", value="7")],
            preview=True,
            discard_draft=True,
        )
        self.assertEqual(Decimal(preview["data"]["rate"]), 70)
        self.assertEqual(preview["revision"], draft["revision"])
        self.assertEqual(self.runtime.call("state"), draft)
        self.agent("edit_analysis", code="A", ops=[], discard_draft=True)
        before = self.runtime.call("state")
        result = self.tool(
            "edit_measurements", dict(ops=[dict(action="create", template="_1_NLBH", records=[{"Breakup": "2"}])])
        )
        error = result["structuredContent"]["error"]
        self.assertEqual(error["code"], "not_editable")
        self.assertEqual(error["field"], "c1")
        self.assertIn("c2", error["allowed"])
        self.assertEqual(self.runtime.call("state"), before)
        self.assertEqual(self.agent("get_measurements")["data"]["total"], 0)

    def test_failed_recovery_checkpoint_reports_committed_operation(self):
        self.writable()
        self.agent("project", action="new")
        with patch.object(Service, "checkpoint_recovery", side_effect=OSError("Unavailable")):
            result = self.agent("upsert_items", kind="schedule", items=[dict(code="A", category="Work")])
        self.assertEqual(result["warnings"][0]["code"], "recovery_failed")
        self.assertEqual(self.agent("get_state")["data"]["counts"]["schedule"], 1)

    def test_stopped_listener_rejects_an_already_accepted_incomplete_write(self):
        self.writable()
        revision = self.agent("project", action="new")["revision"]
        body = json.dumps(
            dict(
                jsonrpc="2.0",
                id=100,
                method="tools/call",
                params=dict(
                    name="upsert_items",
                    arguments=dict(if_revision=revision, kind="schedule", items=[dict(code="LATE", category="Work")]),
                ),
            )
        ).encode()
        parsed = threading.Event()
        original = BaseHTTPRequestHandler.parse_request

        def parse(handler):
            accepted = original(handler)
            if handler.headers.get("X-Test-Held-Body"):
                parsed.set()
            return accepted

        with (
            patch.object(BaseHTTPRequestHandler, "parse_request", parse),
            socket.create_connection(("127.0.0.1", self.port), timeout=5) as client,
        ):
            headers = f"POST /mcp HTTP/1.1\r\nHost: 127.0.0.1:{self.port}\r\nAuthorization: Bearer {self.token}\r\nContent-Type: application/json\r\nAccept: application/json, text/event-stream\r\nX-Test-Held-Body: true\r\nContent-Length: {len(body)}\r\n\r\n"
            client.sendall(headers.encode())
            self.assertTrue(parsed.wait(timeout=3))
            self.runtime.call("mcp.stop")
            self.runtime.call("mcp.start")
            client.sendall(body)
            response = http.client.HTTPResponse(client)
            response.begin()
            self.assertTrue(json.loads(response.read())["result"]["isError"])
        self.assertEqual(self.runtime.call("schedule.editor.state")["total"], 0)

    def test_move_subtree_reparent_cycle_rollback_and_measurement_links(self):
        self.writable()
        self.agent("project", action="new")
        self.agent(
            "upsert_items",
            kind="schedule",
            items=[
                dict(code="P", category="Work"),
                dict(code="Q", category="Work"),
                dict(code="C", parent="P", unit="m", category="Work"),
            ],
        )
        identity = self.agent(
            "edit_measurements",
            ops=[dict(action="create", template="_1_NLBH", links=[dict(code="C")], records=[{"L": "7"}])],
        )["data"]["results"][0]["id"]
        self.agent("move_items", kind="schedule", codes=["P", "C"], position=dict(after="Q"))
        rows = self.agent("get_items", kind="schedule", codes=["C"])["data"]["items"]
        self.assertEqual([r["parent_code"] for r in rows], ["P"])
        # Two levels only: a subitem cannot take subitems.
        self.assertTrue(
            self.tool(
                "upsert_items", dict(kind="schedule", items=[dict(code="G", parent="C", unit="m", category="Work")])
            )["isError"]
        )
        self.agent("move_items", kind="schedule", codes=["C"], position=dict(parent="Q", index=0))
        self.assertEqual(self.agent("get_items", kind="schedule", codes=["C"])["data"]["items"][0]["parent_code"], "Q")
        before = self.runtime.call("state")
        self.assertTrue(
            self.tool("move_items", dict(kind="schedule", codes=["P"], position=dict(parent="C", index=0)))["isError"]
        )
        self.assertEqual(self.runtime.call("state"), before)
        detail = self.agent("get_measurements", id=identity)["data"]
        self.assertEqual(detail["links"][0]["code"], "C")
        self.assertEqual(Decimal(detail["totals"][0]), 7)
        self.agent("history", action="undo")
        self.assertEqual(self.agent("get_items", kind="schedule", codes=["C"])["data"]["items"][0]["parent_code"], "P")

    def test_delete_usage_policy_preview_and_undo(self):
        self.writable()
        self.setup_estimate()
        revision = self.runtime.call("state")["revision"]
        preview = self.agent("delete_items", kind="resource", codes=["R"], preview=True)
        self.assertEqual(preview["data"]["used_resources"], ["R"])
        self.assertEqual(preview["revision"], revision)
        self.assertTrue(self.tool("delete_items", dict(kind="resource", codes=["R"], policy="protect"))["isError"])
        self.agent("delete_items", kind="resource", codes=["R"], policy="all")
        self.assertEqual(self.agent("get_state")["data"]["counts"]["resource"], 0)
        self.agent("history", action="undo")
        self.assertEqual(Decimal(self.agent("get_items", kind="schedule", codes=["A"])["data"]["items"][0]["rate"]), 40)

    def test_stored_import_rates_recalculate_preview_and_undo(self):
        self.writable()
        self.agent("project", action="new")
        imported = self.agent(
            "import_items",
            source=str(Path("Other databases/DSREM2022.eproj").resolve()),
            kind="schedule",
            codes=["1.10.1"],
            rate_mode="stored",
        )
        self.assertIn("1.10.1", [w["code"] for w in imported["warnings"]])

        def rate():
            return Decimal(self.agent("get_items", kind="schedule", codes=["1.10.1"])["data"]["items"][0]["rate"])

        self.assertEqual(rate(), 1015)
        state = self.runtime.call("state")
        self.agent("recalculate", what="rates", codes=["1.10.1"], preview=True)
        self.assertEqual(self.runtime.call("state"), state)
        self.assertEqual(rate(), 1015)
        self.agent("recalculate", what="rates", codes=["1.10.1"])
        self.assertEqual(rate(), 1061)
        self.agent("history", action="undo")
        self.assertEqual(rate(), 1015)

    def test_analysis_duplicate_and_measurement_base_captions_after_link_remarks(self):
        self.writable()
        self.setup_estimate()
        self.agent(
            "edit_analysis",
            code="A",
            ops=[dict(action="duplicate", ids=["r0"], id="r0"), dict(action="add", kind="Subtotal")],
        )
        definition = self.agent("get_items", kind="schedule", codes=["A"], include=["analysis"])["data"]["items"][0]
        self.assertEqual(Decimal(definition["rate"]), 80)
        self.assertEqual(len(definition["analysis"]), 3)
        self.assertTrue(all(len(row["resources"]) == 1 for row in definition["analysis"][:2]))
        template = next(
            t
            for t in self.agent("get_measurements", section="templates")["data"]["templates"]
            if t["code"] == "_2_LLLLL"
        )
        column = next(c for c in template["columns"] if c["editable"] and c["numeric"])
        identity = self.agent(
            "edit_measurements",
            ops=[
                dict(
                    action="create",
                    template=template["code"],
                    links=[dict(code="A", remark="First quantity")],
                    records=[{column["title"]: "2"}],
                )
            ],
        )["data"]["results"][0]["id"]
        detail = self.agent("get_measurements", id=identity)["data"]
        self.assertEqual(detail["rows"][0][column["field"]], "2")
