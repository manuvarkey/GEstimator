"""The public MCP contract. Desktop service methods remain internal adapters."""

import copy


class ToolError(ValueError):
    def __init__(self, code, message, field=None, allowed=None, hint=None):
        super().__init__(message)
        self.detail = dict(code=code, message=message)
        self.detail.update({k: v for k, v in dict(field=field, allowed=allowed, hint=hint).items() if v is not None})


def obj(properties=None, required=(), extra=False):
    result = dict(type="object", additionalProperties=extra)
    if properties:
        result["properties"] = properties
    if required:
        result["required"] = list(required)
    return result


def enum(*values):
    return dict(enum=list(values))


def array(items, maximum=500):
    result = dict(type="array", items=items)
    if maximum != 500:
        result["maxItems"] = maximum
    return result


S = dict(type="string")
B = dict(type="boolean")
N = dict(type="integer")
V = dict(type=["string", "null"])
CODES = array(S)
KINDS = enum("schedule", "resource")
FIELDS = enum("compact", "full")
POSITION = obj(dict(before=S, after=S, parent=V, category=S, index=N))
RANGE = dict(path=S, sheet=S, first_row=dict(type="integer", minimum=1), last_row=dict(type="integer", minimum=1), first_column=dict(type="integer", minimum=1, maximum=100), rate_first=B)
ROW = obj(dict(kind=enum("Group", "Subtotal", "Weight", "Multiply", "Round"), description=S, code=S, value=S), ("kind",))
SETTINGS = obj(dict(export_break_items=B, number_locale=S, currency_code=S, show_currency_symbol=B, sch_rate_mult_factor=S, ana_copy_delete_rows=N, ana_default_rows=array(ROW, 100), ana_copy_rows=array(ROW, 100)))
ROUNDING = enum("No rounding", "Round to .000", "Round to .00", "Round to .0", "Round to 0", "Round to 10", "Round to 100", "Round to 1000", "Round to 10000", "Round within 1%", "Round within 5%", "Round within 10%")
OPERATIONS = {}


def operation(name, description, properties=None, required=(), write=False):
    props = dict(properties or {})
    if write:
        props["if_revision"] = N
    OPERATIONS[name] = dict(write=write, definition=dict(
        name=name, description=description, inputSchema=obj(props, required),
        outputSchema=dict(type="object", properties=dict(revision=dict(type="integer"), warnings=dict(type="array")), required=["data", "revision", "warnings"]),
        annotations=dict(readOnlyHint=not write)))
    if write:
        del OPERATIONS[name]["definition"]["annotations"]


operation("get_state", "Project state/sources.")
operation("describe_source", "Source notes; read first. Schema.", dict(source=S, section=S))
operation("search_items", "Ranked item search.", dict(source=S, query=dict(type="string", maxLength=500), kind=KINDS, category=S, limit=dict(type="integer", minimum=1, maximum=50)), ("query", "kind"))
operation("browse", "Paged category/parent hierarchy.", dict(source=S, kind=KINDS, under=S, depth=dict(type="integer", minimum=1, maximum=10), offset=N, limit=dict(type="integer", minimum=1, maximum=200), fields=FIELDS), ("kind",))
operation("get_items", "Definitions/relations by code.", dict(source=S, kind=KINDS, codes=CODES, include=array(enum("analysis", "resources", "children", "parent", "usage", "dependents"), 6)), ("kind", "codes"))
operation("get_measurements", "Measurements or template columns.", dict(id=S, section=enum("items", "templates"), offset=N, limit=dict(type="integer", minimum=1, maximum=200), record_offset=N))
operation("get_summary", "Totals and consistency checks.", dict(fields=FIELDS))
operation("project", "Project/files/settings/import.", dict(action=enum("new", "open", "save", "save_copy", "export_xlsx", "set_settings", "import_xlsx"), path=S, discard=B, settings=obj(dict(project_name=S, project_item_code=S, project_resource_code=S, project_metadata=S)), kind=KINDS, preview=B, mapping=obj(extra=N), duplicates=enum("error", "skip", "update"), sheet=S, header_row=dict(type="integer", minimum=1), break_lines=B), ("action",), True)
operation("import_items", "Import with ancestors/dependencies; returns code_map.", dict(source=S, kind=KINDS, codes=CODES, include_parents=B, qty=obj(extra=S), rate_mode=enum("recalculate", "stored"), position=POSITION, on_conflict=enum("error", "skip", "rename", "update"), settings=SETTINGS), ("source", "kind", "codes"), True)
ITEM = obj(dict(code=S, duplicate_from=S, parent=V, category=S, description=S, unit=S, rate=S, vat=S, discount=S, qty=S, remarks=S, reference=S, colour=V))
operation("upsert_items", "Upsert/duplicate by code; categories use category_kind.", dict(kind=enum("schedule", "resource", "category"), category_kind=KINDS, items=array(ITEM), position=POSITION), ("kind", "items"), True)
operation("move_items", "Reorder/reparent items/categories.", dict(kind=enum("schedule", "resource", "category"), category_kind=KINDS, codes=CODES, position=POSITION, renumber=B), ("kind", "codes", "position"), True)
operation("delete_items", "Guarded subtree/category deletion.", dict(kind=enum("schedule", "resource", "category"), category_kind=KINDS, codes=CODES, policy=enum("protect", "unused", "all"), preview=B), ("kind", "codes"), True)
ANA_OP = obj(dict(action=enum("add", "edit", "delete", "move", "duplicate", "insert_template", "import_xlsx", "set_remarks"), target=enum("row", "resource"), id=S, ids=CODES, ref=S, kind=ROW["properties"]["kind"], description=S, code=S, value=S, field=S, qty=S, unit=S, rate=S, vat=S, discount=S, reference=S, category=S, remarks=S, source=S, delta=enum("up", "down"), rows=array(ROW, 100), **RANGE), ("action",))
operation("edit_analysis", "Atomic analysis edits; IDs: r0/r0:0/ref.", dict(code=S, ops=array(ANA_OP), preview=B, discard_draft=B), ("code", "ops"), True)
# Nested rule groups are validated by the existing bounded rules engine. $defs
# avoids repeating the same condition schema three times in tools/list.
CONDITION = obj(dict(field=enum("description", "code", "value", "remarks"), operator=enum("equals", "not_equals", "contains", "not_contains", "starts_with", "ends_with", "glob", "is_empty", "not_empty", "numeric_eq", "numeric_ne", "gt", "gte", "lt", "lte", "between"), value=S, value2=S, mode=enum("all", "any"), conditions=array({"$ref": "#/$defs/condition"}, 8)))
MATCH = obj(dict(kind=enum("Any", "Group", "Resource", "Subtotal", "Weight", "Multiply", "Round"), mode=enum("all", "any"), occurrence=enum("all", "first", "last"), case_sensitive=B, conditions=array({"$ref": "#/$defs/condition"}, 8)))
RULE = obj(dict(match=MATCH, action=enum("set", "multiply", "add", "replace_text", "delete", "insert_before", "insert_after", "replace", "append", "prepend"), field=enum("description", "code", "value", "remarks"), value=S, find=S, rows=array(ROW, 100)), ("action",))
operation("apply_analysis_rules", "Analysis rules; preview defaults true.", dict(scope=obj(dict(codes=CODES, categories=CODES, all=B)), rules=array(RULE, 50), preview=B), ("scope", "rules"), True)
OPERATIONS["apply_analysis_rules"]["definition"]["inputSchema"]["$defs"] = dict(condition=CONDITION)
MEAS_OP = obj(dict(action=enum("create", "update", "delete", "move", "duplicate", "records_add", "records_edit", "records_delete", "records_move", "records_import", "caption"), id=S, ids=CODES, template=S, description=S, after=S, links=array(obj(dict(code=S, remark=S), ("code",)), 100), user_data=array(S, 100), records=array(obj(dict(id=S), extra=S), 1000), record_ids=CODES, record_id=S, delta=enum("up", "down"), value=S, ref=S, **RANGE), ("action",))
operation("edit_measurements", "Atomic measurements; records use titles/cN keys.", dict(ops=array(MEAS_OP)), ("ops",), True)
operation("recalculate", "Recalculate rates/quantities/source prices.", dict(what=enum("rates", "quantities", "source_rates"), codes=CODES, rounding=ROUNDING, source=S, kind=KINDS, preview=B), ("what",), True)
operation("batch", "Atomic writes, one undo; excludes file/context actions.", dict(ops=array(obj(dict(tool=enum("project", "import_items", "upsert_items", "move_items", "delete_items", "edit_analysis", "apply_analysis_rules", "edit_measurements", "recalculate"), args=obj(extra=True)), ("tool", "args")), 100)), ("ops",), True)
operation("history", "Undo/redo one project transaction.", dict(action=enum("undo", "redo")), ("action",), True)
operation("query", "Read-only SQL view fallback; prefer typed reads.", dict(source=S, sql=dict(type="string", maxLength=20000), params=array({}, 100), limit=dict(type="integer", minimum=1, maximum=500)), ("sql",))


# JSON Schema enum implies the allowed value types. Reuse identical row schemas
# locally; clients receive the same contract with fewer schema tokens.
for _operation in OPERATIONS.values():
    _schema = _operation["definition"]["inputSchema"]
    if _operation["definition"]["name"] == "import_items":
        _settings = _schema["properties"]["settings"]["properties"]
        _schema.setdefault("$defs", {})["row"] = ROW
        for _key in ("ana_default_rows", "ana_copy_rows"):
            _settings[_key] = array({"$ref": "#/$defs/row"}, 100)


def validate(value, schema, path="arguments", depth=0, root=None):
    root = schema if root is None else root
    if depth > 16:
        raise ToolError("invalid_arguments", "Arguments are nested too deeply", path)
    if "$ref" in schema:
        schema = root["$defs"][schema["$ref"].rsplit("/", 1)[-1]]
    if not schema:
        return
    kind = schema.get("type", "string" if "enum" in schema else None)
    kinds = kind if isinstance(kind, list) else [kind]
    actual = "null" if value is None else "boolean" if type(value) is bool else "integer" if type(value) is int else "number" if type(value) is float else "string" if isinstance(value, str) else "array" if isinstance(value, list) else "object" if isinstance(value, dict) else "invalid"
    if actual not in kinds:
        raise ToolError("invalid_arguments", "Expected " + str(kind), path)
    if "enum" in schema and value not in schema["enum"]:
        raise ToolError("invalid_arguments", "Choose an allowed value", path, schema["enum"])
    if actual == "object":
        for key in schema.get("required", []):
            if key not in value:
                raise ToolError("invalid_arguments", "Missing required field", path + "." + key)
        for key, item in value.items():
            rule = schema.get("properties", {}).get(key, schema.get("additionalProperties", False))
            if rule is False:
                raise ToolError("invalid_arguments", "Unknown field", path + "." + key, list(schema.get("properties", {})))
            if isinstance(rule, dict):
                validate(item, rule, path + "." + key, depth + 1, root)
    elif actual == "array":
        if len(value) > schema.get("maxItems", 500):
            raise ToolError("invalid_arguments", "Too many items", path)
        for i, item in enumerate(value):
            validate(item, schema["items"], f"{path}[{i}]", depth + 1, root)
    elif actual == "string" and len(value) > schema.get("maxLength", 10000):
        raise ToolError("invalid_arguments", "Text is too long", path)
    elif actual in ("integer", "number") and not schema.get("minimum", 0) <= value <= schema.get("maximum", float("inf")):
        raise ToolError("invalid_arguments", "Number is outside the allowed range", path)


def is_preview(name, args):
    return (name in ("edit_analysis", "delete_items", "recalculate") and args.get("preview", False)) or (name == "apply_analysis_rules" and args.get("preview", True)) or (name == "project" and args.get("action") == "import_xlsx" and args.get("preview", False))


def execute(service, name, arguments):
    if not isinstance(name, str) or name not in OPERATIONS:
        raise ToolError("unknown_tool", "Unknown tool", "name", list(OPERATIONS))
    operation = OPERATIONS[name]
    validate(arguments, operation["definition"]["inputSchema"])
    args = copy.deepcopy(arguments)
    if operation["write"]:
        if service.mcp.access != "read-write":
            raise ToolError("read_only", "MCP write access is disabled")
        if "if_revision" in args and args["if_revision"] != service.revision:
            raise ToolError("stale_revision", "Project changed since this revision", "if_revision", hint="Use the latest returned revision or omit if_revision.")
    from .mcp_workspace import Workspace
    workspace = Workspace(service)
    previous_db = service.db
    preview = is_preview(name, args)
    atomic = operation["write"] and name not in ("project", "history") and not (name == "delete_items" and preview)
    if name == "project" and args.get("action") in ("set_settings", "import_xlsx") and not preview:
        atomic = True
    warnings = []
    if atomic:
        workspace.require_project()
        data = service.project_editor.compound(lambda: workspace.call(name, args, warnings), preview=preview)
    else:
        data = workspace.call(name, args, warnings)
    if operation["write"] and not preview:
        service.mcp.change_seq += 1
        if service.db is not previous_db:
            service.mcp.project_epoch += 1
        try:
            service.checkpoint_recovery()
        except Exception:
            warnings.append(dict(code="recovery_failed", message="Operation applied, but the recovery copy could not be updated. Save the project."))
    return dict(data=data, revision=service.revision, warnings=warnings)
