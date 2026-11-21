"""Build the DSR 2023 (civil) database.

Source: spreadsheets/DSR2023/dsr_combined_ref.sqlite, the tables of an estimating
program holding DSR 2018, 2021 and 2023:

  dsr (CURSR 'DSR-23')  schedule items: code, text, unit, rate, level
  der_itm23             analysis headers: cost basis (COST_FOR), unit, IS_DSR
                        (1 schedule item, 2 sub-analysis such as mortars)
  analy23               analysis lines: IS_BASIC 1 basic rate, 2 another analysis,
                        IS_TEXT text, TITLEHEAD group title ("MATERIAL", "LABOUR")
  b_rates23             basic rates (SR23RATE)

The book's "Basic rates" and "Schedule 1.1/1.2" sheets of
"Master Copy of DSR 2023 and DAR 2023.xlsx" give the resource categories and
printed descriptions and the carriage rates by lead.

Analyses follow DAR 2023: materials and labour (W), 1 % water charges, GST on works
contract by the multiplying factor 0.2127, 15 % CP & OH, 1 % cess, rounded to 0.05.
Schedule items used inside an analysis already include these additions, so they are
added after them (the book's "W-A"). Where an analysis without water charges gives
the book rate (carriage, loading), the water charges line is left out. Sub-analyses
(mortars, chapter 3; others in SUB ANALYSIS) are bare cost.

Every schedule item keeps the DSR 2023 rate. Items whose analysis gives a different
rate by more than Rs 1 say so in their remarks.

Usage: python tools/build_dsr2023.py [output.eproj]
"""

import re
import sqlite3
import sys
import warnings
from collections import Counter, OrderedDict
from decimal import Decimal
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

from estimator import misc  # noqa: E402
from estimator.data.schedule import ResourceItemModel, ScheduleDatabase, ScheduleItemModel  # noqa: E402
from estimator.undo import Stack  # noqa: E402
from tools.printed_dsr2023 import printed_schedule  # noqa: E402

FOLDER = ROOT / "spreadsheets" / "DSR2023"
SOURCE = FOLDER / "dsr_combined_ref.sqlite"
BOOK = FOLDER / "Master Copy of DSR 2023 and DAR 2023.xlsx"
OUTPUT = ROOT / "estimator" / "database" / "DSR2023.eproj"
RESOURCE_CODE = "DC23"

GST_FACTOR = Decimal("0.2127")
RESOURCE_CATEGORIES = ["HIRE CHARGES OF PLANTS & MACHINERY", "LABOUR", "MATERIALS", "CARRIAGE CODES",
                       misc.SUB_ANA_TITLE, "UNCATEGORISED"]
CLASS_CATEGORY = {1: "MATERIALS", 2: "LABOUR", 3: "HIRE CHARGES OF PLANTS & MACHINERY", 4: "CARRIAGE CODES"}
UNITS = {
    "one square metre": "sqm", "each": "each", "one each": "each", "one running metre": "metre",
    "one metre": "metre", "one cubic metre": "cum", "one kilogram": "kg", "100 metre": "100 metre",
    "one quintal": "quintal", "one metric tonne": "tonne", "one joint": "joint", "per test": "per test",
    "each cut": "each cut", "1000 nos": "1000 Nos", "one litre": "litre", "each set": "set", "one set": "set",
    "one pair": "pair", "each pair": "pair", "each job": "job", "per wheel": "per wheel", "each hole": "hole",
    "one hour": "hour", "one kilo litre": "kilolitre", "one cubic decimetre": "cudm", "one centimetre": "cm",
}
REFERENCE = FOLDER / "reference"
# The source numbers 9.27.2.1.1 as 9.27.2.11.
RENAMED = {f"9.27.2.{a}{b}": f"9.27.2.{a}.{b}" for a in (1, 2) for b in (1, 2, 3)}
SIMPLE_UNITS = {"each", "sqm", "metre", "cum", "kg", "100 metre", "quintal", "joint", "each cut", "per test",
                "set", "litre", "pair", "1000 Nos", "per wheel", "job", "tonne", "hole", "kilolitre"}
PRINTED_UNITS = {"MT": "tonne", "each set": "set", "one set": "set", "each job": "job", "per litre": "litre",
                 "each hole": "hole", "kilo litre": "kilolitre"}
UNIT_FIX = {"6.24": "cum per metre depth"}
SHORT_UNITS = {"cum": "cum", "sqm": "sqm", "m": "metre", "nos": "each", "no.": "each", "kg": "kg",
               "qtl": "quintal", "mt": "tonne", "job": "job", "100 m": "100 metre", "joint": "joint",
               "holes": "hole", "times": "times", "units": "unit", "ltr": "litre"}


def text(value):
    value = (value or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in value.split("\n")]
    return "\n".join(line for line in lines if line).strip()


def one_line(value):
    return re.sub(r"\s+", " ", value or "").strip()


def code_key(code):
    key = []
    for part in code.split("."):
        match = re.match(r"(\d+)(.*)", part)
        key.append((0, int(match.group(1)), match.group(2)) if match else (1, 0, part))
    return key


def unit_of(full, short=""):
    cleaned = one_line(full)
    if cleaned.lower() in UNITS:
        return UNITS[cleaned.lower()]
    if cleaned:
        return cleaned[0].lower() + cleaned[1:]
    return SHORT_UNITS.get(one_line(short).lower(), one_line(short))


def number(value):
    value = Decimal(str(value))
    return format(value.normalize(), "f") if value == value.to_integral() or value.as_tuple().exponent < -2 else str(value)


def nearest(code, codes):
    """Parent of a code: the nearest existing shorter code (9.147.A1 is under 9.147A)."""
    parts = code.split(".")
    while len(parts) > 1:
        parts = parts[:-1]
        candidate = ".".join(parts)
        if candidate in codes:
            return candidate
        if candidate + "A" in codes and candidate not in codes and "." in candidate and len(parts) >= 2 and code.split(".")[len(parts)][:1].isalpha():
            return candidate + "A"
    return None


def read_book():
    """Basic rates (category, description, unit, rate) and carriage rates by lead."""
    book = openpyxl.load_workbook(BOOK, read_only=True, data_only=True)
    basic, section = {}, None
    names = {"0.1": RESOURCE_CATEGORIES[0], "0.2": "LABOUR", "0.3": "MATERIALS", "0.4": "CARRIAGE CODES"}
    for row in book["Basic rates"].iter_rows(values_only=True):
        first = str(row[0]).strip() if row[0] is not None else ""
        if re.match(r"0\.\d ", first) and not row[2]:
            section = names[first[:3]]
        elif first and row[1] and row[2] and section:
            basic[first.rstrip("*")] = dict(category=section, description=text(str(row[1])), unit=one_line(str(row[2])),
                                           rate=row[3])
    carriage = {}
    for row in book["Schedule 1.1"].iter_rows(values_only=True):
        if isinstance(row[0], str) and row[0].startswith("1.1.") and isinstance(row[3], (int, float)):
            carriage[row[0].strip()] = ("mechanical", row[3:11], row[11])
    for row in book["Schedule 1.2"].iter_rows(values_only=True):
        if isinstance(row[0], str) and row[0].startswith("1.2.") and isinstance(row[3], (int, float)):
            carriage[row[0].strip()] = ("manual", row[3:5], row[5])
    return basic, carriage


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else OUTPUT
    if output.exists():
        raise SystemExit(f"{output} exists; remove it first")
    src = sqlite3.connect(SOURCE)
    src.row_factory = sqlite3.Row
    basic_book, carriage = read_book()
    brates = {row["RATE_CODE"]: row for row in src.execute("SELECT * FROM b_rates23")}
    der = {row["ITM_CODE"]: row for row in src.execute("SELECT * FROM der_itm23")}
    lines = {}
    for row in src.execute("SELECT * FROM analy23 ORDER BY ITM_CODE, LINE_NO"):
        lines.setdefault(row["ITM_CODE"], []).append(row)
    chapters = {row["SH_NO"]: one_line(row["SH"]).upper() for row in src.execute("SELECT * FROM sh") if row["SH_NO"] != "00"}
    warnings_out = []

    # Schedule rows (the table repeats a few rows), reconciled with the printed book.
    printed = printed_schedule([REFERENCE / "DSR_Vol_1_Civil.pdf", REFERENCE / "DSR_Vol_2_Civil.pdf"])
    sched = OrderedDict()
    for row in src.execute("SELECT * FROM dsr WHERE CURSR='DSR-23'"):
        row = dict(row)
        row["DSR_CODE"] = RENAMED.get(row["DSR_CODE"], row["DSR_CODE"])
        sched.setdefault(row["DSR_CODE"], row)
    source_parents = {nearest(code, sched) for code in sched}
    der_by_code = {row["DSR_CODE"]: itm for itm, row in der.items() if row["IS_DSR"] == 1 and row["DSR_CODE"]}
    book_changes = []
    for code in [c for c in sched if c not in source_parents and not c.startswith("1.") and c not in printed]:
        book_changes.append(f"{code}: not in the printed book, left out")
        del sched[code]
    printed_parents = {code.rsplit(".", 1)[0] for code in printed}
    for code, item in printed.items():
        if (code not in sched and code not in printed_parents and item["rate"] and code.split(".")[0] not in ("1", "3")
                and not code.endswith(".0")):
            book_changes.append(f"{code}: added from the printed book")
            sched[code] = dict(DSR_CODE=code, ITM_CODE=der_by_code.get(code, code), DES_ITEM=item["description"],
                               UNIT_FUL="", UNIT_NAME="", EST_RATE=item["rate"], SH_NO=f"{int(code.split('.')[0]):02d}")
    for code, row in sched.items():
        book = printed.get(code)
        if code.startswith("1.") or not book or book["rate"] is None or code in source_parents:
            continue
        rate = Decimal(str(book["rate"]))
        if (row["EST_RATE"] or 0) < 0:
            rate = -rate  # deductions: the book prints the amount, the source keeps the sign
        if rate != Decimal(str(row["EST_RATE"] or 0)):
            book_changes.append(f"{code}: source rate {row['EST_RATE'] or 'none'}, printed {book['rate']}")
            row["EST_RATE"] = rate
        unit = PRINTED_UNITS.get(book["unit"], book["unit"])
        if unit in SIMPLE_UNITS and (unit_of(row["UNIT_FUL"], row["UNIT_NAME"]) in SIMPLE_UNITS | {""}):
            row["UNIT_FUL"], row["UNIT_NAME"] = unit, unit
        elif code in UNIT_FIX:
            row["UNIT_FUL"] = UNIT_FIX[code]
    codes = set(sched)

    def parent_of(code):
        return nearest(code, codes)

    children = Counter(parent_of(code) for code in codes)
    by_itm = {row["ITM_CODE"]: code for code, row in sched.items()}

    # Codes of analyses: schedule items by DSR code, mortars by their DAR code, other sub-analyses SA.
    analysis_code = {itm: code for itm, code in by_itm.items() if itm in der}
    mortars = []
    for itm, row in der.items():
        match = re.match(r"DAR-2023.*Item Code\s*:\s*(3\.\d+)$", one_line(row["REF_DAR"]))
        if itm.startswith("03.0") and row["IS_DSR"] == 2 and match:
            analysis_code[itm] = match.group(1)
            mortars.append(itm)
    owners = {}
    reach, stack = set(), [itm for itm in analysis_code]
    while stack:
        itm = stack.pop()
        if itm in reach:
            continue
        reach.add(itm)
        for line in lines.get(itm, []):
            if line["IS_BASIC"] == 2:
                if line["RATE_CODE"] in der:
                    owners.setdefault(line["RATE_CODE"], []).append(itm)
                    stack.append(line["RATE_CODE"])
                else:
                    warnings_out.append(f"{analysis_code.get(itm, itm)}: analysis {line['RATE_CODE']} not found")
    subs, pending = [], sorted(itm for itm in reach if itm not in analysis_code)
    serial = Counter()
    while pending:  # a sub-analysis is named after the first item using it, outer ones first
        ready = [itm for itm in pending if any(o in analysis_code for o in owners[itm])]
        if not ready:
            raise SystemExit(f"sub-analyses without an owner: {pending}")
        for itm in sorted(ready, key=lambda i: code_key(min((analysis_code[o] for o in owners[i] if o in analysis_code), key=code_key))):
            owner = min((analysis_code[o] for o in owners[itm] if o in analysis_code), key=code_key)
            serial[owner] += 1
            analysis_code[itm] = f"{owner}.SA{serial[owner]}"
            subs.append(itm)
        pending = [itm for itm in pending if itm not in analysis_code]

    def unit_for(itm):
        if itm in by_itm:
            return unit_of(sched[by_itm[itm]]["UNIT_FUL"], sched[by_itm[itm]]["UNIT_NAME"])
        row = der[itm]
        return SHORT_UNITS.get(one_line(row["DUNIT_NAME"]).lower(), one_line(row["DUNIT_NAME"]))

    # Resources.
    resources = {}

    def resource(code, line_description=""):
        if code in resources:
            return resources[code]
        row, book = brates.get(code), basic_book.get(code)
        if row is None:
            warnings_out.append(f"basic rate {code} not found")
            return None
        rate = Decimal(str(row["SR23RATE"] or 0))
        category = book["category"] if book else CLASS_CATEGORY.get(row["ITM_CLS"], "UNCATEGORISED")
        if row["ISCARRIAGE"] == 1:
            category = "CARRIAGE CODES"
        reference = ""
        if category == "CARRIAGE CODES" and book and book["rate"]:
            reference = f"Basic rates list Rs {book['rate']}; DAR 2023 analyses take carriage as nil"
        description = book["description"] if book else text(row["FULLDES"] if len(row["FULLDES"] or "") > len(row["ITEM_DES"] or "") else row["ITEM_DES"])
        description = description or one_line(line_description)
        unit = book["unit"] if book else one_line(row["DFULL_UNIT"]).lower().replace("l.s.", "L.S.").replace("nos", "Nos")
        if category == "CARRIAGE CODES" and "carriage" not in description.lower():
            description = "Carriage of " + description[0].lower() + description[1:]
        if not book:
            warnings_out.append(f"basic rate {code} ({description[:50]}) is not in the book's basic rates")
        resources[code] = ResourceItemModel(code, description, unit, rate, Decimal(0), Decimal(0), reference, category)
        return resources[code]

    def cost_basis(head):
        unit = one_line(head["DUNIT_NAME"])
        return f"Details of cost for {number(head['COST_FOR'] or 1)} {SHORT_UNITS.get(unit.lower(), unit)}"

    # Analyses.
    models, rates, computed = {}, {}, {}
    building = set()

    def published(itm):
        return Decimal(str(sched[by_itm[itm]]["EST_RATE"] or 0)) if itm in by_itm else None

    def title(value):
        value = one_line(value)
        value = re.sub(r"^\(?[a-zA-Z]\)\s*", "", value)
        return re.sub(r"[\s:\-.]+$", "", value).upper()

    def build(itm, water=True, scale=Decimal(1)):
        head = der[itm]
        own = analysis_code[itm]
        item = ScheduleItemModel(own, "", unit_for(itm), 0)
        groups, current, pending, a_rows, used = [], None, [], [], {}
        for line in lines.get(itm, []):
            if line["IS_TEXT"] == 1 and line["IS_BASIC"] in (0, None):
                if line["TITLEHEAD"] == 1 and title(line["TEXT"]):
                    current = [title(line["TEXT"]), []]
                    groups.append(current)
                elif one_line(line["TEXT"]):
                    pending.append(one_line(line["TEXT"]))
                continue
            if line["IS_BASIC"] == 1:
                res = resource(line["RATE_CODE"], line["ITEM_DES"])
                if res is None:
                    continue
                target_code = res.code
            elif line["IS_BASIC"] == 2:
                ref = line["RATE_CODE"]
                if ref not in der:
                    continue
                target_code = analysis_code[ref]
                if target_code not in used:
                    res = ResourceItemModel(target_code, f"Rate as per item {target_code}: {one_line(der[ref]['DITM_DES'])}",
                                            unit_for(ref), rate_of(ref), Decimal(0), Decimal(0), "", misc.SUB_ANA_TITLE)
                    resources.setdefault(target_code, res)
                res = resources[target_code]
            else:
                continue
            remark = " ".join(pending)
            pending = []
            description = one_line(line["ITEM_DES"])
            extra = re.findall(r"\([^()]*\d[^()]*\)", description)
            extra = [e for e in extra if e not in res.description and e not in remark]
            if extra:
                remark = (remark + " " + " ".join(extra)).strip()
            row = [res.code, Decimal(str(line["A_QTY"] or 0)), remark]
            used[res.code] = res
            if line["IS_BASIC"] == 2 and der[line["RATE_CODE"]]["IS_DSR"] == 1:
                a_rows.append(row)
            else:
                if current is None:
                    current = ["MATERIAL", []]
                    groups.append(current)
                current[1].append(row)
        for name, rows in groups:
            if rows:
                item.add_ana_group(name, rows)
        cost_for = Decimal(str(head["COST_FOR"] or 1)) / scale
        if head["IS_DSR"] == 1:
            item.add_ana_sum('TOTAL (W)' if not a_rows else 'TOTAL (W-A)')
            if water:
                item.add_ana_weight('Add 1 % water charges on "W"', Decimal("0.01"))
                item.add_ana_sum("TOTAL (X)")
            item.add_ana_weight(f'Add GST on "X" (multiplying factor {GST_FACTOR})', GST_FACTOR)
            item.add_ana_sum("TOTAL (Y)")
            item.add_ana_weight('Add 15 % CP & OH on "Y"', Decimal("0.15"))
            item.add_ana_sum("TOTAL (Z)")
            item.add_ana_weight('Add cess @ 1 % on "Z"', Decimal("0.01"))
            item.add_ana_sum("TOTAL")
            if a_rows:
                item.add_ana_group("ITEMS AT SCHEDULE RATES (A), INCLUSIVE OF OVERHEADS", a_rows)
                item.add_ana_sum("TOTAL")
        else:
            item.add_ana_sum("TOTAL")
        if cost_for != 1:
            item.add_ana_times(f"Cost for 1 {item.unit}", Decimal(1) / cost_for)
        if head["IS_DSR"] == 1 or itm in mortars:
            item.add_ana_round("Say", 2.5)
        item.resources = used
        item.evaluate_results()
        if not item.ana_items or not any(entry["itemtype"] == ScheduleItemModel.ANA_GROUP for entry in item.ana_items):
            return None, None
        return item, Decimal(item.get_ana_rate())

    def rate_of(itm):
        """Rate of an analysis referenced by another: the book rate of a schedule item,
        the analysis of a sub-analysis."""
        book = published(itm)
        if book:
            return book
        if itm not in computed:
            if itm in building:
                warnings_out.append(f"{analysis_code[itm]}: circular reference")
                return Decimal(0)
            building.add(itm)
            computed[itm] = analysis(itm)[1] or Decimal(0)
        return computed[itm]

    def analysis(itm):
        if itm in models:
            return models[itm]
        model, value = build(itm)
        book = published(itm)
        if model is not None and book and der[itm]["IS_DSR"] == 1 and abs(value - book) > Decimal("0.05"):
            # Carriage and loading analyses have no water charges; some source analyses
            # price 10, 100 or 1000 units with the cost basis left at 1.
            for water, scale in [(False, 1)] + [(w, Decimal(k)) for k in ("10", "100", "1000", "0.1", "0.01") for w in (True, False)]:
                other, other_value = build(itm, water=water, scale=scale)
                if abs(other_value - book) < abs(value - book) and (scale == 1 or abs(other_value - book) <= Decimal("0.10")):
                    model, value = other, other_value
        models[itm] = (model, value)
        return models[itm]

    # Schedule items in book order, two levels (headings, priced items).
    out = ScheduleDatabase(Stack())
    out.create_new_database(str(output))
    settings = dict(misc.default_project_settings)
    settings.update(project_name="DSR 2023", project_item_code="DSR23", project_resource_code=RESOURCE_CODE,
                    project_metadata=(FOLDER / "database_notes.md").read_text(encoding="utf-8"))
    out.set_project_settings(settings)
    numbers = sorted({row["SH_NO"] for row in sched.values()} | {"03"})
    for chapter in numbers:
        out.insert_schedule_category_atomic(chapters[chapter], path=[-1])
    out.insert_schedule_category_atomic(misc.SUB_ANA_TITLE, path=[-1])
    for name in RESOURCE_CATEGORIES:
        out.insert_resource_category_atomic(name, path=[-1])

    items, report = [], Counter()
    mismatch = []

    def chain(code):
        result = []
        while code:
            result.append(code)
            code = parent_of(code)
        return result[::-1]

    for code in sorted(codes, key=lambda c: (code_key(chain(c)[0]), c != chain(c)[0], code_key(c))):
        row = sched[code]
        path = chain(code)
        is_heading = children[code] > 0
        if is_heading and len(path) > 1:
            continue  # a sub-heading: its text goes into its items
        description = "\n".join(text(sched[c]["DES_ITEM"]) for c in path[1:]) if len(path) > 1 else text(row["DES_ITEM"])
        unit = "" if is_heading else unit_of(row["UNIT_FUL"], row["UNIT_NAME"])
        rate = Decimal(0) if is_heading else Decimal(str(row["EST_RATE"] or 0))
        remarks, ana_remarks, model = "", None, None
        if code in carriage:
            kind, values, note = carriage[code]
            if kind == "mechanical":
                description += " Lead - 5 Km"
                rate = Decimal(str(values[4]))
                remarks = ("Lead 1 km Rs {}, 2 km Rs {}, 3 km Rs {}, 4 km Rs {}, 5 km Rs {}; per additional km beyond 5 km "
                           "up to 10 km Rs {}, beyond 10 km up to 20 km Rs {}, beyond 20 km Rs {}.").format(*values)
            else:
                description += " Lead - first 50 m"
                rate = Decimal(str(values[0]))
                remarks = f"Every additional lead of 50 m or part thereof (up to 9 such leads) Rs {values[1]}."
            if note and len(str(note)) > 20:
                remarks += " " + one_line(str(note))
        elif not is_heading and not rate:
            warnings_out.append(f"{code}: no rate")
        if not is_heading and row["ITM_CODE"] in der:
            model, value = analysis(row["ITM_CODE"])
            if model is not None:
                head = der[row["ITM_CODE"]]
                ana_remarks = cost_basis(head)
                if abs(value - rate) > 1:
                    remarks = f"The analysis gives Rs {value}; the rate is the DSR 2023 rate."
                    mismatch.append((code, rate, value))
                elif value != rate:
                    report["small differences"] += 1
        items.append(dict(code=code, description=description, unit=unit, rate=rate, remarks=remarks,
                          ana_remarks=ana_remarks, category=chapters[row["SH_NO"]],
                          parent=path[0] if len(path) > 1 else None, model=model))

    for itm in sorted(mortars, key=lambda i: code_key(analysis_code[i])):
        model, value = analysis(itm)
        head = der[itm]
        items.append(dict(code=analysis_code[itm], description=text(head["DITM_DES"]), unit=model.unit, rate=value,
                          remarks="Sub-analysis: bare cost of materials and labour, no overheads. Used inside other analyses.",
                          ana_remarks=cost_basis(head),
                          category=chapters["03"], parent=None, model=model))
    for itm in sorted(subs, key=lambda i: code_key(analysis_code[i])):
        model, value = analysis(itm)
        head = der[itm]
        if model is None:
            warnings_out.append(f"{analysis_code[itm]}: empty sub-analysis {itm}")
            model, value = ScheduleItemModel(analysis_code[itm], "", unit_for(itm), 0), Decimal(0)
        owner = analysis_code[itm].rsplit(".SA", 1)[0]
        items.append(dict(code=analysis_code[itm], description=text(head["DITM_DES"]), unit=model.unit, rate=value,
                          remarks=f"Sub-analysis for item {owner}" + (f" ({one_line(head['REF_DAR'])})" if one_line(head["REF_DAR"]) else ""),
                          ana_remarks=cost_basis(head),
                          category=misc.SUB_ANA_TITLE, parent=None, model=model))

    # Resource rates of sub-analyses follow their items.
    item_rates = {entry["code"]: entry["rate"] for entry in items}
    for code, res in resources.items():
        if res.category == misc.SUB_ANA_TITLE:
            res.rate = item_rates.get(code, res.rate)
            res.unit = next((e["unit"] for e in items if e["code"] == code), res.unit)
    for name in RESOURCE_CATEGORIES:
        for res in sorted((r for r in resources.values() if r.category == name), key=lambda r: code_key(r.code) if name == misc.SUB_ANA_TITLE else (0, r.code)):
            if not out.insert_resource_atomic(res):
                raise SystemExit(f"resource {res.code} not inserted")

    for entry in items:
        model = entry.pop("model")
        item = ScheduleItemModel(entry["code"], entry["description"], entry["unit"], entry["rate"],
                                 0 if not entry["unit"] else 1, category=entry["category"], parent=entry["parent"],
                                 remarks=entry["remarks"], ana_remarks=entry["ana_remarks"])
        if model is not None:
            item.ana_items = model.ana_items
            item.resources = {code: resources[code] for code in model.resources}
        if not out.insert_item_atomic(item):
            raise SystemExit(f"{entry['code']} not inserted")
        report["items"] += 1
        report["analyses"] += model is not None

    # Check: every analysis in the saved database evaluates as built.
    differs = []
    for entry in items:
        saved = out.get_item(entry["code"])
        if saved.ana_items and saved.get_ana_rate() is not None:
            value = Decimal(saved.get_ana_rate())
            if abs(value - entry["rate"]) > 1 and entry["code"] not in {m[0] for m in mismatch}:
                differs.append((entry["code"], entry["rate"], value))
    out.close_database()

    print(f"{output.name}: {report['items']} items, {report['analyses']} analyses, {len(resources)} resources, "
          f"{len(mortars)} mortars, {len(subs)} other sub-analyses")
    print(f"analysis differs from the DSR rate: by more than Rs 1 {len(mismatch)}, by up to Rs 1 {report['small differences']}")
    for code, rate, value in mismatch:
        print(f"  {code}: rate {rate}, analysis {value}")
    print(f"reconciled with the printed book: {len(book_changes)}")
    for change in book_changes:
        print("  ", change)
    print(f"saved analyses not as built: {len(differs)}", differs[:10])
    print(f"warnings: {len(warnings_out)}")
    for warning in sorted(set(warnings_out), key=lambda w: code_key(w.split(":")[0]) if re.match(r"\d", w) else [(2, 0, w)]):
        print("  ", warning)


if __name__ == "__main__":
    main()
