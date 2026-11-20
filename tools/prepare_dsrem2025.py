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


def apply_slip_analysis(rows):
    """Analysis codes follow the schedule; resource lines follow the corrected Appendix I and II."""
    item = None
    for row in rows:
        code = str(row[0]).strip() if row[0] is not None else ""
        if code and "." in code and row[1] and not row[2] and not isinstance(row[0], (int, float)):
            if code in nomenclature.ANALYSIS_RENUMBER:
                row[0] = nomenclature.ANALYSIS_RENUMBER[code]
            else:
                for old, new in nomenclature.ANALYSIS_RENUMBER_PREFIX:
                    if code.startswith(old):
                        row[0] = new + code[len(old):]
                        break
            item = row[0]
            continue
        if code in slip.RESOURCE_RENAMED and isinstance(row[0], (int, float)):
            row[0], row[1] = int(slip.RESOURCE_RENAMED[code][0]), slip.RESOURCE_RENAMED[code][1]
        elif code in slip.RESOURCE_RATES and isinstance(row[4], (int, float)):
            row[4] = slip.RESOURCE_RATES[code]
            row[5] = row[3] * row[4] if isinstance(row[3], (int, float)) else row[5]
        elif (item, code) in nomenclature.ANALYSIS_LINE_RATES and isinstance(row[4], (int, float)):
            row[4] = nomenclature.ANALYSIS_LINE_RATES[(item, code)]
            row[5] = row[3] * row[4] if isinstance(row[3], (int, float)) else row[5]


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
        apply_slip_analysis(analysis_rows)
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
