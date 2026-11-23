#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# database_lifecycle.py
#
#  Copyright 2014 Manu Varkey <manuvarkey@gmail.com>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
#

"""Create, bind and migrate the schedule engine's SQLite databases."""

import logging

import peewee
from playhouse.migrate import SqliteMigrator, migrate

from .. import misc

log = logging.getLogger()

_VERSION_ONE = "GESTIMATOR_FILE_REFERENCE_VER_1"
_INVALID_DATABASE = "Error validating file. unknown/corrupt file."
_NEWER_DATABASE = "Newer project file version found. Please use the latest application version."


def create_database(owner, filename=None):
    """Bind a new project to a file or an in-memory connection and set defaults."""
    owner.open_database(filename if filename else ":memory:")
    owner.database_filename = filename if filename else None
    # Each ScheduleDatabase instance owns the models bound to its connection.
    tables = [
        owner.ProjectTable,
        owner.ScheduleTable,
        owner.ResourceTable,
        owner.ScheduleCategoryTable,
        owner.ResourceCategoryTable,
        owner.SequenceTable,
        owner.ResourceItemTable,
    ]
    owner.database.create_tables(tables)
    owner.set_project_settings(misc.default_project_settings)
    log.info("ScheduleDatabase - create_new_database - database tables created")


def open_database(owner, filename):
    """Bind the existing project and enable foreign keys on its connection."""
    owner.database.init(filename)
    owner.database_filename = filename
    owner.database.execute_sql("PRAGMA foreign_keys=ON;")
    return True


def close_database(owner):
    """Close the bound database and clear the active filename."""
    owner.database.close()
    owner.database_filename = None


def _version(database):
    row = database.execute_sql("SELECT value FROM ProjectTable WHERE key='file_version'").fetchone()
    return row[0] if row else None


def validate_database(filename):
    """Check a project file and upgrade version one in a single transaction."""
    database = peewee.SqliteDatabase(filename)
    try:
        with database.connection_context():
            version = _version(database)
            if not isinstance(version, str):
                return [False, _INVALID_DATABASE]
            if version > misc.PROJECT_FILE_VER:
                return [False, _NEWER_DATABASE]
            if version == _VERSION_ONE:
                # Keep validation and DDL on one connection. Recheck the version
                # under the write lock in case another caller migrated this file.
                with database.atomic("IMMEDIATE"):
                    version = _version(database)
                    if version == misc.PROJECT_FILE_VER:
                        return [True]
                    if version != _VERSION_ONE:
                        return [False, _INVALID_DATABASE]
                    _add_colour_column(database)
                    database.execute_sql(
                        "UPDATE ProjectTable SET value = ? WHERE key='file_version'", (misc.PROJECT_FILE_VER,)
                    )
                    if _version(database) != misc.PROJECT_FILE_VER:
                        raise peewee.IntegrityError("Project version marker was not updated")
    except (OSError, peewee.DatabaseError):
        return [False, _INVALID_DATABASE]
    return [True]


def _add_colour_column(database):
    migrate(SqliteMigrator(database).add_column("ScheduleTable", "colour", peewee.CharField(null=True)))


def migrate_from_ver_1(filename):
    """Provide the existing column-only migration entry point."""
    log.info("ScheduleDatabase - migrate_from_ver_1 called - %s", filename)
    database = peewee.SqliteDatabase(filename)
    with database.connection_context(), database.atomic():
        _add_colour_column(database)
    log.info("ScheduleDatabase - database migrated - %s", filename)
