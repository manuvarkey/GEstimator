"""Serialized, authoritative analysis session; no GTK or frontend calculations."""

from __future__ import annotations
import copy
from contextlib import closing
from decimal import Decimal, InvalidOperation
from pathlib import Path
import sqlite3
import json
import tempfile
from uuid import uuid4
from typing import Any
from estimator.data.schedule import (
    ScheduleDatabase,
    ScheduleItemModel,
    ResourceItemModel,
    Currency,
)
from estimator.undo import Stack
from estimator import misc


from .numbers import decimal, tax_text
from .persistence import fingerprint, save_existing, write_recovery


def text(value: Any) -> str:
    if not isinstance(value, str) or len(value) > 10000:
        raise ValueError("Expected text of at most 10000 characters")
    return value


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
        self.source_fingerprint = None
        self.recovery_dir = recovery_dir
        self.recovery_id = uuid4().hex
        self.recovery_state = None
        self.recovered_path = None
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
        if (self.dirty or (project and self.workspace_dirty)) and params.get(
            "discard"
        ) is not True:
            raise ValueError(
                "Unsaved analysis: save the project or explicitly discard the draft first"
            )

    def identify(self):
        for row in self.model.ana_items:
            row.setdefault("_id", uuid4().hex)
            if row["itemtype"] == 0:
                # Resource records remain legacy lists; identities live on their group.
                row.setdefault(
                    "_resource_ids", [uuid4().hex for _ in row["resource_list"]]
                )

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
                kind=["Group", "Subtotal", "Weight", "Multiply", "Round"][
                    row["itemtype"]
                ],
                description=row["description"] or "",
                code=row.get("code") or "",
                value=str(row.get("value", "")),
                amount=str(result[-1] if isinstance(result, list) else result),
            )
            if row["itemtype"] == 0:
                data["_children"] = []
                for identity, entry, res_result in zip(
                    row["_resource_ids"], row["resource_list"], result[:-1]
                ):
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
            unit=self.model.unit or "",
            dirty=self.dirty,
            measurement_draft=(self.project_editor.measurement_draft.state() if self.db and self.project_editor.measurement_draft else None),
            libraries=(
                self.project_editor.sources() if hasattr(self, "project_editor") else []
            ),
            workspace_dirty=self.workspace_dirty,
            project_name=(
                self.db.get_project_settings().get("project_name", "")
                if self.db
                else ""
            ),
            ana_remarks=self.model.ana_remarks or "",
        )

    def call(self, method: str, p: dict, progress=lambda value: None):
        if method.startswith("mcp."):
            if method == "mcp.status":
                return self.mcp.status(include_tools=p.get("include_tools", False))
            if method == "mcp.configure":
                return self.mcp.configure(p)
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
        if method == "search.warm":
            # Build search indexes after opening so the first search is quick.
            if self.db:
                from .search import search
                from .program_settings import library_directory
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
                return dict(settings=program_settings.defaults(), library_directory=str(program_settings.library_directory()))
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
            return [dict(kind=kinds[row["itemtype"]], description=row["description"], value=str(row.get("value", ""))) for row in misc.ana_default_add_items]
        if method == "analysis.rules.validate":
            from .analysis_rules import validate
            return validate(p.get("rules"))
        if method == "recovery.list":
            return self.recovery_projects()
        if method == "recovery.discard":
            self.clear_recovery()
            return True
        if method == "recovery.open":
            if not self.recovery_dir or not isinstance(p.get("id"), str):
                raise ValueError("Recovery copy unavailable")
            if p["id"] not in {item["id"] for item in self.recovery_projects()}:
                raise ValueError("Recovery copy unavailable")
            recovery = self.recovery_dir / (p["id"] + ".eproj")
            self.call("project.open", dict(path=str(recovery), discard=p.get("discard")))
            self.source_path = self.source_fingerprint = None
            self.workspace_dirty = True
            self.recovered_path = recovery
            return self.state()
        if method.startswith("library."):
            if not self.db:
                raise ValueError("Open a project first")
            return self.project_editor.call(method, p, progress)
        if method == "project.close":
            # Close the working project; unsaved work must be saved or discarded first.
            self.guard_draft(p, project=True)
            if p.get("discard") is True or not self.workspace_dirty:
                self.clear_recovery()
            self.clear_mcp_indexes()
            if hasattr(self, "project_editor"):
                self.project_editor.close()
                del self.project_editor
            if self.db:
                self.db.close_database()
            self.db = None
            self.loaded = False
            self.source_path = self.source_fingerprint = self.recovered_path = None
            self.workspace_dirty = False
            self.model = ScheduleItemModel("DEMO", "Untitled rate analysis", "m³")
            self.model.add_ana_group("MATERIALS")
            self.model.add_ana_sum("TOTAL")
            self.model.add_ana_round("Say", Decimal("2"))
            self.identify()
            self.history.clear()
            self.future.clear()
            self.clipboard.clear()
            self.revision += 1
            self.saved_signature = copy.deepcopy(self.signature())
            return self.state()
        if method == "project.new":
            self.guard_draft(p, project=True)
            target = Path(self.temp.name) / (uuid4().hex + ".eproj")
            new = ScheduleDatabase(Stack())
            new.create_new_database(str(target))
            if p.get("discard") is True:
                self.clear_recovery()
            self.clear_mcp_indexes()
            if hasattr(self, "project_editor"):
                self.project_editor.close()
            if self.db:
                self.db.close_database()
            self.db = new
            self.loaded = False
            self.source_path = None
            self.source_fingerprint = None
            self.recovered_path = None
            self.workspace_dirty = True
            self.model = ScheduleItemModel("", "Select a schedule item")
            self.history.clear()
            self.future.clear()
            self.clipboard.clear()
            self.revision += 1
            self.saved_signature = copy.deepcopy(self.signature())
            from .project import ProjectEditor

            self.project_editor = ProjectEditor(self)
            return self.state()
        if method == "project.settings":
            if not self.db:
                raise ValueError("Open a project first")
            settings = self.db.get_project_settings()
            return {
                key: settings.get(key, "")
                for key in (
                    "project_name",
                    "project_item_code",
                    "project_resource_code",
                )
            }
        if method == "project.open":
            self.guard_draft(p, project=True)
            source = Path(text(p["path"])).resolve(strict=True)
            before = fingerprint(source)
            progress("Copying project into isolated workspace")
            target = Path(self.temp.name) / (uuid4().hex + ".eproj")
            with closing(
                sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)
            ) as src:
                version = src.execute(
                    "SELECT value FROM ProjectTable WHERE key='file_version'"
                ).fetchone()
                if version not in (
                    (misc.PROJECT_FILE_VER,),
                    ("GESTIMATOR_FILE_REFERENCE_VER_1",),
                ):
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
            if p.get("discard") is True:
                self.clear_recovery()
            self.clear_mcp_indexes()
            if hasattr(self, "project_editor"):
                self.project_editor.close()
            if self.db:
                self.db.close_database()
            self.db = new
            self.workspace_dirty = False
            from .project import ProjectEditor

            self.project_editor = ProjectEditor(self)
            self.source_path = str(source)
            self.source_fingerprint = before
            self.recovered_path = None
            self.loaded = False
            self.model = ScheduleItemModel("", "Select a schedule item")
            self.history.clear()
            self.future.clear()
            self.clipboard.clear()
            self.revision += 1
            self.saved_signature = copy.deepcopy(self.signature())
            return dict(opened=str(source))
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
            from .importing import import_analysis

            from .importing import analysis_rows
            draft = import_analysis(self.model, p)
            return dict(rows=len(draft.ana_items), resources=len(draft.resources),
                        rate=str(draft.get_ana_rate()), items=analysis_rows(draft))
        if method in ("schedule.list", "resources.search"):
            if not self.db:
                raise ValueError("Open a project first")
            limit = p.get("limit", 100)
            offset = p.get("offset", 0)
            if (
                type(limit) is not int
                or not 1 <= limit <= 200
                or type(offset) is not int
                or offset < 0
            ):
                raise ValueError("Invalid page")
            selected_db = (
                self.project_editor.libraries[p["source"]][1]
                if p.get("source") in self.project_editor.libraries
                else self.db
            )
            table = (
                selected_db.ScheduleTable
                if method == "schedule.list"
                else selected_db.ResourceTable
            )
            query = text(p.get("query", ""))
            if query.strip():
                from .search import desktop_codes
                codes, _ = desktop_codes(self, selected_db, "schedule" if method == "schedule.list" else "resources", query)
                positions = {code: index for index, code in enumerate(codes[offset:offset + limit])}
                records = sorted(table.select().where(table.code.in_(list(positions))), key=lambda row: positions[row.code])
            else:
                records = table.select().order_by(table.id).offset(offset).limit(limit)
            return [
                dict(
                    code=r.code,
                    description=r.description,
                    unit=r.unit,
                    rate=str(r.rate),
                )
                for r in records
            ]
        if method == "analysis.load":
            self.guard_draft(p)
            if not self.db:
                raise ValueError("Open a project first")
            model = self.db.get_item(text(p["code"]), modify_res_code=False)
            if model is None:
                raise ValueError("Unknown schedule code")
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
            if not self.source_path or not self.source_fingerprint:
                raise ValueError("Choose a location with Save project copy first")
            destination = Path(self.source_path)
            if not (self.workspace_dirty or (self.loaded and self.dirty) or self.records_dirty):
                return dict(saved=str(destination))
            progress("Saving project and preserving a backup")
            backup = save_existing(
                destination, self.source_fingerprint, self.write_project_snapshot
            )
            self.source_fingerprint = fingerprint(destination)
            self.finish_project_save()
            return dict(saved=str(destination), backup=str(backup))
        if method == "project.save_copy":
            if not self.db:
                raise ValueError("Open a project first")
            destination = Path(text(p["path"])).resolve()
            # Reserve the output before writing it.
            with destination.open("xb"):
                pass
            try:
                progress("Saving analysis and updating dependent rates")
                self.write_project_snapshot(destination)
            except Exception:
                destination.unlink()
                raise
            self.finish_project_save()
            if not self.source_path:
                self.source_path = str(destination)
                self.source_fingerprint = fingerprint(destination)
            return dict(saved=str(destination))
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
            self.project_editor.mutate(
                lambda: self.write_analysis(self.db), reload=False
            )
            self.sync_analysis()
            self.saved_signature = copy.deepcopy(self.signature())
            self.revision += 1
            return self.state()
        if method in ("undo", "redo"):
            source, dest = (
                (self.history, self.future)
                if method == "undo"
                else (self.future, self.history)
            )
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
        if method == "analysis.resources_add":
            if not self.db:
                raise ValueError("Open a project first")
            source_id = p.get("source")
            if source_id and source_id not in self.project_editor.libraries:
                raise ValueError("Resource database is no longer attached")
            source = self.project_editor.libraries[source_id][1] if source_id else self.db
            _, rows = self.project_editor.selection("resources", p.get("ids"), source, include_descendants=False)
            index, child = self.locate(p.get("id"))
            group = self.model.ana_items[index]
            if group["itemtype"] != 0:
                raise ValueError("Select a resource group")
            prefix = source.get_project_settings().get("project_resource_code", "") if source is not self.db else ""
            quantity = decimal(p.get("qty", "0"))
            entries, identities = [], []
            for row in sorted(rows, key=lambda row: (row.category.order, row.order, row.id)):
                resource = source.get_resource(row.code, modify_code=bool(prefix))
                if resource is None:
                    raise ValueError("Unknown resource")
                resource = self.model.resources.get(resource.code) or self.db.get_resource(resource.code) or resource
                self.model.resources[resource.code] = resource
                entries.append([resource.code, quantity, ""])
                identities.append(uuid4().hex)
            position = child + 1 if child is not None else 0
            group["resource_list"][position:position] = entries
            group["_resource_ids"][position:position] = identities
            return
        if method == "analysis.batch":
            operations = p.get("operations")
            if not isinstance(operations, list) or not 1 <= len(operations) <= 500:
                raise ValueError("Provide between 1 and 500 analysis edits")
            cursor = p.get("id")
            for operation in operations:
                if not isinstance(operation, dict) or operation.get("method") not in ("edit", "add"):
                    raise ValueError("Batch supports only row edits and calculation-row insertion")
                params = dict(operation)
                action = params.pop("method")
                if action == "add":
                    params["id"] = cursor
                    position = self.locate(cursor)[0] + 1 if cursor else 0
                    self.edit(action, params)
                    cursor = self.model.ana_items[position]["_id"]
                else:
                    self.edit(action, params)
            return
        if method == "analysis.insert_template":
            position = self.locate(p["id"])[0] + 1 if p.get("id") else 0
            if "rows" in p:
                from .program_settings import legacy_rows
                rows = legacy_rows(p["rows"])
            else:
                rows = copy.deepcopy(misc.ana_default_add_items)
            for row in rows:
                if "value" in row:
                    row["value"] = Decimal(str(row["value"]))
            self.model.ana_items[position:position] = rows
            self.identify()
            return
        if method == "analysis.import_xlsx":
            if not self.loaded:
                raise ValueError("Load an analysis first")
            from .importing import import_analysis

            draft = import_analysis(self.model, p)
            self.model.ana_items = draft.ana_items
            self.model.resources = draft.resources
            self.model.ana_remarks = draft.ana_remarks or self.model.ana_remarks
            self.identify()
            return
        if method == "analysis.edit":
            if p["field"] != "ana_remarks":
                raise ValueError("Unknown analysis field")
            self.model.ana_remarks = text(p["value"])
            return
        if method == "add":
            kind = p["kind"]
            description = text(p.get("description", kind))
            pos = self.locate(p["id"])[0] + 1 if p.get("id") else 0
            if kind == "Group":
                self.model.add_ana_group(description, code=text(p.get("code", "")), pos=pos)
            elif kind == "Subtotal":
                self.model.add_ana_sum(description, pos=pos)
            elif kind in ("Weight", "Multiply", "Round"):
                value = decimal(p["value"])
                if kind == "Round" and (
                    abs(value) > 12
                    or (value != int(value) and int((value - int(value)) * 10) == 0)
                ):
                    raise ValueError(
                        "Use rounding places from -12 to 12 with a non-zero tenth for interval rounding"
                    )
                {
                    "Weight": self.model.add_ana_weight,
                    "Multiply": self.model.add_ana_times,
                    "Round": self.model.add_ana_round,
                }[kind](description, value, pos=pos)
            else:
                raise ValueError("Unknown row kind")
            self.identify()
            return
        if method in ("resource.add", "resource.duplicate"):
            i, child = self.locate(p["id"])
            group = self.model.ana_items[i]
            if group["itemtype"] != 0:
                raise ValueError("Select a resource group")
            if method == "resource.duplicate":
                if child is None:
                    raise ValueError("Select a resource entry to duplicate")
                resource = copy.deepcopy(
                    self.model.resources[group["resource_list"][child][0]]
                )
                resource.code = text(p["code"])
                if (
                    not resource.code
                    or resource.code in self.model.resources
                    or (self.db and self.db.get_resource(resource.code))
                ):
                    raise ValueError("Choose an unused resource code")
            elif p.get("library"):
                if not self.db:
                    raise ValueError("Open a project first")
                source = (
                    self.project_editor.libraries[p["source"]][1]
                    if p.get("source") in self.project_editor.libraries
                    else self.db
                )
                prefix = (
                    source.get_project_settings().get("project_resource_code", "")
                    if source is not self.db
                    else ""
                )
                resource = source.get_resource(
                    text(p["code"]), modify_code=bool(prefix)
                )
                if resource:
                    resource = (
                        self.model.resources.get(resource.code)
                        or self.db.get_resource(resource.code)
                        or resource
                    )
                if resource is None:
                    raise ValueError("Unknown resource")
            else:
                code = text(p.get("code", ""))
                if not code:
                    code = self.db.get_new_resource_code(exclude=self.model.resources) if self.db else "MR.1"
                    while code in self.model.resources:
                        code = "MR." + str(int(code.split(".")[-1]) + 1)
                if code in self.model.resources:
                    raise ValueError("Use a new resource code")
                resource = ResourceItemModel(
                    code,
                    text(p["description"]),
                    text(p["unit"]),
                    Currency(decimal(p["rate"])),
                    Currency(decimal(p.get("vat", "0")), 4),
                    Currency(decimal(p.get("discount", "0"))),
                    text(p.get("reference", "")),
                    text(p.get("category", "")),
                )
            self.model.resources[resource.code] = resource
            pos = child + 1 if child is not None else 0
            self.model.add_ana_res(
                [resource.code, decimal(p.get("qty", "0")), text(p.get("remarks", ""))],
                i,
                pos,
            )
            group["_resource_ids"].insert(pos, uuid4().hex)
            return
        if method in ("copy", "delete", "duplicate", "paste"):
            ids = p.get("ids", [])
            if not isinstance(ids, list) or len(ids) > 1000:
                raise ValueError("Invalid selection")
            locations = sorted(
                set(self.locate(x) for x in ids),
                key=lambda x: (x[0], -1 if x[1] is None else x[1]),
            )
            if method in ("copy", "duplicate"):
                self.clipboard = []
                for i, j in locations:
                    entry = copy.deepcopy(
                        self.model.get_item([i] if j is None else [i, j], deep=False)
                    )
                    self.clipboard.append(entry)
            if method == "delete":
                locations = [
                    x
                    for x in locations
                    if x[1] is None or (x[0], None) not in locations
                ]
                for i, j in reversed(locations):
                    self.model.delete_item([i] if j is None else [i, j])
                    if j is not None:
                        self.model.ana_items[i]["_resource_ids"].pop(j)
            if method in ("paste", "duplicate"):
                i, j = self.locate(p["id"]) if p.get("id") else (-1, None)
                for entry in self.clipboard:
                    if entry[0] == "ana_item":
                        row = copy.deepcopy(entry[1])
                        row["_id"] = uuid4().hex
                        if row["itemtype"] == 0:
                            row["_resource_ids"] = []
                        i += 1
                        j = None
                        self.model.ana_items.insert(i, row)
                    else:
                        if i < 0 or self.model.ana_items[i]["itemtype"] != 0:
                            raise ValueError("Select a destination resource group")
                        j = 0 if j is None else j + 1
                        self.model.resources.setdefault(
                            entry[2].code,
                            (self.db.get_resource(entry[2].code) if self.db else None) or copy.deepcopy(entry[2]),
                        )
                        self.model.add_ana_res(copy.deepcopy(entry[1]), i, j)
                        self.model.ana_items[i]["_resource_ids"].insert(j, uuid4().hex)
            return
        i, j = self.locate(p["id"])
        row = self.model.ana_items[i]
        if method == "move":
            delta = p["delta"]
            if type(delta) is not int or delta not in (-1, 1):
                raise ValueError("Invalid direction")
            values = self.model.ana_items if j is None else row["resource_list"]
            index = i if j is None else j
            target = index + delta
            if 0 <= target < len(values):
                values[index], values[target] = values[target], values[index]
                if j is not None:
                    ids = row["_resource_ids"]
                    ids[index], ids[target] = ids[target], ids[index]
            return
        if method != "edit":
            raise ValueError("Unknown operation")
        field = p["field"]
        value = p["value"]
        if j is not None:
            resource = self.model.resources[row["resource_list"][j][0]]
            if field == "value":
                row["resource_list"][j][1] = decimal(value)
            elif field == "code":
                code = text(value)
                replacement = self.model.resources.get(code) or (
                    self.db.get_resource(code) if self.db else None
                )
                if replacement is None:
                    raise ValueError("Resource code not found")
                self.model.resources.setdefault(code, replacement)
                row["resource_list"][j][0] = code
            elif field == "remarks":
                row["resource_list"][j][2] = text(value)
            elif field in ("description", "unit", "reference", "category"):
                setattr(resource, field, text(value))
            elif field in ("rate", "vat", "discount"):
                setattr(resource, field, Currency(decimal(value), 4 if field == "vat" else 2))
            else:
                raise ValueError("Field is not editable")
        elif field == "description" or (field == "code" and row["itemtype"] == 0):
            row[field] = text(value)
        elif field == "value" and row["itemtype"] in (2, 3, 4):
            value = decimal(value)
            if row["itemtype"] == 4 and (
                abs(value) > 12
                or (value != int(value) and int((value - int(value)) * 10) == 0)
            ):
                raise ValueError("Unsupported rounding places")
            row[field] = value
        else:
            raise ValueError("Field is not editable")

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
            used = {
                entry[0]
                for group in model.ana_items
                if group["itemtype"] == 0
                for entry in group["resource_list"]
            }
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
                            (
                                "description",
                                "unit",
                                "rate",
                                "vat",
                                "discount",
                                "reference",
                            ),
                            1,
                        ):
                            value = getattr(resource, field)
                            if value != getattr(existing, field):
                                if not db.update_resource(
                                    code, newvalue=value, column=column
                                ):
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
            self.project_editor.mutate(
                lambda: self.write_analysis(self.db), reload=False
            )
            self.sync_analysis()
        self.workspace_dirty = False
        self.saved_signature = copy.deepcopy(self.signature())
        if self.recovered_path:
            self.recovered_path.unlink(missing_ok=True)
            self.recovered_path = None

    def recovery_projects(self):
        if not self.recovery_dir:
            return []
        projects = []
        live = {self.recovery_id} | {peer.recovery_id for peer in self.peers()}
        claimed = {self.recovered_path} | {peer.recovered_path for peer in self.peers()}
        for path in self.recovery_dir.glob("*.eproj"):
            if path.stem in live or path in claimed:
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
        with destination.open("xb"):
            pass
        scratch = ScheduleDatabase(Stack())
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
            sheet.save(destination)
        except Exception:
            destination.unlink()
            raise
        finally:
            scratch.close_database()
        return dict(saved=str(destination))

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
        self.temp.cleanup()
