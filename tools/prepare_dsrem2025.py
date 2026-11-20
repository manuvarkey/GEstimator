"""Prepare the CPWD DSR (E&M) 2025 workbook for import into a GEstimator database.

Reads ``spreadsheets/DSREM2025/DSR EandM 2025 3 09 2025.xlsx`` (saved values) and
writes three plain workbooks next to it:

- ``schedule.xlsx``  Code, Description, Unit, Rate, Category — chapter titles
  become categories; headings and items keep their codes so the importer's
  code hierarchy places 1.1.1 under 1.1.
- ``resources.xlsx`` Code, Description, Unit, Rate, Category — section headings
  of Appendix I/II become categories; descriptive lines above short item rows
  ("LED Down lighter … of following wattage" + "5 - 7 watt") are joined into the
  item description.
- ``analysis.xlsx``  the six analysis columns of every chapter sheet ("CH…"),
  one after another, for a single multiple-analysis import.

Usage: python tools/prepare_dsrem2025.py [source.xlsx]
"""

import re
import sys
from pathlib import Path

from openpyxl import Workbook, load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dsrem2025_correction_slip1 as slip  # noqa: E402
import dsrem2025_nomenclature as nomenclature  # noqa: E402

FOLDER = Path(__file__).resolve().parent.parent / "spreadsheets" / "DSREM2025"
SOURCE = FOLDER / "DSR EandM 2025 3 09 2025.xlsx"
CODE = re.compile(r"^\d+(\.\d+)*[A-Za-z]?(\s*\([A-Za-z0-9]+\))?$")  # 1101, 1.1.1, 4143 (B)
# Title-case section headings that read like descriptions; listed explicitly.
RESOURCE_SECTIONS = {"HVAC ITEMS", "METAL BOXES", "PASSENGER LIFTS", "GOODS LIFTS"}
HEADER_CODES = ("code no", "item no", "s no", "sr no", "sl no", "icd no")


def text(value):
    if value is None:
        return ""
    if isinstance(value, float):
        value = "%.12g" % value
    return " ".join(str(value).replace(" ", " ").split())


class CodeSequence:
    """Restore trailing zeros of codes stored as numbers: Excel shows 15.10 but
    keeps 15.1. A number is extended (15.1 -> 15.10) only when the result is the
    next sibling after the previous code, allowing a few withdrawn numbers; the
    sequence never moves backwards, so mistyped codes are left as they are."""

    def __init__(self):
        self.previous = {}

    def fix(self, raw, code):
        parent, _, last = code.rpartition(".")
        before = self.previous.get(parent)
        if isinstance(raw, float) and before is not None and last.isdigit() and int(last) <= before:
            extended = last
            while int(extended) <= before and len(extended) < 3:
                extended += "0"
            if before < int(extended) <= before + 5:
                last = extended
        code = f"{parent}.{last}" if parent else last
        if last.isdigit() and (before is None or int(last) > before):
            self.previous[parent] = int(last)
        return code


def is_header(code, description):
    key = re.sub(r"[^a-z ]", " ", code.lower())
    return " ".join(key.split()) in HEADER_CODES or description.lower().startswith(("description", "descr"))


def write(path, header, rows):
    book = Workbook()
    sheet = book.active
    if header:
        sheet.append(header)
    for row in rows:
        sheet.append(row)
    book.save(path)
    return len(rows)


def schedule(book):
    """Chapter rows set the category; other rows are copied unchanged."""
    rows, category, sequence = [], "", CodeSequence()
    for values in book["DSR 2025"].iter_rows(min_row=1, max_col=4, values_only=True):
        values = (tuple(values) + (None,) * 4)[:4]
        code, description, unit, rate = (text(v) for v in values)
        if description.upper().startswith("DELETED"):
            continue  # withdrawn items keep their number in the book only
        if CODE.match(code):
            code = sequence.fix(values[0], code)
        joined = f"{code} {description}".strip()
        chapter = re.match(r"^chapter\s*-?\s*\d+\s*(.*)$", joined, re.IGNORECASE)
        if chapter:
            category = chapter[1].strip(" -").upper()
            continue
        if not (code or description) or is_header(code, description):
            continue
        if not code and description.upper() == description:
            # Sub-section headings are kept as category-only rows: the importer
            # reads uppercase description-only rows as category changes, so emit
            # nothing and keep the chapter category instead.
            continue
        rows.append([code, description, unit, rate, category, ""])
    return rows


def civil_rates(schedule_rows, analysis_rows):
    """Items marked "Rate to be taken from Civil DSR" have no rate in the
    schedule, but the analyses use them as sub-analyses at a definite rate.
    Fill that rate (the most common one) and say where it came from."""
    from collections import Counter
    pending = {row[0]: row for row in schedule_rows if row[3] and not re.match(r"^-?[\d.]+$", str(row[3]))}
    used = {}
    for code, description, unit, qty, rate, amount in analysis_rows:
        code = text(code)
        if code in pending and unit and isinstance(rate, (int, float)) and rate:
            used.setdefault(code, Counter())[round(rate, 2)] += 1
    for code, counts in used.items():
        row = pending[code]
        row[5] = f"{row[3]}; rate as used in the DSR (E&M) 2025 analyses"
        row[3] = counts.most_common(1)[0][0]
    return len(used)


def apply_edits(rows, blocks, edits, report):
    """Text edits on the description lines of items; a new text already present counts as applied."""
    for code, old, new in edits:
        done = False
        for index in blocks.get(code, []):
            if old.startswith("re:"):
                text, count = re.subn(old[3:], new, rows[index][1])
                done = count > 0
            else:
                done = old in rows[index][1]
                text = rows[index][1].replace(old, new, 1)
            if done:
                rows[index][1] = text
                break
        if done:
            report["text"] += 1
        elif any(new in rows[index][1] for index in blocks.get(code, [])):
            report["already"] += 1
        else:
            report["unmatched"].append(f"{code}: {old[:50]}")


def item_blocks(rows):
    blocks, current = {}, None
    for index, row in enumerate(rows):
        if row[0]:
            current = row[0]
        if current:
            blocks.setdefault(current, []).append(index)
    return blocks


def apply_slip_schedule(rows):
    """Printed-book nomenclature, then Correction Slip No. 1: modified rates, deleted items
    and description edits. Description lines that follow an item (rows without a code) belong to it."""
    report = {"rates": 0, "text": 0, "deleted": 0, "already": 0, "unmatched": []}
    for index, row in enumerate(rows):
        if (row[0], str(row[3])) in nomenclature.RENUMBER:
            row[0] = nomenclature.RENUMBER[(row[0], str(row[3]))]
        if row[2] == "Metre":
            row[2] = "Meter"
    for row in rows:
        try:
            value = float(row[3])
        except (TypeError, ValueError):
            continue
        if value != round(value) and not str(row[0]).startswith(nomenclature.KEEP_DECIMALS_PREFIX):
            digits = nomenclature.KEEP_DECIMALS.get(row[0])
            row[3] = round(value, digits) if digits else int(value + 0.5)
    for row in rows:
        if row[0].split('.')[0] in nomenclature.CHAPTER_CATEGORY:
            row[4] = nomenclature.CHAPTER_CATEGORY[row[0].split('.')[0]]
    blocks = item_blocks(rows)
    apply_edits(rows, blocks, nomenclature.TEXT, report)
    for code, rate in slip.RATES.items():
        if code not in blocks:
            report["unmatched"].append(f"{code}: item not found")
            continue
        rows[blocks[code][0]][3] = rate
        report["rates"] += 1
    apply_edits(rows, blocks, slip.TEXT, report)
    deleted = slip.DELETED | nomenclature.DELETED
    drop = {index for code in deleted for index in blocks.get(code, [])}
    drop |= {index for code, text in nomenclature.DROP_ROWS for index in blocks.get(code, []) if rows[index][1] == text and not rows[index][0]}
    report["deleted"] = len(deleted & set(blocks))
    rows[:] = [row for index, row in enumerate(rows) if index not in drop]
    return report


def apply_slip_resources(rows):
    """Correction Slip No. 1: Appendix I code 1020 becomes 1021 Technician; Appendix II cable rates."""
    seen = set()
    result = []
    for row in rows:
        code = row[0]
        if "." in str(code) and row[3] in (None, ""):
            continue  # sub-heading of the book that carries a schedule item number
        if code in slip.RESOURCE_RENAMED:
            row[0], row[1] = slip.RESOURCE_RENAMED[code]
        row[2] = nomenclature.RESOURCE_UNIT_BY_CODE.get(str(row[0]), nomenclature.RESOURCE_UNITS.get(str(row[2]).lower(), row[2]))
        for old, new in nomenclature.RESOURCE_TEXT:
            row[1] = row[1].replace(old, new)
        if str(row[0]) in nomenclature.RESOURCE_RATES:
            row[3] = nomenclature.RESOURCE_RATES[str(row[0])]
        if row[0] in slip.RESOURCE_RATES:
            row[3] = slip.RESOURCE_RATES[row[0]]
        if row[0] in slip.RESOURCE_RENAMED.values() and row[0] in seen:
            continue  # the book lists the technician once
        seen.add(row[0])
        result.append(row)
    rows[:] = result


def apply_slip_analysis(rows, resource_rows=None):
    """Analysis codes follow the schedule; resource lines follow the corrected Appendix I and II."""
    item, section, previous_header, seen_say, renamed, result, pending, amounts = None, None, None, False, set(), [], None, []
    for row in rows:
        row = list(row)
        code = str(row[0]).strip() if row[0] is not None else ""
        if isinstance(row[0], (int, float)) and not row[2] and row[3] is None:
            row[0] = code = str(int(row[0]))
        if row[1] == "Details of cost for 1 No" and seen_say and item in nomenclature.ANALYSIS_INSERT_HEADERS:
            result.append(list(nomenclature.ANALYSIS_INSERT_HEADERS[item]) + [None] * 4)
            item, seen_say = nomenclature.ANALYSIS_INSERT_HEADERS[item][0], False
        if row[1] == "Say":
            seen_say = True
        if (code and "." in code or code in {old for old, _ in nomenclature.ANALYSIS_HEADER_CODES}) and (row[1] or code in nomenclature.ANALYSIS_CODE_ROW_ITEMS) and not row[2] and row[3] is None:
            seen_say = False
            if code in nomenclature.ANALYSIS_RENUMBER:
                row[0] = nomenclature.ANALYSIS_RENUMBER[code]
            else:
                for old, new in nomenclature.ANALYSIS_RENUMBER_PREFIX:
                    if code.startswith(old):
                        row[0] = new + code[len(old):]
                        break
            for (old, start), new in nomenclature.ANALYSIS_HEADER_CODES.items():
                if code == old and str(row[1]).startswith(start) and old not in renamed:
                    row[0] = new
                    renamed.add(old)
            if section in nomenclature.ANALYSIS_CHILD_PREFIX:
                old, new = nomenclature.ANALYSIS_CHILD_PREFIX[section]
                if str(row[0]).startswith(old):
                    row[0] = new + str(row[0])[len(old):]
            if (previous_header, str(row[0])) in nomenclature.ANALYSIS_BLANK_AFTER:
                row[0], previous_header = None, None
            elif row[0] is not None:
                previous_header = str(row[0])
                if row[0].count(".") == 1:
                    section = row[0]
                item = row[0]
            amounts = list(nomenclature.ANALYSIS_AMOUNTS.get(str(row[0]), []))
            result.append(row)
            continue
        if code and not isinstance(row[0], (int, float)) and "." in code and row[1] and row[2] is None:
            previous_header = None
        if item in nomenclature.ANALYSIS_CODE_ROW_ITEMS:
            if code.isdigit() and row[2] is None and row[3] is None:
                pending, row[0], code = row[0], None, ""
            elif pending is not None and row[0] is None and row[2] and isinstance(row[3], (int, float, str)):
                row[0], code, pending = pending, str(pending), None
        if item in nomenclature.ANALYSIS_AMOUNTS and row[0] is None and row[1] in nomenclature.ANALYSIS_AMOUNT_LABELS and amounts:
            row[5] = amounts.pop(0)
        text_ = str(row[1]).strip().lower() if row[1] is not None else ""
        if row[0] is None and isinstance(row[3], (int, float, str)) and row[3] not in ("", None) and row[2] is not None:
            if text_.startswith(nomenclature.ANALYSIS_DROP_BY_DESCRIPTION):
                continue
            if text_ in nomenclature.ANALYSIS_LINE_BY_DESCRIPTION:
                new, rate = nomenclature.ANALYSIS_LINE_BY_DESCRIPTION[text_]
                row[0], row[4] = new, rate
                code = new
                row[5] = row[3] * rate if isinstance(row[3], (int, float)) else row[5]
        if (item, code) in nomenclature.ANALYSIS_LINE_CODES:
            new, qty = nomenclature.ANALYSIS_LINE_CODES[(item, code)]
            row[0] = code = new
            if qty is not None:
                row[3] = qty
            row[4] = next((r[3] for r in resource_rows if str(r[0]) == new), row[4]) if resource_rows else row[4]
            row[5] = row[3] * row[4] if isinstance(row[3], (int, float)) and isinstance(row[4], (int, float)) else row[5]
        if code == nomenclature.ANALYSIS_FITTER[0] and str(row[1]).startswith("Fitter"):
            row[0] = code = int(nomenclature.ANALYSIS_FITTER[1])
        if row[0] is None and row[2] == "day" and str(row[1]).strip().lower() in nomenclature.ANALYSIS_LABOUR:
            labour = nomenclature.ANALYSIS_LABOUR[str(row[1]).strip().lower()]
            if row[4] == labour[2]:
                row[0], row[1] = labour[0], labour[1]
                code = str(row[0])
        if code in slip.RESOURCE_RENAMED and isinstance(row[0], (int, float)):
            row[0], row[1] = int(slip.RESOURCE_RENAMED[code][0]), slip.RESOURCE_RENAMED[code][1]
        elif code in slip.RESOURCE_RATES and isinstance(row[4], (int, float)):
            row[4] = slip.RESOURCE_RATES[code]
            row[5] = row[3] * row[4] if isinstance(row[3], (int, float)) else row[5]
        result.append(row)
    rows[:] = result


def apply_chapter16(rows):
    """Chapter 16 analyses keep their formulas without saved values, so the workbook has no amounts. The chain of the
    DAR (cartage 1 %, ITC 4 %, overheads 15 %, cess 1 %, GST 18 %) is written out; the tank (Rs 11 per litre) and
    connections (Rs 400) of the evacuated tube systems have no Appendix II item and are added to the collector rate."""
    start = None
    blocks = []
    for index, row in enumerate(rows):
        code = str(row[0]).strip() if row[0] is not None else ""
        if code.startswith("16.") and row[1] and row[2] is None and code.count(".") == 2:
            start = index
            blocks.append([index, None])
        elif start is not None and row[1] == "Say":
            blocks[-1][1] = index
            start = None
    for first, last in blocks:
        if last is None:
            continue
        lines = [i for i in range(first, last) if rows[i][0] is not None and str(rows[i][0]).isdigit() and rows[i][4] not in (None, "")]
        collector = lines[0]
        extras = sum(float(rows[i][3]) * 11 for i in range(first, last) if str(rows[i][1]).startswith("Cold water tank")) + \
            sum(float(rows[i][3]) for i in range(first, last) if str(rows[i][1]).startswith("Tank Connections"))
        rate = float(rows[collector][5] if rows[collector][5] not in (None, "") else rows[collector][4]) + extras
        rows[collector][2:6] = ["Each", 1, rate, rate]
        cart = round(rate * 0.01, 2); total_a = rate + cart
        itc = round(total_a * 0.04, 2); total_b = total_a + itc
        overhead = round(total_b * 0.15, 2); total = total_b + overhead
        cess = round(total * 0.01, 2); total_c = total + cess
        gst = round(total_c * 0.18, 2); final = round(total_c + gst, 2)
        labels = [r for r in range(collector + 1, last + 1) if rows[r][1] not in (None, "", "MATERIALS (A)", "LABOUR (B)") and not str(rows[r][1]).startswith(("Cold water tank", "Tank Connections"))]
        values = ([rate] if str(rows[labels[0]][1]).lower() == "total" else []) + [cart, total_a, itc, total_b, total_b, overhead, total, cess, total_c, gst, final]
        if str(rows[labels[-2]][1]).startswith("Rate"):
            values.append(final)
        values.append(round(final))
        for r, value in zip(labels, values):
            rows[r][5] = value
    rows[:] = [r for r in rows if not (r[1] and str(r[1]).startswith(("Cold water tank", "Tank Connections")))]


def resources(book):

    rows, category, context, coded_since_context = [], "LABOUR & HIRE CHARGES", [], False
    sheet = list(book["APPENDIX-II BASIC MATERIAL RATE"].iter_rows(min_row=1, max_col=4, values_only=True))
    cells = [[text(v) for v in (tuple(values) + (None,) * 4)[:4]] for values in sheet]

    def next_kind(index):
        for code, description, unit, rate in cells[index + 1:index + 4]:
            if not (code or description):
                continue
            if is_header(code, description):
                return "header"
            return "item" if CODE.match(code) else "text"
        return "end"

    for index, (code, description, unit, rate) in enumerate(cells):
        if not (code or description):
            context, coded_since_context = [], False
            continue
        if is_header(code, description):
            continue
        if CODE.match(code):
            full = "\n".join(context + [description]) if context else description
            rows.append([code, full, unit, rate, category])
            coded_since_context = True
            continue
        label = code or description
        if label.lower().startswith("note"):
            continue
        if label.upper().startswith("APPENDIX-II"):
            # The material appendix starts with cables but has no heading for them.
            category, context = "WIRES AND CABLES", []
            continue
        if label.upper().startswith("APPENDIX-I"):
            category, context = "LABOUR & HIRE CHARGES", []
            continue
        following = next_kind(index)
        heading = (label.upper() == label or label.upper() in RESOURCE_SECTIONS or following == "header"
                   or (len(label.split()) <= 4 and following == "item" and not context))
        if heading and len(label) <= 80:
            category, context, coded_since_context = label.upper(), [], False
            continue
        if coded_since_context:
            context, coded_since_context = [], False
        context.append(label)
    return rows


def analysis(book):
    rows = []
    for name in book.sheetnames:
        if not name.upper().startswith("CH"):
            continue
        sequence = CodeSequence()
        for values in book[name].iter_rows(min_row=1, max_col=6, values_only=True):
            values = (tuple(values) + (None,) * 6)[:6]
            row = [v if isinstance(v, (int, float)) else (text(v) or None) for v in values]
            # Item code rows: a dotted code with a description and no unit.
            if values[0] is not None and "." in text(values[0]) and CODE.match(text(values[0])) and values[1] and not values[2]:
                row[0] = sequence.fix(values[0], text(values[0]))
            rows.append(row)
        rows.extend([[None] * 6] * 3)
    return rows


def main():
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else SOURCE
    book = load_workbook(source, read_only=True, data_only=True)
    try:
        schedule_rows, analysis_rows = schedule(book), analysis(book)
        filled = civil_rates(schedule_rows, analysis_rows)
        slip_report = apply_slip_schedule(schedule_rows)
        resource_rows = resources(book)
        apply_slip_resources(resource_rows)
        apply_chapter16(analysis_rows)
        apply_slip_analysis(analysis_rows, resource_rows)
        counts = dict(
            schedule=write(FOLDER / "schedule.xlsx", ["Code", "Description", "Unit", "Rate", "Category", "Remarks"], schedule_rows),
            resources=write(FOLDER / "resources.xlsx", ["Code", "Description", "Unit", "Rate", "Category"], resource_rows),
            analysis=write(FOLDER / "analysis.xlsx", None, analysis_rows),  # chapter sheets carry their own headers
            civil_rates_filled=filled,
            correction_slip_1=slip_report,
        )
    finally:
        book.close()
    print(counts)


if __name__ == "__main__":
    main()
