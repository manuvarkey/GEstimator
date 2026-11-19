"""Worksheet helpers (lenient numbers, cell previews, ranges) and mapped schedule/resource import."""

from pathlib import Path
import re
from openpyxl import load_workbook
from estimator.data.schedule import Currency, ScheduleItemModel, ResourceItemModel
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
        from decimal import Decimal
        return Decimal(repr(value)) if isinstance(value, float) else Decimal(value)
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


HEADER_LOOKUP = {alias: field for field, aliases in HEADER_ALIASES.items() for alias in aliases}
# Prefixes tolerate misspelt or extended headers ("Descpription", "Quantity (cum)", "Sr. No.").
HEADER_PREFIXES = (("desc", "description"), ("particul", "description"), ("quant", "qty"), ("qty", "qty"),
                   ("sr no", "code"), ("sl no", "code"), ("s no", "code"), ("item no", "code"), ("code", "code"),
                   ("remark", "remarks"), ("unit rate", "rate"), ("rate", "rate"), ("unit", "unit"))


def header_field(text):
    key = header_key(text)
    if key in HEADER_LOOKUP:
        return HEADER_LOOKUP[key]
    return next((field for prefix, field in HEADER_PREFIXES if key.startswith(prefix)), None)


def is_header_row(values):
    """True for a row whose code (and description) cells are column names."""
    code = values.get("code", "")
    description = values.get("description")
    return (bool(code.strip()) and header_field(code) == "code"
            and (description is None or header_field(description) == "description"))


def preview(params):
    sheets, headers, records = rows(params, cached=True)
    mapping = {}
    for index, header in enumerate(headers):
        field = header_field(header)
        if field and field not in mapping:
            mapping[field] = index
    return dict(
        sheets=sheets,
        headers=headers,
        rows=[[("%.12g" % v if isinstance(v, float) else str(v)) if v is not None else "" for v in row] for row in records[:12]],
        mapping=mapping,
    )


def deduce_hierarchy(entries, mapped_category):
    """GTK structured schedule import: uppercase description-only rows set the
    category; code rows without a unit are headings (following description-only
    rows continue them); a priced item whose code extends the heading's code
    (1.1.1 under 1.1) becomes its subitem. Headings are added with their first
    priced subitem, using the joined heading descriptions."""
    def text(values, field):
        return (values.get(field) or "").strip()

    def is_child(codes, code):
        if not codes:
            return True
        parts = code.split(".")
        return len(parts) > 1 and parts[:-1] == codes[-1].split(".")

    result, category, codes, descriptions, parent = [], "", [], [], None
    index = 0
    while index < len(entries):
        number, values, numbers = entries[index]
        code, description, unit = text(values, "code"), text(values, "description"), text(values, "unit")
        if not code and description and not unit and description.upper() == description and any(ch.isalpha() for ch in description):
            category, parent = description, None
            codes.clear()
            descriptions.clear()
            index += 1
            continue
        if not (code and description):
            index += 1
            continue
        last = index
        if not unit:
            # Multi-line description: following rows without a code (lowercase text).
            while (last + 1 < len(entries) and not text(entries[last + 1][1], "code")
                   and text(entries[last + 1][1], "description")
                   and text(entries[last + 1][1], "description").upper() != text(entries[last + 1][1], "description")):
                last += 1
                description += "\n" + text(entries[last][1], "description")
        final_number, final, final_numbers = entries[last]
        unit = text(final, "unit")

        def item(item_code, item_description, item_unit, source, source_numbers, item_parent):
            values = dict(source, code=item_code, description=item_description, unit=item_unit, parent=item_parent or "")
            if not mapped_category or not text(source, "category"):
                values["category"] = category
            return values, dict(source_numbers)

        if not is_child(codes, code) and codes:
            codes.pop()
            descriptions.pop()
            parent = None
        if not unit and is_child(codes, code):
            codes.append(code)
            descriptions.append(description)
            parent = None
        elif unit and is_child(codes, code):
            if parent is None and codes:
                heading, heading_numbers = item(codes[-1], "\n".join(descriptions), "", {}, {}, None)
                heading.update(rate="0", qty="0")
                result.append((final_number, heading, dict(rate=decimal("0"), qty=decimal("0"))))
                parent = codes[-1]
            values, item_numbers = item(code, description, unit, final, final_numbers, parent)
            result.append((final_number, values, item_numbers))
        else:
            codes.clear()
            descriptions.clear()
            parent = None
            values, item_numbers = item(code, description, unit, final, final_numbers, None)
            result.append((final_number, values, item_numbers))
        index = last + 1
    return result


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
    entries = []
    for number, (row, saved) in enumerate(zip(records, cached_records), data_range(params)[1]):
        row = tuple(row) + (None,) * (len(headers) - len(row))
        saved = tuple(saved) + (None,) * (len(headers) - len(saved))
        values = {}
        for field, index in mapping.items():
            raw = row[index]
            if isinstance(raw, str) and raw.startswith("=") and saved[index] is not None and field not in ("rate", "vat", "discount", "qty"):
                raw = saved[index]
            values[field] = ("%.12g" % raw if isinstance(raw, float) else str(raw)) if raw is not None else ""
        if is_header_row(values):
            continue  # a header repeated on a later printed page
        numbers = {}
        for field in ("rate", "vat", "discount", "qty"):
            if field not in mapping:
                continue
            raw, value = row[mapping[field]], saved[mapping[field]]
            # A typed expression (2*3) is kept; a formula uses Excel's saved value.
            formula = isinstance(raw, str) and raw.startswith("=")
            parsed = loose_number(value) if formula and value is not None else loose_number(raw)
            if parsed is None:
                if values.get("code", "").strip():
                    warnings.append(f"Row {number} ({values.get('code', '').strip()}): {field} '{raw}' is not a number; imported as 0")
                parsed = decimal("0")
            numbers[field] = parsed
        entries.append((number, values, numbers))
    if params.get("hierarchy") is True:
        if kind != "schedule":
            raise ValueError("Code hierarchy applies to schedule imports")
        entries = deduce_hierarchy(entries, "category" in mapping)
    for number, values, numbers in entries:
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


