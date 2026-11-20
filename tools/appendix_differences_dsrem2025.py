"""List the differences between the printed DSR (E&M) 2025 appendices and the
prepared resources (spreadsheets/DSREM2025/resources.xlsx), for review.

Writes spreadsheets/DSREM2025/printed_appendix_differences.csv with, for every
code that differs: the workbook and printed description, unit and rate, what
differs, and the rates the book's analyses use for that code.

Usage: python tools/appendix_differences_dsrem2025.py  (after prepare_dsrem2025.py)
"""

import csv
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parent))
from printed_dsrem2025 import printed_appendix  # noqa: E402

FOLDER = Path(__file__).resolve().parent.parent / "spreadsheets" / "DSREM2025"
PRINTED = Path(os.environ.get("DSREM2025_PRINTED", FOLDER / "reference" / "DSR E&M 2025.pdf"))
UNITS = {"meter": "metre", "mtr": "metre", "no": "each", "nos": "each", "sqm": "sq m", "per sq meter": "sq m"}


def normal(text):
    return " ".join(re.sub(r"[^a-z0-9½]+", " ", str(text or "").lower()).split())


def unit_key(text):
    key = normal(text).replace("per ", "")
    return UNITS.get(key, key)


def main():
    if not PRINTED.exists():
        raise SystemExit(f"The printed book is required: {PRINTED} (or set DSREM2025_PRINTED)")
    workbook = {}
    for code, description, unit, rate, category in load_workbook(FOLDER / "resources.xlsx", read_only=True).active.iter_rows(min_row=2, values_only=True):
        workbook.setdefault(str(code), (description or "", unit or "", rate, category or ""))
    used = defaultdict(set)
    for row in load_workbook(FOLDER / "analysis.xlsx", read_only=True).active.iter_rows(values_only=True):
        if row[0] is not None and row[2] and isinstance(row[4], (int, float)):
            used[str(row[0]).strip()].add(round(row[4], 2))
    slip = {}
    with open(FOLDER / "correction_slip_1.csv", encoding="utf-8") as handle:
        for change in csv.DictReader(handle):
            if change["kind"] == "resource":
                slip[change["code"]] = f"Correction Slip No. 1: {change['field']} {change['existing']} -> {change['modified']}. {change['note']}".strip()
    printed = {}
    for code, description, unit, rate, section, context in printed_appendix(PRINTED):
        printed.setdefault(code, (description, unit, rate, section, context))
    records = []
    for code in sorted(set(workbook) | set(printed), key=lambda value: (len(value), value)):
        mine, theirs = workbook.get(code), printed.get(code)
        differs = []
        if mine is None:
            differs.append("only printed")
        elif theirs is None:
            differs.append("only workbook")
        else:
            name = mine[0].split("\n")[-1]
            # Superscripts split numbers in the print ("68 0 centigrade", "kg/cm 2").
            if normal(name).replace(" ", "") != normal(theirs[0]).replace(" ", ""):
                differs.append("description")
            if unit_key(mine[1]) != unit_key(theirs[1]):
                differs.append("unit")
            try:
                # The print rounds half rupees (49.50 -> 50); smaller differences are not listed.
                if theirs[2] and abs(float(mine[2]) - float(theirs[2])) >= 1:
                    differs.append("rate")
            except (TypeError, ValueError):
                differs.append("rate")
        if not differs:
            continue
        records.append(dict(
            code=code, differs=", ".join(differs),
            workbook_description=(mine[0] if mine else "").replace("\n", " / "),
            printed_description=theirs[0] if theirs else "",
            printed_context=theirs[4] if theirs else "",
            printed_section=theirs[3] if theirs else "",
            workbook_unit=mine[1] if mine else "", printed_unit=theirs[1] if theirs else "",
            workbook_rate=mine[2] if mine else "", printed_rate=theirs[2] if theirs else "",
            analysis_rates=", ".join(f"{value:g}" for value in sorted(used.get(code, ()))),
            note=slip.get(code, ""),
        ))
    path = FOLDER / "printed_appendix_differences.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    counts = defaultdict(int)
    for record in records:
        for kind in record["differs"].split(", "):
            counts[kind] += 1
    print(f"{len(records)} codes differ: {dict(counts)}; written to {path}")


if __name__ == "__main__":
    main()
