"""Project file and recovery commands dispatched by the authoritative service."""

import copy
import sqlite3
from contextlib import closing
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from estimator import misc
from estimator.data.schedule import ScheduleDatabase, ScheduleItemModel
from estimator.undo import Stack

from .insertion import keep_sub_analysis_last
from .persistence import (
    RecoveryClaim,
    check_database_access,
    export_output,
    fingerprint,
    flatpak_document,
    portal_needs_folder,
    portal_parts,
    resolve_input,
    same_project_path,
    save_existing,
    save_target,
    verified_alias,
)
from .project import ProjectEditor
from .validation import request_text as text


def canonical_path(p):
    """Look up the current canonical path without opening a project."""
    target = text(p.get("path", ""))
    if not target:
        return dict(path="", canonical="", exists=False)
    # Resolve canonical filesystem identity, normalizing Windows 8.3 short names and symlinks.
    try:
        resolved = resolve_input(target)
        return dict(path=str(resolved), canonical=str(resolved), exists=True)
    except (FileNotFoundError, OSError, ValueError):
        try:
            resolved = Path(target).resolve()
            return dict(path=str(resolved), canonical=str(resolved), exists=False)
        except (OSError, ValueError):
            return dict(path=target, canonical=target, exists=False)


def open_recovery(service, p):
    """Claim a listed recovery copy and open it as unsaved project work."""
    if not service.recovery_dir or not isinstance(p.get("id"), str):
        raise ValueError("Recovery copy unavailable")
    if p["id"] not in {item["id"] for item in service.recovery_projects()}:
        raise ValueError("Recovery copy unavailable")
    recovery = service.recovery_dir / (p["id"] + ".eproj")
    claim = RecoveryClaim(service.recovery_dir, p["id"])
    if not claim.acquire():
        raise ValueError("Recovery copy is open in another window")
    try:
        service.call("project.open", dict(path=str(recovery), discard=p.get("discard")))
    except Exception:
        claim.release()
        raise
    service.source_path = service.source_save_path = service.source_fingerprint = None
    service.workspace_dirty = True
    service.recovered_path = recovery
    service.recovered_claim = claim
    return service.state()


def close_project(service, p):
    """Release the working database after the service checks for unsaved drafts."""
    if p.get("discard") is True or not service.workspace_dirty:
        service.clear_recovery()
    service.clear_mcp_indexes()
    if hasattr(service, "project_editor"):
        service.project_editor.close()
        del service.project_editor
    if service.db:
        service.db.close_database()
    service.db = None
    service.loaded = False
    service.source_path = service.source_save_path = service.source_fingerprint = service.recovered_path = None
    service.workspace_dirty = False
    service.model = ScheduleItemModel("DEMO", "Untitled rate analysis", "m³")
    service.model.add_ana_group("MATERIALS")
    service.model.add_ana_sum("TOTAL")
    service.model.add_ana_round("Say", Decimal("2"))
    service.identify()
    service.history.clear()
    service.future.clear()
    service.clipboard.clear()
    service.revision += 1
    service.saved_signature = copy.deepcopy(service.signature())
    return service.state()


def new_project(service, p):
    """Install a blank project after the service checks for unsaved drafts."""
    target = Path(service.temp.name) / (uuid4().hex + ".eproj")
    new = ScheduleDatabase(Stack())
    new.create_new_database(str(target))
    if p.get("discard") is True:
        service.clear_recovery()
    service.clear_mcp_indexes()
    if hasattr(service, "project_editor"):
        service.project_editor.close()
    if service.db:
        service.db.close_database()
    service.db = new
    service.loaded = False
    service.source_path = service.source_save_path = None
    service.source_fingerprint = None
    service.recovered_path = None
    service.workspace_dirty = True
    service.model = ScheduleItemModel("", "Select a schedule item")
    service.history.clear()
    service.future.clear()
    service.clipboard.clear()
    service.revision += 1
    service.saved_signature = copy.deepcopy(service.signature())
    service.project_editor = ProjectEditor(service)
    return service.state()


def open_project(service, p, progress):
    """Copy and validate the source before replacing the active working project."""
    source = resolve_input(text(p["path"]))
    check_database_access(source)
    before = fingerprint(source)
    progress("Copying project into isolated workspace")
    target = Path(service.temp.name) / (uuid4().hex + ".eproj")
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as src:
        version = src.execute("SELECT value FROM ProjectTable WHERE key='file_version'").fetchone()
        if version not in ((misc.PROJECT_FILE_VER,), ("GESTIMATOR_FILE_REFERENCE_VER_1",)):
            raise ValueError("Unsupported project file version")
        with closing(sqlite3.connect(target)) as dst:
            src.backup(dst)
    if fingerprint(source) != before:
        target.unlink()
        raise ValueError("Project changed while opening. Try opening it again.")
    new = ScheduleDatabase(Stack())
    if version == ("GESTIMATOR_FILE_REFERENCE_VER_1",):
        result = new.validate_database(str(target))
        if not result[0]:
            raise ValueError(result[1])
    new.open_database(str(target))
    # Display order only: earlier projects can hold SUB ANALYSIS first.
    keep_sub_analysis_last(new)
    if p.get("discard") is True:
        service.clear_recovery()
    service.clear_mcp_indexes()
    if hasattr(service, "project_editor"):
        service.project_editor.close()
    if service.db:
        service.db.close_database()
    service.db = new
    service.workspace_dirty = False
    service.project_editor = ProjectEditor(service)
    service.source_path = str(source)
    service.source_save_path = None
    service.source_fingerprint = before
    service.recovered_path = None
    service.loaded = False
    service.model = ScheduleItemModel("", "Select a schedule item")
    service.history.clear()
    service.future.clear()
    service.clipboard.clear()
    service.revision += 1
    service.saved_signature = copy.deepcopy(service.signature())
    return dict(opened=str(source))


def save_project(service, p, progress):
    """Publish the working project to its source and preserve a backup."""
    if not service.source_path or not service.source_fingerprint:
        raise ValueError("Choose a location with Save project copy first")
    if not (service.workspace_dirty or (service.loaded and service.dirty) or service.records_dirty):
        return dict(saved=service.source_path)
    destination = Path(service.source_save_path or service.source_path)
    expected = service.source_fingerprint
    if flatpak_document(destination) and (p.get("directory") or portal_needs_folder(destination)):
        destination, expected = save_target(destination, expected, p.get("directory"))
    progress("Saving project and preserving a backup")
    backup, service.source_fingerprint = save_existing(destination, expected, service.write_project_snapshot)
    service.source_save_path = str(destination)
    service.finish_project_save()
    return dict(saved=service.source_path, backup=str(backup))


def save_project_copy(service, p, progress):
    """Publish a copy, or replace a Flatpak destination confirmed by the chooser."""
    if not service.db:
        raise ValueError("Open a project first")
    destination = Path(text(p["path"])).resolve()
    source = service.source_save_path or service.source_path
    replacing = p.get("replace_selected") is True and portal_parts(destination) and destination.exists()
    is_source = False
    current = None
    if replacing:
        check_database_access(destination)
        original = Path(source) if source else None
        is_source = original is not None and same_project_path(original, destination)
        expected = (
            verified_alias(original, service.source_fingerprint, destination) if is_source else fingerprint(destination)
        )
        progress("Saving project copy and preserving a backup")
        _, current = save_existing(destination, expected, service.write_project_snapshot)
    else:
        with export_output(destination) as output:
            progress("Saving analysis and updating dependent rates")
            service.write_project_snapshot(output)
    if not service.source_path:
        service.source_path = str(destination)
        service.source_fingerprint = current or fingerprint(destination)
    elif is_source:
        service.source_save_path = str(destination)
        service.source_fingerprint = current
    service.finish_project_save()
    return dict(saved=str(destination))
