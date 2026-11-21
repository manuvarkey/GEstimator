"""File operations for isolated projects and explicit in-place saves."""

import errno
import hashlib
import os
from pathlib import Path
import shutil
from tempfile import NamedTemporaryFile
from contextlib import contextmanager


def fingerprint(path):
    """Capture the main database and journal identity without changing either."""
    parts = []
    for candidate in (path, Path(str(path) + "-wal"), Path(str(path) + "-journal")):
        try:
            with candidate.open("rb") as stream:
                before = os.fstat(stream.fileno())
                digest = hashlib.file_digest(stream, "sha256").digest()
                after = candidate.stat()
            identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            if identity != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
                raise ValueError("Project changed on disk. Reopen it or save a copy.")
            parts.append((identity, digest))
        except FileNotFoundError:
            if candidate == path:
                raise
            parts.append(None)
    return tuple(parts)


def verify_source(path, expected):
    if not path.is_file() or fingerprint(path) != expected:
        raise ValueError("Project changed on disk. Reopen it or save a copy.")
    if any(expected[1:]):
        raise ValueError("Project has an active SQLite journal. Close other editors or save a copy.")


def temporary_sibling(path):
    with NamedTemporaryFile(prefix=".gestimator-", suffix=".tmp", dir=path.parent,
                            delete=False) as stream:
        return Path(stream.name)


def write_recovery(path, write):
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = temporary_sibling(path)
    try:
        write(staged)
        with staged.open("rb+") as stream:
            os.fsync(stream.fileno())
        staged.replace(path)
    finally:
        staged.unlink(missing_ok=True)


def preserve_backup(staged, destination):
    try:
        os.link(staged, destination)
    except OSError as exc:
        if exc.errno not in (errno.ENOSYS, errno.ENOTSUP, errno.EPERM, errno.EACCES):
            raise
        with destination.open("xb") as output:
            try:
                with staged.open("rb") as source:
                    shutil.copyfileobj(source, output)
                output.flush()
                os.fsync(output.fileno())
            except Exception:
                output.close()
                destination.unlink(missing_ok=True)
                raise


def lock_exclusive(stream):
    """Take a non-blocking exclusive lock on an open file; OSError when held elsewhere."""
    stream.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)


@contextmanager
def save_lock(source):
    lock_path = source.with_name(f".{source.name}.gestimator-lock")
    with lock_path.open("a+b") as lock:
        try:
            lock_exclusive(lock)
        except OSError as exc:
            raise ValueError("Another GEstimator window is saving this project") from exc
        yield


class RecoveryClaim:
    """Lock on <id>.lock beside a recovery copy, held while a window uses that copy.

    Windows in other processes (each snap launch is its own process) skip
    claimed copies, so they never offer or delete another window's live copy.
    The OS drops the lock when the process ends, so copies left by a crash
    become available again.
    """

    def __init__(self, directory, identity):
        self.path = Path(directory) / (identity + ".lock")
        self.stream = None

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        stream = self.path.open("a+b")
        try:
            lock_exclusive(stream)
        except OSError:
            stream.close()
            return False
        self.stream = stream
        return True

    def release(self):
        if self.stream is None:
            return
        self.stream.close()
        self.stream = None
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass

    @staticmethod
    def held(directory, identity):
        """True when another open file holds the claim on this copy."""
        path = Path(directory) / (identity + ".lock")
        if not path.exists():
            return False
        try:
            with path.open("a+b") as stream:
                lock_exclusive(stream)
        except OSError:
            return True
        return False


def save_existing(source, expected, write):
    with save_lock(source):
        return replace_project(source, expected, write)


def replace_project(source, expected, write):
    """Publish a complete SQLite snapshot after preserving the previous file."""
    verify_source(source, expected)
    staged = temporary_sibling(source)
    backup_staged = None
    try:
        write(staged)
        with staged.open("rb+") as stream:
            os.fsync(stream.fileno())
        backup_staged = temporary_sibling(source)
        shutil.copyfile(source, backup_staged)
        with backup_staged.open("rb+") as stream:
            os.fsync(stream.fileno())
        verify_source(source, expected)
        backup = source.with_name(source.name + ".bak")
        os.chmod(staged, source.stat().st_mode)
        suffix = 1
        while True:
            try:
                preserve_backup(backup_staged, backup)
                break
            except FileExistsError:
                suffix += 1
                backup = source.with_name(f"{source.name}.{suffix}.bak")
        verify_source(source, expected)
        staged.replace(source)
        return backup
    finally:
        staged.unlink(missing_ok=True)
        if backup_staged:
            backup_staged.unlink(missing_ok=True)
