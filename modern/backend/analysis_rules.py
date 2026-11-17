"""Ordered project analysis rules; calculations and persistence stay in the GTK engine."""

from contextlib import closing
import copy
from fnmatch import fnmatchcase
from pathlib import Path
import sqlite3
from uuid import uuid4

from estimator.data.schedule import ScheduleDatabase
from estimator.undo import Stack
from .numbers import decimal
from .program_settings import legacy_rows
from .service import text

KINDS = ("Group", "Subtotal", "Weight", "Multiply", "Round")
FIELDS = ("description", "code", "value", "remarks")
NUMERIC = ("numeric_eq", "numeric_ne", "gt", "gte", "lt", "lte", "between")
OPERATORS = ("equals", "not_equals", "contains", "not_contains", "starts_with", "ends_with", "glob", "is_empty", "not_empty", *NUMERIC)
ACTIONS = ("set", "multiply", "add", "replace_text", "delete", "insert_before", "insert_after", "replace", "append", "prepend")


def validate_group(group, depth=0, count=None):
    count = count if count is not None else [0]
    if depth > 2 or not isinstance(group, dict) or group.get("mode", "all") not in ("all", "any"):
        raise ValueError("Use All/Any condition groups up to three levels deep")
    conditions = group.get("conditions", [])
    if not isinstance(conditions, list) or len(conditions) > 8:
        raise ValueError("Use at most eight entries in each condition group")
    for condition in conditions:
        count[0] += 1
        if count[0] > 32:
            raise ValueError("Use at most 32 conditions/groups per rule")
        if isinstance(condition, dict) and "conditions" in condition:
            validate_group(condition, depth + 1, count)
            continue
        if not isinstance(condition, dict) or condition.get("field") not in FIELDS or condition.get("operator") not in OPERATORS:
            raise ValueError("Unknown match condition")
        text(condition.get("value", ""))
        if condition["operator"] in NUMERIC:
            lower = decimal(condition.get("value", ""))
            if condition["operator"] == "between" and lower > decimal(condition.get("value2", "")):
                raise ValueError("The lower range bound must not exceed the upper bound")


def validate(rules):
    if not isinstance(rules, list) or not 1 <= len(rules) <= 50:
        raise ValueError("Provide between 1 and 50 ordered rules")
    result = copy.deepcopy(rules)
    for rule in result:
        if not isinstance(rule, dict) or rule.get("action") not in ACTIONS:
            raise ValueError("Unknown analysis rule action")
        match = rule.get("match", {})
        if not isinstance(match, dict) or match.get("kind", "Any") not in (*KINDS, "Resource", "Any"):
            raise ValueError("Unknown match row type")
        if match.get("mode", "all") not in ("all", "any") or match.get("occurrence", "all") not in ("all", "first", "last"):
            raise ValueError("Choose all/any conditions and all/first/last matches")
        if type(match.get("case_sensitive", False)) is not bool:
            raise ValueError("Choose case-sensitive or case-insensitive matching")
        validate_group(match)
        if rule["action"] in ("set", "multiply", "add", "replace_text"):
            if rule.get("field") not in FIELDS:
                raise ValueError("Unknown field to change")
            text(rule.get("value", ""))
            if rule["field"] == "value":
                decimal(rule["value"])
            if rule["action"] in ("multiply", "add"):
                if rule["field"] != "value":
                    raise ValueError("Arithmetic actions apply to quantity / factor only")
                decimal(rule["value"])
            if rule["action"] == "replace_text":
                if rule["field"] == "value" or not text(rule.get("find", "")):
                    raise ValueError("Text replacement needs non-empty find text and a text field")
        if rule["action"] in ("insert_before", "insert_after", "replace", "append", "prepend"):
            if not rule.get("rows"):
                raise ValueError("Add at least one calculation row to insert or replace")
            legacy_rows(rule["rows"])
    return result


def entries(model):
    for row in model.ana_items:
        yield dict(id=row["_id"], kind=KINDS[row["itemtype"]], description=row["description"] or "",
                   code=row.get("code", ""), value=str(row["value"]) if "value" in row else "")
        if row["itemtype"] == 0:
            for identity, entry in zip(row["_resource_ids"], row["resource_list"]):
                resource = model.resources[entry[0]]
                yield dict(id=identity, kind="Resource", code=entry[0], description=resource.description or "",
                           value=str(entry[1]), remarks=entry[2] or "")


def matches(row, match):
    if match.get("kind", "Any") not in ("Any", row["kind"]):
        return False

    def check(condition):
        if "conditions" in condition:
            return group_matches(condition)
        if condition["field"] not in row:
            return False
        actual, expected, operator = str(row[condition["field"]]), condition.get("value", ""), condition["operator"]
        if operator in ("is_empty", "not_empty"):
            return not actual.strip() if operator == "is_empty" else bool(actual.strip())
        if operator in NUMERIC:
            if not actual:
                return False
            try:
                left, right = decimal(actual), decimal(expected)
            except ValueError:
                return False
            if operator == "between":
                return right <= left <= decimal(condition["value2"])
            return {"numeric_eq": left == right, "numeric_ne": left != right, "gt": left > right, "gte": left >= right, "lt": left < right, "lte": left <= right}[operator]
        if not match.get("case_sensitive", False):
            actual, expected = actual.casefold(), expected.casefold()
        return {"equals": lambda: actual == expected, "not_equals": lambda: actual != expected,
                "contains": lambda: expected in actual, "not_contains": lambda: expected not in actual,
                "starts_with": lambda: actual.startswith(expected), "ends_with": lambda: actual.endswith(expected),
                "glob": lambda: fnmatchcase(actual, expected)}[operator]()

    def group_matches(group):
        conditions = group.get("conditions", [])
        return not conditions or (all if group.get("mode", "all") == "all" else any)(check(condition) for condition in conditions)

    return group_matches(match)


def transform(owner, model, rules):
    engine = copy.copy(owner)
    engine.model = model
    engine.identify()
    original = copy.deepcopy(model.ana_items)
    counts, changes = [0] * len(rules), []
    for index, rule in enumerate(rules):
        action, match = rule["action"], rule.get("match", {})
        targets = [row for row in entries(model) if matches(row, match)]
        if match.get("occurrence") == "first":
            targets = targets[:1]
        elif match.get("occurrence") == "last":
            targets = targets[-1:]
        if action in ("append", "prepend"):
            targets = [dict(id=None, kind="Analysis", description=model.code)]
        counts[index] = len(targets)
        # Work backwards so insertions/deletions never rematch or shift another target.
        for row in reversed(targets):
            changed = True
            old, new = "", ""
            if action in ("set", "multiply", "add", "replace_text"):
                field, value = rule["field"], rule.get("value", "")
                allowed = ("code", "value", "remarks") if row["kind"] == "Resource" else ("description", "code") if row["kind"] == "Group" else ("description", "value") if row["kind"] in ("Weight", "Multiply", "Round") else ("description",)
                if field not in allowed:
                    raise ValueError(f"{model.code}: {field} is not editable on {row['kind']} entries; narrow the match type")
                i, j = engine.locate(row["id"])
                entry = model.ana_items[i] if j is None else model.ana_items[i]["resource_list"][j]
                before = copy.deepcopy(entry)
                old = row.get(field, "")
                if action in ("multiply", "add"):
                    number, operand = decimal(old), decimal(value)
                    value = str(number * operand if action == "multiply" else number + operand)
                elif action == "replace_text":
                    value = old.replace(rule["find"], value)
                engine.edit("edit", dict(id=row["id"], field=field, value=value))
                changed = entry != before
                new = next(item for item in entries(model) if item["id"] == row["id"])[field]
            elif action == "delete":
                # A group match already owns its children; children selected by the
                # same rule are removed first because targets are traversed backwards.
                engine.edit("delete", dict(ids=[row["id"]]))
                old = row.get("value") or row["description"]
                new = "Deleted"
            else:
                if row["kind"] == "Resource":
                    raise ValueError(f"{model.code}: insert/replace calculation rows must match a calculation row, not a resource entry")
                position = len(model.ana_items) if action == "append" else 0 if action == "prepend" else engine.locate(row["id"])[0] + (action == "insert_after")
                if action == "replace":
                    old = row["description"]
                    engine.edit("delete", dict(ids=[row["id"]]))
                model.ana_items[position:position] = legacy_rows(rule["rows"])
                engine.identify()
                new = "; ".join(item["description"] or item["kind"] for item in rule["rows"])
            if changed:
                if len(changes) < 500:
                    changes.append(dict(rule=index + 1, kind=row["kind"], row=row.get("description", ""), action=action,
                                        field=rule.get("field", ""), before=old, after=new))
        model.evaluate_results()
        if len(model.ana_items) > 5000:
            raise ValueError("A rule would create more than 5000 calculation rows in one analysis")
    return model.ana_items != original, counts, changes


def execute(editor, params):
    rules = validate(params.get("rules"))
    db = editor.db
    if params.get("scope", "selected") == "all":
        records = list(db.ScheduleTable.select())
    elif params.get("scope", "selected") == "selected":
        ids = params.get("ids") or ([str(db.get_item_key(text(params["code"])))] if params.get("code") else [])
        _, records = editor.selection("schedule", ids)
    else:
        raise ValueError("Choose selected schedule items/categories or the whole schedule")
    if len(records) > 10000:
        raise ValueError("Use a scope of at most 10000 schedule items")
    records.sort(key=lambda row: (row.category.order, row.order, row.suborder or 0, row.id))
    initial_rates = {row.code: str(row.rate or 0) for row in db.ScheduleTable.select()}
    plans, counts, details, unmatched = [], [0] * len(rules), [], 0
    for record in records:
        model = db.get_item(record.code, modify_res_code=False)
        changed, matches_per_rule, changes = transform(editor.owner, model, rules)
        counts = [a + b for a, b in zip(counts, matches_per_rule)]
        if not any(matches_per_rule):
            unmatched += 1
        details.extend(dict(code=model.code, **change) for change in changes[:max(0, 500 - len(details))])
        if changed:
            model.update_rate()
            plans.append(model)
    # Plan every item before writing any item. Invalid rules cannot partly apply.
    for model in plans:
        if not db.insert_item_atomic(model, update=True):
            raise ValueError("Unable to save analysis " + model.code)
    if plans:
        editor.owner.update_dependent_rates(db, schedules={model.code for model in plans})
    direct = {model.code for model in plans}
    affected = [dict(code=row.code, description=row.description, before=initial_rates[row.code], after=str(row.rate or 0), dependent=row.code not in direct)
                for row in db.ScheduleTable.select() if row.code in direct or str(row.rate or 0) != initial_rates[row.code]]
    return dict(revision=editor.owner.revision, selected=len(records), changed=len(plans), unmatched=unmatched,
                rule_matches=counts, changes=details, items=affected[:200], affected=len(affected), truncated=len(affected) > 200 or len(details) >= 500)


def preview_in_copy(editor, action):
    target = Path(editor.owner.temp.name) / (uuid4().hex + ".rule-preview")
    scratch = ScheduleDatabase(Stack())
    try:
        with closing(sqlite3.connect(target)) as output:
            editor.db.database.connection().backup(output)
        scratch.open_database(str(target))
        preview_editor = copy.copy(editor)
        preview_editor.owner = copy.copy(editor.owner)
        preview_editor.owner.db = scratch
        return action(preview_editor)
    finally:
        scratch.close_database()
        target.unlink(missing_ok=True)


def run(editor, params, apply=False):
    # Preview runs the same writes and dependency calculation on an isolated copy.
    result = preview_in_copy(editor, lambda scratch: execute(scratch, params))
    if apply and result["changed"]:
        result = editor.mutate(lambda: execute(editor, params))
    result["revision"] = editor.owner.revision
    return result
