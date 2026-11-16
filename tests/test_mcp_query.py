import json
import re
import time
import unittest
from modern.backend.mcp_operations import execute, ToolError
from modern.backend.mcp_server import MCPServer, INSTRUCTIONS
from modern.backend.service import Service


class MCPQueryTests(unittest.TestCase):
    def setUp(self):
        self.s = Service()
        self.addCleanup(self.s.close)
        self.s.mcp.access = "read-write"
        execute(self.s, "project", dict(action="new"))
        execute(self.s, "upsert_items", dict(kind="schedule", items=[dict(code="A", unit="m", description="Example", qty="2", rate="3", category="Work")]))

    def test_discovery_size_names_and_output_schemas(self):
        server = MCPServer(None)
        server.access = "read-write"
        tools = server.tools()
        encoded = json.dumps(dict(jsonrpc="2.0", id=1, result=dict(tools=tools)), separators=(",", ":")).encode()
        self.assertEqual(len(tools), 19)
        self.assertLessEqual(len(encoded), 16 * 1024)
        self.assertEqual(len({t["name"] for t in tools}), 19)
        self.assertTrue(all(re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", t["name"]) for t in tools))
        self.assertTrue(all(t["outputSchema"]["type"] == "object" for t in tools))
        self.assertLess(len(INSTRUCTIONS.split()), 230)
        server.access = "read"
        self.assertEqual(len(server.tools()), 8)

    def test_query_views_parameters_joins_and_read_only_access(self):
        before = self.s.state()
        self.s.mcp.access = "read"
        result = execute(self.s, "query", dict(sql="SELECT code, amount FROM v_schedule WHERE qty > ?", params=["1"]))["data"]
        self.assertEqual(result, dict(columns=["code", "amount"], rows=[["A", "6.00"]], truncated=False))
        result = execute(self.s, "query", dict(sql="WITH picked AS (SELECT code FROM v_schedule) SELECT code FROM picked"))["data"]
        self.assertEqual(result["rows"], [["A"]])
        self.assertEqual(self.s.state(), before)
        schema = execute(self.s, "describe_source", dict(section="schema"))["data"]
        self.assertEqual(len(schema["views"]), 6)
        self.assertIn("amount", schema["views"]["v_schedule"])

    def test_mutations_raw_tables_pragmas_extensions_and_multiple_statements_rejected(self):
        before = self.s.state()
        statements = ["INSERT INTO _schedule(code) VALUES ('BAD')", "UPDATE _schedule SET code='BAD'", "DELETE FROM _schedule", "ATTACH DATABASE ':memory:' AS other", "PRAGMA table_info(v_schedule)", "SELECT * FROM scheduletable", "SELECT * FROM _schedule", "SELECT * FROM sqlite_master", "SELECT load_extension('anything')", "SELECT 1; SELECT 2", "SELECT 1e999", "CREATE TABLE x(y)", 'WITH v_schedule AS (SELECT * FROM "_schedule") SELECT * FROM v_schedule']
        for sql in statements:
            with self.subTest(sql=sql), self.assertRaises(ToolError) as error:
                execute(self.s, "query", dict(sql=sql))
            self.assertEqual(error.exception.detail["code"], "invalid_query")
            self.assertEqual(self.s.state(), before)

    def test_summary_reports_an_orphan_instead_of_loading_its_broken_parent(self):
        db = self.s.db
        db.database.execute_sql("PRAGMA foreign_keys=OFF")
        db.ScheduleTable.update(parent=99999).where(db.ScheduleTable.code == "A").execute()
        result = execute(self.s, "get_summary", {})["data"]
        self.assertEqual(result["checks"]["orphan_children"]["items"], ["A"])
        self.assertEqual(result["grand_total"], "6.00")

    def test_limits_stop_runaway_query_large_result_and_excess_rows(self):
        for sql in ("WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM n) SELECT sum(x) FROM n", "SELECT printf('%300000s','x')", "WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM n WHERE x<501) SELECT x FROM n"):
            started = time.monotonic()
            with self.subTest(sql=sql), self.assertRaises(ToolError) as error:
                execute(self.s, "query", dict(sql=sql))
            self.assertEqual(error.exception.detail["code"], "too_large")
            self.assertLess(time.monotonic() - started, 3)
        self.assertEqual(execute(self.s, "query", dict(sql="SELECT code FROM v_schedule LIMIT 1", limit=1))["data"]["rows"], [["A"]])


if __name__ == "__main__":
    unittest.main()
