"""Version-one migration and connection behavior through ScheduleDatabase."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from estimator import misc
from estimator.data.schedule import ResourceItemModel, ScheduleDatabase
from estimator.undo import Stack


class DatabaseLifecycleTests(unittest.TestCase):
    def test_resource_category_insert_failure_leaves_resource_and_undo_intact(self):
        owner = ScheduleDatabase(Stack())
        owner.create_new_database()
        self.addCleanup(owner.close_database)
        owner.insert_resource(ResourceItemModel("R", "Original", "kg", 10, category="Materials"))
        undo_count = owner.stack.undocount()
        owner.database.execute_sql(
            """
            CREATE TRIGGER block_category BEFORE INSERT ON ResourceCategoryTable
            WHEN NEW.description='Labour' BEGIN SELECT RAISE(ABORT, 'blocked category'); END
            """
        )

        with self.assertLogs(level="ERROR"):
            result = owner.update_resource("R", res_model=ResourceItemModel("R", "Edited", "kg", 10, category="Labour"))
            inserted = owner.insert_resource(ResourceItemModel("L", "New", "hour", 20, category="Labour"))

        self.assertFalse(result)
        self.assertFalse(inserted)
        resource = owner.get_resource("R")
        self.assertEqual((resource.description, resource.category), ("Original", "Materials"))
        self.assertEqual(owner.stack.undocount(), undo_count)
        self.assertFalse(
            owner.ResourceCategoryTable.select().where(owner.ResourceCategoryTable.description == "Labour").exists()
        )
        self.assertIsNone(owner.get_resource("L"))

    def test_failed_version_update_rolls_back_the_column_and_can_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "old.eproj")
            owner = ScheduleDatabase(Stack())
            owner.create_new_database(path)
            owner.close_database()
            version_one = "GESTIMATOR_FILE_REFERENCE_VER_1"
            with closing(sqlite3.connect(path)) as database, database:
                database.execute("ALTER TABLE ScheduleTable DROP COLUMN colour")
                database.execute("UPDATE ProjectTable SET value=? WHERE key='file_version'", (version_one,))
                database.execute(
                    """
                    CREATE TRIGGER block_version_update BEFORE UPDATE ON ProjectTable
                    WHEN old.key='file_version' BEGIN SELECT RAISE(ABORT, 'blocked version update'); END
                    """
                )

            self.assertFalse(owner.validate_database(path)[0])
            with closing(sqlite3.connect(path)) as database, database:
                columns = {row[1] for row in database.execute("PRAGMA table_info(ScheduleTable)")}
                self.assertNotIn("colour", columns)
                self.assertEqual(
                    database.execute("SELECT value FROM ProjectTable WHERE key='file_version'").fetchone(),
                    (version_one,),
                )
                database.execute("DROP TRIGGER block_version_update")

            self.assertEqual(owner.validate_database(path), [True])
            self.assertTrue(owner.open_database(path))
            try:
                self.assertEqual(owner.get_project_settings()["file_version"], misc.PROJECT_FILE_VER)
                self.assertEqual(owner.database.execute_sql("PRAGMA foreign_keys").fetchone(), (1,))
                columns = {column.name for column in owner.database.get_columns("ScheduleTable")}
                self.assertIn("colour", columns)
            finally:
                owner.close_database()

    def test_invalid_and_future_versions_keep_their_validation_messages(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "project.eproj")
            owner = ScheduleDatabase(Stack())
            owner.create_new_database(path)
            owner.close_database()

            with closing(sqlite3.connect(path)) as database, database:
                database.execute("UPDATE ProjectTable SET value='ZZZ' WHERE key='file_version'")
            self.assertEqual(
                owner.validate_database(path),
                [False, "Newer project file version found. Please use the latest application version."],
            )
            with closing(sqlite3.connect(path)) as database, database:
                database.execute("DELETE FROM ProjectTable WHERE key='file_version'")
            self.assertEqual(owner.validate_database(path), [False, "Error validating file. unknown/corrupt file."])
