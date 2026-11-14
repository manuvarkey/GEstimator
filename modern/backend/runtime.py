"""One owner thread for desktop and MCP requests, including every SQLite call."""

from concurrent.futures import Future
from queue import Queue, Full
from threading import Thread
from .service import Service


class Runtime:
    def __init__(self, recovery_dir=None):
        self.queue = Queue(maxsize=128)
        self.closed = False
        self.thread = Thread(target=self.run, args=(recovery_dir,), name="project-service")
        self.thread.start()

    def run(self, recovery_dir):
        service = Service(recovery_dir, dispatch=lambda method, params: self.call(method, params, timeout=30))
        try:
            while True:
                job = self.queue.get()
                if job is None:
                    break
                future, method, params, progress = job
                if not future.set_running_or_notify_cancel():
                    continue
                try:
                    future.set_result(service.checkpoint_recovery() if method == "_checkpoint" else service.call(method, params, progress))
                except Exception as exc:
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
