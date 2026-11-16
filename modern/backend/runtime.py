"""One owner thread for desktop and MCP requests, including every SQLite call."""

from concurrent.futures import Future
from queue import Queue, Full
from threading import Thread
from .service import Service
import logging
import time

log = logging.getLogger("gestimator.actions")


class Runtime:
    def __init__(self, recovery_dir=None):
        self.queue = Queue(maxsize=128)
        self.closed = False
        self.thread = Thread(target=self.run, args=(recovery_dir,), name="project-service")
        self.thread.start()

    def run(self, recovery_dir):
        from .mcp_operations import OPERATIONS
        def dispatch(method, params):
            name = params.get("name")
            write = isinstance(name, str) and OPERATIONS.get(name, {}).get("write", False)
            return self.call(method, params, timeout=110 if write else 30)
        service = Service(recovery_dir, dispatch=dispatch)
        try:
            while True:
                job = self.queue.get()
                if job is None:
                    break
                future, method, params, progress = job
                if not future.set_running_or_notify_cancel():
                    continue
                started, revision = time.monotonic(), service.revision
                tool = params.get("name", "") if method == "mcp.read" else ""
                if not isinstance(tool, str):
                    tool = "<invalid>"
                log.debug("action.start method=%s tool=%s write=%s access=%s revision=%s", method, tool, OPERATIONS.get(tool, {}).get("write", False) if tool else "desktop", service.mcp.access, revision)
                try:
                    future.set_result(service.checkpoint_recovery() if method == "_checkpoint" else service.call(method, params, progress))
                    log.debug("action.done method=%s tool=%s revision=%s changed=%s ms=%.1f", method, tool, service.revision, service.revision != revision, (time.monotonic() - started) * 1000)
                except Exception as exc:
                    log.debug("action.failed method=%s tool=%s error=%s ms=%.1f", method, tool, type(exc).__name__, (time.monotonic() - started) * 1000)
                    future.set_exception(exc)
        finally:
            service.close()

    def call(self, method, params=None, progress=lambda value: None, timeout=None):
        if self.closed:
            raise ValueError("Application is closing")
        future = Future()
        try:
            self.queue.put_nowait((future, method, params or {}, progress))
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

    def checkpoint_recovery(self):
        return self.call("_checkpoint")
