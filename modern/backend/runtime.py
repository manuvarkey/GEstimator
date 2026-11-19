"""One owner thread for desktop and MCP requests, including every SQLite call.

Each open document is a separate Service ("session"). Desktop requests name
their session; MCP requests act on the session the desktop marked active.
"""

from concurrent.futures import Future
from queue import Queue, Full
import re
from threading import Thread
from .service import Service
import logging
import time

log = logging.getLogger("gestimator.actions")
MAIN = "main"


def session_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
        raise ValueError("Invalid document session")
    return value


class Runtime:
    def __init__(self, recovery_dir=None):
        self.queue = Queue(maxsize=128)
        self.closed = False
        self.active = MAIN
        self.thread = Thread(target=self.run, args=(recovery_dir,), name="project-service")
        self.thread.start()

    def run(self, recovery_dir):
        from .mcp_operations import OPERATIONS
        from .mcp_server import MCPServer
        def dispatch(method, params):
            name = params.get("name")
            write = isinstance(name, str) and OPERATIONS.get(name, {}).get("write", False)
            return self.call(method, params, timeout=110 if write else 30)
        mcp = MCPServer(dispatch)
        services = {}
        def open_session(identity):
            service = Service(recovery_dir, dispatch=dispatch, mcp=mcp)
            service.peers = lambda: [peer for peer in services.values() if peer is not service]
            services[identity] = service
            return service
        open_session(MAIN)
        try:
            while True:
                job = self.queue.get()
                if job is None:
                    break
                future, method, params, progress, session = job
                if not future.set_running_or_notify_cancel():
                    continue
                try:
                    if method.startswith("session."):
                        future.set_result(self.session_call(method, params, services, open_session, session))
                        continue
                    identity = self.active if session is None else session_id(session)
                    service = services.get(identity)
                    if service is None:
                        raise ValueError("This document is closed; reopen the project")
                except Exception as exc:
                    future.set_exception(exc)
                    continue
                started, revision = time.monotonic(), service.revision
                tool = params.get("name", "") if method == "mcp.read" else ""
                if not isinstance(tool, str):
                    tool = "<invalid>"
                log.debug("action.start session=%s method=%s tool=%s write=%s access=%s revision=%s", identity, method, tool, OPERATIONS.get(tool, {}).get("write", False) if tool else "desktop", service.mcp.access, revision)
                try:
                    future.set_result(service.checkpoint_recovery() if method == "_checkpoint" else service.call(method, params, progress))
                    log.debug("action.done method=%s tool=%s revision=%s changed=%s ms=%.1f", method, tool, service.revision, service.revision != revision, (time.monotonic() - started) * 1000)
                except Exception as exc:
                    log.debug("action.failed method=%s tool=%s error=%s ms=%.1f", method, tool, type(exc).__name__, (time.monotonic() - started) * 1000)
                    future.set_exception(exc)
        finally:
            for service in services.values():
                try:
                    service.close()
                except Exception:
                    log.exception("Could not close document session")
            mcp.stop()

    def session_call(self, method, params, services, open_session, session=None):
        if method == "session.list":
            return dict(sessions=list(services), active=self.active)
        identity = session_id(params.get("session", session))
        if method == "session.open":
            if identity in services:
                raise ValueError("Document session already exists")
            if len(services) >= 32:
                raise ValueError("Close a document before opening more than 32")
            open_session(identity)
            return dict(session=identity)
        if identity not in services:
            raise ValueError("This document is closed; reopen the project")
        if method == "session.activate":
            # MCP clients act on the document the desktop shows.
            if self.active != identity and self.active in services:
                services[identity].mcp.project_epoch += 1
            self.active = identity
            return dict(active=identity)
        if method == "session.close":
            if len(services) == 1:
                raise ValueError("At least one document stays open")
            services.pop(identity).close()
            if self.active == identity:
                self.active = next(iter(services))
            return dict(active=self.active)
        raise ValueError("Unknown session operation")

    def call(self, method, params=None, progress=lambda value: None, timeout=None, session=None):
        if self.closed:
            raise ValueError("Application is closing")
        future = Future()
        try:
            self.queue.put_nowait((future, method, params or {}, progress, session))
        except Full:
            raise ValueError("Project service is busy; retry shortly") from None
        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            future.cancel()
            raise ValueError("Project service timed out") from None

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.queue.put(None)
        self.thread.join()

    def checkpoint_recovery(self, session=None):
        return self.call("_checkpoint", session=session)
