"""Record-level edits using the active measurement draft or project transaction."""

import copy
from uuid import uuid4

from estimator import misc
from estimator.data import measurement

from .importing import selected_rows
from .numbers import decimal
from .validation import text


def edit(editor, meas, item, op, p):
    """Update record values and identities together; the caller owns rollback."""
    # Step 1: resolve record identities before applying single or multi-row edits.
    result = {}
    if not isinstance(item, measurement.MeasurementItemCustom):
        raise ValueError("Select a custom measurement item")
    ids = editor.record_ids[p["id"]]
    record_index = ids.index(p["record_id"]) if p.get("record_id") in ids else None
    selection = p.get("record_ids")
    if selection:
        if (
            not isinstance(selection, list)
            or len(selection) > 1000
            or any(identity not in ids for identity in selection)
        ):
            raise ValueError("Select existing measurement records")
        indexes = [index for index, identity in enumerate(ids) if identity in selection]
        record_index = indexes[-1]
        if op in ("record_delete", "record_duplicate", "record_move"):
            if op == "record_delete":
                for index in reversed(indexes):
                    item.remove_record(index)
                    ids.pop(index)
            elif op == "record_duplicate":
                pos = indexes[-1] + 1
                item.records[pos:pos] = [copy.deepcopy(item.records[index]) for index in indexes]
                ids[pos:pos] = [uuid4().hex for _ in indexes]
            else:
                delta = p.get("delta")
                if type(delta) is not int or delta not in (-1, 1):
                    raise ValueError("Invalid move")
                for index in indexes if delta < 0 else reversed(indexes):
                    other = index + delta
                    if 0 <= other < len(ids) and ids[other] not in selection:
                        item.records[index], item.records[other] = item.records[other], item.records[index]
                        ids[index], ids[other] = ids[other], ids[index]
            editor.set_measurement(meas)
            return
    # Step 2: preserve raw expressions on copy; validate new values before insertion.
    if op == "record_copy":
        if record_index is None:
            raise ValueError("Select a record")
        editor.clipboard = ("records", item.itemtype, copy.deepcopy(item.records[record_index].data_string))
        return
    if op == "record_import":
        fields = [i for i, kind in enumerate(item.columntypes) if kind != misc.MEAS_CUST]
        records = selected_rows(p, len(fields), cached=True)
        pos = record_index + 1 if record_index is not None else len(item.records)
        imported = 0
        for values in records:
            if all(value is None for value in values):
                continue
            raw = [""] * len(item.columntypes)
            for column, value in zip(fields, values):
                if value is not None:
                    raw[column] = text(str(value))
                    if item.columntypes[column] in (misc.MEAS_L, misc.MEAS_NO):
                        decimal(raw[column])
            item.insert_record(
                pos, measurement.RecordCustom(raw, item.cust_funcs, item.total_func_item, item.columntypes)
            )
            ids.insert(pos, uuid4().hex)
            pos += 1
            imported += 1
        if not imported:
            raise ValueError("No measurement records found in the selected range")
        editor.set_measurement(meas)
        return dict(imported=imported)
    if op == "record_paste":
        if not editor.clipboard or editor.clipboard[:2] != ("records", item.itemtype):
            raise ValueError("Copy a record from the same measurement template first")
        pos = record_index + 1 if record_index is not None else len(item.records)
        records = editor.clipboard[2] if len(editor.clipboard) == 4 else [editor.clipboard[2]]
        item.records[pos:pos] = [
            measurement.RecordCustom(copy.deepcopy(raw), item.cust_funcs, item.total_func_item, item.columntypes)
            for raw in records
        ]
        ids[pos:pos] = [uuid4().hex for _ in records]
        result = dict(selected_records=ids[pos : pos + len(records)], record_offset=pos // 100 * 100)
    elif op in ("record_add", "record_duplicate"):
        count = p.get("count", 1) if op == "record_add" else 1
        if type(count) is not int or not 1 <= count <= 1000:
            raise ValueError("Insert between 1 and 1000 records")
        if op == "record_duplicate" and record_index is None:
            raise ValueError("Select a record")
        values = (
            [""] * item.model_width() if op == "record_add" else copy.deepcopy(item.records[record_index].data_string)
        )
        pos = record_index + 1 if record_index is not None else len(item.records)
        item.records[pos:pos] = [
            measurement.RecordCustom(list(values), item.cust_funcs, item.total_func_item, item.columntypes)
            for _ in range(count)
        ]
        ids[pos:pos] = [uuid4().hex for _ in range(count)]
        result = dict(selected_records=ids[pos : pos + count], record_offset=pos // 100 * 100)
    elif op == "record_delete":
        if record_index is None:
            raise ValueError("Select a record")
        item.remove_record(record_index)
        ids.pop(record_index)
    elif op == "record_move":
        delta = p["delta"]
        if type(delta) is not int or delta not in (-1, 1) or record_index is None:
            raise ValueError("Invalid move")
        other = record_index + delta
        if 0 <= other < len(ids):
            item.records[record_index], item.records[other] = (item.records[other], item.records[record_index])
            ids[record_index], ids[other] = ids[other], ids[record_index]
    elif op == "record_edit":
        field = p["field"]
        col = int(field[1:]) if isinstance(field, str) and field.startswith("c") else -1
        if record_index is None or not 0 <= col < item.model_width() or item.columntypes[col] == misc.MEAS_CUST:
            raise ValueError("Cell is not editable")
        value = text(p["value"])
        if value and item.columntypes[col] in (misc.MEAS_L, misc.MEAS_NO):
            decimal(value)
        values = copy.deepcopy(item.records[record_index].data_string)
        values[col] = value
        item.records[record_index] = measurement.RecordCustom(
            values, item.cust_funcs, item.total_func_item, item.columntypes
        )
    else:
        raise ValueError("Unknown record operation")

    # Step 3: store values and identities together in the caller's draft or transaction.
    editor.set_measurement(meas)
    editor.ensure_ids(meas)
    return result
