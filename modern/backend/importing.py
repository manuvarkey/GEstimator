"""Mapped Excel import using openpyxl and existing project CRUD operations."""

from pathlib import Path
from openpyxl import load_workbook
from estimator.data.schedule import Currency, ScheduleItemModel, ResourceItemModel, parse_analysis
from .numbers import decimal

FIELDS = {
    "schedule": (
        "code",
        "description",
        "unit",
        "rate",
        "qty",
        "remarks",
        "category",
        "parent",
    ),
    "resources": (
        "code",
        "description",
        "unit",
        "rate",
        "vat",
        "discount",
        "reference",
        "category",
    ),
}


def selected_rows(params, width, *, cached=False):
    first = params.get("first_row", 1)
    last = params.get("last_row")
    column = params.get("first_column", 1)
    if (type(first) is not int or first < 1 or type(column) is not int
            or not 1 <= column <= 100 or (last is not None and
            (type(last) is not int or not first <= last < first + 10000))):
        raise ValueError("Choose a valid spreadsheet range")
    path = Path(params["path"]).resolve(strict=True)
    book = load_workbook(path, read_only=True, data_only=cached)
    try:
        name = params.get("sheet") or book.sheetnames[0]
        if name not in book.sheetnames:
            raise ValueError("Worksheet not found")
        sheet = book[name]
        end = min(last, sheet.max_row) if last and sheet.max_row else last or sheet.max_row
        if end is None or end >= first + 10000:
            raise ValueError("Select at most 10,000 rows")
        return list(sheet.iter_rows(
            min_row=first, max_row=end, min_col=column,
            max_col=column + width - 1, values_only=True,
        ))
    finally:
        book.close()


def import_analysis(model, params):
    records = selected_rows(params, 6, cached=True)
    if params.get("rate_first") is True:
        records = [(code, desc, unit, qty, rate, amount)
                   for code, desc, unit, rate, qty, amount in records]
    data = []
    for line, record in enumerate(records, params.get("first_row", 1)):
        try:
            labels = [str(value) if value is not None else "" for value in record[:3]]
            header = "description" in labels[1].lower() and "unit" in labels[2].lower()
            data.append([
                *labels,
                *[decimal(str(value)) if value is not None and not header else decimal("0")
                  for value in record[3:]],
            ])
        except ValueError as exc:
            raise ValueError(f"Invalid analysis number on worksheet row {line}") from exc
    draft = ScheduleItemModel(model.code, model.description, model.unit)
    parse_analysis(data, draft, 0, set_code=True)
    if not any(row.get("resource_list") for row in draft.ana_items):
        raise ValueError("No analysis resources found. Check the worksheet range and column order.")
    draft.resources.update({
        code: model.resources[code] for code in draft.resources if code in model.resources
    })
    draft.evaluate_results()
    return draft


def rows(params):
    start = params.get("header_row", 1)
    if type(start) is not int or not 1 <= start <= 10000:
        raise ValueError("Invalid header row")
    path = Path(params["path"]).resolve(strict=True)
    book = load_workbook(path, read_only=True, data_only=False)
    try:
        sheet = book[params.get("sheet") or book.sheetnames[0]]
        if sheet.max_column > 100 or sheet.max_row - start > 10000:
            raise ValueError("Import sheet is too large; select a smaller worksheet")
        records = list(
            sheet.iter_rows(
                min_row=start,
                max_row=min(sheet.max_row, start + 10000),
                values_only=True,
            )
        )
        headers = [str(v or "") for v in records[0]] if records else []
        return book.sheetnames, headers, records[1:]
    finally:
        book.close()


def preview(params):
    sheets, headers, records = rows(params)
    aliases = {
        "quantity": "qty",
        "basic rate": "rate",
        "tax": "vat",
        "tax %": "vat",
        "vat %": "vat",
        "discount %": "discount",
    }
    mapping = {}
    for index, header in enumerate(headers):
        key = aliases.get(header.strip().lower(), header.strip().lower())
        if key in set(FIELDS["schedule"] + FIELDS["resources"]):
            mapping[key] = index
    return dict(
        sheets=sheets,
        headers=headers,
        rows=[[str(v) if v is not None else "" for v in row] for row in records[:12]],
        mapping=mapping,
    )


def apply(editor, params, progress):
    kind = params["kind"]
    mapping = params["mapping"]
    policy = params.get("duplicates", "error")
    if (
        kind not in FIELDS
        or not isinstance(mapping, dict)
        or "code" not in mapping
        or policy not in ("error", "skip", "update")
    ):
        raise ValueError("Invalid import mapping")
    sheets, headers, records = rows(params)
    for field, index in mapping.items():
        if (
            field not in FIELDS[kind]
            or type(index) is not int
            or not 0 <= index < len(headers)
        ):
            raise ValueError("Invalid mapped column")
    db = editor.db
    table = db.ResourceTable if kind == "resources" else db.ScheduleTable
    added = updated = skipped = 0
    changed = set()
    for number, row in enumerate(records, params.get("header_row", 1) + 1):
        values = {
            field: str(row[index]) if row[index] is not None else ""
            for field, index in mapping.items()
        }
        code = values.get("code", "").strip()
        if not code:
            continue
        if any(len(value) > 10000 for value in values.values()):
            raise ValueError(f"Row {number}: field too long")
        existing = table.get_or_none(table.code == code)
        if existing and policy == "skip":
            skipped += 1
            continue
        if existing and policy == "error":
            raise ValueError(f"Row {number}: code {code} already exists")
        try:
            model = (
                (
                    db.get_resource(code)
                    if kind == "resources"
                    else db.get_item(code, modify_res_code=False)
                )
                if existing
                else (
                    ResourceItemModel(
                        code, "", "", Currency(0), Currency(0), Currency(0)
                    )
                    if kind == "resources"
                    else ScheduleItemModel(code, "", "", Currency(0), decimal("0"))
                )
            )
            for field, value in values.items():
                if field in ("rate", "vat", "discount"):
                    value = Currency(decimal(value.lstrip("=") or "0"), 4 if field == "vat" else 2)
                elif field == "qty":
                    value = round(decimal(value.lstrip("=") or "0"), 4)
                elif field == "parent":
                    value = value or None
                    if (
                        value
                        and not db.ScheduleTable.select()
                        .where(db.ScheduleTable.code == value)
                        .exists()
                    ):
                        raise ValueError("Parent code not found")
                    ancestor = (
                        db.ScheduleTable.get_or_none(db.ScheduleTable.code == value)
                        if value
                        else None
                    )
                    seen = {code}
                    while ancestor:
                        if ancestor.code in seen:
                            raise ValueError(
                                "Schedule hierarchy cannot contain a cycle"
                            )
                        seen.add(ancestor.code)
                        ancestor = ancestor.parent
                setattr(model, field, value)
            if not model.category:
                model.category = params.get("category", "") or "UNCATEGORISED"
            if kind == "resources":
                if existing:
                    old = db.get_resource(code)
                    if old.category != model.category:
                        result = db.update_resource(code, res_model=model)
                    else:
                        result = True
                        for column, field in enumerate(
                            (
                                "description",
                                "unit",
                                "rate",
                                "vat",
                                "discount",
                                "reference",
                            ),
                            1,
                        ):
                            if getattr(old, field) != getattr(model, field):
                                result = (
                                    bool(
                                        db.update_resource(
                                            code,
                                            newvalue=getattr(model, field),
                                            column=column,
                                        )
                                    )
                                    and result
                                )
                else:
                    result = db.insert_resource(model)
                changed.add(code)
            else:
                result = db.insert_item_atomic(model, update=existing is not None)
            if result is False or result is None:
                raise ValueError("Database rejected row")
        except Exception as exc:
            raise ValueError(f"Row {number} ({code}): {exc}") from exc
        if existing:
            updated += 1
        else:
            added += 1
        if number % 100 == 0:
            progress(f"Imported through row {number}")
    if changed:
        editor.owner.update_dependent_rates(db, resources=changed)
    return dict(added=added, updated=updated, skipped=skipped)
