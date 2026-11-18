"""Bounded SQL over a disposable, read-only reporting projection.

Only the existing Python engine interprets analyses and measurement templates.
Reporting files never modify the project or any attached source.
"""

from contextlib import closing
import json
import re
from pathlib import Path
import sqlite3
import time
from uuid import uuid4

from .mcp_operations import ToolError

SCHEMA = {
    "v_schedule": ["code", "description", "unit", "rate", "qty", "amount", "category", "parent_code"],
    "v_resources": ["code", "description", "unit", "rate", "vat", "discount", "reference", "category"],
    "v_analysis_rows": ["code", "row_index", "resource_index", "kind", "description", "resource_code", "value", "remarks"],
    "v_measurements": ["id", "template", "description", "totals"],
    "v_measurement_records": ["measurement_id", "id", "record_index", "values_json", "display_json"],
    "v_links": ["measurement_id", "slot", "code", "remark"],
}
FUNCTIONS = {"abs", "avg", "count", "sum", "total", "min", "max", "round", "coalesce", "ifnull", "nullif", "length", "lower", "upper", "substr", "substring", "trim", "ltrim", "rtrim", "replace", "instr", "like", "glob", "printf", "format", "group_concat", "concat", "concat_ws", "json_extract", "json_array_length", "json_valid", "json_type", "row_number", "rank", "dense_rank", "lag", "lead"}


def projection(service, db):
    from .mcp_workspace import item_rows
    from estimator.data.schedule import Currency
    from estimator.data.measurement import MeasurementItemCustom
    from .clipboard import analysis_data
    result = {name: [] for name in SCHEMA}
    schedules = item_rows(db, "schedule")
    by_id = {r.id: r.code for r in schedules}
    for row in schedules:
        result["v_schedule"].append((row.code, row.description, row.unit or "", str(row.rate or 0), str(row.qty or 0), str(Currency((row.rate or 0) * (row.qty or 0))), row.category.description, by_id.get(row.parent_id)))
        model = db.get_item(row.code, modify_res_code=False)
        for i, original in enumerate(model.ana_items):
            data = analysis_data(original)
            result["v_analysis_rows"].append((row.code, i, None, data["kind"], data["description"], None, data["value"], ""))
            for j, entry in enumerate(data.get("resources", [])):
                result["v_analysis_rows"].append((row.code, i, j, "Resource", model.resources[entry[0]].description, entry[0], entry[1], entry[2]))
    for row in item_rows(db, "resource"):
        result["v_resources"].append((row.code, row.description, row.unit or "", str(row.rate or 0), str(row.vat or 0), str(row.discount or 0), row.reference or "", row.category.description))
    editor = service.project_editor if service.db is db else None
    if editor:
        editor.ensure_ids()
    for i, item in enumerate(db.get_measurement().items):
        identity = editor.ids[i] if editor else "m" + str(i)
        custom = isinstance(item, MeasurementItemCustom)
        result["v_measurements"].append((identity, item.itemtype if custom else None, item.remark, json.dumps([str(v) for v in item.get_total()] if custom else [])))
        if not custom:
            continue
        for j, record in enumerate(item.records):
            draft = editor.measurement_draft if editor else None
            record_id = (draft.saved_ids if draft and draft.identity == identity else editor.record_ids[identity])[j] if editor else identity + ":" + str(j)
            result["v_measurement_records"].append((identity, record_id, j, json.dumps(record.data_string), json.dumps(record.get_model_rendered(j + 1), default=str)))
        for slot, (key, remark) in enumerate(zip(item.itemnos, item.item_remarks)):
            result["v_links"].append((identity, slot, by_id.get(key), remark))
    return result


def query(service, db, sql, params, limit=500):
    # SQLite reports a view and a same-named CTE as the same authorizer source.
    # Reject internal identifiers in client SQL as well, so a CTE cannot
    # impersonate a documented view to read its backing table directly.
    internal = {"_" + name[2:] for name in SCHEMA}
    lexemes = re.findall(r"--[^\n]*|/\*[\s\S]*?\*/|'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|`(?:``|[^`])*`|\[[^\]]*\]|[A-Za-z_]\w*|\S", sql)
    for token in lexemes:
        if token.startswith(("'", "--", "/*")):
            continue
        identifier = token.strip('"`[]').replace('""', '"').replace('``', '`').casefold()
        if identifier in internal:
            raise ToolError("invalid_query", "Direct backing-table access is forbidden", "sql", hint="Read documented v_* views instead.")
    path = Path(service.temp.name) / (uuid4().hex + ".report")
    values = projection(service, db)
    try:
        with closing(sqlite3.connect(path)) as output:
            for view, columns in SCHEMA.items():
                table = "_" + view[2:]
                declarations = ",".join('"' + col + '" ' + ("INTEGER" if col in ("row_index", "resource_index", "record_index", "slot") else "TEXT") for col in columns)
                output.execute(f'CREATE TABLE "{table}" ({declarations})')
                output.executemany(f'INSERT INTO "{table}" VALUES ({",".join("?" for _ in columns)})', values[view])
                output.execute(f'CREATE VIEW "{view}" AS SELECT * FROM "{table}"')
            output.commit()
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
            connection.enable_load_extension(False)
            connection.execute("PRAGMA query_only=ON")
            connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 1000000)
            connection.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, 20000)
            connection.setlimit(sqlite3.SQLITE_LIMIT_EXPR_DEPTH, 100)
            def authorize(action, arg1, arg2, database, source):
                if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_RECURSIVE):
                    return sqlite3.SQLITE_OK
                if action == sqlite3.SQLITE_READ and (arg1 in SCHEMA or source in SCHEMA and arg1 == "_" + source[2:]):
                    return sqlite3.SQLITE_OK
                if action == sqlite3.SQLITE_FUNCTION and arg2.lower() in FUNCTIONS:
                    return sqlite3.SQLITE_OK
                return sqlite3.SQLITE_DENY
            connection.set_authorizer(authorize)
            deadline, steps = time.monotonic() + 2, [0]
            def progress():
                steps[0] += 1000
                return steps[0] >= 2_000_000 or time.monotonic() >= deadline
            connection.set_progress_handler(progress, 1000)
            cursor = connection.execute(sql, params)
            if cursor.description is None:
                raise ToolError("invalid_query", "Only SELECT queries are allowed", "sql")
            rows, size = [], 0
            for row in cursor:
                try:
                    encoded = json.dumps(row, ensure_ascii=False, allow_nan=False)
                except (TypeError, ValueError):
                    raise ToolError("invalid_query", "Query produced a value that cannot be represented in JSON", "sql") from None
                size += len(encoded.encode())
                if len(rows) == limit or size > 262144:
                    raise ToolError("too_large", "Query exceeds the row or result-size limit", "sql", hint="Aggregate or page with LIMIT/OFFSET.")
                rows.append(list(row))
            return dict(columns=[col[0] for col in cursor.description], rows=rows, truncated=False)
    except sqlite3.Error as error:
        message = str(error)
        if "interrupted" in message or "too big" in message:
            raise ToolError("too_large", "Query exceeded its execution or size limit", "sql", hint="Aggregate or narrow the query.") from None
        raise ToolError("invalid_query", message, "sql", hint="Use one SELECT over the views in describe_source section=schema.") from None
    finally:
        path.unlink(missing_ok=True)
