"""Code-addressed MCP intents over the application's existing editors."""

import copy
import re
from decimal import Decimal
from pathlib import Path

from estimator import misc
from estimator.data.measurement import MeasurementItemCustom

from . import mcp_skills, metadata
from .mcp_operations import OPERATIONS, ToolError, is_preview, validate
from .mcp_writes import Writes
from .numbers import decimal

READ_NOTES = (
    "This source has database notes. Read describe_source (overview) and describe_source "
    "section=category:<name> for each category you take items from before choosing items: "
    "they explain what the items include and how to pick the right one."
)
START_HERE = (
    "1. Read the relevant skill and references with describe_source. "
    "2. Check available_sources, read source and category notes, and search for reusable items or resources before pricing custom work. "
    "3. Plan measurement headings by work package, phase or location. Use category=heading ID or $name when creating sheets. "
    "Record dimensions, deductions and source by storey, room, grid, element or run wherever the evidence allows. "
    "4. Present draft measurements and item matches for review. Link sheets, recalculate quantities, verify and save the GEstimator project. "
    "Export a workbook when requested."
)


def item_rows(db, kind):
    table = db.ResourceTable if kind == "resource" else db.ScheduleTable
    category = db.ResourceCategoryTable if kind == "resource" else db.ScheduleCategoryTable
    rows = list(
        table.select(table, category)
        .join(category)
        .order_by(category.order, table.order, *([] if kind == "resource" else [table.suborder]), table.id)
    )
    if kind == "schedule":
        by_id = {r.id: r for r in rows}
        for row in rows:
            if row.parent_id in by_id:
                row.__rel__["parent"] = by_id[row.parent_id]
    return rows


def heading_summaries(db, items):
    """Heading text for child results: a child's own description holds only
    the variant ("Group A", "18 watt"), so return its parent's text and any
    title heading above it by code (30.7 over 30.7.3) whose text the parent
    does not already repeat, keyed by code. Long specifications are cut at
    600 characters (where similar headings usually differ); get_items returns
    the full text."""
    from .search import heading_codes

    chains = {
        item["parent_code"]: [item["parent_code"], *heading_codes(item["parent_code"])]
        for item in items
        if item.get("parent_code")
    }
    codes = list(dict.fromkeys(code for chain in chains.values() for code in chain))
    if not codes:
        return {}
    table = db.ScheduleTable
    texts = {}
    for start in range(0, len(codes), 500):
        for row in table.select(table.code, table.description, table.rate).where(
            table.code.in_(codes[start : start + 500])
        ):
            if not row.rate:
                texts[row.code] = " ".join((row.description or "").split())
    result = {}
    for parent, chain in chains.items():
        for code in chain:
            text = texts.get(code)
            if text and (code == parent or text not in texts.get(parent, "")):
                result[code] = text if len(text) <= 600 else text[:599].rstrip() + "…"
    return result


def page(items, args):
    offset, limit = args.get("offset", 0), args.get("limit", 100)
    return dict(
        items=items[offset : offset + limit],
        total=len(items),
        offset=offset,
        next_offset=offset + limit if offset + limit < len(items) else None,
    )


def natural(code):
    return tuple((0, int(part)) if part.isdigit() else (1, part.casefold()) for part in re.split(r"(\d+)", code))


def full_row(row, kind, enrichment=None, compact=False):
    data = dict(code=row.code, unit=row.unit or "", rate=str(row.rate or 0), category=row.category.description or "")
    if compact:
        data["short"] = metadata.short(row, enrichment)
    else:
        data["description"] = row.description or ""
    if kind == "schedule":
        data.update(
            parent_code=row.parent.code if row.parent_id else None,
            qty=str(row.qty or 0),
            remarks=row.remarks or "",
            colour=row.colour,
        )
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
            table = (
                self.service.db.ResourceCategoryTable
                if category_kind == "resource"
                else self.service.db.ScheduleCategoryTable
            )
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

    def notes_read(self):
        """Note sections read since the server started, as (source name, section)."""
        mcp = self.service.mcp
        if not hasattr(mcp, "notes_read"):
            mcp.notes_read = set()
        return mcp.notes_read

    def source_name(self, identity):
        return self.editor.libraries[identity][0] if identity in self.editor.libraries else None

    def skill(self, section):
        """Read the current skill catalog or a qualified document without a project."""
        catalog = self.service.mcp.skill_libraries.active
        skills = catalog.skills()
        if section == "skills":
            return dict(
                library=catalog.library_id,
                skills=skills,
                hint="Read the skill whose description fits the work using its URI as section, then follow its references.",
            )
        uri = section if section.startswith(mcp_skills.SCHEME) else mcp_skills.SCHEME + section.partition(":")[2]
        try:
            text = catalog.read_resource(uri)["contents"][0]["text"]
        except mcp_skills.ResourceNotFound:
            raise ToolError(
                "not_found",
                "Unknown skill or skill file",
                "section",
                [skill["uri"] for skill in skills],
                hint="Use section=skills to list skills and their reference paths.",
            ) from None
        result = dict(uri=uri, text=text)
        entry = next((skill for skill in skills if skill["uri"] == uri), None)
        if entry:
            result["references"] = [
                dict(section=ref["uri"], title=ref["title"], description=ref["description"])
                for ref in entry["references"]
            ]
        return result

    def get_state(self, args, warnings):
        from .program_settings import defaults, library_catalog

        service = self.service
        sources = []
        for identity, (name, db) in self.editor.libraries.items():
            counts = dict(schedule=db.ScheduleTable.select().count(), resource=db.ResourceTable.select().count())
            enrichment = metadata.presentation(db)
            notes, category_notes = metadata.notes(db)
            sources.append(
                dict(
                    id=identity,
                    name=name,
                    counts=counts,
                    summary=enrichment["summary"]
                    if enrichment and enrichment["summary"]
                    else f"{counts['schedule']} schedule items; {counts['resource']} resources",
                    **(
                        {"metadata": notes[:600] + ("…" if len(notes) > 600 else ""), "read_first": READ_NOTES}
                        if notes or category_notes
                        else {}
                    ),
                )
            )
        catalog = service.mcp.skill_libraries.active
        skills = [
            dict(
                skill=skill["skill"],
                library=skill["library"],
                description=skill["description"],
                read=f"describe_source section={skill['uri']}",
            )
            for skill in catalog.skills()
        ]
        program_settings = defaults()
        program_settings["mcp_enabled"] = service.mcp.enabled
        program_settings["estimation_skill_library"] = catalog.library_id
        state = dict(
            start_here=START_HERE,
            skills=skills,
            project_open=service.db is not None,
            path=service.source_path,
            analysis_dirty=service.dirty,
            records_dirty=service.records_dirty,
            project_dirty=service.workspace_dirty,
            program_settings=program_settings,
            sources=sources,
            available_sources=library_catalog(),
        )
        if service.db:
            db = service.db
            state.update(
                settings={
                    k: v
                    for k, v in db.get_project_settings().items()
                    if k not in ("project_measurement", "project_metadata")
                },
                metadata=db.get_project_settings().get("project_metadata") or "",
                counts=dict(
                    schedule=db.ScheduleTable.select().count(),
                    resource=db.ResourceTable.select().count(),
                    measurements=len(db.get_measurement().items),
                ),
                enrichment=bool(metadata.read(db)),
            )
        return state

    def describe_source(self, args, warnings):
        section = args.get("section", "overview")
        if section == "skills" or section.startswith(("skill:", "gestimator://skills/")):
            return self.skill(section)
        identity, db = self.source(args.get("source", "project"))
        enrichment = metadata.read(db)
        if identity is not None:
            self.notes_read().add((self.source_name(identity), section))
        if section == "schema":
            from .mcp_query import SCHEMA

            return dict(
                views=SCHEMA,
                draft_policy="Stored working-project data; excludes unsaved desktop analysis and measurement records drafts.",
                numeric_policy="Decimal values are exact text; CAST(column AS REAL) for numeric SQL comparisons and aggregations. get_summary uses original decimal calculations.",
            )
        if section == "dictionary":
            from .dictionary import entries

            return dict(
                entries=entries(
                    "\n".join(
                        row.description or "" for kind in ("schedule", "resource") for row in item_rows(db, kind)
                    ),
                    enrichment,
                    self.user_dictionary(),
                )
            )
        groups = {kind: metadata.categories(db, kind, enrichment) for kind in ("schedule", "resource")}
        general, category_notes = metadata.notes(db)
        if section == "categories":
            for rows in groups.values():
                for row in rows:
                    row["notes"] = row["name"] in category_notes
            return groups
        if section.startswith("category:"):
            name = section.partition(":")[2]
            result = {kind: [row for row in rows if row["name"] == name] for kind, rows in groups.items()}
            if name in category_notes:
                result["notes"] = category_notes[name]
            return result
        if section != "overview":
            raise ToolError(
                "invalid_arguments",
                "Unknown source section",
                "section",
                [
                    "overview",
                    "categories",
                    "category:<name>",
                    "dictionary",
                    "schema",
                    "skills",
                    "skill:<library>/<skill>",
                ],
            )
        settings = db.get_project_settings()
        # Author-maintained notes (Markdown): scope, rate basis, revision, conventions.
        # Notes first: clients that truncate a long response keep them.
        result = dict(
            metadata=general,
            settings={k: v for k, v in settings.items() if k not in ("project_measurement", "project_metadata")},
            categories={
                kind: [
                    dict(name=c["name"], count=c["count"], **({"notes": True} if c["name"] in category_notes else {}))
                    for c in rows
                ]
                for kind, rows in groups.items()
            },
        )
        if category_notes:
            result["category_notes"] = (
                "Each category marked notes=true has its own notes: read describe_source section=category:<name> before choosing items from it."
            )
        if enrichment:
            result.update(
                enrichment=enrichment.get("database", {}),
                provenance=enrichment.get("provenance", {}),
                ai_generated=True,
            )
        return result

    def user_dictionary(self):
        from .program_settings import library_directory

        return library_directory().parent / "dictionary.user.json"

    def search_items(self, args, warnings):
        from .search import search

        _, db = self.source(args.get("source", "project"))
        result = search(
            self.service,
            db,
            args["kind"],
            args["query"],
            args.get("limit", 20),
            args.get("category"),
            self.user_dictionary(),
        )
        if args["kind"] == "schedule":
            headings = heading_summaries(db, result["items"])
            if headings:
                result = dict(result, headings=headings)
        general, category_notes = metadata.notes(db)
        found = list(dict.fromkeys(row["category"] for row in result["items"] if row["category"] in category_notes))
        if general or found:
            result = dict(result, notes=dict(read_first=READ_NOTES, categories=found))
        return result

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
                result.append(
                    dict(full_row(row, kind, enrichment, args.get("fields", "compact") == "compact"), depth=depth)
                )
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
                    data["children"] = [
                        full_row(child, kind) for child in row.children.order_by(db.ScheduleTable.suborder)
                    ]
            if "usage" in include or "dependents" in include:
                # Use an isolated editor view so source queries never switch the
                # desktop selection or active analysis draft.
                view = copy.copy(self.editor)
                view.owner = copy.copy(self.service)
                view.owner.db = db
                if "usage" in include:
                    data["usage"] = (
                        [r for r in view.resource_usage(dict(query=code))["rows"] if r["code"] == code]
                        if kind == "resource"
                        else []
                    )
                if "dependents" in include:
                    data["dependents"] = view.resource_dependents(dict(code=code))["rows"]
            result.append(data)
        return dict(items=result)

    def get_measurements(self, args, warnings):
        if args.get("section") == "templates":
            from .measurement_templates import catalog, column_title

            result = []
            for entry in catalog():
                item = MeasurementItemCustom(plugin=entry["code"])
                columns = [
                    dict(
                        field="c" + str(i),
                        title=column_title(item, i),
                        editable=kind != misc.MEAS_CUST,
                        numeric=kind in (misc.MEAS_L, misc.MEAS_NO),
                    )
                    for i, kind in enumerate(item.columntypes)
                ]
                result.append(
                    dict(
                        entry,
                        columns=columns,
                        links=[dict(code="", remark="") for _ in item.itemnos],
                        user_data=[str(v) for v in item.user_data],
                    )
                )
            return dict(templates=result)
        self.require_project()
        editor = self.editor
        if editor.measurement_draft:
            editor = copy.copy(editor)
            editor.record_ids = copy.deepcopy(editor.record_ids)
            editor.record_ids[editor.measurement_draft.identity] = editor.measurement_draft.saved_ids[:]
            editor.measurement_draft = None
        if "id" in args:
            data = editor.measurement_state(
                dict(id=args["id"], record_offset=args.get("record_offset", 0), record_limit=args.get("limit", 100)),
                detail_only=True,
            )
            if data["detail"] is None:
                raise ToolError("not_found", "Measurement item was not found or is a heading", "id")
            detail = data["detail"]
            detail["next_offset"] = (
                detail["offset"] + len(detail["rows"])
                if detail["offset"] + len(detail["rows"]) < detail["total_records"]
                else None
            )
            return detail
        data = editor.measurement_state({})
        rows = []
        category_id = None
        for row in data["rows"]:
            heading = row["type"] == "Heading"
            if heading:
                category_id = row["id"]
            rows.append(dict(row, description=row["description"][:60], category_id=None if heading else category_id))
        return dict(page(rows, args), caption=data["caption"])

    def get_summary(self, args, warnings):
        self.require_project()
        db = self.service.db
        total, groups, checks = (
            Decimal(0),
            {},
            dict(
                zero_quantities=[], unlinked_items=[], orphan_children=[], unlinked_measurements=[], rate_differences=[]
            ),
        )
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
                    checks["rate_differences"].append(
                        dict(code=row.code, stored=str(row.rate or 0), recalculated=str(Currency(calculated)))
                    )
        for identity, item in zip(self.editor.ids, db.get_measurement().items):
            if isinstance(item, MeasurementItemCustom) and (
                not any(key in ids for key in item.itemnos)
                or any(key is not None and key not in ids for key in item.itemnos)
            ):
                checks["unlinked_measurements"].append(identity)
        if args.get("fields", "compact") == "compact":
            checks = {key: dict(count=len(values), items=values[:20]) for key, values in checks.items()}
        return dict(
            grand_total=str(total),
            categories=[dict(category=k, total=str(v)) for k, v in groups.items()],
            checks=checks,
            analysis_dirty=self.service.dirty,
        )

    def query(self, args, warnings):
        from .mcp_query import query

        _, db = self.source(args.get("source", "project"))
        return query(self.service, db, args["sql"], args.get("params", []), args.get("limit", 500))
