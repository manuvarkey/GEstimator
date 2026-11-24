"""File operations for isolated projects and explicit in-place saves."""

import errno
import hashlib
import os
import shutil
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile

PORTAL_HOST_PATH = "user.document-portal.host-path"


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


def portal_parts(path):
    """Return the path within the app's filtered Documents mount."""
    if not os.environ.get("FLATPAK_ID"):
        return ()
    roots = [Path("/run/flatpak/doc")]
    if runtime := os.environ.get("XDG_RUNTIME_DIR"):
        roots.append(Path(runtime) / "doc")
    for root in roots:
        try:
            return Path(path).relative_to(root).parts
        except ValueError:
            continue
    return ()


def flatpak_document(path):
    """Identify a document root by its document ID and filename."""
    return len(portal_parts(path)) == 2


def portal_needs_folder(path):
    """Only a read-only file grant needs an additional folder selection."""
    return flatpak_document(path) and not os.access(path, os.W_OK)


def resolve_input(path):
    """Explain how to grant access when an incoming host path is unavailable."""
    try:
        return Path(path).resolve(strict=True)
    except FileNotFoundError as error:
        if os.environ.get("FLATPAK_ID"):
            raise ValueError("File unavailable. Use Browse to select it again.") from error
        raise


def check_database_access(path):
    """A single-file export can hide SQLite's committed WAL transactions."""
    if flatpak_document(path):
        with path.open("rb") as source:
            header = source.read(20)
        if header.startswith(b"SQLite format 3\x00") and 2 in header[18:20]:
            raise ValueError("This SQLite database uses a write-ahead log. Select a standalone SQLite backup instead.")


def save_target(source, expected, directory):
    """Confirm that a folder grant exposes the same unchanged project."""
    if not directory:
        raise ValueError("Choose the project folder in GEstimator to save in place, or use Save Copy.")
    directory = Path(directory).resolve(strict=True)
    destination = directory / source.name
    if len(portal_parts(directory)) < 2 or not directory.is_dir() or destination.is_symlink():
        raise ValueError("Choose the folder containing the open project.")
    if not same_project_path(source, destination):
        raise ValueError("Choose the folder containing the open project.")
    return destination, verified_alias(source, expected, destination)


def same_project_path(source, destination):
    """Compare portal grant identities without accessing the underlying host paths."""
    if source == destination:
        return True
    if not (portal_parts(source) and portal_parts(destination)):
        return False
    try:
        return os.getxattr(source, PORTAL_HOST_PATH) == os.getxattr(destination, PORTAL_HOST_PATH)
    except FileNotFoundError:
        return False
    except OSError as error:
        raise ValueError("Could not identify the original project through the Documents portal.") from error


def verified_alias(source, expected, destination):
    """Verify both grants still expose the unchanged project opened by the editor."""
    verify_source(source, expected)
    actual = fingerprint(destination)
    # The file and folder grants have different virtual inode identities.
    if any(actual[1:]) or (actual[0][0][2:], actual[0][1]) != (expected[0][0][2:], expected[0][1]):
        raise ValueError("Project changed on disk. Reopen it or save a copy.")
    return actual


def temporary_sibling(path):
    with NamedTemporaryFile(prefix=".gestimator-", suffix=".tmp", dir=path.parent, delete=False) as stream:
        return Path(stream.name)


@contextmanager
def export_output(destination, replace_selected=False):
    """Publish a chooser-confirmed replacement only after a complete export."""
    if replace_selected and flatpak_document(destination):
        staged = temporary_sibling(destination)
        try:
            yield staged
            with staged.open("rb+") as stream:
                os.fsync(stream.fileno())
            staged.replace(destination)
        finally:
            staged.unlink(missing_ok=True)
        return

    with destination.open("xb"):
        pass
    try:
        yield destination
    except Exception:
        destination.unlink()
        raise


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
    """Serialize saves for the same project, including through different folder grants."""
    if portal_parts(source):
        # The Documents mount does not implement flock. Use the shared per-app
        # runtime directory and hash the host path so grant IDs share one lock.
        try:
            directory = Path(os.environ["XDG_RUNTIME_DIR"]) / "app" / os.environ["FLATPAK_ID"] / "project-locks"
            directory.mkdir(mode=0o700, exist_ok=True)
            lock_path = directory / portal_key(source)
        except (KeyError, OSError) as exc:
            raise ValueError("Could not lock this project through the Documents portal. Try Save Copy.") from exc
    else:
        lock_path = source.with_name(f".{source.name}.gestimator-lock")
    with lock_path.open("a+b") as lock:
        try:
            lock_exclusive(lock)
        except OSError as exc:
            if exc.errno in (errno.EACCES, errno.EAGAIN):
                raise ValueError("Another GEstimator window is saving this project") from exc
            raise
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
    """Publish and capture the new fingerprint while the save lock is held."""
    with save_lock(source):
        backup = replace_project(source, expected, write)
        return backup, fingerprint(source)


def portal_key(source):
    """A stable key for the same host path exposed by different document grants."""
    return hashlib.sha256(os.getxattr(source, PORTAL_HOST_PATH)).hexdigest()


def backup_directory(source):
    """Keep persistent backups in app data when the grant covers only one file."""
    if not flatpak_document(source):
        return source.parent
    data = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    folder = data / "project-backups" / portal_key(source)
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    return folder


def replace_project(source, expected, write):
    """Publish a complete SQLite snapshot after preserving the previous file."""
    verify_source(source, expected)
    staged = temporary_sibling(source)
    backup_staged = None
    try:
        write(staged)
        with staged.open("rb+") as stream:
            os.fsync(stream.fileno())
        backup_base = backup_directory(source) / source.name
        backup_staged = temporary_sibling(backup_base)
        shutil.copyfile(source, backup_staged)
        with backup_staged.open("rb+") as stream:
            os.fsync(stream.fileno())
        verify_source(source, expected)
        backup = backup_base.with_suffix(backup_base.suffix + ".bak")
        os.chmod(staged, source.stat().st_mode)
        suffix = 1
        while True:
            try:
                preserve_backup(backup_staged, backup)
                break
            except FileExistsError:
                suffix += 1
                backup = backup_base.with_name(f"{source.name}.{suffix}.bak")
        verify_source(source, expected)
        staged.replace(source)
        return backup
    finally:
        staged.unlink(missing_ok=True)
        if backup_staged:
            backup_staged.unlink(missing_ok=True)
