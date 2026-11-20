import hashlib
import json
from pathlib import Path
import tempfile
from decimal import Decimal
from test_mcp_server import MCPFixture


class MCPCanonicalTests(MCPFixture):
    def test_house_estimate_in_at_most_twenty_http_tool_calls(self):
        fixture = json.loads((Path(__file__).parent / "data/mcp_canonical.json").read_text())
        source = Path("Other databases/DSREM2022.eproj")
        original = hashlib.sha256(source.read_bytes()).digest()
        self.runtime.call("mcp.configure", dict(access="read-write"))
        self.start()
        calls = []
        def agent(name, **args):
            calls.append(name)
            result = self.tool(name, args)
            self.assertFalse(result["isError"], result)
            return result["structuredContent"]
        agent("get_state")
        agent("project", action="new")
        agent("project", action="set_settings", settings=dict(project_name=fixture["name"]))
        fixture["source"] = str(Path(fixture["source"]).resolve())  # the 2022 book, kept outside the bundle
        agent("describe_source", source=fixture["source"])
        matches = agent("search_items", source=fixture["source"], kind="schedule", query="modular switch light point PVC conduit")["data"]["items"]
        self.assertIn("1.10.1", [m["code"] for m in matches[:5]])
        codes = [row["code"] for row in fixture["items"]]
        imported = agent("import_items", source=fixture["source"], kind="schedule", codes=codes)
        self.assertEqual(imported["data"]["parents"], 3)
        self.assertEqual(imported["data"]["imported"], 14)
        self.assertTrue(imported["warnings"])
        agent("get_measurements", section="templates")
        agent("edit_measurements", ops=[dict(action="create", template="_1_NLBH", description=row["code"], links=[dict(code=row["code"])], records=[{"No":row["qty"]}]) for row in fixture["items"]])
        agent("recalculate", what="quantities", rounding="No rounding")
        summary = agent("get_summary")["data"]
        self.assertEqual(Decimal(summary["grand_total"]), Decimal(fixture["grand_total"]))
        self.assertTrue(all(c["count"] == 0 for c in summary["checks"].values()))
        rows = agent("get_items", kind="schedule", codes=codes)["data"]["items"]
        for expected, actual in zip(fixture["items"], rows):
            for field in ("code", "parent_code"):
                self.assertEqual(expected[field], actual[field])
            for field in ("qty", "rate"):
                self.assertEqual(Decimal(expected[field]), Decimal(actual[field]))
        with tempfile.TemporaryDirectory() as directory:
            path, book = Path(directory) / "house.eproj", Path(directory) / "house.xlsx"
            agent("project", action="export_xlsx", path=str(book))
            agent("project", action="save_copy", path=str(path))
            agent("project", action="open", path=str(path), discard=True)
            self.assertEqual(Decimal(agent("get_summary")["data"]["grand_total"]), Decimal(fixture["grand_total"]))
            self.assertGreater(book.stat().st_size, 0)
        self.assertEqual(len(calls), 15)
        self.assertLessEqual(len(calls), 20)
        self.assertEqual(hashlib.sha256(source.read_bytes()).digest(), original)
