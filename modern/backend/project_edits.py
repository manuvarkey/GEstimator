"""Schedule and resource edits inside ProjectEditor transaction boundaries.

All writes use the caller's mutation boundary. The editor owns revision checks,
clipboard lifetime, rollback and history.
"""

import copy
import re

from estimator.data.schedule import Currency, ResourceItemModel, ScheduleItemModel

from .clipboard import order as tree_order
from .insertion import defaults, last_selected, place, prepare
from .numbers import decimal
from .rates import recalculate_rates
from .validation import text


def edit(editor, kind, op, p):
    """Dispatch a schedule or resource edit after the editor checks its revision."""
    # Step 1: resolve editor tables and route bulk or clipboard operations.
    db = editor.db
    resource = kind == "resources"
    table = db.ResourceTable if resource else db.ScheduleTable
    category = db.ResourceCategoryTable if resource else db.ScheduleCategoryTable
    if resource and op == "move_to":
        return _move_resources_to_category(editor, kind, p, table, category)
    if resource and op == "renumber":
        return editor.renumber_resources(p.get("exclude", []))
    if resource and op == "sync_schedule":
        return _sync_resources_from_schedule(editor, db, kind, p, table)
    if not resource and op == "renumber":
        return editor.renumber_schedule()
    if not resource and op in ("colour", "update_quantities", "update_rates"):
        return _update_schedule_items(editor, db, kind, op, p)
    if op == "copy":
        return _copy_items(editor, db, kind, p, table, resource)
    if op == "paste":
        return _paste_items(editor, kind, p, resource)
    if op == "delete_many":
        return editor.delete_selection(kind, p)
    if op == "category_add":
        name = text(p["description"])
        selected, is_category = last_selected(editor, kind, p)
        destination = selected if is_category else selected.category if selected is not None else None
        method = db.insert_resource_category_atomic if resource else db.insert_schedule_category_atomic
        if method(name, [destination.order] if destination is not None else None) is False:
            raise ValueError("Category could not be added")
        return dict(selected=[f"cat:{category.get(description=name).id}"])
    if op == "rates":
        recalculate_rates(db, [r.code for r in db.ScheduleTable.select()])
        return
    # Step 2: route category and item operations using the original row identity.
    identity = str(p.get("id", ""))
    if identity.startswith("cat:") and op != "add":
        return _edit_category(editor, db, kind, op, p, category, resource, identity)
    row = table.get_by_id(int(identity)) if identity and not identity.startswith("cat:") else None
    if op == "delete":
        return editor.delete_selection(kind, dict(p, ids=[identity]))
    if op in ("add", "duplicate"):
        return _insert_or_duplicate(editor, db, kind, op, p, table, resource, row)
    if op == "move":
        return _move_item(editor, db, p, table, resource, row)
    if op != "edit":
        raise ValueError("Unknown project operation")
    return _update_item(editor, db, p, table, category, resource, row)


def _move_resources_to_category(editor, kind, p, table, category):
    """Move selected resources together, then restore dense order in their source categories."""
    _, records = editor.selection(kind, p.get("ids"), include_descendants=False)
    destination = category.get_or_none(category.description == text(p.get("category", "")))
    if not records or destination is None:
        raise ValueError("Select resources and an existing destination category")
    records.sort(key=lambda row: (row.category.order, row.order, row.id))
    previous = {row.category_id for row in records}
    table.update(category=destination.id).where(table.id.in_([row.id for row in records])).execute()
    place(editor, kind, [row.code for row in records], dict(id="cat:" + str(destination.id)))
    for category_id in previous - {destination.id}:
        for order, row in enumerate(
            table.select().where(table.category == category_id).order_by(table.order, table.id)
        ):
            table.update(order=order).where(table.id == row.id).execute()
    return dict(selected=[str(row.id) for row in records])


def _sync_resources_from_schedule(editor, db, kind, p, table):
    """Copy rates for matching codes and recalculate their dependents."""
    _, rows = editor.selection(kind, p.get("ids"), include_descendants=False)
    if not rows:
        raise ValueError("Select resources to synchronize")
    changed = set()
    for row in rows:
        schedule = db.ScheduleTable.get_or_none(db.ScheduleTable.code == row.code)
        if schedule is not None and Currency(row.rate) != Currency(schedule.rate):
            table.update(rate=Currency(schedule.rate)).where(table.id == row.id).execute()
            changed.add(row.code)
    if changed:
        editor.owner.update_dependent_rates(db, resources=changed)
    return


def _update_schedule_items(editor, db, kind, op, p):
    """Apply a schedule operation to selected item rows, excluding category expansion."""
    ids = p.get("ids")
    if not isinstance(ids, list) or not 1 <= len(ids) <= 1000:
        raise ValueError("Select between 1 and 1000 schedule items")
    item_ids = [identity for identity in ids if not str(identity).startswith("cat:")]
    _, rows = editor.selection(kind, item_ids, include_descendants=False)
    codes = [row.code for row in rows]
    if op == "colour":
        colour = p["colour"]
        if colour is not None:
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", text(colour)):
                raise ValueError("Choose a six-digit RGB colour")
            colour = colour.upper()
        if not db.update_item_colour(codes, colour):
            raise ValueError("Unable to update schedule colours")
    elif op == "update_rates":
        editor.owner.update_dependent_rates(db, schedules=codes)
    elif not db.update_qty(codes, text(p["rounding"])):
        raise ValueError("Unable to update schedule quantities")
    return


def _copy_items(editor, db, kind, p, table, resource):
    """Save the selected models in the editor clipboard without changing project rows."""
    ids = p.get("ids", [])
    if not isinstance(ids, list) or len(ids) > 1000:
        raise ValueError("Invalid selection")
    records = [table.get_by_id(int(identity)) for identity in ids if not str(identity).startswith("cat:")]
    if not records:
        raise ValueError("Select one or more items")
    if not resource:
        # GTK copies exactly the selected rows; a subitem keeps its parent
        # code so paste can place it under the selected heading.
        records.sort(key=tree_order)
        models = [db.get_item(row.code, modify_res_code=False) for row in records]
    else:
        models = [db.get_resource(row.code) for row in records]
    editor.clipboard = (kind, copy.deepcopy(models))
    return


def _paste_items(editor, kind, p, resource):
    """Paste a copy of the editor clipboard through the schedule or resource placement path."""
    if not editor.clipboard or editor.clipboard[0] != kind:
        raise ValueError("Copy items from this editor first")
    items = copy.deepcopy(editor.clipboard[1])
    local = p.get("_local_res_code")
    if local is not None and not (isinstance(local, str) and re.fullmatch(r"[0-9A-F]{1,16}", local)):
        raise ValueError("Invalid clipboard instance code")
    if resource:
        return editor.paste_resources(items, p)
    return editor.paste_schedule(items, p, local)


def _edit_category(editor, db, kind, op, p, category, resource, identity):
    """Rename, move or delete one category through the existing editor operations."""
    cat = category.get_by_id(int(identity[4:]))
    if op == "edit" and p["field"] == "description":
        method = db.update_resource_category if resource else db.update_schedule_category
        if not method(cat.description, text(p["value"])):
            raise ValueError("Category could not be renamed")
        return
    if op == "move":
        delta = p["delta"]
        if type(delta) is not int or delta not in (-1, 1):
            raise ValueError("Invalid direction")
        siblings = list(category.select().order_by(category.order, category.id))
        index = siblings.index(cat)
        other = index + delta
        if 0 <= other < len(siblings):
            target = siblings[other]
            category.update(order=target.order).where(category.id == cat.id).execute()
            category.update(order=cat.order).where(category.id == target.id).execute()
        return
    if op == "delete":
        return editor.delete_selection(kind, dict(p, ids=[identity]))
    raise ValueError("Unsupported category operation")


def _insert_or_duplicate(editor, db, kind, op, p, table, resource, row):
    """Build or copy a model, then reuse insertion defaults and placement."""
    data = p.get("data", {})
    code = (
        text(data.get("code", ""))
        or defaults(editor, kind, dict(p, category=data.get("category"), parent=data.get("parent")))["code"]
    )
    if not code or table.select().where(table.code == code).exists():
        raise ValueError("Choose a new code")
    if op == "duplicate" and row:
        item = db.get_resource(row.code) if resource else db.get_item(row.code, modify_res_code=False)
        item.code = code
    elif resource:
        item = ResourceItemModel(
            code,
            text(data.get("description", "")),
            text(data.get("unit", "")),
            decimal(data.get("rate", "0")),
            decimal(data.get("vat", "0")),
            decimal(data.get("discount", "0")),
            text(data.get("reference", "")),
            text(data.get("category", "")),
        )
    else:
        parent = text(data.get("parent", "")) or None
        if parent and not table.select().where(table.code == parent).exists():
            raise ValueError("Parent schedule item not found")
        item = ScheduleItemModel(
            code,
            text(data.get("description", "")),
            text(data.get("unit", "")),
            decimal(data.get("rate", "0")),
            decimal(data.get("qty", "0")),
            category=text(data.get("category", "")),
            parent=parent,
        )
    method = db.insert_resource if resource else editor.insert_schedule_item
    prepare(editor, kind, item, p)
    if not method(item):
        raise ValueError("Item could not be inserted")
    place(editor, kind, [item.code], p)
    return dict(selected=[str(table.get(code=item.code).id)])


def _move_item(editor, db, p, table, resource, row):
    """Move an item among its siblings, preserving a schedule parent's child rows."""
    delta = p["delta"]
    if type(delta) is not int or delta not in (-1, 1):
        raise ValueError("Invalid direction")
    if resource:
        siblings = list(table.select().where(table.category == row.category).order_by(table.order, table.id))
        index = siblings.index(row)
        new = index + delta
        if 0 <= new < len(siblings):
            next(db.update_resource_path(row.code, [row.category.order, siblings[new].order - (1 if delta < 0 else 0)]))
    else:
        siblings = list(
            table.select()
            .where((table.category == row.category) & (table.parent == row.parent_id))
            .order_by(table.suborder if row.parent_id else table.order, table.id)
        )
        index = siblings.index(row)
        new = index + delta
        if 0 <= new < len(siblings):
            other = siblings[new]
            if row.parent_id:
                table.update(suborder=other.suborder).where(table.id == row.id).execute()
                table.update(suborder=row.suborder).where(table.id == other.id).execute()
            else:
                table.update(order=other.order).where((table.id == row.id) | (table.parent == row.id)).execute()
                table.update(order=row.order).where((table.id == other.id) | (table.parent == other.id)).execute()
            editor.normalize_schedule_order({row.category_id})
    return


def _update_item(editor, db, p, table, category, resource, row):
    """Validate and apply one editable field through the shared engine."""
    field = p["field"]
    value = p["value"]
    if field == "code" and (not value or table.select().where((table.code == value) & (table.id != row.id)).exists()):
        raise ValueError("Choose an unused code")
    if field in ("rate", "vat", "discount"):
        value = Currency(decimal(value), 4 if field == "vat" else 2)
    elif field == "qty":
        value = round(decimal(value), 4)
    else:
        value = text(value)
    if not resource and field in ("category", "parent"):
        if field == "parent":
            parent = table.get_or_none(table.code == value) if value else None
            if value and parent is None:
                raise ValueError("Parent not found")
            return editor.relocate_schedule(row, parent, row.category_id)
        destination = category.get_or_none(category.description == value)
        if destination is None:
            if db.insert_schedule_category_atomic(value, [-1]) is False:
                raise ValueError("Unable to create schedule category")
            destination = category.get(description=value)
        if row.category_id != destination.id:
            editor.relocate_schedule(row, None, destination.id)
        return
    if field in ("category", "parent"):
        if field == "parent":
            raise ValueError("Resources do not have parents")
        item = db.get_resource(row.code)
        item.category = value or None
        result = db.update_resource(row.code, res_model=item)
    else:
        columns = (
            ["code", "description", "unit", "rate", "vat", "discount", "reference"]
            if resource
            else ["code", "description", "unit", "rate", "qty", None, "remarks"]
        )
        if field not in columns:
            raise ValueError("Field is not editable")
        result = (
            db.update_resource(row.code, newvalue=value, column=columns.index(field))
            if resource
            else db.update_item_schedule(row.code, value, columns.index(field))
        )
    if not result:
        raise ValueError("Update rejected by database")
    if resource and field in ("rate", "vat", "discount"):
        editor.owner.update_dependent_rates(db, resources={row.code})
