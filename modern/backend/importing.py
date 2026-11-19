"""Mapped Excel import using openpyxl and existing project CRUD operations."""

from pathlib import Path
import re
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


_CURRENCY = re.compile(r"^(?:rs\.?|inr|usd|eur|gbp|[₹$€£])\s*", re.IGNORECASE)


def loose_number(value):
    """Decimal from a worksheet value, tolerating thousands separators,
    currency marks, percent signs and dash/blank placeholders. None when the
    text is not a number (e.g. "LS", "Nos")."""
    if value is None or isinstance(value, bool):
        return decimal("0") if value is None else None
    if isinstance(value, (int, float)):
        return decimal(repr(value)) if isinstance(value, float) else decimal(str(value))
    text = str(value).strip().replace(",", "").replace("\u00a0", "")
    text = _CURRENCY.sub("", text).rstrip("%").strip()
    if text in ("", "-", "–", "—", "nil", "Nil", "NIL"):
        return decimal("0")
    try:
        return decimal(text.lstrip("="))
    except ValueError:
        return None


def selected_rows(params, width, *, cached=False):
    first = params.get("first_row", 1)
    last = params.get("last_row")
    column = params.get("first_column", 1)
    if (type(first) is not int or first < 1 or type(column) is not int
            or not 1 <= column <= 101 - width or (last is not None and
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


def analysis_data(params):
    records = selected_rows(params, 6, cached=True)
    if params.get("rate_first") is True:
        records = [(code, desc, unit, qty, rate, amount)
                   for code, desc, unit, rate, qty, amount in records]
    data = []
    for record in records:
        record = tuple(record) + (None,) * (6 - len(record))
        labels = [str(value).strip() if value is not None else "" for value in record[:3]]
        header = "description" in labels[1].lower() and "unit" in labels[2].lower()
        # Text in a number column (units such as "LS", notes, dashes) reads as 0.
        data.append([*labels, *[decimal("0") if header else (loose_number(value) or decimal("0")) for value in record[3:6]]])
    return data


def parser_settings(params):
    comment = params.get("comment_position", 1)
    rounding = params.get("rounding", -1)
    if type(comment) is not int or comment not in (0, 1) or type(rounding) not in (int, float) or rounding not in (-1, 0, 1, 2, 1.5, 2.5):
        raise ValueError("Invalid analysis parser options")
    return comment, rounding


def import_analysis(model, params):
    data = analysis_data(params)
    draft = ScheduleItemModel(model.code, model.description, model.unit)
    parse_analysis(data, draft, 0, set_code=True, settings=parser_settings(params))
    if not any(row.get("resource_list") for row in draft.ana_items):
        raise ValueError("No analysis resources found. Check the worksheet range and column order.")
    draft.resources.update({
        code: model.resources[code] for code in draft.resources if code in model.resources
    })
    draft.evaluate_results()
    return draft


def data_range(params):
    start = params.get("header_row", 1)
    first = params.get("first_row", start + 1)
    last = params.get("last_row")
    if (type(start) is not int or not 1 <= start <= 1_000_000 or type(first) is not int or first <= start
            or (last is not None and (type(last) is not int or last < first))):
        raise ValueError("Choose a header row followed by a valid data row range")
    return start, first, last


def rows(params, *, cached=False):
    start, first, last = data_range(params)
    path = Path(params["path"]).resolve(strict=True)
    book = load_workbook(path, read_only=True, data_only=cached)
    try:
        name = params.get("sheet") or book.sheetnames[0]
        if name not in book.sheetnames:
            raise ValueError("Worksheet not found")
        sheet = book[name]
        end = min(last or sheet.max_row or first, sheet.max_row or first)
        if (sheet.max_column or 0) > 100 or end - first >= 10000:
            raise ValueError("Import at most 10,000 rows and 100 columns; narrow the row range")
        headers = [str(v or "") for v in next(sheet.iter_rows(min_row=start, max_row=start, values_only=True), ())]
        records = list(sheet.iter_rows(min_row=first, max_row=max(end, first - 1), values_only=True)) if end >= first else []
        return book.sheetnames, headers, records
    finally:
        book.close()


HEADER_ALIASES = {
    "code": ("code", "item code", "item no", "item number", "sl no", "s no", "si no", "serial no", "no", "code no", "dsr code", "ref no"),
    "description": ("description", "particulars", "item description", "description of item", "description of work", "item", "name", "work"),
    "unit": ("unit", "units", "uom"),
    "rate": ("rate", "basic rate", "unit rate", "price"),
    "qty": ("qty", "quantity", "qnty", "nos"),
    "remarks": ("remarks", "remark", "notes", "note"),
    "category": ("category", "head", "group", "section"),
    "parent": ("parent", "parent code"),
    "vat": ("vat", "tax", "gst", "tax %", "vat %", "gst %"),
    "discount": ("discount", "discount %"),
    "reference": ("reference", "ref", "source"),
}


def header_key(text):
    # "Rate (Rs.)" -> "rate", "Sl. No." -> "sl no", "Qty." -> "qty"
    text = re.sub(r"\([^)]*\)", " ", text.lower())
    return " ".join(re.sub(r"[^\w%]+", " ", text).split())


def preview(params):
    sheets, headers, records = rows(params, cached=True)
    lookup = {alias: field for field, aliases in HEADER_ALIASES.items() for alias in aliases}
    mapping = {}
    for index, header in enumerate(headers):
        field = lookup.get(header_key(header))
        if field and field not in mapping:
            mapping[field] = index
    return dict(
        sheets=sheets,
        headers=headers,
        rows=[[("%.12g" % v if isinstance(v, float) else str(v)) if v is not None else "" for v in row] for row in records[:12]],
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
    _, _, cached_records = rows(params, cached=True)
    warnings = []
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
    for number, (row, saved) in enumerate(zip(records, cached_records), data_range(params)[1]):
        row = tuple(row) + (None,) * (len(headers) - len(row))
        saved = tuple(saved) + (None,) * (len(headers) - len(saved))
        values = {
            field: str(row[index]) if row[index] is not None else ""
            for field, index in mapping.items()
        }
        numbers = {}
        for field in ("rate", "vat", "discount", "qty"):
            if field not in mapping:
                continue
            raw, value = row[mapping[field]], saved[mapping[field]]
            # A typed expression (2*3) is kept; a formula uses Excel's saved value.
            formula = isinstance(raw, str) and raw.startswith("=")
            parsed = loose_number(value) if formula and value is not None else loose_number(raw)
            if parsed is None:
                warnings.append(f"Row {number} ({values.get('code', '').strip()}): {field} '{raw}' is not a number; imported as 0")
                parsed = decimal("0")
            numbers[field] = parsed
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
                    value = Currency(numbers[field], 4 if field == "vat" else 2)
                elif field == "qty":
                    value = round(numbers[field], 4)
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
    return dict(added=added, updated=updated, skipped=skipped, warnings=warnings[:200], warning_count=len(warnings))


def workbook_analyses(editor, params, *, apply=False):
    data = analysis_data(params)
    settings = parser_settings(params)
    drafts = {}
    # Bound each legacy parse to its own table. A final "Say" row is
    # optional; without this boundary the legacy parser consumes later items.
    starts = []
    for header, row in enumerate(data):
        if "description" in row[1].lower() and "unit" in row[2].lower():
            start = next((i for i in range(header - 1, max(-1, header - 5), -1) if data[i][0]), None)
            if start is not None:
                starts.append(start)
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(data)
        draft = ScheduleItemModel("", "", "")
        parse_analysis(data[start:end], draft, 0, set_code=True, settings=settings)
        if draft.code and any(row.get("resource_list") for row in draft.ana_items):
            if draft.code in drafts:
                raise ValueError(f"Duplicate workbook analysis code: {draft.code}")
            drafts[draft.code] = draft
    if not drafts:
        raise ValueError("No analysis resources found")
    matched, unmatched, analyses = [], [], []
    for code, draft in drafts.items():
        row = editor.db.ScheduleTable.get_or_none(editor.db.ScheduleTable.code == code)
        draft.evaluate_results()
        analyses.append(dict(code=code, matched=row is not None, description=row.description if row else "",
                             current=str(row.rate or 0) if row else "", rate=str(draft.get_ana_rate() or 0),
                             rows=len(draft.ana_items), resources=len(draft.resources)))
        if row is None:
            unmatched.append(code)
            continue
        matched.append(code)
        if apply:
            model = editor.db.get_item(code, modify_res_code=False)
            model.ana_items = draft.ana_items
            model.ana_remarks = draft.ana_remarks
            model.resources = {key: editor.db.get_resource(key) or resource
                               for key, resource in draft.resources.items()}
            model.evaluate_results()
            if not editor.db.insert_item_atomic(model, update=True):
                raise ValueError(f"Could not import analysis: {code}")
    if apply and not matched:
        raise ValueError("No workbook item codes match existing schedule items")
    if apply:
        editor.owner.update_dependent_rates(editor.db, schedules=set(matched))
    return dict(matched=matched, unmatched=unmatched, analyses=analyses)


def sheet_preview(params):
    """Cells of one worksheet for the import range picker (saved values)."""
    path = Path(params["path"]).resolve(strict=True)
    limit = params.get("rows", 400)
    if type(limit) is not int or not 1 <= limit <= 2000:
        raise ValueError("Invalid preview size")
    book = load_workbook(path, read_only=True, data_only=True)
    try:
        name = params.get("sheet") or book.sheetnames[0]
        if name not in book.sheetnames:
            raise ValueError("Worksheet not found")
        sheet = book[name]
        width = min(sheet.max_column or 1, 40)
        cells = []
        for row in sheet.iter_rows(min_row=1, max_row=min(sheet.max_row or 1, limit), max_col=width, values_only=True):
            cells.append(["" if value is None else ("%.12g" % value if isinstance(value, float) else str(value)) for value in row])
        return dict(sheets=book.sheetnames, sheet=name, rows=cells, max_row=sheet.max_row or 0, max_column=sheet.max_column or 0)
    finally:
        book.close()


def analysis_rows(draft):
    """Parsed analysis as display rows for an import preview."""
    rows = []
    draft.evaluate_results()
    for index, item in enumerate(draft.ana_items):
        kind = item["itemtype"]
        if kind == ScheduleItemModel.ANA_GROUP:
            rows.append(dict(kind="Group", description=item["description"] or "", amount=str(draft.results[index][-1])))
            for (code, qty, remarks), (rate, total) in zip(item["resource_list"], draft.results[index][:-1]):
                resource = draft.resources.get(code)
                rows.append(dict(kind="Resource", code=code, description=getattr(resource, "description", "") or "",
                                 unit=getattr(resource, "unit", "") or "", qty=str(qty), rate=str(rate), amount=str(total), remarks=remarks or ""))
        else:
            label = {ScheduleItemModel.ANA_SUM: "Subtotal", ScheduleItemModel.ANA_WEIGHT: "Weight",
                     ScheduleItemModel.ANA_TIMES: "Multiply", ScheduleItemModel.ANA_ROUND: "Round"}.get(kind, "")
            rows.append(dict(kind=label, description=item.get("description") or "", qty=str(item.get("value") or ""), amount=str(draft.results[index])))
    return rows
