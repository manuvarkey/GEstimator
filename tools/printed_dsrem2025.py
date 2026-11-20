"""Read the printed DSR (E&M) 2025 book (`DSR E&M 2025.pdf`), the authoritative text.

poppler's `pdftohtml -xml` gives every text fragment with its position and
font size. Pages are laid out in four columns (Item No., Description, Unit,
Rate); chapter titles are set in 16 pt and the centred subheadings that name a
group of items ("2 MP IP IR Dome Camera") in 14 pt.

`printed_schedule(pdf)` returns the schedule items in book order as
[code, description, unit, rate, subheading, printed code]; `printed_appendix(pdf)` the
Appendix I/II rows as [code, description, unit, rate]. Descriptions keep the
book's numbered specification lists on separate lines.
"""

import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ElementTree
from pathlib import Path

CODE = re.compile(r"^\d+(\.\d+)+$")
RESOURCE_CODE = re.compile(r"^\d{4}[A-Z]?$")
LIST_ITEM = re.compile(r"^(\(?\d{1,2}\)|\(?[a-z]\)|\(?[ivx]+\)|\d{1,2}\.\s|[•\-–]\s)")
NUMBER = re.compile(r"^-?[\d,]+(\.\d+)?$")
# Column boundaries (points at zoom 1): Item No. | Description | Unit | Rate.
DESCRIPTION, UNIT, RATE = 100, 450, 505


def fragments(pdf):
    """Yield (page, page height, top, left, width, size, text) for every text fragment."""
    tool = shutil.which("pdftohtml")
    if tool is None:
        raise SystemExit("pdftohtml (poppler) is required to read the printed book")
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder) / "book"
        subprocess.run([tool, "-xml", "-i", "-nomerge", "-q", "-zoom", "1", str(pdf), str(target)], check=True)
        root = ElementTree.parse(target.with_suffix(".xml")).getroot()
    for page in root.iter("page"):
        sizes = {spec.get("id"): float(spec.get("size")) for spec in root.iter("fontspec")}
        height = float(page.get("height"))
        for text in page.iter("text"):
            value = " ".join("".join(text.itertext()).replace(" ", " ").split())
            if value:
                yield (int(page.get("number")), height, int(text.get("top")), int(text.get("left")),
                       int(text.get("width")), sizes.get(text.get("font"), 12.0), value)


def lines(pdf, first_marker, last_marker):
    """Text lines between two markers: (page, top, [(left, width, size, text)…])."""
    started = False
    current, key = [], None
    for page, height, top, left, width, size, value in fragments(pdf):
        if value.upper().replace(" ", "").startswith(first_marker):
            started = True
        if not started:
            continue
        if last_marker and value.upper().replace(" ", "").startswith(last_marker):
            break
        if top > height - 90 and ("DELHI SCHEDULE OF RATE" in value.upper() or NUMBER.match(value)):
            continue  # page footer
        if key is None or page != key[0] or abs(top - key[1]) > 3:
            if current:
                yield key[0], key[1], sorted(current)
            current, key = [], (page, top)
        current.append((left, width, size, value))
    if current:
        yield key[0], key[1], sorted(current)


def columns(parts, boundary=DESCRIPTION):
    """Split a line into code, description, unit and rate by position."""
    split = []
    for left, width, size, text in parts:
        # A narrow gap merges the code with the description ("11.1.10  3 X 35 sq. mm").
        match = re.match(r"^(\d+(?:\.\d+)+|\d{4}[A-Z]?)\s+(\S.*)$", text) if left < boundary else None
        merged_rate = re.match(r"^(\D.*?)\s+(-?[\d,]+(?:\.\d+)?)$", text) if UNIT <= left < RATE else None
        if match:
            split += [(left, 0, size, match[1]), (boundary, width, size, match[2])]
        elif merged_rate:
            # A narrow gap merges the unit with the rate ("Each 601606").
            split += [(left, 0, size, merged_rate[1]), (RATE, width, size, merged_rate[2])]
        else:
            split.append((left, width, size, text))
    parts = split
    code = " ".join(text for left, width, size, text in parts if left < boundary)
    description = [(left, size, text) for left, width, size, text in parts if boundary <= left < UNIT]
    # A number in the unit area is a rate set a little to the left ("38,870").
    unit = " ".join(text for left, width, size, text in parts if UNIT <= left < RATE and not number(text))
    rate = " ".join(text for left, width, size, text in parts if left >= RATE or (UNIT <= left < RATE and number(text)))
    return code.strip(), description, unit.strip(), rate.strip()


def paragraph(text_lines):
    """Join description lines: list items and blank-line gaps start a new line."""
    result, previous = [], None
    for (page, top), text in text_lines:
        # A blank line within a page starts a new line; a page break does not.
        gap = previous is not None and previous[0] == page and top - previous[1] > 22
        if result and (LIST_ITEM.match(text) or gap):
            result.append("\n" + text)
        elif result:
            result.append(" " + text)
        else:
            result.append(text)
        previous = (page, top)
    return re.sub(r"[ \t]+", " ", "".join(result)).strip()


def number(text):
    text = text.replace(",", "").replace("₹", "").strip()
    return text if NUMBER.match(text) else ""


def printed_schedule(pdf):
    items, current, pending, chapter, in_title = [], None, [], None, False
    for page, top, parts in lines(pdf, "CHAPTER-1", "APPENDIX-I"):
        code, description, unit, rate = columns(parts)
        whole = " ".join(part[3] for part in parts)
        title = re.match(r"\s*CHAPTER\s*[-–]?\s*(\d+)", whole.upper())
        if title:
            # The title (one or two lines, in varying sizes) runs to the column headings.
            current, pending, chapter, in_title = None, [], title[1], True
            continue
        if code.lower().startswith("item no"):
            in_title = False
            continue  # column headings
        if in_title:
            continue
        size = max(part[2] for part in parts)
        text = " ".join(part[2] for part in description)
        if not code and text and size >= 13.5:
            pending.append(text)  # subheading over the next items
            continue
        if CODE.match(code):
            printed = code
            if chapter and code.split(".")[0] != chapter:
                # Chapter 38 is printed as 36.1–36.5.
                code = chapter + code[len(code.split(".")[0]):]
            current = dict(code=code, lines=[], unit="", rate="", subheading="\n".join(pending), printed=printed)
            pending = []
            items.append(current)
        elif code and current is None:
            continue
        if current is None:
            continue
        if text and current["rate"] and not code:
            letters = [c for c in text if c.isalpha()]
            if (not pending and current["lines"] and current["lines"][-1][0][0] != page
                    and not all(c.isupper() for c in letters) and not LIST_ITEM.match(text)):
                # The first line of a page that finishes the item before the page
                # break ("CM/Min (Minimum)" of 9.2.3, "loading < 5300watt)" of 24.27.23).
                current["lines"].append(((page, top), text))
                continue
            pending.append(text)  # after an item's rate: the heading of the next items
            continue
        if text:
            current["lines"].append(((page, top), text))
        if unit and not current["rate"]:
            current["unit"] = f"{current['unit']} {unit}".strip()  # a unit may wrap ("Per sq / meter")
        if number(rate) and not current["rate"]:
            current["rate"] = number(rate)
    result = []
    for item in items:
        description = paragraph(item["lines"])
        if description.upper().startswith("DELETED"):
            continue  # withdrawn items keep their number in the book only
        result.append([item["code"], description, item["unit"], item["rate"], item["subheading"], item["printed"]])
    return result


def printed_appendix(pdf):
    """Appendix I/II rows [code, description, unit, rate, section, context].

    Lines between items are either a section heading (upper case, e.g.
    "METAL BOXES") or context for the short items that follow ("LED Down
    lighter … of following wattage" before "5 - 7 watt"); both are returned
    separately, not joined to the previous item."""
    rows, current, section, context, fresh = [], None, "", [], False
    for page, top, parts in lines(pdf, "APPENDIX-I", None):
        code, description, unit, rate = columns(parts, boundary=90)  # Appendix I descriptions start at x = 99
        text = " ".join(part[2] for part in description)
        if code.upper().startswith("CODE") or text.upper() in ("DESCRIPTION", "DESCRIPTION UNIT"):
            continue
        if RESOURCE_CODE.match(code):
            current = dict(code=code, lines=[], unit="", rate="", section=section, context=list(context))
            rows.append(current)
            fresh = False
        elif code:
            continue
        elif text and (current is None or current["rate"]):
            letters = [c for c in text if c.isalpha()]
            if letters and all(c.isupper() for c in letters):
                section, context, fresh = text, [], False
            else:
                context = context + [text] if fresh else [text]
                fresh = True
            continue
        if current is None:
            continue
        if text:
            current["lines"].append(((page, top), text))
        if unit and (not current["rate"] or not current["unit"]):
            current["unit"] = f"{current['unit']} {unit}".strip()  # a unit may wrap ("Per sq / meter")
        if number(rate) and not current["rate"]:
            current["rate"] = number(rate)
    return [[row["code"], paragraph(row["lines"]), row["unit"], row["rate"], row["section"], " ".join(row["context"])]
            for row in rows]
