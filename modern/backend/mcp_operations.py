"""Typed MCP adapters for application operations; the Python service owns edits."""

import copy


def string(description="", maximum=10000):
    return dict(type="string", maxLength=maximum, description=description)


def integer(minimum=0, maximum=1000000):
    return dict(type="integer", minimum=minimum, maximum=maximum)


def enum(*values):
    return dict(type="string", enum=list(values))


def array(items, maximum=1000):
    return dict(type="array", items=items, maxItems=maximum)


def obj(properties=None, required=(), extra=False):
    return dict(type="object", properties=properties or {}, required=list(required), additionalProperties=extra)


S = string()
ID = string("Stable row ID from a state response; categories use cat:<id>.", 100)
IDS = array(ID)
REV = integer()
BOOL = dict(type="boolean")
DECIMAL = string("Decimal or bounded arithmetic expression as text, e.g. 2*3.", 200)
PAGE = dict(query=string("Code/description search.", 500), offset=integer(), limit=integer(1, 200), source=ID, categories=array(S, 200))
TARGET = dict(id=ID, ids=IDS, target_ids=IDS)
CELL = dict(id=ID, field=S, value=S)
EDITS = array(obj(CELL, ("id", "field", "value")))
RANGE = dict(path=S, sheet=S, first_row=integer(1), last_row=integer(1), first_column=integer(1, 100), rate_first=BOOL)
ROW = obj(dict(kind=enum("Group", "Subtotal", "Weight", "Multiply", "Round"), description=S, code=S, value=DECIMAL), ("kind",))
SETTINGS = obj(dict(export_break_items=BOOL, sch_rate_mult_factor=DECIMAL, ana_copy_delete_rows=integer(0, 5), ana_default_rows=array(ROW, 100), ana_copy_rows=array(ROW, 100)))
OPERATIONS = {}


def operation(name, description, properties=None, required=(), *, method=None, write=False, revision=False, destructive=False):
    properties = dict(properties or {})
    required = list(required)
    if write or revision:
        properties["revision"] = REV
        required.append("revision")
    OPERATIONS[name] = dict(method=method or name, write=write,
        definition=dict(name=name, description=description + (" Requires current revision; use state/get_project to refresh after a stale edit." if write or revision else ""),
            inputSchema=obj(properties, required), annotations=dict(readOnlyHint=not write, destructiveHint=bool(write or destructive), idempotentHint=not write, openWorldHint=False)))


operation("state", "Read the active analysis, dirty flags, current revision and project metadata.")
operation("project.new", "Create an empty working estimate. Unsaved work is protected unless discard is explicitly true.", dict(discard=BOOL), write=True)
operation("project.open", "Open an .eproj as an isolated working copy; preserve its original file until Save.", dict(path=S, discard=BOOL), ("path",), write=True)
operation("project.save", "Save to the existing project path with conflict checks and a numbered backup; includes the active analysis draft.", write=True)
operation("project.save_copy", "Save the estimate and active draft to a NEW .eproj path; refuses overwriting an existing file.", dict(path=S), ("path",), write=True)
operation("project.settings", "Read project name and schedule/resource code prefixes.")
operation("project.settings.edit", "Change project name or code prefixes as one undoable operation.", dict(settings=obj(dict(project_name=S, project_item_code=S, project_resource_code=S))), ("settings",), write=True)
for action in ("undo", "redo"):
    operation("project." + action, action.capitalize() + " a project transaction, including linked data and quantities.", write=True)
operation("project.export_xlsx", "Export the original five-sheet workbook to a NEW .xlsx path; the working estimate is not replaced.", dict(path=S, break_lines=BOOL), ("path",), write=True)
IMPORT = dict(kind=enum("schedule", "resources"), path=S, sheet=S, header_row=integer(1, 10000))
operation("project.import_preview", "Preview workbook headers, suggested mappings and sample rows without importing.", IMPORT, ("kind", "path"))
operation("project.import_apply", "Atomically import mapped workbook rows. Mapping uses zero-based columns; duplicate policy is error/skip/update.", dict(IMPORT, mapping=obj(extra=integer(0, 99)), duplicates=enum("error", "skip", "update")), ("kind", "path", "mapping"), write=True)
operation("program.settings", "Read shipped program defaults and the custom database directory (application preferences are managed in the UI).")
operation("program.settings.validate", "Validate a complete set of Modify & Add/default-row/export options for use in an import.", dict(settings=SETTINGS), ("settings",))
operation("program.libraries", "Discover bundled and custom databases; returned paths can be passed to library.attach.")
operation("library.list", "List attached read-only database snapshots.")
operation("library.attach", "Attach an external .eproj path or bundled:<filename> snapshot; deduplicates paths and never edits the source file.", dict(path=S), ("path",), write=True)
operation("database.inspect", "Read ALL project metadata, category lists and counts from the working project or an attached source, without switching views.", dict(source=ID))
operation("database.analysis", "Read a complete stored schedule definition, resources and calculation rows by code from the project or attached database. Does not load or replace the active draft.", dict(source=ID, code=S), ("code",))
operation("database.resource", "Read one complete resource definition by code from the project or attached database.", dict(source=ID, code=S), ("code",))

for kind in ("schedule", "resources"):
    prefix = kind + ".editor."
    fields = ["code", "description", "unit", "rate", "category"] + (["qty", "remarks", "parent"] if kind == "schedule" else ["vat", "discount", "reference"])
    data = obj({field: DECIMAL if field in ("rate", "qty", "vat", "discount") else S for field in fields})
    operation(prefix + "state", "Read the " + kind + " hierarchy, IDs, categories, stored values and paging. source selects an attached database; categories filters before paging.", dict(PAGE, reveal_id=ID))
    operation(prefix + "defaults", "Get numbering and insertion defaults at selected item/category IDs; child=true chooses a subitem.", dict(ids=IDS, child=BOOL, category=S, parent=S))
    operation(prefix + "add", "Insert one " + kind + " item at target IDs. Blank code uses GTK numbering. A parent code creates a schedule subitem.", dict(TARGET, data=data), ("data",), write=True)
    operation(prefix + "duplicate", "Duplicate an item including its definition/analysis and optionally replace its code. Supply an unused data.code.", dict(TARGET, data=data), ("id", "data"), write=True)
    operation(prefix + "edit", "Edit a single field, or rename a category via its description. Category/parent remain editable through this API even though their columns are hidden.", CELL, ("id", "field", "value"), write=True)
    operation(prefix + "edit_many", "Atomically edit multiple item/category cells. Validation failure rolls back the entire batch.", dict(edits=EDITS), ("edits",), write=True)
    operation(prefix + "category_add", "Create an empty category.", dict(description=S), ("description",), write=True)
    operation(prefix + "move", "Move one item/category among siblings. delta is -1 or 1; preserve hierarchy and links.", dict(id=ID, delta=dict(type="integer", enum=[-1, 1])), ("id", "delta"), write=True)
    operation(prefix + "delete_preview", "Preview selected category/subtree deletion, used resources and measurement references before choosing a policy.", dict(ids=IDS), ("ids",), revision=True)
    operation(prefix + "delete_many", "Delete selected items/categories/subtrees as one undo step. protect rejects used resources; unused skips them; all removes their analysis uses.", dict(ids=IDS, policy=enum("protect", "unused", "all")), ("ids",), write=True, destructive=True)
    operation(prefix + "delete", "Delete one item/category using the same usage and association guards as the application.", dict(id=ID, policy=enum("protect", "unused", "all")), ("id",), write=True, destructive=True)
    operation(prefix + "add_from_library", "Import selected source IDs/categories into the working estimate at target_ids. Includes dependencies and collision handling. Schedule modify=true applies supplied Modify & Add settings.", dict(source=ID, ids=IDS, target_ids=IDS, preserve_categories=BOOL, modify=BOOL, settings=SETTINGS), ("source", "ids"), write=True)
    operation(prefix + "price_preview", "Preview rates matching selected project IDs by code in the attached library. No changes are made.", dict(library=ID, ids=IDS), ("library", "ids"), revision=True)
    operation(prefix + "price_update", "Load matching database rates for selected project IDs. Schedule copies stored rates; resources copy rate/VAT/discount/reference and update dependent analyses.", dict(library=ID, ids=IDS), ("library", "ids"), write=True)
    for action in ("copy", "paste"):
        operation(prefix + action, action.capitalize() + " application-session rows; prefer clipboard.export/paste for portable structured data.", dict(TARGET, preserve_categories=BOOL), write=action == "paste", revision=action == "copy")
operation("resources.editor.move_to", "Move selected resource IDs to an existing category while preserving resource identities and analysis links.", dict(ids=IDS, category=S), ("ids", "category"), write=True)
operation("resources.editor.usage", "Read project resource quantities/amounts, 50 per page.", dict(query=S, offset=integer()))
operation("resources.editor.dependents", "Find analyses that directly or indirectly use a resource code, 50 per page.", dict(code=S, offset=integer()), ("code",))
operation("resources.editor.rates", "Recalculate stored schedule rates from current resource definitions through the original engine.", write=True)
operation("schedule.editor.renumber", "Apply original schedule hierarchy numbering, preserving identities, parent links and measurement associations.", write=True)
operation("schedule.editor.colour", "Set selected schedule item colours to #RRGGBB or null to clear.", dict(ids=IDS, colour=dict(type=["string", "null"], maxLength=7)), ("ids", "colour"), write=True)
operation("schedule.editor.update_rates", "Recalculate selected schedule analyses and their dependents.", dict(ids=IDS), ("ids",), write=True)
operation("schedule.editor.update_quantities", "Update selected item quantities from linked measurements with a GTK rounding label, e.g. No rounding or Round to .000.", dict(ids=IDS, rounding=S), ("ids", "rounding"), write=True)

operation("analysis.load", "Load the selected project schedule code into the active analysis. Protects an existing dirty draft unless discard=true.", dict(code=S, discard=BOOL), ("code",), write=True)
operation("analysis.template_rows", "Read shipped default analysis calculation rows.")
operation("analysis.add_row", "Insert a calculation row after id, or at the beginning without id. Group/Subtotal need no numeric value; Weight/Multiply/Round use value.", dict(id=ID, kind=enum("Group", "Subtotal", "Weight", "Multiply", "Round"), description=S, code=S, value=DECIMAL), ("kind",), method="add", write=True)
operation("analysis.edit_cell", "Edit an analysis row/resource field. Use IDs from state; value is quantity/factor, rate/VAT/discount affect the resource definition.", CELL, ("id", "field", "value"), method="edit", write=True)
operation("analysis.edit", "Edit active analysis remarks (field=ana_remarks).", dict(field=enum("ana_remarks"), value=S), ("field", "value"), write=True)
RES = dict(id=ID, code=S, description=S, unit=S, rate=DECIMAL, vat=DECIMAL, discount=DECIMAL, reference=S, category=S, qty=DECIMAL, remarks=S, library=BOOL, source=ID)
operation("analysis.resource_add", "Add a custom resource to a group/after a resource id. library=true reads code from the project or attached source instead of creating a definition.", RES, ("id", "code"), method="resource.add", write=True)
operation("analysis.resource_duplicate", "Duplicate one resource definition with an unused new code and explicit quantity. analysis.duplicate instead copies entries sharing the same definition.", dict(id=ID, code=S, qty=DECIMAL, remarks=S), ("id", "code", "qty"), method="resource.duplicate", write=True)
for action in ("copy", "paste", "duplicate", "delete", "move", "undo", "redo"):
    required = ("id", "delta") if action == "move" else ("ids",) if action in ("copy", "duplicate", "delete") else ()
    operation("analysis." + action, action.capitalize() + " active draft rows. Undo/redo here affect only the analysis draft; project undo is separate.", dict(id=ID, ids=IDS, delta=dict(type="integer", enum=[-1, 1])), required, method=action, write=action != "copy", revision=action == "copy", destructive=action == "delete")
operation("analysis.apply", "Apply the active analysis draft to the working project and update dependent rates as one project undo transaction. Save persists it to disk.", write=True)
BATCH_ROW = obj(dict(CELL, method=enum("edit", "add"), kind=enum("Group", "Subtotal", "Weight", "Multiply", "Round"), description=S, code=S), ("method",))
for method in ("analysis.batch.preview", "analysis.batch"):
    operation(method, "Preview" + (" or atomically apply" if method == "analysis.batch" else "") + " ordered cell edits/calculation-row additions. Each operation has method=edit/add and that action's fields; additions advance the insertion cursor.", dict(id=ID, operations=array(BATCH_ROW, 500)), ("operations",), write=method == "analysis.batch", revision=method.endswith("preview"))
operation("analysis.insert_template", "Insert supplied calculation rows or the shipped defaults into the active draft.", dict(id=ID, rows=array(ROW, 100)), write=True)
for method in ("analysis.import_preview", "analysis.import_xlsx"):
    operation(method, "Preview or import a six-column analysis workbook range using the original parser. rate_first swaps qty/rate columns.", RANGE, ("path",), write=method.endswith("xlsx"))
operation("analysis.export_xlsx", "Export the active analysis, including its draft, to a NEW workbook path.", dict(path=S), ("path",), write=True)

operation("measurement.templates", "Read installed template codes, General/Civil/E&M groups, inputs, summaries and properties.")
operation("measurement.state", "Read measurement items and optionally one detail; raw expressions, calculated display, Breakup, links and properties are retained.", dict(id=ID, record_offset=integer(), record_limit=integer(1, 200)))
operation("measurement.detail", "Read one measurement item's paged records and complete template/link/property metadata.", dict(id=ID, record_offset=integer(), record_limit=integer(1, 200)), ("id",))
operation("measurement.add", "Insert a custom item with template code, or a heading without template; id places it after an existing measurement item.", dict(id=ID, template=S, description=S), write=True)
operation("measurement.caption", "Change the measurement document caption.", dict(value=S), ("value",), write=True)
operation("measurement.edit", "Edit one measurement/heading description.", dict(id=ID, field=enum("description"), value=S), ("id", "value"), write=True)
for action in ("copy", "paste", "duplicate", "delete", "move"):
    operation("measurement." + action, action.capitalize() + " selected whole measurement items, preserving their records and link order.", dict(id=ID, ids=IDS, delta=dict(type="integer", enum=[-1, 1])), write=action != "copy", revision=action == "copy", destructive=action == "delete")
LINK = obj(dict(code=S, remark=S), ("code", "remark"))
operation("measurement.properties", "Atomically change description, ordered schedule links/remarks and user_data. Arrays must match the installed template metadata.", dict(id=ID, description=S, links=array(LINK, 100), user_data=array(S, 100)), ("id", "links", "user_data"), write=True)
operation("measurement.link", "Set one zero-based schedule link slot by code and remark; empty code removes the link.", dict(id=ID, slot=integer(0, 99), code=S, remark=S), ("id", "slot"), write=True)
operation("measurement.userdata", "Set one zero-based template property slot. Numeric properties accept arithmetic text.", dict(id=ID, slot=integer(0, 99), value=S), ("id", "slot", "value"), write=True)
operation("measurement.update_quantities", "Update all linked schedule quantities using an original rounding label.", dict(rounding=S), write=True)
operation("measurement.record_add", "Insert 1–1000 blank records after record_id, or at the end. Returns stable record IDs/page position.", dict(id=ID, record_id=ID, count=integer(1, 1000)), ("id",), write=True)
operation("measurement.record_edit", "Edit one raw input cell cN by record_id. Derived cells are read-only; numeric expressions are evaluated by the original template.", dict(id=ID, record_id=ID, field=S, value=S), ("id", "record_id", "field", "value"), write=True)
operation("measurement.record_edit_many", "Atomically edit many record input cells. edits[].id is a record ID; top-level id is its measurement item.", dict(id=ID, edits=EDITS), ("id", "edits"), write=True)
for action in ("copy", "paste", "duplicate", "delete", "move"):
    operation("measurement.record_" + action, action.capitalize() + " one record or an ordered record_ids selection in a matching template.", dict(id=ID, record_id=ID, record_ids=IDS, delta=dict(type="integer", enum=[-1, 1])), ("id",), write=action != "copy", revision=action == "copy", destructive=action == "delete")
operation("measurement.record_import", "Import the template's editable columns from a worksheet range using saved formula values; one undoable operation.", dict(RANGE, id=ID, record_id=ID), ("id", "path"), write=True)
CLIP = dict(kind=enum("analysis", "schedule", "resources", "measurement", "records"), id=ID, ids=IDS, record_id=ID, record_ids=IDS, preserve_categories=BOOL)
operation("clipboard.export", "Export selected rows as validated portable JSON, including required dependencies; no OS clipboard access is needed.", CLIP, ("kind",), revision=True)
operation("clipboard.paste", "Paste portable JSON exported by this application as one undoable transaction, remapping schedule links and handling code collisions.", dict(CLIP, data=string(maximum=500000)), ("kind", "data"), write=True)
operation("recovery.list", "List saved recovery checkpoints and metadata.")
operation("recovery.open", "Open a recovery checkpoint into a working project; existing unsaved work is protected unless discard=true.", dict(id=ID, discard=BOOL), ("id",), write=True)
operation("recovery.discard", "Discard the current application's recovery checkpoint.", write=True, destructive=True)

OPERATIONS["analysis.add_row"]["definition"]["inputSchema"]["anyOf"] = [
    obj(dict(kind=enum("Group", "Subtotal")), ("kind",), extra=True),
    obj(dict(kind=enum("Weight", "Multiply", "Round")), ("kind", "value"), extra=True),
]
OPERATIONS["analysis.resource_add"]["definition"]["inputSchema"]["anyOf"] = [
    obj(dict(library=dict(type="boolean", enum=[True])), ("library",), extra=True),
    obj(required=("description", "unit", "rate"), extra=True),
]


def validate(value, schema, path="arguments", depth=0):
    """Validate the bounded JSON-schema subset above before dispatching to the engine."""
    if depth > 16:
        raise ValueError("Arguments are nested too deeply")
    kind = schema.get("type")
    kinds = kind if isinstance(kind, list) else [kind]
    actual = "null" if value is None else "boolean" if type(value) is bool else "integer" if type(value) is int else "number" if type(value) is float else "string" if isinstance(value, str) else "array" if isinstance(value, list) else "object" if isinstance(value, dict) else "invalid"
    if actual not in kinds and not (actual == "integer" and "number" in kinds):
        raise ValueError(path + ": expected " + str(kind))
    if "anyOf" in schema:
        errors = []
        for branch in schema["anyOf"]:
            try:
                validate(value, branch, path, depth + 1)
                break
            except ValueError as error:
                errors.append(str(error))
        else:
            raise ValueError(" or ".join(errors))
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(path + ": choose " + str(schema["enum"]))
    if actual == "object":
        for key in schema.get("required", []):
            if key not in value:
                raise ValueError(path + ": missing " + key)
        properties = schema.get("properties", {})
        for key, item in value.items():
            rule = properties.get(key, schema.get("additionalProperties", False))
            if rule is False:
                raise ValueError(path + ": unknown field " + key)
            if isinstance(rule, dict):
                validate(item, rule, path + "." + key, depth + 1)
    elif actual == "array":
        if len(value) > schema.get("maxItems", 1000):
            raise ValueError(path + ": too many items")
        for item in value:
            validate(item, schema["items"], path + "[]", depth + 1)
    elif actual == "string" and len(value) > schema.get("maxLength", 10000):
        raise ValueError(path + ": text is too long")
    elif actual in ("integer", "number") and not schema.get("minimum", float("-inf")) <= value <= schema.get("maximum", float("inf")):
        raise ValueError(path + ": number is outside the allowed range")


def execute(service, name, arguments):
    operation = OPERATIONS[name]
    validate(arguments, operation["definition"]["inputSchema"])
    if operation["write"]:
        if service.mcp.access != "read-write":
            raise ValueError("MCP write access is disabled. Choose Read and write in MCP settings and restart the server.")
        if arguments["revision"] != service.revision:
            raise ValueError("Stale edit; read state and retry using its revision")
    method = operation["method"]
    previous_db = service.db
    if name.startswith("database."):
        if not service.db:
            raise ValueError("Open a project first")
        source = arguments.get("source")
        if source and source not in service.project_editor.libraries:
            raise ValueError("Database is no longer attached")
        db = service.project_editor.libraries[source][1] if source else service.db
        if name == "database.inspect":
            data = dict(metadata=db.get_project_settings(), schedule_items=db.ScheduleTable.select().count(), resources=db.ResourceTable.select().count(),
                schedule_categories=[row.description or "" for row in db.ScheduleCategoryTable.select().order_by(db.ScheduleCategoryTable.order)],
                resource_categories=[row.description or "" for row in db.ResourceCategoryTable.select().order_by(db.ResourceCategoryTable.order)])
        else:
            from .clipboard import schedule_data, resource_data
            item = db.get_item(arguments["code"], modify_res_code=False) if name == "database.analysis" else db.get_resource(arguments["code"])
            if item is None:
                raise ValueError("Code not found in selected database")
            data = schedule_data(item) if name == "database.analysis" else resource_data(item)
    else:
        data = service.call(method, copy.deepcopy(arguments))
    warning = None
    if operation["write"]:
        service.mcp.change_seq += 1
        if service.db is not previous_db:
            service.mcp.project_epoch += 1
        try:
            service.checkpoint_recovery()
        except Exception:
            warning = "Operation applied, but the recovery copy could not be updated. Save the project."
    return dict(data=data, revision=service.revision, change_seq=service.mcp.change_seq,
                analysis_dirty=service.dirty, project_dirty=service.workspace_dirty, warning=warning)
