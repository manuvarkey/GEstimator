"""Serialized, authoritative analysis session; no GTK or frontend calculations."""

from __future__ import annotations

import copy
import json
import sqlite3
import tempfile
from contextlib import closing
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from estimator import misc
from estimator.data.schedule import ScheduleDatabase, ScheduleItemModel
from estimator.undo import Stack

from . import analysis_edits, project_files
from .numbers import tax_text
from .persistence import RecoveryClaim, export_output, flatpak_document, write_recovery
from .validation import request_text as text


class Service:
    def __init__(self, recovery_dir=None, dispatch=None, mcp=None, peers=None):
        from .mcp_server import MCPServer

        # Document sessions share one MCP listener owned by the runtime.
        self.owns_mcp = mcp is None
        self.mcp = mcp if mcp is not None else MCPServer(dispatch)
        # Other open documents in this process; their live recovery copies are not offered.
        self.peers = peers or (lambda: ())
        self.temp = tempfile.TemporaryDirectory(prefix="gestimator-")
        self.db = None
        self.loaded = False
        self.workspace_dirty = False
        self.source_path = None
        self.source_save_path = None
        self.source_fingerprint = None
        self.recovery_dir = recovery_dir
        self.recovery_id = uuid4().hex
        self.recovery_state = None
        # Locks that keep other processes from offering this window's copies.
        self.recovery_claim = None
        self.recovered_claim = None
        self._recovered_path = None
        if recovery_dir:
            self.recovery_claim = RecoveryClaim(recovery_dir, self.recovery_id)
            self.recovery_claim.acquire()
        self.model = ScheduleItemModel("DEMO", "Untitled rate analysis", "m³")
        self.history = []
        self.future = []
        self.clipboard = []
        self.revision = 0
        self.model.add_ana_group("MATERIALS")
        self.model.add_ana_sum("TOTAL")
        self.model.add_ana_round("Say", Decimal("2"))
        self.identify()
        self.saved_signature = copy.deepcopy(self.signature())

    def signature(self):
        return (
            self.model.ana_items,
            {code: vars(res) for code, res in self.model.resources.items()},
            self.model.ana_remarks,
        )

    @property
    def dirty(self):
        return self.signature() != self.saved_signature

    @property
    def records_dirty(self):
        draft = getattr(getattr(self, "project_editor", None), "measurement_draft", None)
        return bool(draft and draft.dirty)

    def guard_draft(self, params, project=False, records=True):
        if records and self.records_dirty and params.get("discard") is not True:
            raise ValueError("Unsaved measurement records: apply or discard the draft first")
        if (self.dirty or (project and self.workspace_dirty)) and params.get("discard") is not True:
            raise ValueError("Unsaved analysis: save the project or explicitly discard the draft first")

    def identify(self):
        for row in self.model.ana_items:
            row.setdefault("_id", uuid4().hex)
            if row["itemtype"] == 0:
                # Resource records remain legacy lists; identities live on their group.
                row.setdefault("_resource_ids", [uuid4().hex for _ in row["resource_list"]])

    def locate(self, identity):
        for i, row in enumerate(self.model.ana_items):
            if row["_id"] == identity:
                return i, None
            if identity in row.get("_resource_ids", []):
                return i, row["_resource_ids"].index(identity)
        raise ValueError("Row no longer exists")

    def state(self):
        self.model.evaluate_results()
        rows = []
        for row, result in zip(self.model.ana_items, self.model.results):
            data = dict(
                id=row["_id"],
                kind=["Group", "Subtotal", "Weight", "Multiply", "Round"][row["itemtype"]],
                description=row["description"] or "",
                code=row.get("code") or "",
                value=str(row.get("value", "")),
                amount=str(result[-1] if isinstance(result, list) else result),
            )
            if row["itemtype"] == 0:
                data["_children"] = []
                for identity, entry, res_result in zip(row["_resource_ids"], row["resource_list"], result[:-1]):
                    res = self.model.resources[entry[0]]
                    data["_children"].append(
                        dict(
                            id=identity,
                            kind="Resource",
                            code=res.code,
                            description=res.description,
                            unit=res.unit,
                            value=str(entry[1]),
                            rate=str(res.rate),
                            vat=tax_text(res.vat),
                            discount=str(res.discount or 0),
                            effective_rate=str(res_result[0]),
                            amount=str(res_result[1]),
                            remarks=entry[2] or "",
                            reference=res.reference or "",
                            category=res.category or "",
                        )
                    )
            rows.append(data)
        return dict(
            code=self.model.code,
            description=self.model.description,
            rows=rows,
            rate=str(self.model.get_ana_rate() or 0),
            revision=self.revision,
            undo=bool(self.history),
            redo=bool(self.future),
            project=self.db is not None and self.loaded,
            project_open=self.db is not None,
            source_path=self.source_path,
            source_requires_folder=bool(
                self.source_path and not self.source_save_path and flatpak_document(self.source_path)
            ),
            unit=self.model.unit or "",
            dirty=self.dirty,
            measurement_draft=(
                self.project_editor.measurement_draft.state()
                if self.db and self.project_editor.measurement_draft
                else None
            ),
            libraries=(self.project_editor.sources() if hasattr(self, "project_editor") else []),
            workspace_dirty=self.workspace_dirty,
            project_name=(self.db.get_project_settings().get("project_name", "") if self.db else ""),
            ana_remarks=self.model.ana_remarks or "",
        )

    def call(self, method: str, p: dict, progress=lambda value: None):
        if method.startswith("mcp."):
            if method == "mcp.status":
                return self.mcp.status(include_tools=p.get("include_tools", False))
            if method == "mcp.configure":
                return self.mcp.configure(p)
            if method == "mcp.enable":
                return self.mcp.enable(p.get("enabled"))
            if method == "mcp.start":
                return self.mcp.start()
            if method == "mcp.stop":
                return self.mcp.stop()
            if method == "mcp.rotate_token":
                from secrets import token_urlsafe

                return self.mcp.configure(dict(token=token_urlsafe(32)))
            if method == "mcp.read":
                if "_listener" in p and (self.mcp.server is None or p["_listener"] != self.mcp.generation):
                    raise ValueError("MCP listener stopped; reconnect and read state before retrying")
                from .mcp_server import read_tool

                return read_tool(self, p.get("name"), p.get("arguments", {}))
            raise ValueError("Unknown MCP operation")
        if method == "path.canonical":
            return project_files.canonical_path(p)
        if method == "search.warm":
            # Build search indexes after opening so the first search is quick.
            if self.db:
                from .program_settings import library_directory
                from .search import search

                user = library_directory().parent / "dictionary.user.json"
                for kind in ("schedule", "resource"):
                    search(self, self.db, kind, "warm", 1, user_path=user)
            return dict(ok=True)
        if method == "workbook.sheet":
            from .importing import sheet_preview

            return sheet_preview(p)
        if method.startswith("program."):
            from . import program_settings

            if method == "program.desktop_font":
                from .system_fonts import desktop_font

                return desktop_font()
            if method == "program.settings":
                return dict(
                    settings=program_settings.defaults(), library_directory=str(program_settings.library_directory())
                )
            if method == "program.libraries":
                return program_settings.library_catalog()
            if method == "program.fonts":
                from .system_fonts import installed_families

                return installed_families()
            if method == "program.settings.validate":
                settings = program_settings.validate(p.get("settings"))
                program_settings.legacy_rows(settings["ana_default_rows"])
                program_settings.legacy_rows(settings["ana_copy_rows"])
                return settings
            if method == "program.library_directory":
                directory = program_settings.library_directory()
                directory.mkdir(parents=True, exist_ok=True)
                return str(directory)
            raise ValueError("Unknown program settings operation")
        if method == "state":
            return self.state()
        if method == "analysis.template_rows":
            kinds = ["Group", "Subtotal", "Weight", "Multiply", "Round"]
            return [
                dict(kind=kinds[row["itemtype"]], description=row["description"], value=str(row.get("value", "")))
                for row in misc.ana_default_add_items
            ]
        if method == "analysis.rules.validate":
            from .analysis_rules import validate

            return validate(p.get("rules"))
        if method == "recovery.list":
            return self.recovery_projects()
        if method == "recovery.discard":
            self.clear_recovery()
            return True
        if method == "recovery.open":
            return project_files.open_recovery(self, p)
        if method.startswith("library."):
            if not self.db:
                raise ValueError("Open a project first")
            return self.project_editor.call(method, p, progress)
        if method == "project.close":
            self.guard_draft(p, project=True)
            return project_files.close_project(self, p)
        if method == "project.new":
            self.guard_draft(p, project=True)
            return project_files.new_project(self, p)
        if method == "project.settings":
            if not self.db:
                raise ValueError("Open a project first")
            settings = self.db.get_project_settings()
            return {
                key: settings.get(key, "")
                for key in ("project_name", "project_item_code", "project_resource_code", "project_metadata")
            }
        if method == "project.open":
            self.guard_draft(p, project=True)
            return project_files.open_project(self, p, progress)
        if method.startswith(
            (
                "schedule.editor.",
                "resources.editor.",
                "measurement.",
                "project.undo",
                "project.redo",
                "project.export",
                "project.settings.edit",
                "project.reorder",
                "project.enrichment.clear",
                "project.import",
            )
        ):
            if not self.db:
                raise ValueError("Open a project first")
            return self.project_editor.call(method, p, progress)
        if method in ("analysis.export_xlsx",):
            return self.export_analysis(p, progress)
        if method == "analysis.import_preview":
            if not self.loaded:
                raise ValueError("Load an analysis first")
            from .analysis_import import analysis_rows, import_analysis

            warnings = []
            draft = import_analysis(self.model, p, warnings)
            return dict(
                rows=len(draft.ana_items),
                resources=len(draft.resources),
                rate=str(draft.get_ana_rate()),
                items=analysis_rows(draft),
                warnings=warnings[:200],
            )
        if method in ("schedule.list", "resources.search"):
            if not self.db:
                raise ValueError("Open a project first")
            limit = p.get("limit", 100)
            offset = p.get("offset", 0)
            if type(limit) is not int or not 1 <= limit <= 200 or type(offset) is not int or offset < 0:
                raise ValueError("Invalid page")
            selected_db = (
                self.project_editor.libraries[p["source"]][1]
                if p.get("source") in self.project_editor.libraries
                else self.db
            )
            table = selected_db.ScheduleTable if method == "schedule.list" else selected_db.ResourceTable
            query = text(p.get("query", ""))
            if query.strip():
                from .search import desktop_codes

                codes, _ = desktop_codes(
                    self, selected_db, "schedule" if method == "schedule.list" else "resources", query
                )
                positions = {code: index for index, code in enumerate(codes[offset : offset + limit])}
                records = sorted(
                    table.select().where(table.code.in_(list(positions))), key=lambda row: positions[row.code]
                )
            else:
                records = table.select().order_by(table.id).offset(offset).limit(limit)
            return [dict(code=r.code, description=r.description, unit=r.unit, rate=str(r.rate)) for r in records]
        if method == "analysis.load":
            self.guard_draft(p)
            if not self.db:
                raise ValueError("Open a project first")
            model = self.db.get_item(text(p["code"]), modify_res_code=False)
            if model is None:
                raise ValueError("Unknown schedule code")
            S = self.db.ScheduleTable
            if S.select().where(S.parent.in_(S.select(S.id).where(S.code == model.code))).exists():
                raise ValueError(f"Item {model.code} has subitems; edit the analysis of each subitem instead")
            if self.records_dirty and p.get("discard") is True:
                self.project_editor.draft_command("discard", p)
            self.model = model
            self.loaded = True
            self.identify()
            self.history.clear()
            self.future.clear()
            self.revision += 1
            self.saved_signature = copy.deepcopy(self.signature())
            return self.state()
        if method == "project.save":
            return project_files.save_project(self, p, progress)
        if method == "project.save_copy":
            return project_files.save_project_copy(self, p, progress)
        if p.get("revision") != self.revision:
            raise ValueError("Stale edit; reload analysis state")
        if method in ("clipboard.export", "clipboard.paste"):
            from . import clipboard

            return clipboard.export(self, p) if method == "clipboard.export" else clipboard.paste(self, p)
        if self.records_dirty:
            raise ValueError("Apply or discard unsaved measurement records first")
        if method == "analysis.batch.preview":
            original = self.model
            self.model = copy.deepcopy(original)
            try:
                self.edit("analysis.batch", p)
                return self.state()
            finally:
                self.model = original
        if method == "analysis.apply":
            if not self.loaded:
                raise ValueError("Load an analysis first")
            self.project_editor.mutate(lambda: self.write_analysis(self.db), reload=False)
            self.sync_analysis()
            self.saved_signature = copy.deepcopy(self.signature())
            self.revision += 1
            return self.state()
        if method in ("undo", "redo"):
            source, dest = (self.history, self.future) if method == "undo" else (self.future, self.history)
            if source:
                dest.append(copy.deepcopy(self.model))
                self.model = source.pop()
                self.revision += 1
            return self.state()
        before = copy.deepcopy(self.model)
        try:
            self.edit(method, p)
            self.model.evaluate_results()
        except Exception:
            self.model = before
            raise
        if method != "copy" and self.signature() != (
            before.ana_items,
            {code: vars(res) for code, res in before.resources.items()},
            before.ana_remarks,
        ):
            self.history.append(before)
            self.history = self.history[-100:]
            self.future.clear()
            self.revision += 1
        return self.state()

    def edit(self, method, p):
        """Edit the active analysis draft under the existing caller boundary."""
        return analysis_edits.edit(self, method, p)

    def sync_analysis(self):
        model = self.db.get_item(self.model.code, modify_res_code=False)
        if model is None:
            raise ValueError("Schedule item no longer exists")
        for row, old in zip(model.ana_items, self.model.ana_items):
            row["_id"] = old["_id"]
            if row["itemtype"] == 0:
                row["_resource_ids"] = old.get("_resource_ids", [])[:]
        self.model = model
        self.identify()

    def write_analysis(self, db):
        model = copy.deepcopy(self.model)
        model.evaluate_results()
        model.update_rate()
        with db.database.atomic():
            used = {entry[0] for group in model.ana_items if group["itemtype"] == 0 for entry in group["resource_list"]}
            changed = set()
            for code in used:
                resource = model.resources[code]
                existing = db.get_resource(code)
                if existing:
                    if resource.category != existing.category:
                        if not db.update_resource(code, res_model=resource):
                            raise ValueError("Unable to update resource")
                        changed.add(code)
                    else:
                        for column, field in enumerate(
                            ("description", "unit", "rate", "vat", "discount", "reference"), 1
                        ):
                            value = getattr(resource, field)
                            if value != getattr(existing, field):
                                if not db.update_resource(code, newvalue=value, column=column):
                                    raise ValueError("Unable to update resource")
                                if field in ("rate", "vat", "discount"):
                                    changed.add(code)
            if not db.insert_item_atomic(model, update=True):
                raise ValueError("Unable to save analysis")
            self.update_dependent_rates(db, changed, {model.code})
        db.stack.clear()

    def write_project_snapshot(self, destination):
        with closing(sqlite3.connect(destination)) as output:
            self.db.database.connection().backup(output)
        if (self.loaded and self.dirty) or self.records_dirty:
            snapshot = ScheduleDatabase(Stack())
            snapshot.open_database(str(destination))
            try:
                if self.loaded and self.dirty:
                    self.write_analysis(snapshot)
                if self.records_dirty:
                    self.project_editor.measurement_draft.write(self.project_editor, snapshot)
            finally:
                snapshot.close_database()

    def finish_project_save(self):
        if self.records_dirty:
            self.project_editor.measurement_draft.accept(self.project_editor)
        if self.loaded and self.dirty:
            self.project_editor.mutate(lambda: self.write_analysis(self.db), reload=False)
            self.sync_analysis()
        self.workspace_dirty = False
        self.saved_signature = copy.deepcopy(self.signature())
        if self.recovered_path:
            self.recovered_path.unlink(missing_ok=True)
            self.recovered_path = None

    @property
    def recovered_path(self):
        return self._recovered_path

    @recovered_path.setter
    def recovered_path(self, path):
        # Dropping the recovered copy also drops its claim (recovery.open sets the new claim).
        self._recovered_path = path
        if getattr(self, "recovered_claim", None):
            self.recovered_claim.release()
            self.recovered_claim = None

    def recovery_projects(self):
        if not self.recovery_dir:
            return []
        projects = []
        live = {self.recovery_id} | {peer.recovery_id for peer in self.peers()}
        claimed = {self.recovered_path} | {peer.recovered_path for peer in self.peers()}
        for path in self.recovery_dir.glob("*.eproj"):
            if path.stem in live or path in claimed:
                continue
            # Live or reopened copy of a window in another process.
            if RecoveryClaim.held(self.recovery_dir, path.stem):
                continue
            try:
                projects.append(dict(id=path.stem, updated=path.stat().st_mtime))
            except FileNotFoundError:
                continue
        return sorted(projects, key=lambda item: item["updated"], reverse=True)

    def clear_recovery(self):
        if self.recovery_dir:
            (self.recovery_dir / (self.recovery_id + ".eproj")).unlink(missing_ok=True)
        if self.recovered_path:
            self.recovered_path.unlink(missing_ok=True)
            self.recovered_path = None
        self.recovery_state = (self.revision, True)

    def checkpoint_recovery(self):
        if not self.recovery_dir:
            return
        dirty = self.db is not None and (self.workspace_dirty or (self.loaded and self.dirty) or self.records_dirty)
        state = (self.revision, dirty)
        if state == self.recovery_state:
            return
        path = self.recovery_dir / (self.recovery_id + ".eproj")
        if dirty:
            write_recovery(path, self.write_project_snapshot)
        else:
            path.unlink(missing_ok=True)
        self.recovery_state = state

    def instance_code(self):
        """GTK MainWindow.get_instance_code: a short per-document identity."""
        from hashlib import blake2b

        seed = self.source_path or self.recovery_id
        return blake2b(seed.encode("utf-8"), digest_size=2).hexdigest().upper()

    def update_dependent_rates(self, db, resources=(), schedules=()):
        from .rates import update_dependents

        update_dependents(db, resources, schedules)

    def export_analysis(self, params, progress):
        if not self.loaded:
            raise ValueError("Load an analysis first")
        destination = Path(text(params["path"])).resolve()
        scratch = ScheduleDatabase(Stack())
        with export_output(destination, params.get("replace_selected") is True) as output:
            self.write_analysis_export(scratch, output, progress)
        return dict(saved=str(destination))

    def write_analysis_export(self, scratch, output, progress):
        """Write one workbook using a disposable copy of the working database."""
        try:
            target = Path(self.temp.name) / (uuid4().hex + ".eproj")
            with closing(sqlite3.connect(target)) as dst:
                self.db.database.connection().backup(dst)
            scratch.open_database(str(target))
            self.write_analysis(scratch)
            progress("Exporting analysis using existing spreadsheet writer")
            sheet = misc.Spreadsheet()
            scratch.export_ana_item_spreadsheet(self.model.code, sheet)
            sheet.set_title("Analysis")
            sheet.set_column_widths([12, 65, 10, 12, 12, 14])
            sheet.set_page_settings(font="Consolas")
            sheet.save(output)
        finally:
            scratch.close_database()

    def clear_mcp_indexes(self):
        for _, index in getattr(self, "_mcp_search", {}).values():
            index.close()
        self._mcp_search = {}
        self._search_text_memo = {}

    def close(self):
        if self.owns_mcp:
            self.mcp.stop()
        self.clear_mcp_indexes()
        if hasattr(self, "_mcp_catalog"):
            self._mcp_catalog.close()
        if hasattr(self, "project_editor"):
            self.project_editor.close()
        if self.db:
            self.db.close_database()
        self.recovered_path = None
        if self.recovery_claim:
            self.recovery_claim.release()
        self.temp.cleanup()
