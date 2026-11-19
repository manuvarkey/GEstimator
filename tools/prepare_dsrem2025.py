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
        counts = dict(
            schedule=write(FOLDER / "schedule.xlsx", ["Code", "Description", "Unit", "Rate", "Category", "Remarks"], schedule_rows),
            resources=write(FOLDER / "resources.xlsx", ["Code", "Description", "Unit", "Rate", "Category"], resources(book)),
            analysis=write(FOLDER / "analysis.xlsx", None, analysis_rows),  # chapter sheets carry their own headers
            civil_rates_filled=filled,
        )
    finally:
        book.close()
    print(counts)


if __name__ == "__main__":
    main()
