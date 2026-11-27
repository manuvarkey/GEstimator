"""Background rendering for captured reports, independent of the project owner thread."""

from concurrent.futures import Future
from threading import Thread
from uuid import uuid4

# Only the owner thread touches the registry. The worker completes its Future.
jobs = {}


def start(render, *args):
    """Start one desktop export after the owner thread has validated and captured it."""
    if any(not future.done() for future in jobs.values()):
        raise ValueError("A report export is already running")
    if len(jobs) >= 8:
        del jobs[next(iter(jobs))]
    token = uuid4().hex
    future = Future()
    jobs[token] = future

    def run():
        try:
            future.set_result(render(*args))
        except Exception as error:
            # Carry renderer and publication errors back to the request boundary.
            future.set_exception(error)

    Thread(target=run, daemon=True, name="report-export").start()
    return {"token": token}


def status(params):
    """Poll a detached job using its opaque ID, even after switching projects."""
    token = params.get("token")
    if not isinstance(token, str) or token not in jobs:
        raise ValueError("Report export is unavailable")
    future = jobs[token]
    if not future.done():
        return {"result": None}
    del jobs[token]
    return {"result": future.result()}
