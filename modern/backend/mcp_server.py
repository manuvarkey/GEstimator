"""Local, authenticated MCP 2025-11-25 Streamable HTTP (JSON responses).

HTTP threads only parse transport messages. Tool reads are queued onto the same
owner thread as desktop requests; they never access ORM connections directly.
"""

import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import secrets
from threading import Thread, Lock

VERSION = "2025-11-25"
VERSIONS = (VERSION, "2025-06-18", "2025-03-26")
PAGE = dict(query=dict(type="string", maxLength=500), offset=dict(type="integer", minimum=0))


def tool(name, description, properties=None, required=None):
    return dict(name=name, description=description,
                inputSchema=dict(type="object", properties=properties or {}, required=required or [], additionalProperties=False),
                annotations=dict(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False))


TOOLS = [
    tool("get_project", "Read the current project name, revision and unsaved-state flags. No files are opened or saved."),
    tool("list_schedule", "Search the open project's schedule hierarchy, 100 items per page. Includes current stored rates and quantities.", PAGE),
    tool("list_resources", "Search the open project's resource hierarchy, 100 items per page. Includes base rates, VAT and discounts.", PAGE),
    tool("get_analysis", "Read the active analysis, including its unsaved draft and original Python calculation results. Does not change the selected item."),
    tool("list_measurements", "List the open project's measurement items, links and totals. Returns at most 100 items per page.", dict(offset=dict(type="integer", minimum=0))),
    tool("get_measurement", "Read one measurement's template, raw expressions, rendered cells, Breakup and calculated totals, at most 100 records per page.", dict(id=dict(type="string", minLength=1, maxLength=100), record_offset=dict(type="integer", minimum=0)), ["id"]),
    tool("list_databases", "List attached read-only database snapshots available in the application."),
]


def read_tool(service, name, arguments):
    definition = next((item for item in TOOLS if item["name"] == name), None)
    if not definition:
        raise ValueError("Unknown read-only tool")
    schema = definition["inputSchema"]
    if not isinstance(arguments, dict) or set(arguments) - set(schema["properties"]) or any(key not in arguments for key in schema["required"]):
        raise ValueError("Invalid tool arguments")
    for key, value in arguments.items():
        rule = schema["properties"][key]
        if rule["type"] == "integer":
            if type(value) is not int or not 0 <= value <= 1_000_000:
                raise ValueError("Invalid page offset")
        elif not isinstance(value, str) or not rule.get("minLength", 0) <= len(value) <= rule["maxLength"]:
            raise ValueError("Invalid text argument")
    if name == "get_project":
        return dict(project_open=service.db is not None, name=service.db.get_project_settings().get("project_name", "") if service.db else "",
                    revision=service.revision, analysis_dirty=service.dirty, project_dirty=service.workspace_dirty)
    if name == "get_analysis":
        return service.state()
    if not service.db:
        raise ValueError("Open a project in GEstimator first")
    method = {"list_schedule": "schedule.editor.state", "list_resources": "resources.editor.state",
              "list_measurements": "measurement.state", "get_measurement": "measurement.detail", "list_databases": "library.list"}[name]
    result = service.call(method, arguments)
    if name == "list_measurements":
        offset = arguments.get("offset", 0)
        rows = result["rows"]
        result["total"] = len(rows)
        result["offset"] = offset
        result["rows"] = rows[offset:offset + 100]
    if name == "get_measurement" and not result.get("detail"):
        raise ValueError("Measurement no longer exists or is a heading")
    return result


class MCPServer:
    def __init__(self, dispatch):
        self.dispatch = dispatch
        self.port = 8765
        self.token = secrets.token_urlsafe(32)
        self.server = None
        self.thread = None
        self.lock = Lock()
        self.requests = 0
        self.last_activity = ""

    def status(self):
        with self.lock:
            return dict(running=self.server is not None, port=self.port, token=self.token,
                        url=f"http://127.0.0.1:{self.port}/mcp", requests=self.requests,
                        last_activity=self.last_activity, protocol=VERSION, tools=TOOLS)

    def configure(self, params):
        if self.server:
            raise ValueError("Stop the MCP server before changing its configuration")
        port = params.get("port", self.port)
        token = params.get("token", self.token)
        if type(port) is not int or not 1024 <= port <= 65535:
            raise ValueError("Port must be an integer from 1024 to 65535")
        if not isinstance(token, str) or not 32 <= len(token) <= 128 or not all(char.isascii() and (char.isalnum() or char in "-_") for char in token):
            raise ValueError("Use a connection token of 32–128 letters, digits, hyphens or underscores")
        self.port, self.token = port, token
        return self.status()

    def start(self):
        if self.server:
            return self.status()
        if not self.dispatch:
            raise ValueError("MCP requires the application's serialized service runtime")
        owner = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "GEstimator-MCP"

            def setup(self):
                super().setup()
                self.connection.settimeout(5)

            def log_message(self, *args):
                pass  # Never log headers, connection tokens or project contents.

            def reply(self, status, body=None):
                data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else b""
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Connection", "close")
                if status == 405:
                    self.send_header("Allow", "POST")
                if status == 401:
                    self.send_header("WWW-Authenticate", "Bearer")
                self.end_headers()
                self.wfile.write(data)

            def authorized(self):
                if self.path != "/mcp":
                    self.reply(404); return False
                hosts = {f"127.0.0.1:{owner.port}", f"localhost:{owner.port}"}
                if self.headers.get("Host") not in hosts:
                    self.reply(403); return False
                origin = self.headers.get("Origin")
                if origin and origin not in {"http://" + host for host in hosts}:
                    self.reply(403); return False
                if not hmac.compare_digest(self.headers.get("Authorization", "").encode("utf-8"), ("Bearer " + owner.token).encode("utf-8")):
                    self.reply(401); return False
                return True

            def do_GET(self):
                if self.authorized():
                    self.reply(405)  # No unsolicited SSE stream or session state.

            do_DELETE = do_GET

            def do_POST(self):
                if not self.authorized():
                    return
                if self.headers.get_content_type() != "application/json":
                    self.reply(415); return
                if not all(value in self.headers.get("Accept", "") for value in ("application/json", "text/event-stream")):
                    self.reply(406); return
                version = self.headers.get("MCP-Protocol-Version")
                if version and version not in VERSIONS:
                    self.reply(400); return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 1_000_000 or self.headers.get("Transfer-Encoding"):
                        self.reply(413); return
                    message = json.loads(self.rfile.read(length))
                except (ValueError, UnicodeError):
                    self.reply(400, dict(jsonrpc="2.0", id=None, error=dict(code=-32700, message="Invalid JSON"))); return
                if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str) or ("id" in message and type(message["id"]) not in (str, int)):
                    self.reply(400, dict(jsonrpc="2.0", id=None, error=dict(code=-32600, message="Invalid request"))); return
                if "id" not in message:
                    self.reply(202); return
                identity, method, params = message["id"], message["method"], message.get("params", {})
                if not isinstance(params, dict):
                    self.reply(200, dict(jsonrpc="2.0", id=identity, error=dict(code=-32602, message="Invalid params"))); return
                with owner.lock:
                    owner.requests += 1
                    owner.last_activity = method if method != "tools/call" else "Tool: " + str(params.get("name", ""))[:100]
                if method == "initialize":
                    result = dict(protocolVersion=params.get("protocolVersion") if params.get("protocolVersion") in VERSIONS else VERSION,
                                  capabilities=dict(tools=dict(listChanged=False)), serverInfo=dict(name="GEstimator", version="0.1.0"),
                                  instructions="Read-only access to the project currently open in GEstimator. Analysis includes the active draft; rates and totals use the existing Python engine.")
                elif method == "ping":
                    result = {}
                elif method == "tools/list":
                    result = dict(tools=TOOLS)
                elif method == "tools/call":
                    try:
                        value = owner.dispatch("mcp.read", params)
                        result = dict(content=[dict(type="text", text=json.dumps(value, ensure_ascii=False))], isError=False)
                    except Exception as exc:
                        result = dict(content=[dict(type="text", text=str(exc))], isError=True)
                else:
                    self.reply(200, dict(jsonrpc="2.0", id=identity, error=dict(code=-32601, message="Method not found"))); return
                self.reply(200, dict(jsonrpc="2.0", id=identity, result=result))

        class Server(ThreadingHTTPServer):
            daemon_threads = True
            block_on_close = False

        server = Server(("127.0.0.1", self.port), Handler)
        self.server = server
        self.thread = Thread(target=server.serve_forever, kwargs=dict(poll_interval=0.1), daemon=True, name="mcp-http")
        self.thread.start()
        return self.status()

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=2)
            self.server = self.thread = None
        return self.status()
