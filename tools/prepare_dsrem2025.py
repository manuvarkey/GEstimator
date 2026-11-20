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
from collections import Counter
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
        for column, value in enumerate(row, 1):
            if isinstance(value, str) and value.startswith("="):
                # Notes such as "= 50.0 + 2.5 (Wastage @ 5%) = 52.5m" are text,
                # not formulas (openpyxl would store them as formulas).
                sheet.cell(row=sheet.max_row, column=column).data_type = "s"
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
    return fix_duplicate_codes(rows)


def normal(description):
    return " ".join(re.sub(r"[^a-z0-9.½]+", " ", description.lower()).split())


def fix_duplicate_codes(rows):
    """Give repeated schedule codes the number the analyses use.

    - A coded sub-heading followed by an item with the same code ("31.12.1 High
      Static Ductable units", "31.12.1 5.5 TR") keeps only its text.
    - A repeated code under another heading becomes that heading's next number
      (23.4 lists 23.3, 23.3.1… → 23.4.1, 23.4.2…; 24.8.6 under 24.9 → 24.9.6).
    - A repeated code among its siblings takes the next free number, and later
      siblings move up (11.1.34 twice, 11.1.35 → 11.1.34, 11.1.35, 11.1.36).
    """
    for row, following in zip(rows, rows[1:]):
        if row[0] and row[0] == following[0] and not row[2] and following[2]:
            row[0] = ""
    assigned, heading, renumbered = set(), "", []
    for row in rows:
        code = row[0]
        if not code or not CODE.match(code):
            continue
        if not row[2]:
            heading = code
        if code in assigned:
            if heading and code != heading and not code.startswith(heading + "."):
                parent = heading
            else:
                parent = code.rpartition(".")[0]
            # After the last sibling: withdrawn numbers are not reused.
            used = [int(other.rpartition(".")[2]) for other in assigned
                    if other.rpartition(".")[0] == parent and other.rpartition(".")[2].isdigit()]
            row[0] = f"{parent}.{max(used, default=0) + 1}"
            row[5] = f"Numbered {code} in the book"
            renumbered.append((code, row[0], row[1]))
        assigned.add(row[0])
    for old, new, description in renumbered:
        print(f"schedule {old} -> {new} ({description[:40]})")
    return rows


def analysis_codes(schedule_rows):
    """lookup(code, description, result, analysed) -> schedule code, for
    analyses numbered differently from the schedule:

    - the schedule item with that code has another description and exactly one
      sibling has the analysis description and the analysis result as its rate
      (31.12.2 "6.6 TR", ₹78065, is 31.12.3 in the schedule);
    - the code is not in the schedule and exactly one item without an analysis
      has the analysis result as its rate and the same code ending or
      description (18.19.1 is 8.19.1, 30.10.1.1 is 30.10.1, 5.1.4 is 26.1.4).
    """
    by_code = {row[0]: normal(row[1]) for row in schedule_rows if row[0]}
    rates = {row[0]: float(row[3]) for row in schedule_rows if row[0] and re.fullmatch(r"-?\d+(\.\d+)?", str(row[3]))}
    siblings = {}
    for row in schedule_rows:
        if row[0] and row[2]:
            siblings.setdefault(row[0].rpartition(".")[0], []).append((row[0], normal(row[1])))

    def same_ending(code, other):
        ours, theirs = code.split("."), other.split(".")
        # 18.19.1 ~ 8.19.1, 5.1.4 ~ 26.1.4, 30.10.1.2 ~ 30.10.2 (and 30.10.1.1 ~ 30.10.1)
        return len(ours) > 1 and len(theirs) > 1 and (
            ours[-2:] == theirs[-2:] or ours[:-1] == theirs or ours[:-2] + ours[-1:] == theirs)

    def lookup(code, description, final, analysed, unknown):
        """`unknown` selects the second rule (codes missing from the schedule)."""
        wanted = normal(description or "")
        if by_code.get(code) == wanted or final is None or abs(rates.get(code, -1e9) - final) < 1:
            return code
        if code in by_code and not unknown:
            matches = [other for other, text in siblings.get(code.rpartition(".")[0], [])
                       if text == wanted and abs(rates.get(other, -1e9) - final) < 1]
        elif code not in by_code and unknown:
            matches = [other for other, rate in rates.items() if abs(rate - final) < 1 and not analysed[other]
                       and (same_ending(code, other) or by_code.get(other) == wanted)]
        else:
            return code
        return matches[0] if len(matches) == 1 else code
    return lookup


def civil_rates(schedule_rows, analysis_rows):
    """Items marked "Rate to be taken from Civil DSR" have no rate in the
    schedule, but the analyses use them as sub-analyses at a definite rate.
    Fill that rate (the most common one) and say where it came from."""
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


def analysis(book, lookup):
    rows, blocks = [], []
    for name in book.sheetnames:
        if not name.upper().startswith("CH"):
            continue
        sequence = CodeSequence()
        columns = (0, 1, 2, 3, 4, 5)
        sheet_codes = []
        for values in book[name].iter_rows(min_row=1, max_col=7, values_only=True):
            values = tuple(values) + (None,) * 7
            labels = [text(v).lower() for v in values[:7]]
            if labels[1].startswith("descr"):
                # CH-16 has an extra unit column ("LPD", "Liter") between Qty
                # and Rate: Code, Description, Unit, Qty, -, Rate, Amount.
                extra = not labels[4] and labels[5].startswith("rate") and labels[6].startswith("amount")
                columns = (0, 1, 2, 3, 5, 6) if extra else (0, 1, 2, 3, 4, 5)
            values = tuple(values[index] for index in columns)
            row = [v if isinstance(v, (int, float)) else (text(v) or None) for v in values]
            # Item code rows: a dotted code with a description and no unit.
            if values[0] is not None and "." in text(values[0]) and CODE.match(text(values[0])) and values[1] and not values[2]:
                row[0] = sequence.fix(values[0], text(values[0]))
                sheet_codes.append(len(rows))
            rows.append(row)
            if (len(rows) > 1 and labels[1].startswith("descr") and rows[-2][0] is not None and rows[-2][1]
                    and not rows[-2][2] and len(rows) - 2 not in sheet_codes and CODE.match(text(rows[-2][0]))):
                # An undotted item code just above the analysis header ("5190" for 20.15).
                rows[-2][0] = text(rows[-2][0])
                sheet_codes.append(len(rows) - 2)
        blocks += zip(sheet_codes, sheet_codes[1:] + [len(rows)])
        rows.extend([[None] * 6] * 3)
    # The analysis result: the last amount without a unit ("Say 78065").
    results = [(index, next((row[5] for row in reversed(rows[index + 1:end])
                             if isinstance(row[5], (int, float)) and not row[2]), None)) for index, end in blocks]
    analysed = Counter(rows[index][0] for index, final in results if final is not None)
    for unknown in (False, True):
        for index, final in results:
            code = rows[index][0]
            rows[index][0] = lookup(code, rows[index][1], final, analysed, unknown)
            if rows[index][0] != code:
                analysed[code] -= 1
                analysed[rows[index][0]] += 1
                print(f"analysis {code} -> {rows[index][0]} ({rows[index][1][:40]}, {final})")
    return rows


SLIPS = [("correction_slip_1.csv", "Correction Slip No. 1 (27-11-2025)")]
SLIP_ANALYSES = ["correction_slip_1_analysis.csv"]  # corrected DAR (E&M) 2025 analyses


def item_code_row(row):
    code = text(row[0])
    return "." in code and CODE.match(code) and row[1] and not row[2]


def apply_slip_analyses(analysis_rows):
    """Replace the book's analysis of each item in the slip analysis files
    (same six columns) with the corrected one."""
    import csv
    replaced = []
    for name in SLIP_ANALYSES:
        with open(FOLDER / name, encoding="utf-8") as handle:
            rows = [[(float(value) if re.fullmatch(r"-?\d+(\.\d+)?", value) else value or None) for value in row]
                    for row in list(csv.reader(handle))[1:]]
        for row in rows:
            if row[0] is not None and isinstance(row[0], float):
                row[0] = text(row[0]) if "." in text(row[0]) else int(row[0])
        codes = [text(row[0]) for row in rows if item_code_row(row)]
        for code in codes:
            starts = [index for index, row in enumerate(analysis_rows) if item_code_row(row) and text(row[0]) == code]
            for start in reversed(starts):
                end = next((index for index in range(start + 1, len(analysis_rows)) if item_code_row(analysis_rows[index])),
                           len(analysis_rows))
                del analysis_rows[start:end]
            replaced.append(f"{code} ({len(starts)} book block{'s' if len(starts) != 1 else ''} replaced)")
        analysis_rows.extend([[None] * 6] * 3)
        analysis_rows.extend(rows)
    for line in replaced:
        print("slip analysis:", line)
    return len(replaced)


def apply_slips(schedule_rows, resource_rows, analysis_rows):
    """Apply the transcribed correction slips. Each change names the book's
    existing value; a value the workbook already carries is reported, not
    changed again."""
    import csv
    applied = []
    for name, title in SLIPS:
        with open(FOLDER / name, encoding="utf-8") as handle:
            changes = list(csv.DictReader(handle))
        for change in changes:
            code, field, new = change["code"], change["field"], change["modified"]
            if change["kind"] == "analysis":
                # Analysis lines with this code and description use another code.
                moved = 0
                for line in analysis_rows:
                    if text(line[0]) == code and line[2] and text(line[1]) == change["existing"]:
                        line[0] = int(new) if new.isdigit() else new
                        moved += 1
                applied.append(f"analysis lines {code} {change['existing']} -> {new} ({moved})")
                continue
            rows = schedule_rows if change["kind"] == "schedule" else resource_rows
            row = next((row for row in rows if row[0] == code), None)
            if change["kind"] == "resource" and field == "add":
                if row is None:
                    unit, rate, category = change["existing"].split("|")
                    resource_rows.append([code, new, unit, rate, category])
                    applied.append(f"resource {code} {new} added")
                else:
                    applied.append(f"resource {code} already present")
                continue
            if row is None:
                applied.append(f"{title}: {change['kind']} {code} not found")
                continue
            if change["kind"] == "schedule":
                note = lambda text: row.__setitem__(5, "; ".join(filter(None, [row[5], f"{title}: {text}"])))  # noqa: E731
                if field == "rate":
                    if abs(float(row[3] or 0) - float(new)) < 0.005:
                        applied.append(f"{code} rate {new} already in the workbook")
                        note(f"rate {new}")
                    else:
                        applied.append(f"{code} rate {row[3]} -> {new}")
                        note(f"rate {change['existing']} -> {new}")
                        row[3] = new
                elif field == "delete":
                    rows.remove(row)
                    applied.append(f"{code} deleted")
                elif field == "description":
                    row[1] = new
                    note("description modified")
                    applied.append(f"{code} description replaced")
                elif field == "specification":
                    note(f"specification modified ({change['note']})")
                    applied.append(f"{code} specification noted")
            else:
                if field == "description":
                    lines = row[1].split("\n")
                    row[1] = "\n".join(lines[:-1] + [new])
                    applied.append(f"resource {code} description {new}")
                elif field == "rate":
                    if abs(float(row[3] or 0) - float(new)) < 0.005:
                        applied.append(f"resource {code} rate {new} already in the workbook")
                    else:
                        applied.append(f"resource {code} rate {row[3]} -> {new}")
                        row[3] = new
    for line in applied:
        print("slip:", line)
    return len(applied)


def main():
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else SOURCE
    book = load_workbook(source, read_only=True, data_only=True)
    try:
        schedule_rows = schedule(book)
        analysis_rows = analysis(book, analysis_codes(schedule_rows))
        filled = civil_rates(schedule_rows, analysis_rows)
        resource_rows = resources(book)
        slip_changes = apply_slips(schedule_rows, resource_rows, analysis_rows)
        slip_analyses = apply_slip_analyses(analysis_rows)
        counts = dict(
            schedule=write(FOLDER / "schedule.xlsx", ["Code", "Description", "Unit", "Rate", "Category", "Remarks"], schedule_rows),
            resources=write(FOLDER / "resources.xlsx", ["Code", "Description", "Unit", "Rate", "Category"], resource_rows),
            analysis=write(FOLDER / "analysis.xlsx", None, analysis_rows),  # chapter sheets carry their own headers
            civil_rates_filled=filled,
            slip_changes=slip_changes,
            slip_analyses=slip_analyses,
        )
    finally:
        book.close()
    print(counts)


if __name__ == "__main__":
    main()
