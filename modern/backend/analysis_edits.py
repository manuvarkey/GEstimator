"""Edits to the active analysis draft; Service owns acceptance and history."""

import copy
from decimal import Decimal
from uuid import uuid4

from estimator import misc
from estimator.data.schedule import Currency, ResourceItemModel

from .analysis_import import import_analysis
from .numbers import decimal
from .program_settings import legacy_rows
from .validation import request_text as text


def edit(service, method, p):
    """Edit the current draft within the caller's rollback and history boundary."""
    # Step 1: route operations that accept an insertion point or a selection.
    if method == "analysis.resources_add":
        return _add_selected_resources(service, p)
    if method == "analysis.batch":
        return _edit_batch(service, p)
    if method == "analysis.insert_template":
        return _insert_template(service, p)
    if method == "analysis.import_xlsx":
        return _import_workbook(service, p)
    if method == "analysis.edit":
        if p["field"] != "ana_remarks":
            raise ValueError("Unknown analysis field")
        service.model.ana_remarks = text(p["value"])
        return
    if method == "add":
        return _add_calculation_row(service, p)
    if method in ("resource.add", "resource.duplicate"):
        return _insert_resource(service, method, p)
    if method in ("copy", "delete", "duplicate", "paste"):
        return _edit_selection(service, method, p)
    # Step 2: resolve a single target for move and field edits.
    i, j = service.locate(p["id"])
    row = service.model.ana_items[i]
    if method == "move":
        return _move_row(service, p, i, j, row)
    if method != "edit":
        raise ValueError("Unknown operation")
    return _edit_field(service, p, j, row)


def _add_selected_resources(service, p):
    """Insert selected library or project resources in source order."""
    if not service.db:
        raise ValueError("Open a project first")
    source_id = p.get("source")
    if source_id and source_id not in service.project_editor.libraries:
        raise ValueError("Resource database is no longer attached")
    source = service.project_editor.libraries[source_id][1] if source_id else service.db
    _, rows = service.project_editor.selection("resources", p.get("ids"), source, include_descendants=False)
    index, child = service.locate(p.get("id"))
    group = service.model.ana_items[index]
    if group["itemtype"] != 0:
        raise ValueError("Select a resource group")
    prefix = source.get_project_settings().get("project_resource_code", "") if source is not service.db else ""
    quantity = decimal(p.get("qty", "0"))
    entries, identities = [], []
    for row in sorted(rows, key=lambda row: (row.category.order, row.order, row.id)):
        resource = source.get_resource(row.code, modify_code=bool(prefix))
        if resource is None:
            raise ValueError("Unknown resource")
        resource = service.model.resources.get(resource.code) or service.db.get_resource(resource.code) or resource
        service.model.resources[resource.code] = resource
        entries.append([resource.code, quantity, ""])
        identities.append(uuid4().hex)
    position = child + 1 if child is not None else 0
    group["resource_list"][position:position] = entries
    group["_resource_ids"][position:position] = identities
    return


def _edit_batch(service, p):
    """Apply draft edits in order, advancing the insertion cursor after each added row."""
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
            position = service.locate(cursor)[0] + 1 if cursor else 0
            service.edit(action, params)
            cursor = service.model.ana_items[position]["_id"]
        else:
            service.edit(action, params)
    return


def _insert_template(service, p):
    """Insert a configured or default calculation template."""
    position = service.locate(p["id"])[0] + 1 if p.get("id") else 0
    if "rows" in p:
        rows = legacy_rows(p["rows"])
    else:
        rows = copy.deepcopy(misc.ana_default_add_items)
    for row in rows:
        if "value" in row:
            row["value"] = Decimal(str(row["value"]))
    service.model.ana_items[position:position] = rows
    service.identify()
    return


def _import_workbook(service, p):
    """Replace draft rows and resources with the worksheet import."""
    if not service.loaded:
        raise ValueError("Load an analysis first")
    draft = import_analysis(service.model, p)
    service.model.ana_items = draft.ana_items
    service.model.resources = draft.resources
    service.model.ana_remarks = draft.ana_remarks or service.model.ana_remarks
    service.identify()
    return


def _add_calculation_row(service, p):
    """Add a validated calculation row at the draft cursor."""
    kind = p["kind"]
    description = text(p.get("description", kind))
    pos = service.locate(p["id"])[0] + 1 if p.get("id") else 0
    if kind == "Group":
        service.model.add_ana_group(description, code=text(p.get("code", "")), pos=pos)
    elif kind == "Subtotal":
        service.model.add_ana_sum(description, pos=pos)
    elif kind in ("Weight", "Multiply", "Round"):
        value = decimal(p["value"])
        if kind == "Round" and (abs(value) > 12 or (value != int(value) and int((value - int(value)) * 10) == 0)):
            raise ValueError("Use rounding places from -12 to 12 with a non-zero tenth for interval rounding")
        {
            "Weight": service.model.add_ana_weight,
            "Multiply": service.model.add_ana_times,
            "Round": service.model.add_ana_round,
        }[kind](description, value, pos=pos)
    else:
        raise ValueError("Unknown row kind")
    service.identify()
    return


def _insert_resource(service, method, p):
    """Resolve a resource definition and insert its use and row identity together."""
    i, child = service.locate(p["id"])
    group = service.model.ana_items[i]
    if group["itemtype"] != 0:
        raise ValueError("Select a resource group")
    if method == "resource.duplicate":
        if child is None:
            raise ValueError("Select a resource entry to duplicate")
        resource = copy.deepcopy(service.model.resources[group["resource_list"][child][0]])
        resource.code = text(p["code"])
        if (
            not resource.code
            or resource.code in service.model.resources
            or (service.db and service.db.get_resource(resource.code))
        ):
            raise ValueError("Choose an unused resource code")
    elif p.get("library"):
        if not service.db:
            raise ValueError("Open a project first")
        source = (
            service.project_editor.libraries[p["source"]][1]
            if p.get("source") in service.project_editor.libraries
            else service.db
        )
        prefix = source.get_project_settings().get("project_resource_code", "") if source is not service.db else ""
        resource = source.get_resource(text(p["code"]), modify_code=bool(prefix))
        if resource:
            resource = service.model.resources.get(resource.code) or service.db.get_resource(resource.code) or resource
        if resource is None:
            raise ValueError("Unknown resource")
    else:
        code = text(p.get("code", ""))
        if not code:
            code = service.db.get_new_resource_code(exclude=service.model.resources) if service.db else "MR.1"
            while code in service.model.resources:
                code = "MR." + str(int(code.split(".")[-1]) + 1)
        if code in service.model.resources:
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
    service.model.resources[resource.code] = resource
    pos = child + 1 if child is not None else 0
    service.model.add_ana_res([resource.code, decimal(p.get("qty", "0")), text(p.get("remarks", ""))], i, pos)
    group["_resource_ids"].insert(pos, uuid4().hex)
    return


def _edit_selection(service, method, p):
    """Copy, remove or insert selected rows using the service clipboard."""
    ids = p.get("ids", [])
    if not isinstance(ids, list) or len(ids) > 1000:
        raise ValueError("Invalid selection")
    locations = sorted(set(service.locate(x) for x in ids), key=lambda x: (x[0], -1 if x[1] is None else x[1]))
    if method in ("copy", "duplicate"):
        service.clipboard = []
        for i, j in locations:
            entry = copy.deepcopy(service.model.get_item([i] if j is None else [i, j], deep=False))
            service.clipboard.append(entry)
    if method == "delete":
        locations = [x for x in locations if x[1] is None or (x[0], None) not in locations]
        for i, j in reversed(locations):
            service.model.delete_item([i] if j is None else [i, j])
            if j is not None:
                service.model.ana_items[i]["_resource_ids"].pop(j)
    if method in ("paste", "duplicate"):
        i, j = service.locate(p["id"]) if p.get("id") else (-1, None)
        for entry in service.clipboard:
            if entry[0] == "ana_item":
                row = copy.deepcopy(entry[1])
                row["_id"] = uuid4().hex
                if row["itemtype"] == 0:
                    row["_resource_ids"] = []
                i += 1
                j = None
                service.model.ana_items.insert(i, row)
            else:
                if i < 0 or service.model.ana_items[i]["itemtype"] != 0:
                    raise ValueError("Select a destination resource group")
                j = 0 if j is None else j + 1
                service.model.resources.setdefault(
                    entry[2].code,
                    (service.db.get_resource(entry[2].code) if service.db else None) or copy.deepcopy(entry[2]),
                )
                service.model.add_ana_res(copy.deepcopy(entry[1]), i, j)
                service.model.ana_items[i]["_resource_ids"].insert(j, uuid4().hex)
    return


def _move_row(service, p, i, j, row):
    """Move a row within its current sequence, preserving resource identities."""
    delta = p["delta"]
    if type(delta) is not int or delta not in (-1, 1):
        raise ValueError("Invalid direction")
    values = service.model.ana_items if j is None else row["resource_list"]
    index = i if j is None else j
    target = index + delta
    if 0 <= target < len(values):
        values[index], values[target] = values[target], values[index]
        if j is not None:
            ids = row["_resource_ids"]
            ids[index], ids[target] = ids[target], ids[index]
    return


def _edit_field(service, p, j, row):
    """Apply one validated field to a calculation row or resource use."""
    field = p["field"]
    value = p["value"]
    if j is not None:
        resource = service.model.resources[row["resource_list"][j][0]]
        if field == "value":
            row["resource_list"][j][1] = decimal(value)
        elif field == "code":
            code = text(value)
            replacement = service.model.resources.get(code) or (service.db.get_resource(code) if service.db else None)
            if replacement is None:
                raise ValueError("Resource code not found")
            service.model.resources.setdefault(code, replacement)
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
        if row["itemtype"] == 4 and (abs(value) > 12 or (value != int(value) and int((value - int(value)) * 10) == 0)):
            raise ValueError("Unsupported rounding places")
        row[field] = value
    else:
        raise ValueError("Field is not editable")
