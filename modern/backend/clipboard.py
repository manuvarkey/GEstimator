"""Bounded, versioned row transfer. Never deserialize executable Python objects."""

import json
import re
from pathlib import Path

from estimator import misc
from estimator.data import measurement
from estimator.data.schedule import ResourceItemModel, ScheduleItemModel

from .insertion import insert_categories
from .numbers import decimal, stored_decimal
from .program_settings import legacy_rows, template_rows
from .validation import MAX_TEXT_LENGTH

FORMAT = "org.gestimator.rows"
KINDS = ("analysis", "schedule", "resources", "measurement", "records")
MAX_TEXT = 500_000


def text(value):
    if not isinstance(value, str) or len(value) > MAX_TEXT_LENGTH:
        raise ValueError(f"Clipboard fields must be text of at most {MAX_TEXT_LENGTH} characters")
    return value


def array(value, limit=1000):
    if not isinstance(value, list) or len(value) > limit:
        raise ValueError("Clipboard row limit exceeded or invalid row list")
    return value


def obj(value):
    if not isinstance(value, dict):
        raise ValueError("Invalid clipboard row")
    return value


def resource_data(resource):
    return {
        key: str(getattr(resource, key) or ("0" if key in ("rate", "vat", "discount") else ""))
        for key in ("code", "description", "unit", "rate", "vat", "discount", "reference", "category")
    }


def resource_model(data):
    data = obj(data)
    code = text(data.get("code"))
    if not code:
        raise ValueError("A copied resource must have a code")
    return ResourceItemModel(
        code,
        text(data.get("description", "")),
        text(data.get("unit", "")),
        stored_decimal(data.get("rate", "0")),
        stored_decimal(data.get("vat", "0")),
        stored_decimal(data.get("discount", "0")),
        text(data.get("reference", "")),
        text(data.get("category", "")),
    )


def analysis_data(item):
    row = template_rows([item])[0]
    row["code"] = row["code"] or ""
    row["description"] = row["description"] or ""
    if item["itemtype"] == 0:
        row["resources"] = [[entry[0], str(entry[1]), entry[2] or ""] for entry in item["resource_list"]]
    return row


def analysis_model(data, resources):
    data = obj(data)
    row = legacy_rows([data], parse_number=stored_decimal)[0]
    if row["itemtype"] == 0:
        for entry in array(data.get("resources", [])):
            if not isinstance(entry, list) or len(entry) != 3:
                raise ValueError("Invalid copied resource entry")
            code, quantity, remarks = text(entry[0]), stored_decimal(entry[1]), text(entry[2])
            if code not in resources:
                raise ValueError("Copied analysis is missing a resource definition")
            row["resource_list"].append([code, quantity, remarks])
    return row


def schedule_data(item):
    fields = {
        key: str(getattr(item, key) or ("0" if key in ("rate", "qty") else ""))
        for key in (
            "code",
            "description",
            "unit",
            "rate",
            "qty",
            "category",
            "parent",
            "remarks",
            "ana_remarks",
            "colour",
        )
    }
    return dict(
        **fields,
        analysis=[analysis_data(row) for row in item.ana_items],
        resources=[resource_data(resource) for resource in item.resources.values()],
    )


def schedule_model(data):
    data = obj(data)
    code = text(data.get("code"))
    if not code:
        raise ValueError("A copied schedule item must have a code")
    colour = text(data.get("colour", ""))
    if colour and not re.fullmatch(r"#[0-9a-fA-F]{6}", colour):
        raise ValueError("Invalid copied row colour")
    model = ScheduleItemModel(
        code,
        text(data.get("description", "")),
        text(data.get("unit", "")),
        stored_decimal(data.get("rate", "0")),
        stored_decimal(data.get("qty", "0")),
        category=text(data.get("category", "")),
        parent=text(data.get("parent", "")) or None,
        remarks=text(data.get("remarks", "")),
        ana_remarks=text(data.get("ana_remarks", "")),
        colour=colour or None,
    )
    resources = [resource_model(value) for value in array(data.get("resources", []))]
    model.resources = {value.code: value for value in resources}
    if len(model.resources) != len(resources):
        raise ValueError("Duplicate copied resource definitions")
    model.ana_items = [analysis_model(row, model.resources) for row in array(data.get("analysis", []))]
    model.evaluate_results()
    return model


def custom_template(code):
    code = text(code)
    allowed = {path.stem for path in Path(misc.abs_path("meas_templates")).glob("*.py") if path.name != "__init__.py"}
    if code not in allowed:
        raise ValueError("Unknown clipboard measurement template")
    return measurement.MeasurementItemCustom(plugin=code)


def record_values(values, item):
    values = array(values, 100)
    if len(values) != len(item.columntypes):
        raise ValueError("Clipboard record width does not match its template")
    result = []
    for value, kind in zip(values, item.columntypes):
        value = text(value)
        if value and kind in (misc.MEAS_L, misc.MEAS_NO):
            decimal(value)
        result.append("" if kind == misc.MEAS_CUST else value)
    return result


def measurement_data(item, db):
    if isinstance(item, measurement.MeasurementItemHeading):
        return dict(heading=True, description=item.remark)
    return dict(
        heading=False,
        template=item.itemtype,
        description=item.remark,
        links=[db.get_item_code(key) or "" if key is not None else "" for key in item.itemnos],
        remarks=item.item_remarks,
        user_data=[str(value) for value in item.user_data],
        records=[record.data_string for record in item.records],
    )


def measurement_model(data, db):
    data = obj(data)
    if type(data.get("heading")) is not bool:
        raise ValueError("Invalid clipboard measurement type")
    if data["heading"]:
        return measurement.MeasurementItemHeading([text(data.get("description", ""))]), 0
    item = custom_template(data.get("template"))
    links, remarks, user_data = (array(data.get(key), 100) for key in ("links", "remarks", "user_data"))
    if (
        len(links) != len(item.itemnos)
        or len(remarks) != len(item.item_remarks)
        or len(user_data) != len(item.user_data)
    ):
        raise ValueError("Clipboard measurement metadata does not match its template")
    item.remark = text(data.get("description", ""))
    links = [text(code) for code in links]
    item.itemnos = [db.get_item_key(code) if code else None for code in links]
    item.item_remarks = [text(value) for value in remarks]
    item.user_data = [text(value) for value in user_data]
    for value, kind in zip(item.user_data, item.columntypes_udata):
        if kind in (misc.MEAS_L, misc.MEAS_NO):
            decimal(value)
    for values in array(data.get("records", [])):
        item.append_record(
            measurement.RecordCustom(
                record_values(values, item), item.cust_funcs, item.total_func_item, item.columntypes
            )
        )
    return item, sum(bool(code) and key is None for code, key in zip(links, item.itemnos))


def order(row):
    ancestors, seen, current = [], set(), row
    while current and current.id not in seen:
        seen.add(current.id)
        ancestors.append(current.suborder if current.parent_id else current.order)
        current = current.parent
    return row.category.order, tuple(reversed(ancestors)), row.id


def export(service, params):
    if params.get("source"):
        raise ValueError("Import library rows into the project before copying them")
    kind = params.get("kind")
    if kind not in KINDS:
        raise ValueError("Unknown clipboard kind")
    categories, dependencies = [], []
    if kind == "analysis":
        service.edit("copy", params)
        items = []
        for entry in service.clipboard:
            if entry[0] == "ana_item":
                items.append(dict(type="row", row=analysis_data(entry[1])))
            else:
                items.append(
                    dict(
                        type="resource",
                        entry=[entry[1][0], str(entry[1][1]), entry[1][2] or ""],
                        resource=resource_data(entry[2]),
                    )
                )
    else:
        if not service.db:
            raise ValueError("Open a project first")
        service.guard_draft(params, records=not service.project_editor.records_operation("clipboard.export", params))
        editor = service.project_editor
        if kind in ("schedule", "resources"):
            # GTK copies only the selected rows; selected categories bring their contents.
            cats, records = editor.selection(kind, params.get("ids"), include_descendants=False)
            categories = [cat.description for cat in sorted(cats, key=lambda cat: (cat.order, cat.id))]
            records.sort(key=order if kind == "schedule" else lambda row: (row.category.order, row.order, row.id))
            models = [
                (
                    service.db.get_item(row.code, modify_res_code=False)
                    if kind == "schedule"
                    else service.db.get_resource(row.code)
                )
                for row in records
            ]
            items = [schedule_data(model) if kind == "schedule" else resource_data(model) for model in models]
            if kind == "schedule":
                visited = {model.code for model in models}
                pending = [code for model in models for code in model.resources]
                while pending:
                    code = pending.pop()
                    if code in visited:
                        continue
                    visited.add(code)
                    model = service.db.get_item(code, modify_res_code=False)
                    if model:
                        dependencies.append(schedule_data(model))
                        pending.extend(model.resources)
                    if len(visited) > 10000:
                        raise ValueError("Copied sub-analysis graph is too large")
        else:
            editor.ensure_ids()
            measurement_items = editor.get_measurement().items
            if kind == "measurement":
                ids = array(params.get("ids"))
                if any(identity not in editor.ids for identity in ids):
                    raise ValueError("Select existing measurement items")
                items = [
                    measurement_data(item, service.db)
                    for identity, item in zip(editor.ids, measurement_items)
                    if identity in ids
                ]
            else:
                if params.get("id") not in editor.ids:
                    raise ValueError("Select a measurement item")
                item = measurement_items[editor.ids.index(params["id"])]
                ids = editor.record_ids.get(params["id"], [])
                selected = params.get("record_ids") or [params.get("record_id")]
                if not isinstance(selected, list) or not selected or any(identity not in ids for identity in selected):
                    raise ValueError("Select a measurement record")
                items = [
                    dict(template=item.itemtype, values=record.data_string)
                    for identity, record in zip(ids, item.records)
                    if identity in selected
                ]
    if len(items) > 1000 or len(dependencies) > 1000:
        raise ValueError("Selection is too large for the system clipboard; copy fewer rows")
    if not items and not categories:
        raise ValueError("Select one or more rows to copy")
    document = dict(format=FORMAT, version=1, kind=kind, items=items, categories=categories, dependencies=dependencies)
    if kind == "schedule":
        document["instance"] = service.instance_code()
    if kind == "resources" and params.get("cut"):
        # GTK ResourceView.cut_selection: a reference that moves the resources
        # on paste within the same project.
        codes = [item["code"] for item in items]
        if not codes:
            raise ValueError("Select resources to cut")
        document["instance"] = service.instance_code()
        document["cut"] = codes
    data = json.dumps(document, ensure_ascii=False)
    if len(data) > MAX_TEXT:
        raise ValueError("Selection is too large for the system clipboard; copy fewer rows")
    return data


def decode(data, expected, service):
    if not isinstance(data, str) or len(data) > MAX_TEXT:
        raise ValueError("Clipboard data exceeds the supported size")
    try:
        document = json.loads(
            data, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Invalid clipboard number"))
        )
    except (ValueError, RecursionError) as error:
        raise ValueError("Clipboard does not contain valid GEstimator rows") from error
    document = obj(document)
    if document.get("format") != FORMAT or type(document.get("version")) is not int or document["version"] != 1:
        raise ValueError("Unsupported GEstimator clipboard format or version")
    kind = document.get("kind")
    if kind != expected or kind not in KINDS:
        raise ValueError("Clipboard rows belong to a different editor")
    values = array(document.get("items"))
    categories = list(dict.fromkeys(text(value) for value in array(document.get("categories", []))))
    if kind not in ("schedule", "resources") and categories:
        raise ValueError("Categories cannot be pasted into this editor")
    if kind != "schedule" and array(document.get("dependencies", [])):
        raise ValueError("Sub-analysis definitions belong to schedule rows")
    if not values and not categories:
        raise ValueError("Clipboard contains no rows")
    dependencies, missing = [], 0
    if kind == "analysis":
        items = []
        for value in values:
            value = obj(value)
            if value.get("type") == "row":
                items.append(["ana_item", analysis_model(value.get("row"), {})])
            elif value.get("type") == "resource":
                resource = resource_model(value.get("resource"))
                entry = array(value.get("entry"), 3)
                if len(entry) != 3 or text(entry[0]) != resource.code:
                    raise ValueError("Invalid clipboard resource entry")
                items.append(["resource_item", [resource.code, stored_decimal(entry[1]), text(entry[2])], resource])
            else:
                raise ValueError("Unknown clipboard analysis row")
    elif kind == "resources":
        items = [resource_model(value) for value in values]
    elif kind == "schedule":
        items = [schedule_model(value) for value in values]
        codes = {item.code for item in items}
        if len(codes) != len(items):
            raise ValueError("Duplicate copied schedule codes")
        # Keep the copied order (GTK pastes rows in sequence) and each parent
        # code: a subitem copied without its parent still pastes as a subitem.
        parents = {item.code: item.parent for item in items}
        for item in items:
            seen, current = {item.code}, item.parent
            while current in parents:
                if current in seen:
                    raise ValueError("Copied schedule hierarchy contains a cycle")
                seen.add(current)
                current = parents[current]
        dependencies = [schedule_model(value) for value in array(document.get("dependencies", []))]
        dependency_codes = {item.code for item in dependencies}
        if len(dependency_codes) != len(dependencies) or dependency_codes.intersection(codes):
            raise ValueError("Duplicate copied sub-analysis definitions")
    elif kind == "measurement":
        decoded = [measurement_model(value, service.db) for value in values]
        items = [item for item, _ in decoded]
        missing = sum(count for _, count in decoded)
    else:
        first = obj(values[0])
        item = custom_template(first.get("template"))
        if any(obj(value).get("template") != item.itemtype for value in values):
            raise ValueError("Copied records must use the same measurement template")
        items = (item.itemtype, [record_values(value.get("values"), item) for value in values])
    instance = document.get("instance") if kind in ("schedule", "resources") else None
    if instance is not None and not (isinstance(instance, str) and re.fullmatch(r"[0-9A-F]{1,16}", instance)):
        raise ValueError("Invalid clipboard instance code")
    cut = document.get("cut")
    if cut is not None:
        cut = [text(code) for code in array(cut)]
        if kind != "resources" or not cut:
            raise ValueError("Invalid cut clipboard")
    return kind, items, categories, dependencies, missing, (instance, cut)


def paste_categories(editor, kind, params, categories, items):
    """Create independent category copies and route their contents to them."""
    if not categories:
        return []
    inserted = insert_categories(editor, kind, categories, params, from_clipboard=True)
    original_categories = {item.code: item.category for item in items} if kind == "schedule" else {}
    for item in items:
        if item.category in inserted:
            # A category copy can only inherit schedule parents copied with it.
            if kind == "schedule" and original_categories.get(item.parent) != item.category:
                item.parent = None
            item.category = inserted[item.category].description
    return [f"cat:{row.id}" for row in inserted.values()]


def paste(service, params):
    kind = params.get("kind")
    if params.get("source"):
        raise ValueError("Library snapshots are read-only")
    if kind != "analysis" and not service.db:
        raise ValueError("Open a project first")
    kind, items, categories, dependencies, missing, (instance, cut) = decode(params.get("data"), kind, service)
    if cut is not None:
        if instance != service.instance_code():
            raise ValueError("Cut resources can only be pasted in the project they were cut from")
        service.guard_draft(params)
        result = service.project_editor.mutate(lambda: service.project_editor.move_resources(cut, params))
        return dict(ok=True, moved=True, **result)
    # GTK: rows from another project keep their own resources under
    # "<instance>.<code>" instead of merging with same-coded local ones.
    local = instance if instance and instance != service.instance_code() else None
    if kind == "analysis":
        previous = service.clipboard
        try:
            service.clipboard = items
            return service.call("paste", params)
        except Exception:
            service.clipboard = previous
            raise
    service.guard_draft(params, records=not service.project_editor.records_operation("clipboard.paste", params))
    editor = service.project_editor
    previous = editor.clipboard

    def apply():
        if kind in ("schedule", "resources"):
            category_ids = paste_categories(editor, kind, params, categories, items)
            for dependency in dependencies:
                if local is not None and ":" not in dependency.code:
                    dependency.code = local + "." + dependency.code
                existing = service.db.get_item(dependency.code, copy_ana=False)
                # Same project: the referenced item is already here (any category); reuse it.
                if existing and local is None:
                    continue
                if existing and existing.category != misc.SUB_ANA_TITLE:
                    raise ValueError("Copied sub-analysis conflicts with schedule item " + dependency.code)
                if not existing:
                    dependency.category, dependency.parent = misc.SUB_ANA_TITLE, None
                    if not service.db.insert_item_atomic(dependency, local_res_code=local):
                        raise ValueError("Unable to paste referenced sub-analysis")
            editor.clipboard = (kind, items)
            if items:
                result = editor.edit(
                    kind, "paste", dict(params, preserve_categories=bool(categories), _local_res_code=local)
                )
                return dict(result, selected=category_ids + result["selected"])
            return dict(selected=category_ids)
        elif kind == "measurement":
            editor.clipboard = (kind, items)
            return editor.measurement_edit("paste", params)
        else:
            editor.clipboard = ("records", *items, "batch")
            return editor.measurement_edit("record_paste", params)

    try:
        result = (editor.records_mutate if editor.records_operation("clipboard.paste", params) else editor.mutate)(
            apply
        )
    except Exception:
        editor.clipboard = previous
        raise
    return dict(ok=True, unlinked=missing, **(result or {}))
