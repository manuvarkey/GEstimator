"""Local, authenticated MCP 2025-11-25 Streamable HTTP (JSON responses).

HTTP threads only parse transport messages. Tool reads are queued onto the same
owner thread as desktop requests; they never access ORM connections directly.
"""

import hmac
import json
import logging
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock, Thread

from .mcp_operations import OPERATIONS, ToolError, execute
from .mcp_skills import ResourceNotFound, SkillLibraries

VERSION = "2025-11-25"
log = logging.getLogger("gestimator.actions")
VERSIONS = (VERSION, "2025-06-18", "2025-03-26")
INSTRUCTIONS = """GEstimator estimate workspace.
1. Start with get_state for available_sources and skills. Read the relevant skill via describe_source
section=skill:<library>/<skill> or its gestimator://skills/ URI. Read database overview and category notes before selecting items.
2. Search the project and relevant libraries for compatible schedule items and resources. Inspect full definitions
with get_items. Reuse a suitable definition or analysis via import_items or duplicate_from before pricing custom work.
3. For takeoff, create measurement headings by work package, phase or location. Use category=<heading ID or $ref>
when creating sheets. Record quantities by storey, room, grid, element or run as supported by the source.
4. get_measurements section=templates shows editable columns and outputs. Link sheets to schedule items and
recalculate what=quantities. Verify category placement and totals with get_measurements and get_summary.
5. Use one edit_analysis per item with r0/r0:0 IDs or refs. batch groups writes into one undo step.
Supply if_revision for stale-write protection. Save explicitly. Use query only when typed reads are insufficient.
"""


def read_tool(service, name, arguments):
    return execute(service, name, arguments)


def error_result(error):
    if isinstance(error, ToolError):
        detail = error.detail
    elif isinstance(error, KeyError):
        detail = dict(code="invalid_arguments", message="Missing required field", field=str(error.args[0]))
    else:
        message = str(error)
        code = (
            "draft_conflict"
            if "Unsaved analysis" in message or "unsaved measurement records" in message.lower()
            else "not_found"
            if isinstance(error, FileNotFoundError)
            else "invalid_arguments"
            if isinstance(error, (ValueError, TypeError))
            else "operation_failed"
        )
        detail = dict(code=code, message=message)
    return dict(
        content=[dict(type="text", text=error_text(detail))], structuredContent=dict(error=detail), isError=True
    )


def error_text(detail):
    """One line with the field, allowed values and hint: many clients show
    only the text content, not structuredContent."""
    parts = [detail["message"].replace("\n", " ")[:300].rstrip(".") + "."]
    if detail.get("field"):
        parts.append(f"Field: {detail['field']}.")
    allowed = detail.get("allowed")
    if allowed:
        values = [str(value) for value in allowed] if isinstance(allowed, (list, tuple)) else [str(allowed)]
        parts.append("Allowed: " + ", ".join(values[:12]) + (", …" if len(values) > 12 else "") + ".")
    if detail.get("hint"):
        parts.append("Hint: " + str(detail["hint"]).replace("\n", " ")[:200])
    return " ".join(parts)[:700]


def success_result(value):
    """Provide the same result to structured and text-only clients."""
    # Some clients surface the text blocks but discard structuredContent.
    content = [dict(type="text", text=json.dumps(value, ensure_ascii=False, separators=(",", ":")))]
    return dict(content=content, structuredContent=value, isError=False)


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
        self.access = "read"
        # Off until the user enables the MCP server in Program Settings.
        self.enabled = False
        self.skill_libraries = SkillLibraries()
        self.change_seq = 0
        self.project_epoch = 0
        self.generation = 0

    def tools(self):
        return [
            operation["definition"]
            for operation in OPERATIONS.values()
            if self.access == "read-write" or not operation["write"]
        ]

    def status(self, include_tools=True):
        with self.lock:
            result = dict(
                running=self.server is not None,
                enabled=self.enabled,
                port=self.port,
                token=self.token,
                url=f"http://127.0.0.1:{self.port}/mcp",
                requests=self.requests,
                last_activity=self.last_activity,
                protocol=VERSION,
                access=self.access,
                change_seq=self.change_seq,
                project_epoch=self.project_epoch,
            )
            if include_tools:
                result["tools"] = self.tools()
            return result

    def configure(self, params):
        if self.server:
            raise ValueError("Stop the MCP server before changing its configuration")
        port = params.get("port", self.port)
        token = params.get("token", self.token)
        access = params.get("access", self.access)
        if access not in ("read", "read-write"):
            raise ValueError("Choose read or read-write access")
        if type(port) is not int or not 1024 <= port <= 65535:
            raise ValueError("Port must be an integer from 1024 to 65535")
        if (
            not isinstance(token, str)
            or not 32 <= len(token) <= 128
            or not all(char.isascii() and (char.isalnum() or char in "-_") for char in token)
        ):
            raise ValueError("Use a connection token of 32–128 letters, digits, hyphens or underscores")
        self.port, self.token, self.access = port, token, access
        return self.status()

    def enable(self, enabled, skill_library=None):
        """Apply MCP program preferences, stopping the listener if disabled."""
        if type(enabled) is not bool:
            raise ValueError("Choose whether the MCP server is enabled")
        if skill_library is not None:
            self.skill_libraries.select(skill_library)
        self.enabled = enabled
        if not enabled and self.server:
            return self.stop()
        return self.status()

    def start(self):
        if self.server:
            return self.status()
        if not self.enabled:
            raise ValueError("The MCP server is turned off. Enable it in Program Settings (AI assistants) to start it.")
        if not self.dispatch:
            raise ValueError("MCP requires the application's serialized service runtime")
        owner = self
        generation = self.generation + 1

        class Handler(BaseHTTPRequestHandler):
            server_version = "GEstimator-MCP"

            def setup(self):
                super().setup()
                self.connection.settimeout(5)

            def log_message(self, *args):
                pass  # Never log headers, connection tokens or project contents.

            def reply(self, status, body=None):
                data = (
                    json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                    if body is not None
                    else b""
                )
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
                    self.reply(404)
                    return False
                hosts = {f"127.0.0.1:{owner.port}", f"localhost:{owner.port}"}
                if self.headers.get("Host") not in hosts:
                    log.debug("mcp.access.denied reason=host_or_origin")
                    self.reply(403)
                    return False
                origin = self.headers.get("Origin")
                if origin and origin not in {"http://" + host for host in hosts}:
                    log.debug("mcp.access.denied reason=host_or_origin")
                    self.reply(403)
                    return False
                if not hmac.compare_digest(
                    self.headers.get("Authorization", "").encode("utf-8"), ("Bearer " + owner.token).encode("utf-8")
                ):
                    log.debug("mcp.access.denied reason=bearer_token")
                    self.reply(401)
                    return False
                return True

            def do_GET(self):
                if self.authorized():
                    self.reply(405)  # No unsolicited SSE stream or session state.

            do_DELETE = do_GET

            def do_POST(self):
                if not self.authorized():
                    return
                if self.headers.get_content_type() != "application/json":
                    self.reply(415)
                    return
                if not all(
                    value in self.headers.get("Accept", "") for value in ("application/json", "text/event-stream")
                ):
                    self.reply(406)
                    return
                version = self.headers.get("MCP-Protocol-Version")
                if version and version not in VERSIONS:
                    self.reply(400)
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 1_000_000 or self.headers.get("Transfer-Encoding"):
                        self.reply(413)
                        return
                    message = json.loads(self.rfile.read(length))
                except (ValueError, UnicodeError):
                    self.reply(400, dict(jsonrpc="2.0", id=None, error=dict(code=-32700, message="Invalid JSON")))
                    return
                if (
                    not isinstance(message, dict)
                    or message.get("jsonrpc") != "2.0"
                    or not isinstance(message.get("method"), str)
                    or ("id" in message and type(message["id"]) not in (str, int))
                ):
                    self.reply(400, dict(jsonrpc="2.0", id=None, error=dict(code=-32600, message="Invalid request")))
                    return
                if "id" not in message:
                    self.reply(202)
                    return
                identity, method, params = message["id"], message["method"], message.get("params", {})
                if not isinstance(params, dict):
                    self.reply(200, dict(jsonrpc="2.0", id=identity, error=dict(code=-32602, message="Invalid params")))
                    return
                with owner.lock:
                    owner.requests += 1
                    owner.last_activity = (
                        "Tool: " + str(params.get("name", ""))[:100]
                        if method == "tools/call"
                        else "Resource: " + str(params.get("uri", ""))[:100]
                        if method == "resources/read"
                        else method
                    )
                log.debug(
                    "mcp.request method=%s tool=%s access=%s", method, str(params.get("name", ""))[:64], owner.access
                )
                if method == "initialize":
                    result = dict(
                        protocolVersion=params.get("protocolVersion")
                        if params.get("protocolVersion") in VERSIONS
                        else VERSION,
                        capabilities=dict(tools=dict(listChanged=False), resources=dict(listChanged=False)),
                        serverInfo=dict(name="GEstimator", version="0.1.0"),
                        instructions=INSTRUCTIONS + "Access mode: " + owner.access,
                    )
                elif method == "ping":
                    result = {}
                elif method == "tools/list":
                    result = dict(tools=owner.tools())
                elif method == "resources/list":
                    # Resource requests read the published snapshot without project IO.
                    result = dict(resources=owner.skill_libraries.active.list_resources())
                elif method == "resources/templates/list":
                    result = dict(resourceTemplates=[])
                elif method == "resources/read":
                    if not isinstance(params.get("uri"), str):
                        self.reply(
                            200,
                            dict(
                                jsonrpc="2.0",
                                id=identity,
                                error=dict(code=-32602, message="Invalid params: uri must be a string"),
                            ),
                        )
                        return
                    try:
                        result = owner.skill_libraries.active.read_resource(params["uri"])
                    except ResourceNotFound as exc:
                        self.reply(
                            200,
                            dict(
                                jsonrpc="2.0",
                                id=identity,
                                error=dict(code=-32002, message=str(exc)[:300], data=dict(uri=params["uri"][:300])),
                            ),
                        )
                        return
                elif method == "tools/call":
                    try:
                        # Stamp the accepted listener, never a client-supplied
                        # value. The owner thread rechecks it at execution time.
                        value = owner.dispatch(
                            "mcp.read",
                            dict(name=params.get("name"), arguments=params.get("arguments", {}), _listener=generation),
                        )
                        result = success_result(value)
                    except Exception as exc:
                        result = error_result(exc)
                else:
                    self.reply(
                        200, dict(jsonrpc="2.0", id=identity, error=dict(code=-32601, message="Method not found"))
                    )
                    return
                self.reply(200, dict(jsonrpc="2.0", id=identity, result=result))

        class Server(ThreadingHTTPServer):
            daemon_threads = True
            block_on_close = False

        server = Server(("127.0.0.1", self.port), Handler)
        self.generation = generation
        self.server = server
        self.thread = Thread(target=server.serve_forever, kwargs=dict(poll_interval=0.1), daemon=True, name="mcp-http")
        self.thread.start()
        return self.status()

    def stop(self):
        if self.server:
            self.generation += 1
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=2)
            self.server = self.thread = None
        return self.status()
