import concurrent.futures
import http.client
import json
import socket
import unittest
from modern.backend.runtime import Runtime


class MCPFixture(unittest.TestCase):
    def setUp(self):
        self.runtime = Runtime()
        self.addCleanup(self.runtime.close)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            self.port = listener.getsockname()[1]
        self.status = self.runtime.call("mcp.configure", dict(port=self.port))
        self.token = self.status["token"]

    def start(self):
        self.status = self.runtime.call("mcp.start")
        return self.status

    def http(self, method="POST", message=None, headers=None, raw=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        self.addCleanup(connection.close)
        defaults = {"Authorization": "Bearer " + self.token, "Content-Type": "application/json", "Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-11-25"}
        defaults.update(headers or {})
        body = raw if raw is not None else json.dumps(message or dict(jsonrpc="2.0", id=1, method="ping"))
        connection.request(method, "/mcp", body=body if method == "POST" else None, headers=defaults)
        response = connection.getresponse()
        data = response.read()
        return response.status, json.loads(data) if data else None

    def tool(self, name, arguments=None):
        status, response = self.http(message=dict(jsonrpc="2.0", id=2, method="tools/call", params=dict(name=name, arguments=arguments or {})))
        self.assertEqual(status, 200)
        return response["result"]



class MCPServerTests(MCPFixture):
    def test_protocol_discovery_notifications_and_invalid_transport(self):
        self.assertFalse(self.status["running"])
        self.assertTrue(self.start()["running"])
        status, message = self.http(message=dict(jsonrpc="2.0", id=1, method="initialize", params=dict(protocolVersion="2025-11-25", capabilities={}, clientInfo=dict(name="test", version="1"))))
        self.assertEqual(status, 200)
        self.assertEqual(message["result"]["protocolVersion"], "2025-11-25")
        self.assertEqual(message["result"]["capabilities"], dict(tools=dict(listChanged=False)))
        self.assertEqual(self.http(message=dict(jsonrpc="2.0", method="notifications/initialized")), (202, None))
        tools = self.http(message=dict(jsonrpc="2.0", id=2, method="tools/list"))[1]["result"]["tools"]
        self.assertGreater(len(tools), 7)
        self.assertEqual(len(tools), 8)
        self.assertIn("query", {tool["name"] for tool in tools})
        self.assertTrue(all("outputSchema" in tool for tool in tools))
        self.assertTrue(all(tool["annotations"]["readOnlyHint"] for tool in tools))
        self.assertEqual(self.http(method="GET")[0], 405)
        self.assertEqual(self.http(raw="{")[1]["error"]["code"], -32700)
        self.assertEqual(self.http(message=[{}])[1]["error"]["code"], -32600)
        self.assertEqual(self.http(message=dict(jsonrpc="2.0", id=3, method="arbitrary"))[1]["error"]["code"], -32601)
        self.assertEqual(self.http(headers={"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.http(headers={"Accept": "text/plain"})[0], 406)
        self.assertEqual(self.http(headers={"MCP-Protocol-Version": "invalid"})[0], 400)

    def test_bearer_host_and_origin_guards(self):
        self.start()
        self.assertEqual(self.http(headers={"Authorization": ""})[0], 401)
        self.assertEqual(self.http(headers={"Authorization": "Bearer wrong"})[0], 401)
        self.assertEqual(self.http(headers={"Origin": "https://example.com"})[0], 403)
        self.assertEqual(self.http(headers={"Host": "example.com"})[0], 403)
        self.assertEqual(self.http(headers={"Origin": "http://127.0.0.1:" + str(self.port)})[0], 200)

    def test_live_project_and_measurements_are_read_only(self):
        self.start()
        self.assertFalse(self.tool("get_state")["structuredContent"]["data"]["project_open"])
        self.assertTrue(self.tool("browse", dict(kind="schedule"))["isError"])
        state = self.runtime.call("project.new")
        self.runtime.call("schedule.editor.add", dict(revision=state["revision"], data=dict(code="A", description="Live item", rate="17", category="Work")))
        state = self.runtime.call("state")
        before = self.runtime.call("schedule.editor.state")
        result = self.tool("search_items", dict(kind="schedule", query="Live"))
        self.assertFalse(result["isError"])
        self.assertIn("Live item", result["structuredContent"]["data"]["items"][0]["short"])
        self.assertLess(len(result["content"][0]["text"]), 100)
        self.assertEqual(self.runtime.call("state"), state)
        self.assertEqual(self.runtime.call("schedule.editor.state"), before)
        self.assertTrue(self.tool("project", dict(action="save"))["isError"])
        self.assertTrue(self.tool("browse", dict(kind="schedule", source="arbitrary"))["isError"])
        self.assertTrue(self.tool("browse", dict(kind="schedule", offset=True))["isError"])
        self.assertTrue(self.tool("search_items", dict(kind="schedule", query="x" * 501))["isError"])
        identity = self.runtime.call("measurement.add", dict(revision=state["revision"], template="_1_NLBH"))["selected"][0]
        state = self.runtime.call("state")
        self.runtime.call("measurement.record_add", dict(revision=state["revision"], id=identity))
        state = self.runtime.call("state")
        row = self.runtime.call("measurement.state", dict(id=identity))["detail"]["rows"][0]
        self.runtime.call("measurement.record_edit", dict(revision=state["revision"], id=identity, record_id=row["id"], field="c2", value="2*3"))
        state = self.runtime.call("state")
        detail = self.tool("get_measurements", dict(id=identity))["structuredContent"]["data"]
        self.assertEqual(detail["rows"][0]["c2"], "2*3")
        self.assertEqual(detail["rows"][0]["_display"]["c1"], "[2*3,,,]")
        self.assertEqual(detail["rows"][0]["_display"]["c2"], "6")
        self.assertEqual(self.tool("get_measurements")["structuredContent"]["data"]["total"], 1)
        self.assertTrue(self.tool("get_measurements", dict(id="missing"))["isError"])
        self.assertEqual(self.runtime.call("state"), state)

    def test_parallel_http_and_desktop_reads_share_owner_thread(self):
        self.runtime.call("project.new")
        self.start()
        def read(index):
            if index % 2:
                return self.runtime.call("schedule.editor.state")["total"]
            result = self.tool("browse", dict(kind="schedule"))
            self.assertFalse(result["isError"])
            return result["structuredContent"]["data"]["total"]
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            self.assertEqual(list(pool.map(read, range(24))), [0] * 24)

    def test_configuration_conflict_rotation_and_shutdown_release_socket(self):
        for port in (0, True, 1023, 65536, "8765"):
            with self.assertRaises(ValueError):
                self.runtime.call("mcp.configure", dict(port=port))
        with self.assertRaises(ValueError):
            self.runtime.call("mcp.configure", dict(token="short"))
        with socket.socket() as blocker:
            blocker.bind(("127.0.0.1", self.port))
            blocker.listen()
            with self.assertRaises(OSError):
                self.start()
            self.assertFalse(self.runtime.call("mcp.status")["running"])
        self.start()
        with self.assertRaises(ValueError):
            self.runtime.call("mcp.rotate_token")
        self.assertFalse(self.runtime.call("mcp.stop")["running"])
        new = self.runtime.call("mcp.rotate_token")
        self.assertNotEqual(new["token"], self.token)
        self.start()
        self.assertEqual(self.http()[0], 401)
        self.token = new["token"]
        self.assertEqual(self.http()[0], 200)
        self.runtime.close()
        with self.assertRaises(OSError):
            socket.create_connection(("127.0.0.1", self.port), timeout=1)


if __name__ == "__main__":
    unittest.main()
