"""Reconcile imported DSR (E&M) 2025 analyses with the book.

The analysis import links every resource line to the Appendix II resource with
the same code and keeps the book's coefficient (quantity). Coefficients are
never changed here. For each resource line:

- a line whose code is an Appendix II resource of that kind stays as it is; if
  the book's amount differs from coefficient × Appendix II rate (the book used
  another rate, or its arithmetic slipped), the difference is documented;
- a codeless line, or one whose code is another resource in Appendix II
  (19.9.3 lists an XLR connector under 5164, a keypad controller), is linked to
  the Appendix II resource with the same description when there is one;
- otherwise the coefficient is available but no Appendix II rate is: the line
  gets its own resource whose rate is back-calculated from the book (amount ÷
  coefficient), in category RESOURCES FROM ANALYSES.

Rows the book prices without a coefficient ("Add for screws etc. LS 260",
which the importer skips) are missing resources: they become the "Unit item"
resource X (rate 1, quantity = amount) before the following subtotal. A book
subtotal that adds a row twice is documented, not reproduced. A per-unit step
the book works out after rounding (30.21) is added when it brings the
analysis to the published rate.

Every change and every documented difference goes into the line remarks
(after any remark from the book) and into corrections.csv / discrepancies.csv.
Edits go through the desktop operations (analysis.load, edit, add,
resource.add, analysis.apply), so they are the same as editing by hand.
"""

import csv
import hashlib
import re
from decimal import Decimal, ROUND_HALF_UP

from modern.backend import analysis_import

UNIT_CODE = "X"
UNIT_ITEM = dict(code=UNIT_CODE, description="Unit item", unit="Rs", rate="1", category="UNIT ITEMS")
DERIVED_CATEGORY = "RESOURCES FROM ANALYSES"
GENERATED = re.compile(r"^R[0-9A-F]{6}$")  # importer codes for lines without a code
CENT = Decimal("0.01")


def money(value):
    return Decimal(value).quantize(CENT, ROUND_HALF_UP)


def number(value):
    """Plain text for a quantity or rate (no exponent, no trailing zeros)."""
    return format(Decimal(value).normalize(), "f")


def words(text):
    tokens = re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", (text or "").lower())
    stemmed = []
    for token in tokens:
        if token.endswith("men"):
            token = token[:-3] + "man"
        elif len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
            token = token[:-1]
        stemmed.append(token)
    return stemmed


def similarity(book, appendix):
    """Share of the book description's words found in the Appendix II description."""
    book_words, appendix_words = words(book), set(words(appendix))
    if not book_words:
        return 0.0
    return sum(word in appendix_words for word in book_words) / len(book_words)


def sheet_drafts(path):
    """Parsed analyses with the book figures the importer does not keep.

    Returns ({code: [draft, alternative drafts…]}, {id(line entry): figures},
    {id(draft): [finding, …]}). Findings are rows the importer skipped, book
    subtotals that differ from the lines above them, and rows after the
    rounded rate.
    """
    figures, findings = {}, {}
    block_class = analysis_import._Block
    add_resource, warn, numeric_row = block_class.add_resource, block_class.warn, block_class.numeric_row

    def capture_resource(block, line, code, description, unit, qty, rate, amount):
        add_resource(block, line, code, description, unit, qty, rate, amount)
        # The importer fills a blank coefficient from amount ÷ rate; use its value.
        filled = Decimal(block.last_resource[1] or 0)
        figures[id(block.last_resource)] = dict(
            row=line, code=code or "", description=description or "", unit=unit or "",
            qty=filled, rate=Decimal(rate or 0), amount=None if amount in (None, "") else Decimal(amount))

    def capture_warning(block, line, message):
        warn(block, line, message)
        found = findings.setdefault(id(block.item), [])
        row = next((row for row in block.rows if row[0] == line), None)
        if row is None:
            return
        if message.endswith("not understood; skipped"):
            found.append(dict(kind="skipped", row=line, description=row[2] or row[1] or "", unit=row[3] or "",
                              amount=Decimal(row[6] or 0)))
            return
        total = re.match(r"worksheet total (\S+) differs from the calculated (\S+)$", message)
        if total:
            earlier = [(other[2] or "", Decimal(other[6])) for other in block.rows
                       if other[0] < line and other[6] and not other[3]]
            found.append(dict(kind="total", row=line, position=len(block.item.ana_items), label=row[2] or "Total",
                              book=Decimal(total[1]), calculated=Decimal(total[2]), earlier=earlier))

    def capture_numeric(block, line, description, amount, *args):
        numeric_row(block, line, description, amount, *args)
        if block.finished and not any(entry["kind"] == "tail" for entry in findings.get(id(block.item), [])):
            # Rows after the rounded rate, e.g. "Rate for 1 sqm 890.3" and "Say 890"
            # after the cost of 10 sqm has been rounded.
            after = [row for row in block.rows if row[0] > line and row[2] and row[6] and not row[3]]
            if after:
                findings.setdefault(id(block.item), []).append(dict(
                    kind="tail", rows=[(row[2], Decimal(row[6])) for row in after]))

    block_class.add_resource, block_class.warn, block_class.numeric_row = capture_resource, capture_warning, capture_numeric
    try:
        rows = analysis_import.read_rows(dict(path=str(path), first_row=1, first_column=1))
        drafts, _ = analysis_import.parse_analyses(rows, analysis_import.parser_settings({}))
    finally:
        block_class.add_resource, block_class.warn, block_class.numeric_row = add_resource, warn, numeric_row
    return {code: [draft] + getattr(draft, "alternatives", []) for code, draft in drafts.items()}, figures, findings


class Appendix:
    """Appendix II resources of the project, for matching book descriptions."""

    def __init__(self, db):
        table = db.ResourceTable
        self.rows = {row.code: row for row in table.select()
                     if not GENERATED.match(row.code) and row.code != UNIT_CODE}

    def get(self, code):
        return self.rows.get(code)

    def find(self, description, rate):
        """Appendix II resource with the same rate and (nearly) the same description."""
        best, score = None, 0.0
        for row in self.rows.values():
            if money(row.rate) != money(rate):
                continue
            value = min(similarity(description, row.description), similarity(row.description.split("\n")[-1], description))
            if value > score:
                best, score = row, value
        return best if score >= 0.75 else None

    def named(self, description, unit):
        """Appendix II resource with the same description and unit, at any rate."""
        unit = " ".join(words(unit))
        for row in self.rows.values():
            name = row.description.splitlines()[-1]
            if (" ".join(words(row.unit)) == unit and similarity(description, name) >= 0.9
                    and similarity(name, description) >= 0.9):
                return row
        return None


def close(qty, rate, amount):
    """Coefficient × rate gives the book amount, allowing for the book
    multiplying unrounded rates (₹1850.338983… against Appendix II ₹1850.34)."""
    return abs(qty * rate - amount) <= abs(qty) * Decimal("0.005") + Decimal("0.011")


def book_amount(figures):
    return figures["amount"] if figures["amount"] is not None else figures["qty"] * figures["rate"]


def shown(figures):
    """The book's line, e.g. "1 L.S. @ ₹36 = ₹36"."""
    qty, unit, rate = figures["qty"], figures["unit"], figures["rate"]
    priced = f" @ ₹{number(money(rate))} =" if rate else ","
    return f"{number(qty)} {unit}{priced} ₹{number(money(book_amount(figures)))}".replace("  ", " ")


def decide(figures, current, appendix):
    """(change, note, discrepancy) for one resource line.

    change: None, ("link", code) or ("derive", description, unit, rate);
    note: text for the line remarks; discrepancy: text or None.
    """
    amount, qty, rate = book_amount(figures), figures["qty"], figures["rate"]
    book_code, description, unit = figures["code"], figures["description"], figures["unit"]
    resource = appendix.get(current)
    clash = (resource is not None and book_code and money(rate) != money(resource.rate)
             and similarity(description, resource.description) < 0.5)
    if resource is not None and not clash:
        if close(qty, Decimal(resource.rate), amount):
            return None, None, None
        if money(rate) != money(resource.rate):
            text = f"Book: {shown(figures)}; Appendix II rate ₹{number(resource.rate)}"
        else:
            text = (f"Book: amount ₹{number(money(amount))} for {number(qty)} {unit} @ ₹{number(money(rate))} "
                    f"(coefficient × rate = ₹{number(money(qty * rate))})")
        return None, text, text
    origin = f"Book: {description[:80]} ({'code ' + book_code if book_code else 'no code'})"
    if clash:
        origin += f"; {book_code} is '{resource.description.splitlines()[-1][:60]}' in Appendix II"
    match = appendix.find(description, rate) or appendix.named(description, unit)
    if match is not None:
        note = f"{origin}; linked to Appendix II {match.code}"
        discrepancy = None
        if amount and not close(qty, Decimal(match.rate), amount):
            discrepancy = f"Book: {shown(figures)}; Appendix II {match.code} rate ₹{number(match.rate)}"
            note += f". {discrepancy}"
        return ("link", match.code), note, discrepancy
    if qty and amount:
        derived = money(amount / qty)
        note = (f"{origin}; not in Appendix II: rate ₹{number(derived)} back-calculated from the book "
                f"({number(qty)} {unit} = ₹{number(money(amount))})")
        return ("derive", description, unit, derived), note, None
    if qty and rate:
        note = f"{origin}; not in Appendix II: rate ₹{number(money(rate))} as in the book"
        return ("derive", description, unit, money(rate)), note, None
    return None, None, None


def derived_code(description, unit, rate):
    digest = hashlib.sha1(f"{' '.join(description.lower().split())}|{unit.lower()}|{rate}".encode()).hexdigest()
    return "R" + digest[:6].upper()


def lines(items):
    return [[(entry[0], Decimal(entry[1])) for entry in item["resource_list"]] for item in items if item["itemtype"] == 0]


def append(existing, note):
    return "\n".join(filter(None, [existing or "", note]))


def published_rates(path):
    """Schedule rates from the prepared schedule workbook (Code, …, Rate)."""
    from openpyxl import load_workbook
    book = load_workbook(path, read_only=True)
    try:
        # The prepared workbook keeps rates as text ("1436"); civil items say
        # "Rate to be taken from Civil DSR".
        return {str(row[0]).strip(): Decimal(str(row[3]).strip()) for row in book.active.iter_rows(min_row=2, values_only=True)
                if row[0] is not None and re.fullmatch(r"-?\d+(\.\d+)?", str(row[3] or "").strip())}
    finally:
        book.close()


def missing_lines(found):
    """Unit item lines for rows priced without a coefficient (the importer
    skips them) and documented subtotal slips: ([(position, description,
    amount, remark)], [(row, text)])."""
    units, slips, skipped = [], [], []
    for entry in found:
        if entry["kind"] == "skipped":
            skipped.append(entry)
            continue
        if entry["kind"] != "total":
            continue
        gap = money(entry["book"] - entry["calculated"])
        if skipped and abs(sum(row["amount"] for row in skipped) - gap) <= Decimal("0.5"):
            for row in skipped:
                unit = f"{row['unit']} " if row["unit"] else ""
                units.append((entry["position"], row["description"][:80], money(row["amount"]),
                              f"{row['description']} — {unit}₹{number(money(row['amount']))} in the book "
                              "without a coefficient; no Appendix II resource"))
        elif abs(gap) > Decimal("0.1"):
            repeated = next((label for label, amount in reversed(entry["earlier"])
                             if gap > 0 and abs(amount - gap) <= Decimal("0.05")), None)
            # Other gaps are section totals ("Total of A(4)") or follow from
            # line amounts already documented.
            if repeated is not None:
                slips.append((entry["row"], f"The book's '{entry['label']}' (₹{number(money(entry['book']))}) adds "
                                            f"'{repeated.strip()}' (₹{number(gap)}) a second time"))
        skipped = []
    return units, slips


def reconcile(call, db, workbook, published, report_path=None, discrepancy_path=None):
    """Apply the changes to every imported analysis and document the book's
    differences; returns a summary. `published` maps item codes to the
    schedule rates (after correction slips)."""
    drafts, figures, findings = sheet_drafts(workbook)
    if db.get_resource(UNIT_CODE) is None:
        call("resources.editor.add", data=dict(UNIT_ITEM))
    appendix = Appendix(db)
    table = db.ScheduleTable
    report, discrepancies, items = [], [], 0
    rows = lambda: call("state")["rows"]  # noqa: E731 - analysis rows, one per analysis entry
    rate = lambda: Decimal(call("state")["rate"])  # noqa: E731

    def derive(description, unit, value, item):
        code = derived_code(description, unit, value)
        if db.get_resource(code) is None:
            call("resources.editor.add", data=dict(code=code, description=description, unit=unit or "LS",
                                                   rate=str(value), category=DERIVED_CATEGORY,
                                                   reference=f"Rate back-calculated from DAR (E&M) 2025 {item}"))
        return code

    for code, candidates in drafts.items():
        if table.get_or_none(table.code == code) is None:
            continue
        model = db.get_item(code, modify_res_code=False)
        if model is None or not model.ana_items:
            continue
        stored = lines(model.ana_items)
        draft = next((candidate for candidate in candidates if lines(candidate.ana_items) == stored), None)
        if draft is None:
            continue
        sheet = [[figures.get(id(entry)) for entry in item["resource_list"]] for item in draft.ana_items if item["itemtype"] == 0]
        actions = []
        for group, (stored_group, sheet_group) in enumerate(zip(stored, sheet)):
            for index, ((current, _), line) in enumerate(zip(stored_group, sheet_group)):
                if not line:
                    continue
                change, note, discrepancy = decide(line, current, appendix)
                if discrepancy:
                    discrepancies.append(dict(item=code, row=line["row"], kind="line amount", code=line["code"] or current,
                                              description=line["description"][:100], text=discrepancy))
                if change or note:
                    actions.append((group, index, line, current, change, note))
        found = findings.get(id(draft), [])
        units, slips = missing_lines(found)
        for row, text in slips:
            discrepancies.append(dict(item=code, row=row, kind="subtotal", code="", description="", text=text))
        target_rate = published.get(code)
        model.evaluate_results()
        tail = next((entry["rows"] for entry in found if entry["kind"] == "tail"), None)
        tail = tail if tail and target_rate is not None and abs((model.get_ana_rate() or 0) - target_rate) > 1 else None
        if not actions and not units and not tail and not slips:
            continue
        # New resources first: adding one refreshes the loaded analysis.
        targets = [change[1] if change and change[0] == "link" else
                   derive(change[1], change[2], change[3], code) if change else current
                   for group, index, line, current, change, note in actions]
        call("analysis.load", code=code)
        for (group, index, line, current, change, note), target in zip(actions, targets):
            child = [row for row in rows() if row["kind"] == "Group"][group]["_children"][index]
            if target != current:
                call("edit", id=child["id"], field="code", value=target)
            call("edit", id=child["id"], field="remarks", value=append(child.get("remarks"), note))
            report.append(dict(item=code, row=line["row"], book_code=line["code"], description=line["description"][:100],
                               book_qty=number(line["qty"]), book_rate=number(line["rate"]),
                               book_amount="" if line["amount"] is None else number(money(line["amount"])),
                               resource=target, change=(change or ("note",))[0], remarks=note))
        # Insert from the end so earlier positions stay valid.
        for position, description, amount, remark in sorted(units, key=lambda entry: -entry[0]):
            after = {"id": rows()[position - 1]["id"]} if position else {}
            call("add", kind="Group", description=description, **after)
            call("resource.add", id=rows()[position]["id"], library=True, code=UNIT_CODE, qty=number(amount))
            call("edit", id=rows()[position]["_children"][0]["id"], field="remarks", value=remark)
            report.append(dict(item=code, row="", book_code="", description=description, book_qty="", book_rate="",
                               book_amount=number(amount), resource=UNIT_CODE, change="unit item", remarks=remark))
        if slips:
            # Book arithmetic is documented on the analysis, not reproduced.
            current = call("state").get("ana_remarks", "")
            call("analysis.edit", field="ana_remarks", value=append(current, "; ".join(text for _, text in slips)))
        if tail:
            # "OR SAY 8903", then "Rate for 1 sqm 890.3" and "OR SAY 890".
            before = abs(rate() - target_rate)
            (label, amount), rounded = tail[0], tail[-1]
            factor = (amount / rate()).quantize(Decimal("0.000001"), ROUND_HALF_UP) if rate() else None
            if factor:
                call("add", kind="Multiply", description=label, value=number(factor), id=rows()[-1]["id"])
                steps = 1
                if len(tail) > 1 and rounded[1] == rounded[1].to_integral():
                    call("add", kind="Round", description=rounded[0], value="0", id=rows()[-1]["id"])
                    steps = 2
                if abs(rate() - target_rate) < before:
                    report.append(dict(item=code, row="", book_code="", description=label, book_qty="", book_rate="",
                                       book_amount=number(amount), resource="", change="multiplier",
                                       remarks=f"The book works out '{label}' (₹{number(amount)}) after rounding the "
                                               f"analysis; multiplier {number(factor)} added"))
                else:
                    for _ in range(steps):
                        call("undo")
        call("analysis.apply")
        items += 1
    # Resources the importer created for codeless lines that are no longer used.
    removed = 0
    for row in list(db.ResourceTable.select()):
        if GENERATED.match(row.code) and not row.resourceitems.count() and row.category.description != DERIVED_CATEGORY:
            call("resources.editor.delete", id=str(row.id))
            removed += 1
    # Analyses that still differ from the published rate (after correction slips).
    for row in table.select():
        target_rate = published.get(row.code)
        if target_rate is None or not row.unit:
            continue
        model = db.get_item(row.code, modify_res_code=False)
        if model is None or not model.results:
            continue
        calculated = Decimal(model.get_ana_rate() or 0)
        if abs(calculated - target_rate) > Decimal("0.01"):
            discrepancies.append(dict(item=row.code, row="", kind="rate", code="", description=row.description[:100],
                                      text=f"Analysis gives ₹{number(money(calculated))}, published rate ₹{number(target_rate)} "
                                           f"(difference ₹{number(money(calculated - target_rate))})"))
    for path, records, fields in ((report_path, report, ["item", "row", "book_code", "description", "book_qty", "book_rate",
                                                          "book_amount", "resource", "change", "remarks"]),
                                  (discrepancy_path, discrepancies, ["item", "row", "kind", "code", "description", "text"])):
        if path:
            with open(path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows(records)
    count = lambda kind: sum(record["change"] == kind for record in report)  # noqa: E731
    return dict(items=items, linked=count("link"), derived=count("derive"), unit_items=count("unit item"),
                noted=count("note"), removed_resources=removed,
                line_discrepancies=sum(record["kind"] == "line amount" for record in discrepancies),
                subtotal_discrepancies=sum(record["kind"] == "subtotal" for record in discrepancies),
                rate_differences=sum(record["kind"] == "rate" for record in discrepancies))
