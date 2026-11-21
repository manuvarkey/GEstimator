"""Read the printed DSR 2023 (civil) schedule, Vol. 1 and 2.

poppler's `pdftotext -layout` keeps the four columns (Code No., Description, Unit,
Rate). Every page carries "SUB HEAD : N.0"; a code is taken only in its own
chapter, so codes quoted in other chapters and the appendices are skipped. A code
printed "26.50.1 A" or "2.25(a)" is read as 26.50.1A or 2.25A.

`printed_schedule(pdfs)` returns {code: dict(rate, unit, description)} in book
order. The rate is the first rate printed under the code before the next code;
headings have rate None. A rate printed as a percentage ("20%") gives percent=True. Chapter 1 (carriage by lead) is printed as tables and is
read from the workbook instead.
"""

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

CODE = re.compile(r"^ {0,45}((?:[1-9]|1\d|2[0-6])\.\d+(?: ?[A-Z]\b|\([a-z]\))?(?:\.[A-Za-z]?\d+(?: ?[A-Z]\b)?)*)\.?\s+(\S.*)$")
RATE = re.compile(r"\s{2,}(-?\d[\d,]*\.\d{2}|\d+(?:\.\d+)? ?%)\s*$")
HEAD = re.compile(r"SUB HEAD\s*:\s*(\d+)\.0")
UNIT_COLUMN = 70


def normal(code):
    return re.sub(r"\(([a-z])\)", lambda m: m.group(1).upper(), code.replace(" ", ""))


def text_lines(pdf):
    tool = shutil.which("pdftotext")
    if tool is None:
        raise SystemExit("pdftotext (poppler) is required to read the printed book")
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder) / "book.txt"
        subprocess.run([tool, "-layout", str(pdf), str(target)], check=True)
        return target.read_text(encoding="utf-8", errors="ignore").replace("\f", "\n").splitlines()


def printed_schedule(pdfs):
    items, current, chapter = {}, None, None
    for pdf in pdfs:
        for line in text_lines(pdf):
            head = HEAD.search(line)
            if head:
                chapter = head.group(1)
                continue
            if re.match(r"^\s*APPENDIX", line):
                chapter = current = None
            if chapter is None:
                continue
            match = CODE.match(line)
            if match:
                code, body = normal(match.group(1)), match.group(2)
                level_one = code.count(".") == 1
                if code.split(".")[0] == chapter and len(body) > 3 and not (level_one and body[0].islower()):
                    if code in items:
                        current = None
                        continue
                    current = code
                    items[code] = dict(rate=None, unit=None, percent=False, lines=[])
                    line = line[:match.start(1)] + " " * len(match.group(1)) + line[match.end(1):]
            if current is None or items[current]["rate"] is not None:
                continue
            rate = RATE.search(line)
            if rate and rate.start() >= 60:
                value = rate.group(1).replace(",", "")
                items[current]["percent"] = value.endswith("%")
                items[current]["rate"] = float(value.rstrip("% "))
                left = line[:rate.start()].rstrip()
                unit = re.search(r"\s{2,}(\S+(?: \S+){0,3})$", left)
                if unit and unit.start(1) >= UNIT_COLUMN:
                    items[current]["unit"] = unit.group(1)
                    left = left[:unit.start()]
                line = left
            elif len(line) > UNIT_COLUMN and line[:UNIT_COLUMN].strip() and re.search(r"\s{3,}\S", line[UNIT_COLUMN - 10:]):
                line = re.sub(r"\s{3,}\S+(?: \S+){0,2}\s*$", "", line)
            if not re.match(r"^\s*(Code No|\d+\s+SUB HEAD)", line):
                items[current]["lines"].append(line.strip())
    for item in items.values():
        item["description"] = " ".join(part for part in item.pop("lines") if part)
        item["description"] = re.sub(r"\s+", " ", item["description"]).strip()
    return items
