"""Check file-versus-folder grants using stand-ins for the portal mount."""

import errno
import os
import shutil
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from modern.backend.persistence import (
    check_database_access,
    export_output,
    fingerprint,
    flatpak_document,
    save_lock,
    save_target,
)
from modern.backend.service import Service


class PortalFileTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        # The service resolves chooser paths. Use the same spelling for the
        # simulated mount when the temp directory has an alias.
        self.runtime = Path(temporary.name).resolve(strict=True)
        (self.runtime / "app" / "com.kavilgroup.gestimator").mkdir(parents=True)
        environment = patch.dict(os.environ, FLATPAK_ID="com.kavilgroup.gestimator", XDG_RUNTIME_DIR=str(self.runtime))
        environment.start()
        self.addCleanup(environment.stop)
        data = patch.dict(os.environ, XDG_DATA_HOME=str(self.runtime / "data"))
        data.start()
        self.addCleanup(data.stop)

    def portal_path(self, relative):
        result = self.runtime / "doc" / relative
        result.parent.mkdir(parents=True, exist_ok=True)
        return result

    def test_recognizes_both_paths_to_the_flatpak_mount(self):
        self.assertTrue(flatpak_document("/run/flatpak/doc/file/estimate.eproj"))
        self.assertTrue(flatpak_document(self.runtime / "doc/file/estimate.eproj"))
        self.assertFalse(flatpak_document("/run/flatpak/doc/folder/Jobs/estimate.eproj"))
        self.assertFalse(flatpak_document(self.runtime / "projects/Jobs/estimate.eproj"))

    def test_save_reuses_folder_grant_and_keeps_the_backup_beside_project(self):
        source = self.portal_path("file/estimate.eproj")
        destination = self.portal_path("folder/Jobs/estimate.eproj")
        service = Service()
        self.addCleanup(service.close)
        service.call("project.new", {})
        service.call("project.save_copy", {"path": str(source)})
        shutil.copy2(source, destination)
        original_bytes = source.read_bytes()

        with patch("os.access", return_value=False):
            self.assertTrue(service.state()["source_requires_folder"])
            service.workspace_dirty = True
            with self.assertRaisesRegex(ValueError, "Choose the project folder"):
                service.call("project.save", {})
        with patch("os.getxattr", return_value=b"/host/Jobs/estimate.eproj", create=True):
            result = service.call("project.save", {"directory": str(destination.parent)})
            self.assertEqual(Path(result["backup"]).read_bytes(), original_bytes)
            self.assertEqual(service.state()["source_path"], str(source))
            self.assertFalse(service.state()["source_requires_folder"])
            service.workspace_dirty = True
            second = service.call("project.save", {})

        self.assertEqual(Path(second["backup"]).name, "estimate.eproj.2.bak")
        self.assertFalse(destination.with_name(".estimate.eproj.gestimator-lock").exists())

    def test_writable_file_grant_saves_in_place_with_numbered_private_backups(self):
        source = self.portal_path("file/estimate.eproj")
        service = Service()
        self.addCleanup(service.close)
        service.call("project.new", {})
        service.call("project.save_copy", {"path": str(source)})
        original = source.read_bytes()
        self.assertFalse(service.state()["source_requires_folder"])
        with patch("os.getxattr", return_value=b"/host/estimate.eproj", create=True):
            for notes in ("First save", "Second save"):
                service.call(
                    "project.settings.edit", {"revision": service.revision, "settings": {"project_metadata": notes}}
                )
                backup = Path(service.call("project.save", {})["backup"])
                self.assertTrue(backup.is_relative_to(self.runtime / "data/project-backups"))
                self.assertEqual(backup.read_bytes(), original)
                original = source.read_bytes()
        self.assertEqual(backup.name, "estimate.eproj.2.bak")
        self.assertEqual(list(source.parent.iterdir()), [source])

    def test_confirmed_save_copy_can_replace_a_portal_file(self):
        destination = self.portal_path("file/copy.eproj")
        destination.write_bytes(b"previous contents")
        service = Service()
        self.addCleanup(service.close)
        service.call("project.new", {})
        with self.assertRaises(FileExistsError):
            service.call("project.save_copy", {"path": str(destination)})
        with patch("os.getxattr", return_value=b"/host/copy.eproj", create=True):
            service.call("project.save_copy", {"path": str(destination), "replace_selected": True})
        self.assertEqual(service.state()["source_path"], str(destination))
        self.assertTrue(destination.read_bytes().startswith(b"SQLite format 3\x00"))
        (backup,) = (self.runtime / "data/project-backups").glob("*/copy.eproj.bak")
        self.assertEqual(backup.read_bytes(), b"previous contents")

    def test_confirmed_save_copy_rejects_a_portal_destination_with_wal(self):
        destination = self.portal_path("file/copy.eproj")
        service = Service()
        self.addCleanup(service.close)
        service.call("project.new", {})
        with closing(sqlite3.connect(destination)) as db:
            db.execute("PRAGMA journal_mode = WAL")
            db.execute("CREATE TABLE active (id INTEGER)")
            db.commit()
            with self.assertRaisesRegex(ValueError, "standalone SQLite backup"):
                service.call("project.save_copy", {"path": str(destination), "replace_selected": True})
            self.assertIsNone(service.state()["source_path"])

    def test_save_lock_serializes_grants_for_the_same_host_path(self):
        first = self.portal_path("first/Jobs/estimate.eproj")
        second = self.portal_path("second/Jobs/estimate.eproj")
        with patch("os.getxattr", return_value=b"/host/Jobs/estimate.eproj", create=True):
            with save_lock(first):
                with self.assertRaisesRegex(ValueError, "Another GEstimator window"):
                    with save_lock(second):
                        self.fail("Acquired a second lock for the same project")
            with save_lock(second):
                pass

    def test_unavailable_portal_lock_does_not_look_like_contention(self):
        source = self.portal_path("folder/Jobs/estimate.eproj")
        with patch("os.getxattr", side_effect=OSError(errno.ENOSYS, "No host path"), create=True):
            with self.assertRaisesRegex(ValueError, "Could not lock this project"):
                with save_lock(source):
                    self.fail("Proceeding without coordinating saves")

    def test_save_rejects_wrong_folder_and_external_changes(self):
        source = self.portal_path("file/estimate.eproj")
        source.write_bytes(b"original")
        expected = fingerprint(source)
        destination = self.portal_path("folder/Jobs/estimate.eproj")
        shutil.copy2(source, destination)

        with patch("os.getxattr", side_effect=[b"/original/estimate.eproj", b"/other/estimate.eproj"], create=True):
            with self.assertRaisesRegex(ValueError, "Choose the folder"):
                save_target(source, expected, destination.parent)
        destination.write_bytes(b"updated")
        with patch("os.getxattr", return_value=b"/original/estimate.eproj", create=True):
            with self.assertRaisesRegex(ValueError, "Project changed"):
                save_target(source, expected, destination.parent)

    def test_single_file_grant_rejects_wal_database(self):
        source = self.portal_path("file/library.eproj")
        with closing(sqlite3.connect(source)) as db:
            db.execute("CREATE TABLE library (id INTEGER)")
            self.assertIsNone(check_database_access(source))
            db.execute("PRAGMA journal_mode = WAL")
            db.execute("INSERT INTO library VALUES (1)")
            db.commit()
            with self.assertRaisesRegex(ValueError, "standalone SQLite backup"):
                check_database_access(source)

    def test_confirmed_export_replaces_only_after_success(self):
        destination = self.portal_path("file/estimate.xlsx")
        destination.write_bytes(b"original")
        with self.assertRaises(FileExistsError):
            with export_output(destination):
                self.fail("Existing destination was opened")
        with self.assertRaisesRegex(RuntimeError, "writer failed"):
            with export_output(destination, replace_selected=True) as output:
                output.write_bytes(b"partial")
                raise RuntimeError("writer failed")
        self.assertEqual(destination.read_bytes(), b"original")
        with export_output(destination, replace_selected=True) as output:
            output.write_bytes(b"complete")
        self.assertEqual(destination.read_bytes(), b"complete")
        self.assertEqual(list(destination.parent.iterdir()), [destination])
