"""Code-addressed MCP intents over the application's existing editors."""

import copy
from decimal import Decimal
from pathlib import Path
import re

from estimator import misc
from estimator.data.measurement import MeasurementItemCustom
from . import metadata
from .mcp_operations import ToolError, OPERATIONS, validate, is_preview
from .numbers import decimal
from .mcp_writes import Writes


def item_rows(db, kind):
    table = db.ResourceTable if kind == "resource" else db.ScheduleTable
    category = db.ResourceCategoryTable if kind == "resource" else db.ScheduleCategoryTable
    rows = list(table.select(table, category).join(category).order_by(category.order, table.order, *([] if kind == "resource" else [table.suborder]), table.id))
    if kind == "schedule":
        by_id = {r.id: r for r in rows}
        for row in rows:
            if row.parent_id in by_id:
                row.__rel__["parent"] = by_id[row.parent_id]
    return rows


def page(items, args):
    offset, limit = args.get("offset", 0), args.get("limit", 100)
    return dict(items=items[offset:offset + limit], total=len(items), offset=offset, next_offset=offset + limit if offset + limit < len(items) else None)


def natural(code):
    return tuple((0, int(part)) if part.isdigit() else (1, part.casefold()) for part in re.split(r"(\d+)", code))


def full_row(row, kind, enrichment=None, compact=False):
    data = dict(code=row.code, unit=row.unit or "", rate=str(row.rate or 0), category=row.category.description or "")
    if compact:
        data["short"] = metadata.short(row, enrichment)
    else:
        data["description"] = row.description or ""
    if kind == "schedule":
        data.update(parent_code=row.parent.code if row.parent_id else None, qty=str(row.qty or 0), remarks=row.remarks or "", colour=row.colour)
    else:
        data.update(vat=str(row.vat or 0), discount=str(row.discount or 0), reference=row.reference or "")
    return data


class Workspace(Writes):
    def __init__(self, service):
        self.service = service

    def require_project(self):
        if self.service.db is None:
            raise ToolError("no_project", "Open or create a project first")

    @property
    def editor(self):
        service = self.service
        if service.db:
            editor = service.project_editor
            catalog = getattr(service, "_mcp_catalog", None)
            if catalog:
                editor.libraries.update(catalog.libraries)
                editor.library_paths.update(catalog.library_paths)
                catalog.libraries.clear()
                catalog.library_paths.clear()
            return editor
        if not hasattr(service, "_mcp_catalog"):
            from .project import ProjectEditor
            service._mcp_catalog = ProjectEditor(service)
        return service._mcp_catalog

    def source(self, value="project"):
        if value == "project":
            self.require_project()
            return None, self.service.db
        editor = self.editor
        if value not in editor.libraries:
            attached = editor.attach_library(value)
            value = next(item["id"] for item in attached if item.get("attached"))
        return value, editor.libraries[value][1]

    def row(self, kind, code, db=None):
        db = db or self.service.db
        table = db.ResourceTable if kind == "resource" else db.ScheduleTable
        row = table.get_or_none(table.code == code)
        if row is None:
            raise ToolError("not_found", "Item code was not found", "code", hint=str(code))
        return row

    def ids(self, kind, codes, category_kind=None):
        if not codes:
            raise ToolError("invalid_arguments", "Select at least one item", "codes")
        if kind == "category":
            table = self.service.db.ResourceCategoryTable if category_kind == "resource" else self.service.db.ScheduleCategoryTable
            result = []
            for code in codes:
                row = table.get_or_none(table.description == code)
                if row is None:
                    raise ToolError("not_found", "Category was not found", "codes", hint=code)
                result.append("cat:" + str(row.id))
            return result
        return [str(self.row(kind, code).id) for code in codes]

    def app(self, method, args=None):
        return self.service.call(method, dict(args or {}, revision=self.service.revision))

    def call(self, name, args, warnings):
        method = getattr(self, name)
        return method(args, warnings)

    def get_state(self, args, warnings):
        from .program_settings import library_catalog, defaults
        service = self.service
        sources = []
        for identity, (name, db) in self.editor.libraries.items():
            counts = dict(schedule=db.ScheduleTable.select().count(), resource=db.ResourceTable.select().count())
            enrichment = metadata.presentation(db)
            sources.append(dict(id=identity, name=name, counts=counts,
                summary=enrichment["summary"] if enrichment and enrichment["summary"] else f"{counts['schedule']} schedule items; {counts['resource']} resources"))
        state = dict(project_open=service.db is not None, path=service.source_path, analysis_dirty=service.dirty, records_dirty=service.records_dirty, project_dirty=service.workspace_dirty, program_settings=defaults(), sources=sources, available_sources=library_catalog())
        if service.db:
            db = service.db
            state.update(settings={k: v for k, v in db.get_project_settings().items() if k != "project_measurement"}, counts=dict(schedule=db.ScheduleTable.select().count(), resource=db.ResourceTable.select().count(), measurements=len(db.get_measurement().items)), enrichment=bool(metadata.read(db)))
        return state

    def describe_source(self, args, warnings):
        _, db = self.source(args.get("source", "project"))
        enrichment = metadata.read(db)
        section = args.get("section", "overview")
        if section == "schema":
            from .mcp_query import SCHEMA
            return dict(views=SCHEMA, draft_policy="Stored working-project data; excludes unsaved desktop analysis and measurement records drafts.", numeric_policy="Decimal values are exact text; CAST(column AS REAL) for numeric SQL comparisons and aggregations. get_summary uses original decimal calculations.")
        if section == "dictionary":
            from .dictionary import entries
            return dict(entries=entries("\n".join(row.description or "" for kind in ("schedule", "resource") for row in item_rows(db, kind)), enrichment, self.user_dictionary()))
        groups = {kind: metadata.categories(db, kind, enrichment) for kind in ("schedule", "resource")}
        if section == "categories":
            return groups
        if section.startswith("category:"):
            name = section.partition(":")[2]
            return {kind: [row for row in rows if row["name"] == name] for kind, rows in groups.items()}
        if section != "overview":
            raise ToolError("invalid_arguments", "Unknown source section", "section", ["overview", "categories", "category:<name>", "dictionary", "schema"])
        result = dict(settings={k: v for k, v in db.get_project_settings().items() if k != "project_measurement"}, categories={kind: [dict(name=c["name"], count=c["count"]) for c in rows] for kind, rows in groups.items()})
        if enrichment:
            result.update(enrichment=enrichment.get("database", {}), provenance=enrichment.get("provenance", {}), ai_generated=True)
        return result

    def user_dictionary(self):
        from .program_settings import library_directory
        return library_directory().parent / "dictionary.user.json"

    def search_items(self, args, warnings):
        from .search import search
        _, db = self.source(args.get("source", "project"))
        return search(self.service, db, args["kind"], args["query"], args.get("limit", 20), args.get("category"), self.user_dictionary())

    def browse(self, args, warnings):
        _, db = self.source(args.get("source", "project"))
        kind = args["kind"]
        rows = item_rows(db, kind)
        groups = db.ResourceCategoryTable if kind == "resource" else db.ScheduleCategoryTable
        under = args.get("under")
        if under is None:
            enrichment = metadata.read(db)
            return page([dict(kind="category", **row) for row in metadata.categories(db, kind, enrichment)], args)
        category = groups.get_or_none(groups.description == under)
        children = {}
        for row in rows:
            children.setdefault(row.parent_id if kind == "schedule" else None, []).append(row)
        if category:
            roots = [r for r in rows if r.category_id == category.id and (kind == "resource" or r.parent_id is None)]
        elif kind == "schedule":
            parent = self.row(kind, under, db)
            roots = children.get(parent.id, [])
        else:
            raise ToolError("not_found", "Category was not found", "under")
        enrichment = metadata.read(db)
        result = []
        def collect(values, depth):
            for row in values:
                result.append(dict(full_row(row, kind, enrichment, args.get("fields", "compact") == "compact"), depth=depth))
                if kind == "schedule" and depth < args.get("depth", 1):
                    collect(children.get(row.id, []), depth + 1)
        collect(roots, 1)
        return page(result, args)

    def get_items(self, args, warnings):
        from .clipboard import schedule_data
        _, db = self.source(args.get("source", "project"))
        kind, include = args["kind"], args.get("include", [])
        result = []
        for code in args["codes"]:
            row = self.row(kind, code, db)
            data = full_row(row, kind)
            if kind == "schedule":
                if "analysis" in include or "resources" in include:
                    model = db.get_item(code, modify_res_code=False)
                    definition = schedule_data(model)
                    for field in ("analysis", "resources"):
                        if field in include:
                            data[field] = definition[field]
                if "parent" in include:
                    data["parent"] = full_row(row.parent, kind) if row.parent_id else None
                if "children" in include:
                    data["children"] = [full_row(child, kind) for child in row.children.order_by(db.ScheduleTable.suborder)]
            if "usage" in include or "dependents" in include:
                # Use an isolated editor view so source queries never switch the
                # desktop selection or active analysis draft.
                view = copy.copy(self.editor)
                view.owner = copy.copy(self.service)
                view.owner.db = db
                if "usage" in include:
                    data["usage"] = [r for r in view.resource_usage(dict(query=code))["rows"] if r["code"] == code] if kind == "resource" else []
                if "dependents" in include:
                    data["dependents"] = view.resource_dependents(dict(code=code))["rows"]
            result.append(data)
        return dict(items=result)

    def get_measurements(self, args, warnings):
        if args.get("section") == "templates":
            from .measurement_templates import catalog
            from .measurement_templates import column_title
            result = []
            for entry in catalog():
                item = MeasurementItemCustom(plugin=entry["code"])
                columns = [dict(field="c" + str(i), title=column_title(item, i), editable=kind != misc.MEAS_CUST, numeric=kind in (misc.MEAS_L, misc.MEAS_NO)) for i, kind in enumerate(item.columntypes)]
                result.append(dict(entry, columns=columns, links=[dict(code="", remark="") for _ in item.itemnos], user_data=[str(v) for v in item.user_data]))
            return dict(templates=result)
        self.require_project()
        editor = self.editor
        if editor.measurement_draft:
            editor = copy.copy(editor)
            editor.record_ids = copy.deepcopy(editor.record_ids)
            editor.record_ids[editor.measurement_draft.identity] = editor.measurement_draft.saved_ids[:]
            editor.measurement_draft = None
        if "id" in args:
            data = editor.measurement_state(dict(id=args["id"], record_offset=args.get("record_offset", 0), record_limit=args.get("limit", 100)), detail_only=True)
            if data["detail"] is None:
                raise ToolError("not_found", "Measurement item was not found or is a heading", "id")
            detail = data["detail"]
            detail["next_offset"] = detail["offset"] + len(detail["rows"]) if detail["offset"] + len(detail["rows"]) < detail["total_records"] else None
            return detail
        data = editor.measurement_state({})
        rows = [dict(row, description=row["description"][:60]) for row in data["rows"]]
        return dict(page(rows, args), caption=data["caption"])

    def get_summary(self, args, warnings):
        self.require_project()
        db = self.service.db
        total, groups, checks = Decimal(0), {}, dict(zero_quantities=[], unlinked_items=[], orphan_children=[], unlinked_measurements=[], rate_differences=[])
        linked = {key for item in db.get_measurement().items for key in item.itemnos if key is not None}
        ids = {row.id for row in db.ScheduleTable.select()}
        for row in item_rows(db, "schedule"):
            if row.parent_id and row.parent_id not in ids:
                checks["orphan_children"].append(row.code)
            if not row.unit or row.category.description == misc.SUB_ANA_TITLE:
                continue
            from estimator.data.schedule import Currency
            amount = Currency(Decimal(row.rate or 0) * Decimal(row.qty or 0))
            total += amount
            category = row.category.description or ""
            groups[category] = groups.get(category, Decimal(0)) + amount
            if not row.qty:
                checks["zero_quantities"].append(row.code)
            if row.id not in linked:
                checks["unlinked_items"].append(row.code)
            model = db.get_item(row.code, modify_res_code=False) if not row.parent_id or row.parent_id in ids else None
            if model and model.ana_items:
                model.evaluate_results()
                calculated = model.get_ana_rate()
                if calculated is not None and Currency(calculated) != Currency(row.rate or 0):
                    checks["rate_differences"].append(dict(code=row.code, stored=str(row.rate or 0), recalculated=str(Currency(calculated))))
        for identity, item in zip(self.editor.ids, db.get_measurement().items):
            if isinstance(item, MeasurementItemCustom) and (not any(key in ids for key in item.itemnos) or any(key is not None and key not in ids for key in item.itemnos)):
                checks["unlinked_measurements"].append(identity)
        if args.get("fields", "compact") == "compact":
            checks = {key: dict(count=len(values), items=values[:20]) for key, values in checks.items()}
        return dict(grand_total=str(total), categories=[dict(category=k, total=str(v)) for k, v in groups.items()], checks=checks, analysis_dirty=self.service.dirty)

    def query(self, args, warnings):
        from .mcp_query import query
        _, db = self.source(args.get("source", "project"))
        return query(self.service, db, args["sql"], args.get("params", []), args.get("limit", 500))
