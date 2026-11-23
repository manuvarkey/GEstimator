"""Measurement views and edits; ProjectEditor owns transactions, drafts and undo.

These handlers use the existing measurement engine. They do not commit writes or
create a second history: callers choose the project or records-draft transaction.
"""

import copy
import re
from uuid import uuid4

from estimator import misc
from estimator.data import measurement

from . import measurement_records
from .importing import selected_rows
from .measurement_templates import column_title, link_label, metadata, property_groups
from .numbers import decimal
from .validation import text


def state(editor, p, detail_only=False):
    """Render list totals and an optional record page from the active draft."""
    # Step 1: align row identities with the current measurement model.
    meas = editor.get_measurement()
    editor.ensure_ids(meas)
    rows = []
    totals = {}
    for identity, item in [] if detail_only else zip(editor.ids, meas.items):
        heading = isinstance(item, measurement.MeasurementItemHeading)
        totals[identity] = [] if heading else [str(v) for v in item.get_total()]
        rows.append(
            dict(
                id=identity,
                description=item.remark,
                type="Heading" if heading else item.name,
                totals=(", ".join(totals[identity])),
                count=len(item.records),
            )
        )
    # Step 2: page records and load schedule links together, avoiding per-row queries.
    detail = None
    if p.get("id") in editor.ids:
        index = editor.ids.index(p["id"])
        item = meas.items[index]
        heading = isinstance(item, measurement.MeasurementItemHeading)
        if not heading:
            offset, limit = p.get("record_offset", 0), p.get("record_limit", 100)
            if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 200:
                raise ValueError("Invalid measurement record page")
            offset = min(offset, max(0, (len(item.records) - 1) // limit * limit))
            linked = {
                row.id: row
                for row in editor.db.ScheduleTable.select().where(
                    editor.db.ScheduleTable.id.in_([key for key in item.itemnos if key is not None])
                )
            }
            detail = dict(
                id=p["id"],
                description=item.remark,
                template=item.itemtype,
                info=metadata(item),
                offset=offset,
                total_records=len(item.records),
                property_groups=property_groups(item),
                columns=[
                    dict(
                        title=column_title(item, i),
                        field="c" + str(i),
                        editable=t != misc.MEAS_CUST,
                        width=item.dimensions[0][i],
                        expand=bool(item.dimensions[1][i]),
                        numeric=t in (misc.MEAS_L, misc.MEAS_NO),
                    )
                    for i, (cap, t) in enumerate(zip(item.captions, item.columntypes))
                ],
                rows=[
                    dict(
                        id=identity,
                        **{
                            "c" + str(i): str(value if value is not None else "")
                            for i, value in enumerate(record.get_model_rendered(n + 1))
                        },
                    )
                    for n, (identity, record) in enumerate(
                        zip(editor.record_ids[p["id"]][offset : offset + limit], item.records[offset : offset + limit]),
                        start=offset,
                    )
                ],
                links=[
                    dict(
                        code=linked[key].code if key in linked else "",
                        description=linked[key].description if key in linked else "",
                        unit=linked[key].unit if key in linked else "",
                        label=link_label(item, index),
                        missing=key is not None and key not in linked,
                        remark=remark,
                    )
                    for index, (key, remark) in enumerate(zip(item.itemnos, item.item_remarks))
                ],
                user_data=[
                    dict(caption=cap, value=str(value), numeric=kind in (misc.MEAS_L, misc.MEAS_NO))
                    for cap, value, kind in zip(item.captions_udata, item.user_data, item.columntypes_udata)
                ],
                totals=totals.get(p["id"]) or [str(v) for v in item.get_total()],
            )
            # Raw editable strings preserve measurement expressions and description text.
            for row, record in zip(detail["rows"], item.records[offset : offset + limit]):
                row["_display"] = {key: value for key, value in row.items() if key.startswith("c")}
                for i, t in enumerate(item.columntypes):
                    if t != misc.MEAS_CUST:
                        row["c" + str(i)] = record.data_string[i]
    result = dict(
        rows=rows,
        detail=detail,
        caption=meas.caption,
        revision=editor.owner.revision,
        undo=bool(editor.history),
        redo=bool(editor.future),
        measurement_draft=editor.measurement_draft.state() if editor.measurement_draft else None,
    )
    if detail_only:
        result.pop("rows")
    return result


def record_batch(editor, p, edits):
    """Validate all edited cells, then rebuild each affected record once."""
    # Step 1: resolve stable record IDs before accepting any cell edits.
    meas = editor.get_measurement()
    editor.ensure_ids(meas)
    if p.get("id") not in editor.ids:
        raise ValueError("Select a measurement item")
    item = meas.items[editor.ids.index(p["id"])]
    if not isinstance(item, measurement.MeasurementItemCustom):
        raise ValueError("Select a custom measurement item")
    indexes = {identity: index for index, identity in enumerate(editor.record_ids[p["id"]])}
    values = {}
    for edit in edits:
        if not isinstance(edit, dict) or edit.get("id") not in indexes:
            raise ValueError("Select an existing measurement record")
        index, field = indexes[edit["id"]], edit.get("field", "")
        column = int(field[1:]) if isinstance(field, str) and re.fullmatch(r"c\d+", field) else -1
        if not 0 <= column < item.model_width() or item.columntypes[column] == misc.MEAS_CUST:
            raise ValueError("Cell is not editable")
        value = text(edit["value"])
        if value and item.columntypes[column] in (misc.MEAS_L, misc.MEAS_NO):
            decimal(value)
        if index not in values:
            values[index] = list(item.records[index].data_string)
        values[index][column] = value
    # Step 2: publish complete records together; the caller rolls back on failure.
    for index, raw in values.items():
        item.records[index] = measurement.RecordCustom(raw, item.cust_funcs, item.total_func_item, item.columntypes)
    editor.set_measurement(meas)


def record_import_preview(editor, p):
    """Rows a record import would insert, under the template's column names."""
    meas = editor.get_measurement()
    editor.ensure_ids(meas)
    if p.get("id") not in editor.ids:
        raise ValueError("Select a measurement item")
    item = meas.items[editor.ids.index(p["id"])]
    if not hasattr(item, "columntypes"):
        raise ValueError("Headings have no records")
    fields = [i for i, kind in enumerate(item.columntypes) if kind != misc.MEAS_CUST]
    first = p.get("first_row", 1)
    rows = []
    for line, values in enumerate(selected_rows(p, len(fields), cached=True), first if type(first) is int else 1):
        if all(value is None for value in values):
            continue
        rows.append(
            dict(
                row=line,
                values=[
                    "" if value is None else ("%.12g" % value if isinstance(value, float) else str(value))
                    for value in values
                ],
            )
        )
    return dict(columns=[column_title(item, i) for i in fields], count=len(rows), rows=rows[:200])


def _insertion_index(meas, identities, params, *, category=False):
    """Insert after the last selected item, or after its whole group for a heading."""
    ids = params.get("ids") or ([params["id"]] if params.get("id") else [])
    positions = {identity: index for index, identity in enumerate(identities)}
    # The synthetic header is before the first stored item.
    positions["measurement:uncategorised"] = -1
    if not isinstance(ids, list) or any(not isinstance(identity, str) or identity not in positions for identity in ids):
        raise ValueError("Invalid measurement insertion selection")
    index = max((positions[identity] for identity in ids), default=-1) + 1
    if category:
        # A heading starts a group in the saved flat list. Insert at the next
        # boundary so existing items keep their current category.
        while index < len(meas.items) and not isinstance(meas.items[index], measurement.MeasurementItemHeading):
            index += 1
    return index


def _insert_items(editor, meas, params, items):
    """Insert rows with new stable identities inside the caller's mutation."""
    category = any(isinstance(item, measurement.MeasurementItemHeading) for item in items)
    pos = _insertion_index(meas, editor.ids, params, category=category)
    identities = [uuid4().hex for _ in items]
    for offset, (item, identity) in enumerate(zip(items, identities)):
        meas.insert_item(pos + offset, item)
        editor.ids.insert(pos + offset, identity)
    return dict(selected=identities)


def _edit_selection(editor, meas, *, item_index, op, params):
    """Copy or change a selection while retaining stable measurement identities."""
    result = {}
    ids = params.get("ids", [params.get("id")])
    if (
        not isinstance(ids, list)
        or not ids
        or any(not isinstance(identity, str) or identity not in editor.ids for identity in ids)
    ):
        raise ValueError("Select one or more measurement items")
    selection = set(ids)
    indexes = [position for position, identity in enumerate(editor.ids) if identity in selection]
    if op == "copy":
        editor.clipboard = ("measurement", [copy.deepcopy(meas.items[i]) for i in indexes])
        return
    if op == "duplicate":
        items = [copy.deepcopy(meas.items[i]) for i in indexes]
        result = _insert_items(editor, meas, params, items)
    elif op == "delete":
        for position in reversed(indexes):
            meas.remove_item(position)
            editor.record_ids.pop(editor.ids.pop(position), None)
    else:
        delta = params["delta"]
        if type(delta) is not int or delta not in (-1, 1):
            raise ValueError("Invalid move")
        if params.get("category"):
            starts = [i for i, row in enumerate(meas.items) if isinstance(row, measurement.MeasurementItemHeading)]
            if item_index not in starts:
                raise ValueError("Select a measurement category")
            sibling = starts.index(item_index) + delta
            if 0 <= sibling < len(starts):
                first, second = sorted((starts.index(item_index), sibling))
                a, b = starts[first], starts[second]
                end = starts[second + 1] if second + 1 < len(starts) else len(editor.ids)
                meas.items[a:end] = meas.items[b:end] + meas.items[a:b]
                editor.ids[a:end] = editor.ids[b:end] + editor.ids[a:b]
        else:
            for position in indexes if delta < 0 else reversed(indexes):
                other = position + delta
                if 0 <= other < len(editor.ids) and editor.ids[other] not in selection:
                    meas.items[position], meas.items[other] = meas.items[other], meas.items[position]
                    editor.ids[position], editor.ids[other] = editor.ids[other], editor.ids[position]
    editor.set_measurement(meas)
    editor.ensure_ids(meas)
    return result


def edit(editor, op, p):
    """Edit measurement items without owning their transaction or undo history."""
    # Step 1: resolve the current item from the draft-aware measurement model.
    meas = editor.get_measurement()
    editor.ensure_ids(meas)
    index = editor.ids.index(p["id"]) if p.get("id") in editor.ids else None
    item = meas.items[index] if index is not None else None
    # Step 2: apply the requested item operation, or delegate record-level work.
    result = {}
    if op in ("copy", "duplicate", "delete", "move"):
        return _edit_selection(editor, meas, item_index=index, op=op, params=p)
    if op == "paste":
        if not editor.clipboard or editor.clipboard[0] != "measurement":
            raise ValueError("Copy a measurement item first")
        items = copy.deepcopy(editor.clipboard[1])
        result = _insert_items(editor, meas, p, items)
    elif op == "caption":
        meas.caption = text(p["value"])
    elif op == "add":
        if p.get("template"):
            if p["template"] not in [r["code"] for r in editor.templates()]:
                raise ValueError("Unknown measurement template")
            new = measurement.MeasurementItemCustom(plugin=p["template"])
            new.remark = text(p.get("description", ""))
        else:
            new = measurement.MeasurementItemHeading([text(p.get("description", "Heading"))])
        result = _insert_items(editor, meas, p, [new])
    elif op == "properties":
        if item is None:
            raise ValueError("Select a measurement item")
        item.remark = text(p.get("description", item.remark))
        if isinstance(item, measurement.MeasurementItemCustom):
            links, user_data = p.get("links"), p.get("user_data")
            if (
                not isinstance(links, list)
                or len(links) != len(item.itemnos)
                or not isinstance(user_data, list)
                or len(user_data) != len(item.user_data)
            ):
                raise ValueError("Properties do not match the measurement template")
            for slot, link in enumerate(links):
                code = text(link["code"])
                key = editor.db.get_item_key(code) if code else None
                if code and key is None:
                    raise ValueError("Schedule code not found: " + code)
                item.itemnos[slot], item.item_remarks[slot] = key, text(link["remark"])
            item.user_data = [
                str(decimal(text(value))) if kind in (misc.MEAS_L, misc.MEAS_NO) else text(value)
                for value, kind in zip(user_data, item.columntypes_udata)
            ]
    elif op == "edit":
        if item is None:
            raise ValueError("Select a measurement item")
        item.remark = text(p["value"])
    elif op == "link":
        slot = p["slot"]
        if item is None or type(slot) is not int or not 0 <= slot < len(item.itemnos):
            raise ValueError("Invalid link slot")
        code = text(p.get("code", ""))
        key = editor.db.get_item_key(code) if code else None
        if code and key is None:
            raise ValueError("Schedule code not found")
        item.itemnos[slot] = key
        item.item_remarks[slot] = text(p.get("remark", ""))
    elif op == "userdata":
        slot = p["slot"]
        if item is None or type(slot) is not int or not 0 <= slot < len(item.user_data):
            raise ValueError("Invalid user-data slot")
        value = text(p["value"])
        if item.columntypes_udata[slot] in (misc.MEAS_L, misc.MEAS_NO):
            value = str(decimal(value))
        item.user_data[slot] = value
    elif op == "update_quantities":
        editor.db.update_qty(rounding=p.get("rounding", "Round to .000"))
        return
    elif op.startswith("record_"):
        return measurement_records.edit(editor, meas, item, op, p)
    else:
        raise ValueError("Unknown measurement operation")
    editor.set_measurement(meas)
    editor.ensure_ids(meas)
    return result
