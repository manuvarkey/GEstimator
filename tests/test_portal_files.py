"""Check file-versus-folder grants using stand-ins for the portal mount."""

import os
import shutil
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from modern.backend.persistence import check_database_access, export_output, fingerprint, flatpak_document, save_target
from modern.backend.service import Service


class PortalFileTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.runtime = Path(temporary.name)
        environment = patch.dict(os.environ, FLATPAK_ID="com.kavilgroup.gestimator", XDG_RUNTIME_DIR=str(self.runtime))
        environment.start()
        self.addCleanup(environment.stop)

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
