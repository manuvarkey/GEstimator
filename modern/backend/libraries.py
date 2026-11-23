"""Read-only library snapshots and catalog presentation.

The project editor owns snapshot handles and closes them with its document.
These helpers do not mutate source files or create transaction/history owners.
"""

import os
import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import uuid4

from estimator import misc
from estimator.data.schedule import ScheduleDatabase
from estimator.undo import Stack

from .validation import text


def attach(editor, path):
    """Open a deduplicated working snapshot while preserving the source file."""
    # Step 1: resolve the requested source and reuse an existing attachment.
    path = text(path)
    if path.startswith("bundled:"):
        name = path[len("bundled:") :]
        if not name or Path(name).name != name or "/" in name or "\\" in name or Path(name).suffix.lower() != ".eproj":
            raise ValueError("Invalid bundled database name")
        source = Path(misc.abs_path("database", name)).resolve(strict=True)
    else:
        source = Path(path).resolve(strict=True)
    if source in editor.library_paths:
        selected = editor.library_paths[source]
        return [dict(item, attached=item["id"] == selected) for item in editor.sources()]
    # Step 2: copy first, then validate/migrate only the snapshot.
    target = Path(editor.owner.temp.name) / (uuid4().hex + ".library")
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as src:
        version = src.execute("SELECT value FROM projecttable WHERE key='file_version'").fetchone()
        if version not in ((misc.PROJECT_FILE_VER,), ("GESTIMATOR_FILE_REFERENCE_VER_1",)):
            raise ValueError("Unsupported library version")
        with closing(sqlite3.connect(target)) as dst:
            src.backup(dst)
    db = ScheduleDatabase(Stack())
    if version == ("GESTIMATOR_FILE_REFERENCE_VER_1",):
        result = db.validate_database(str(target))
        if not result[0]:
            raise ValueError(result[1])
    db.open_database(str(target))
    # Step 3: register the snapshot with the document that owns its lifetime.
    name = db.get_project_settings().get("project_name") or source.stem
    identity = uuid4().hex
    editor.libraries[identity] = (name, db)
    editor.library_paths[source] = identity
    return [dict(item, attached=item["id"] == identity) for item in editor.sources()]


def attach_catalog(editor):
    """Attach the bundled databases and the database folder; one failure does not stop the rest."""
    from .program_settings import library_catalog

    if os.environ.get("GESTIMATOR_AUTO_DATABASES") == "0":  # browser tests attach only their fixtures
        return dict(sources=editor.sources(), warnings=[])
    catalog = library_catalog()
    warnings = list(catalog["warnings"])
    for row in catalog["rows"]:
        try:
            editor.attach_library(row["path"])
        except Exception as error:
            warnings.append(f"{row['name']}: {error}")
    return dict(sources=editor.sources(), warnings=warnings)


def sources(editor):
    """Present attachment names and note availability to the shared pickers."""
    return [
        dict(id=key, name=value[0], notes=bool((value[1].get_project_settings().get("project_metadata") or "").strip()))
        for key, value in editor.libraries.items()
    ]


def notes(editor, identity):
    """Database notes (Markdown) of an attached library, read-only."""
    if not isinstance(identity, str) or identity not in editor.libraries:
        raise ValueError("Choose an attached library")
    name, source = editor.libraries[identity]
    return dict(id=identity, name=name, notes=source.get_project_settings().get("project_metadata") or "")
