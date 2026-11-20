"""Reconcile imported DSR (E&M) 2025 analyses with the book's amounts.

The analysis import links every resource line to the Appendix II resource with
the same code and keeps the book's quantity. A line then differs from the book
when the book:

- prices the resource differently from Appendix II (4.4.2 uses ₹36 for 2936,
  Appendix II has ₹7.20);
- uses a code that belongs to another Appendix II resource (19.9.3 lists an XLR
  connector under 5164, a keypad controller in Appendix II);
- names a resource without a code ("Khallasi", "Cold water tank 100 ltr");
- shows an amount that is not quantity × rate (11.4.29 charges 1 day of a
  cable jointer against a quantity of 0.25; 12.5 prices sundries at ₹0).

For each line the book amount is kept by changing the quantity, and the line's
remarks say what the book shows:

- a codeless line or a mismatched code is linked to the Appendix II resource
  with the same description (and rate) when there is one;
- otherwise the line becomes the "Unit item" resource X (rate 1, quantity =
  book amount), with the book's description in the remarks;
- a linked resource whose book amount differs gets quantity = book amount /
  Appendix II rate.

A book subtotal can also differ from the lines above it: a lump sum without
quantity or rate ("Add for screws etc. LS 260", which the importer skips) or a
line counted twice (27.13 adds the cartage again). The difference is added as
a unit item line just before that subtotal.

Edits go through the desktop operations (analysis.load, edit, add,
resource.add, analysis.apply), so they are the same as editing by hand.
"""

import csv
import re
from decimal import Decimal, ROUND_HALF_UP

from modern.backend import analysis_import

UNIT_CODE = "X"
UNIT_ITEM = dict(code=UNIT_CODE, description="Unit item", unit="Rs", rate="1", category="UNIT ITEMS")
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
    {id(draft): [finding, …]}). Findings are rows the importer skipped and book
    subtotals that differ from the lines above them.
    """
    figures, findings = {}, {}
    block_class = analysis_import._Block
    add_resource, warn, numeric_row = block_class.add_resource, block_class.warn, block_class.numeric_row

    def capture_resource(block, line, code, description, unit, qty, rate, amount):
        add_resource(block, line, code, description, unit, qty, rate, amount)
        figures[id(block.last_resource)] = dict(
            row=line, code=code or "", description=description or "", unit=unit or "",
            qty=Decimal(qty or 0), rate=Decimal(rate or 0), amount=None if amount in (None, "") else Decimal(amount))

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


def gap_lines(found, subtotal):
    """Unit item lines for book subtotals that differ from the lines above
    them: [(position, group description, amount, remark)]. `subtotal(position)`
    is the analysis subtotal after the line corrections."""
    result, skipped = [], []
    for entry in found:
        if entry["kind"] == "skipped":
            skipped.append(entry)
            continue
        if entry["kind"] != "total":
            continue
        calculated = subtotal(entry["position"])
        gap = money(entry["book"] - calculated)
        if abs(gap) > Decimal("0.1"):
            if skipped and abs(sum(row["amount"] for row in skipped) - gap) <= Decimal("0.5"):
                for row in skipped:
                    unit = f"{row['unit']} " if row["unit"] else ""
                    result.append((entry["position"], row["description"][:80], money(row["amount"]),
                                   f"{row['description']} — {unit}₹{number(money(row['amount']))} in the book "
                                   "(no quantity or rate); no matching Appendix II resource"))
            else:
                repeated = next((label for label, amount in reversed(entry["earlier"])
                                 if gap > 0 and abs(amount - gap) <= Decimal("0.05")), None)
                if repeated is not None:
                    remark = (f"The book's '{entry['label']}' (₹{number(money(entry['book']))}) adds "
                              f"'{repeated.strip()}' (₹{number(gap)}) a second time")
                else:
                    change = "more" if gap > 0 else "less"
                    remark = (f"The book's '{entry['label']}' is ₹{number(money(entry['book']))}, ₹{number(abs(gap))} "
                              f"{change} than the lines above it (₹{number(money(calculated))})")
                result.append((entry["position"], "Book adjustment", gap,
                               remark + "; the difference is kept as a unit item so the analysis gives the published rate"))
        skipped = []
    return result


def structure(call, rows, rate, code, found, target_rate):
    """Subtotal adjustments, then a per-unit step after the rounded rate, each
    kept only when the analysis gets closer to the published rate."""
    changes = []
    before = abs(rate() - target_rate)
    current_rows = rows()
    extra = gap_lines(found, lambda position: Decimal(current_rows[position]["amount"]))
    steps, added = 0, []
    for position, description, amount, remark in sorted(extra, key=lambda entry: -entry[0]):
        after = {"id": rows()[position - 1]["id"]} if position else {}
        call("add", kind="Group", description=description, **after)
        call("resource.add", id=rows()[position]["id"], library=True, code=UNIT_CODE, qty=number(amount))
        call("edit", id=rows()[position]["_children"][0]["id"], field="remarks", value=remark)
        steps += 3
        added.append(dict(item=code, row="", book_code="", description=description, book_qty="", book_rate="",
                          book_amount=number(amount), resource=UNIT_CODE, qty=number(amount), remarks=remark))
    if added:
        if abs(rate() - target_rate) < before:
            changes += added
            before = abs(rate() - target_rate)
        else:
            for _ in range(steps):
                call("undo")
    tail = next((entry["rows"] for entry in found if entry["kind"] == "tail"), None)
    if tail and before > 1 and rate():
        # "OR SAY 8903", then "Rate for 1 sqm 890.3" and "OR SAY 890".
        (label, amount), rounded = tail[0], tail[-1]
        factor = (amount / rate()).quantize(Decimal("0.000001"), ROUND_HALF_UP)
        call("add", kind="Multiply", description=label, value=number(factor), id=rows()[-1]["id"])
        steps = 1
        if len(tail) > 1 and rounded[1] == rounded[1].to_integral():
            call("add", kind="Round", description=rounded[0], value="0", id=rows()[-1]["id"])
            steps = 2
        if abs(rate() - target_rate) < before:
            changes.append(dict(item=code, row="", book_code="", description=label, book_qty="", book_rate="",
                                book_amount=number(amount), resource="", qty=number(factor),
                                remarks=f"The book works out '{label}' (₹{number(amount)}) after rounding the "
                                        f"analysis; multiplier {number(factor)} added"))
        else:
            for _ in range(steps):
                call("undo")
    return changes


def lines(items):
    return [[(entry[0], Decimal(entry[1])) for entry in item["resource_list"]] for item in items if item["itemtype"] == 0]


class Appendix:
    """Appendix II resources of the project, for matching book descriptions."""

    def __init__(self, db):
        table = db.ResourceTable
        self.rows = {row.code: row for row in table.select() if not GENERATED.match(row.code) and row.code != UNIT_CODE}

    def get(self, code):
        return self.rows.get(code)

    def find(self, description, unit, rate):
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
    """Quantity × rate gives the book amount, allowing for the book multiplying
    unrounded rates (₹1850.338983… against Appendix II ₹1850.34)."""
    return abs(qty * rate - amount) <= abs(qty) * Decimal("0.005") + Decimal("0.011")


def decide(figures, current, appendix):
    """Action for one line: None, or (code, quantity, remark)."""
    book_amount = figures["amount"] if figures["amount"] is not None else figures["qty"] * figures["rate"]
    qty, rate, unit = figures["qty"], figures["rate"], figures["unit"]
    resource = appendix.get(current)
    if not book_amount:
        # A line the book prices at nothing ("Sundries 70 L.S. @ 0 = 0").
        if figures["amount"] == 0 and qty and resource is not None and resource.rate:
            return current, Decimal(0), (f"Book: {number(qty)} {unit} @ ₹{number(money(rate))} = ₹0; "
                                         f"quantity {number(qty)} → 0 to keep the book amount")
        named = appendix.named(figures["description"], unit) if resource is None else None
        if named is not None:
            # A codeless line with no amount ("Khallasi, 0 day @ ₹663").
            return named.code, qty, (f"Book: {figures['description'][:80]} (no code), {number(qty)} {unit} @ "
                                     f"₹{number(money(rate))}; linked to Appendix II {named.code}")
        return None
    priced = f" @ ₹{number(money(rate))} =" if rate else ","
    shown = f"{number(qty)} {unit}{priced} ₹{number(money(book_amount))}".replace("  ", " ")
    book_code = figures["code"]
    if resource is not None and close(qty, Decimal(resource.rate), book_amount):
        return None  # the line already gives the book amount
    if resource is None or money(rate) != money(resource.rate):
        # The book's rate (and description) may belong to another resource.
        match = appendix.find(figures["description"], unit, rate)
        if match is not None and match.code != current:
            origin = (f"Book: {figures['description'][:80]} ({'code ' + book_code if book_code else 'no code'}), "
                      f"{shown}; linked to Appendix II {match.code}")
            return finish(match.code, Decimal(match.rate), qty, book_amount, origin, force=True)
    clash = (resource is not None and book_code and money(rate) != money(resource.rate)
             and similarity(figures["description"], resource.description) < 0.5)
    if resource is None or clash:
        named = appendix.named(figures["description"], unit)
        if named is not None and named.code != current and named.rate:
            origin = (f"Book: {figures['description'][:80]} ({'code ' + book_code if book_code else 'no code'}), "
                      f"{shown}; linked to Appendix II {named.code} at ₹{number(named.rate)}")
            return finish(named.code, Decimal(named.rate), qty, book_amount, origin, force=True)
        remark = f"{figures['description']} — {shown} in the book; no matching Appendix II resource"
        if resource is not None:
            remark += f" (book code {book_code} is '{resource.description.splitlines()[-1][:60]}' in Appendix II)"
        return UNIT_CODE, money(book_amount), remark
    if money(rate) != money(resource.rate):
        reason = f"Book: {shown}; Appendix II rate ₹{number(resource.rate)}"
    else:
        reason = (f"Book: amount ₹{number(money(book_amount))} for {number(qty)} {unit} @ ₹{number(money(rate))} "
                  f"(quantity × rate = ₹{number(money(qty * rate))})")
    return finish(resource.code, Decimal(resource.rate), qty, book_amount, reason)


def finish(code, rate, qty, book_amount, reason, force=False):
    if not rate:
        return (UNIT_CODE, money(book_amount), reason + "; resource has no rate") if book_amount else None
    adjusted = qty
    if not close(qty, rate, book_amount):
        for places in (4, 6, 8):
            adjusted = (book_amount / rate).quantize(Decimal(1).scaleb(-places), ROUND_HALF_UP)
            if money(adjusted * rate) == money(book_amount):
                break
    if adjusted == qty and not force:
        return None
    remark = reason if adjusted == qty else f"{reason}; quantity {number(qty)} → {number(adjusted)} to keep the book amount"
    return code, adjusted, remark


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


def reconcile(call, db, workbook, published, report_path=None):
    """Apply the corrections to every imported analysis; returns a summary.

    `published` maps item codes to the book's schedule rates. Line corrections
    always apply (they copy the book's amounts); subtotal adjustments and a
    per-unit step after the rounded rate are kept only when they bring the
    analysis closer to the published rate.
    """
    drafts, figures, findings = sheet_drafts(workbook)
    if db.get_resource(UNIT_CODE) is None:
        call("resources.editor.add", data=dict(UNIT_ITEM))
    appendix = Appendix(db)
    table = db.ScheduleTable
    report, items = [], 0
    rows = lambda: call("state")["rows"]  # noqa: E731 - analysis rows, one per analysis entry
    rate = lambda: Decimal(call("state")["rate"])  # noqa: E731
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
                action = decide(line, current, appendix) if line else None
                if action:
                    actions.append((group, index, line, current, action))
        found = [entry for entry in findings.get(id(draft), []) if entry["kind"] != "total"
                 or abs(entry["book"] - entry["calculated"]) > Decimal("0.1")]
        target_rate = published.get(code)
        model.evaluate_results()
        if not actions and (not found or target_rate is None or abs((model.get_ana_rate() or 0) - target_rate) <= 1):
            continue
        state = call("analysis.load", code=code)
        groups = [row for row in state["rows"] if row["kind"] == "Group"]
        changes = []
        for group, index, line, current, (target, qty, remark) in actions:
            identity = groups[group]["_children"][index]["id"]
            if target != current:
                call("edit", id=identity, field="code", value=target)
            call("edit", id=identity, field="value", value=number(qty))
            call("edit", id=identity, field="remarks", value=remark)
            changes.append(dict(item=code, row=line["row"], book_code=line["code"], description=line["description"][:100],
                                book_qty=number(line["qty"]), book_rate=number(line["rate"]),
                                book_amount="" if line["amount"] is None else number(money(line["amount"])),
                                resource=target, qty=number(qty), remarks=remark))
        if found and target_rate is not None and abs(rate() - target_rate) > 1:
            changes += structure(call, rows, rate, code, found, target_rate)
        if changes:
            call("analysis.apply")
            report += changes
            items += 1
    # Resources the importer created for codeless lines that are no longer used.
    removed = 0
    for row in list(db.ResourceTable.select()):
        if GENERATED.match(row.code) and not row.resourceitems.count():
            call("resources.editor.delete", id=str(row.id))
            removed += 1
    if report_path:
        with open(report_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(report[0]) if report else ["item"])
            writer.writeheader()
            writer.writerows(report)
    return dict(items=items, lines=len(report), unit_items=sum(row["resource"] == UNIT_CODE for row in report),
                relinked=sum(row["resource"] not in (UNIT_CODE, row["book_code"]) for row in report),
                removed_resources=removed)
