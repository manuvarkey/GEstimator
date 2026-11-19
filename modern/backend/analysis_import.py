"""Tolerant analysis-of-rates import from worksheets.

Reads the six analysis columns (code, description, unit, quantity, rate,
amount) and rebuilds ScheduleItemModel analyses. Compared with the GTK
parse_analysis state machine it:

- evaluates simple formulas (arithmetic, ROUND, MROUND, SUM, ...) when the
  workbook has no saved values, e.g. files written by GEstimator's exporter;
- accepts header synonyms (Particulars, Item, UOM, ...), title-case group
  headings, resources without a code or without a rate (rate = amount/qty);
- recovers base rate, tax, discount and reference from GEstimator exports;
- classifies totals, weights, multipliers and rounding by the numbers as
  well as by keywords, and reports rows it could not use instead of failing.
"""

import ast
from fractions import Fraction
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import hashlib
import re
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import column_index_from_string, get_column_letter

from estimator.data.schedule import Currency, ResourceItemModel, ScheduleItemModel

ZERO = Decimal(0)
GROUP_KEYS = ("material", "labour", "labor", "tool", "plant", "machinery", "equipment", "carriage", "transport",
              "hire", "sundr", "a1", "a2", "a3", "a4", "b1", "b2", "b3", "b4")
REMARK_KEYS = ("cost of", "cost per", "cost for", "rate of", "rate per", "rate for", "details of")
SUM_KEYS = ("total", "sub total", "subtotal", "rate per", "cost per", "cost for", "rate for", "cost of", "rate of", "net")
WEIGHT_KEYS = ("@", "%", "add", "profit", "overhead", "water charge", "contractor")
TIMES_KEYS = ("rate per", "rate for", "cost per", "cost for", "cost of", "rate of", "per unit", "for one", "for 1 ")
ROUND_KEYS = ("say", "rounded", "round off")
DESCRIPTION_HEADERS = ("description", "particular", "item", "details", "name of")
UNIT_HEADERS = ("unit", "uom")


# Formula evaluation -------------------------------------------------------

_REF = re.compile(r"(?<![A-Za-z_\d])\$?([A-Z]{1,3})\$?(\d+)(?:\s*:\s*\$?([A-Z]{1,3})\$?(\d+))?(?![\w(])")


def _round(value, digits=ZERO):
    digits = int(digits)
    quantum = Decimal(1).scaleb(-digits)
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def _mround(value, multiple):
    if not multiple:
        return ZERO
    return (value / multiple).quantize(Decimal(1), rounding=ROUND_HALF_UP) * multiple


def _flatten(values):
    for value in values:
        if isinstance(value, list):
            yield from _flatten(value)
        elif isinstance(value, Decimal):
            yield value


FUNCTIONS = {
    "ROUND": _round,
    "ROUNDUP": lambda v, d=ZERO: v.quantize(Decimal(1).scaleb(-int(d)), rounding="ROUND_UP"),
    "ROUNDDOWN": lambda v, d=ZERO: v.quantize(Decimal(1).scaleb(-int(d)), rounding="ROUND_DOWN"),
    "MROUND": _mround,
    "SUM": lambda *values: sum(_flatten(values), ZERO),
    "MIN": lambda *values: min(_flatten(values), default=ZERO),
    "MAX": lambda *values: max(_flatten(values), default=ZERO),
    "ABS": abs,
    "INT": lambda v: Decimal(int(v // 1)),
}


class Sheet:
    """Cell values for one worksheet: saved values first, formulas evaluated."""

    def __init__(self, path, name=None, max_rows=20000):
        path = Path(path).resolve(strict=True)
        formulas = load_workbook(path, read_only=True, data_only=False)
        values = load_workbook(path, read_only=True, data_only=True)
        try:
            name = name or formulas.sheetnames[0]
            if name not in formulas.sheetnames:
                raise ValueError("Worksheet not found")
            self.name = name
            source, saved = formulas[name], values[name]
            self.max_row = source.max_row or 0
            if self.max_row > max_rows:
                raise ValueError("Select at most 10,000 rows")
            width = min(source.max_column or 1, 100)
            self.raw, self.saved = {}, {}
            for row_index, (row, cached) in enumerate(zip(source.iter_rows(max_col=width, values_only=True),
                                                         saved.iter_rows(max_col=width, values_only=True)), 1):
                for column, (raw, value) in enumerate(zip(row, cached), 1):
                    if raw is not None:
                        self.raw[(row_index, column)] = raw
                    if value is not None:
                        self.saved[(row_index, column)] = value
        finally:
            formulas.close()
            values.close()
        self.cache, self.active = {}, set()

    def value(self, row, column):
        """Saved value, evaluated formula, or raw value of a cell."""
        key = (row, column)
        if key in self.saved:
            return self.saved[key]
        raw = self.raw.get(key)
        if isinstance(raw, str) and raw.startswith("="):
            if key not in self.cache:
                self.cache[key] = self.evaluate(raw[1:], key)
            return self.cache[key]
        return raw

    def number(self, row, column):
        value = self.value(row, column)
        if isinstance(value, Decimal):
            return value
        from .importing import loose_number
        return loose_number(value)

    def evaluate(self, formula, key):
        if key in self.active or len(formula) > 2000:
            return None  # Circular or oversized formula.
        self.active.add(key)
        try:
            cells, ranges = {}, {}

            def reference(match):
                start = (int(match[2]), column_index_from_string(match[1]))
                if match[3]:
                    name = f"_r{len(ranges)}"
                    ranges[name] = (start, (int(match[4]), column_index_from_string(match[3])))
                    return name
                name = f"_c{len(cells)}"
                cells[name] = start
                return name

            expression = _REF.sub(reference, formula).replace("^", "**")
            expression = re.sub(r"(\d+(?:\.\d+)?)%", r"(\1/100)", expression)
            tree = ast.parse(expression, mode="eval")
            if sum(1 for _ in ast.walk(tree)) > 400:
                return None

            def cell(position):
                value = self.number(*position)
                return value if value is not None else ZERO

            def walk(node):
                if isinstance(node, ast.Expression):
                    return walk(node.body)
                if isinstance(node, ast.Constant) and type(node.value) in (int, float):
                    return Decimal(str(node.value))
                if isinstance(node, ast.Name):
                    if node.id in cells:
                        return cell(cells[node.id])
                    if node.id in ranges:
                        (r1, c1), (r2, c2) = ranges[node.id]
                        if (r2 - r1 + 1) * (c2 - c1 + 1) > 10000:
                            raise ValueError("Range too large")
                        return [cell((r, c)) for r in range(min(r1, r2), max(r1, r2) + 1) for c in range(min(c1, c2), max(c1, c2) + 1)]
                    raise ValueError("Unknown name")
                if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                    value = walk(node.operand)
                    return value if isinstance(node.op, ast.UAdd) else -value
                if isinstance(node, ast.BinOp):
                    left, right = walk(node.left), walk(node.right)
                    if isinstance(node.op, ast.Add):
                        return left + right
                    if isinstance(node.op, ast.Sub):
                        return left - right
                    if isinstance(node.op, ast.Mult):
                        return left * right
                    if isinstance(node.op, ast.Div):
                        return left / right if right else ZERO
                    if isinstance(node.op, ast.Pow) and abs(right) <= 10:
                        return left ** int(right)
                    raise ValueError("Unsupported operator")
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id.upper() in FUNCTIONS and not node.keywords:
                    return FUNCTIONS[node.func.id.upper()](*[walk(arg) for arg in node.args])
                raise ValueError("Unsupported formula")

            result = walk(tree)
            return result if isinstance(result, Decimal) else None
        except (ValueError, TypeError, SyntaxError, ArithmeticError, InvalidOperation, RecursionError):
            return None
        finally:
            self.active.discard(key)


def read_rows(params):
    """[(sheet row, code, description, unit, qty, rate, amount)] for the range."""
    first = params.get("first_row", 1)
    last = params.get("last_row")
    column = params.get("first_column", 1)
    if (type(first) is not int or first < 1 or type(column) is not int or not 1 <= column <= 95
            or (last is not None and (type(last) is not int or not first <= last < first + 10000))):
        raise ValueError("Choose a valid spreadsheet range")
    sheet = Sheet(params["path"], params.get("sheet"))
    end = min(last, sheet.max_row) if last else sheet.max_row
    if end >= first + 10000:
        raise ValueError("Select at most 10,000 rows")
    order = (3, 4) if params.get("rate_first") is not True else (4, 3)
    rows = []
    for line in range(first, end + 1):
        labels = []
        for offset in range(3):
            value = sheet.value(line, column + offset)
            if isinstance(value, Decimal):
                value = format(value.normalize(), "f")
            elif isinstance(value, float):
                value = "%.12g" % value
            labels.append("" if value is None else str(value).strip())
        numbers = []
        for offset in (order[0], order[1], 5):
            value = sheet.number(line, column + offset)
            numbers.append(value if value is not None else ZERO)
        rows.append((line, *labels, *numbers))
    return rows


# Parser --------------------------------------------------------------------

def _has(text, keys):
    lower = text.lower()
    return any(key in lower for key in keys)


def _close(a, b):
    return abs(a - b) <= max(Decimal("0.011"), abs(b) * Decimal("0.0005"))


def _is_header(row):
    return _has(row[2], DESCRIPTION_HEADERS) and _has(row[3], UNIT_HEADERS)


_EXPORT_RATE = re.compile(r"\n\(Basic rate (?P<rate>-?[\d.]+)(?: \[(?P<ref>[^\]]*)\])?(?: \+ Tax @(?P<vat>-?[\d.]+)%)?(?: - Discount @(?P<discount>-?[\d.]+)%)?\)\s*$")


def _factor(amount, base):
    """Multiplier that reproduces the worksheet amount: a simple fraction
    (1/9 -> 0.111111, 3/20 -> 0.15) when one fits, else the fewest decimals."""
    if not base:
        return None
    exact = amount / base
    fraction = Fraction(exact).limit_denominator(1000)
    candidate = _round(Decimal(fraction.numerator) / Decimal(fraction.denominator), 6)
    if _round(candidate * base, 2) == _round(amount, 2):
        return candidate.normalize() if candidate == candidate.to_integral() else candidate
    for places in range(2, 7):
        factor = _round(exact, places)
        if _round(factor * base, 2) == _round(amount, 2):
            return factor
    return _round(exact, 6)


def _round_rule(total, amount):
    """GTK round value reproducing the worksheet: places 0/1/2, or 1.5 / 2.5
    for the nearest 0.5 / 0.05 (MROUND)."""
    for rule, rounded in ((0, _round(total, 0)), (1.5, _mround(total, Decimal("0.5"))), (1, _round(total, 1)),
                          (2.5, _mround(total, Decimal("0.05"))), (2, _round(total, 2))):
        if rounded == amount:
            return rule
    return _round_places(amount)


def _round_places(amount):
    amount = abs(amount)
    if amount % 1 == 0:
        return 0
    if (amount * 10) % 1 == 0:
        return 1
    return 2


def _resource_code(description, unit):
    digest = hashlib.sha1((" ".join(description.lower().split()) + "|" + unit.lower()).encode()).hexdigest()[:6].upper()
    return "R" + digest


class _Block:
    def __init__(self, code, header, rows, settings, warnings):
        self.item = ScheduleItemModel(code, "", "")
        self.rows, self.header, self.warnings = rows, header, warnings
        self.comment_up = settings[0] == 0
        self.round_places = settings[1]
        self.group = None
        self.group_sum = ZERO
        self.base = ZERO  # GTK sum_item: base for weights and multipliers
        self.total = ZERO  # running total
        self.last_resource = None
        self.pending_remarks = []
        self.finished = False

    def warn(self, line, message):
        self.warnings.append(f"Row {line} ({self.item.code}): {message}")

    def start_group(self, description, code=None):
        self.item.add_ana_group(description, code=code or None)
        self.group = len(self.item.ana_items) - 1
        self.group_sum = ZERO

    def close_group(self):
        if self.group is not None:
            self.total = Currency(self.total + self.group_sum)
            self.base = self.group_sum
            self.group = None
            self.last_resource = None

    def add_resource(self, line, code, description, unit, qty, rate, amount):
        if self.group is None:
            self.start_group("RESOURCE")
        if not rate and qty and amount:
            rate = Currency(amount / qty)
        if not qty and rate and amount:
            qty = _round(amount / rate, 4)
        vat = discount = ZERO
        reference = None
        match = _EXPORT_RATE.search(description)
        if match:
            # GEstimator export: "Description\n(Basic rate 10 [ref] + Tax @18% - Discount @5%)"
            description = description[:match.start()]
            rate = Decimal(match["rate"])
            vat = Decimal(match["vat"] or 0)
            discount = Decimal(match["discount"] or 0)
            reference = match["ref"]
        code = code or _resource_code(description, unit)
        existing = self.item.resources.get(code)
        if existing and (existing.rate, existing.unit) != (rate, unit):
            self.warn(line, f"resource {code} appears with a different rate or unit; the first one is used")
        else:
            self.item.resources[code] = ResourceItemModel(code, description, unit, rate, vat, discount, reference)
        remarks = "\n".join(self.pending_remarks) if self.comment_up and self.pending_remarks else None
        self.pending_remarks = []
        entry = [code, qty, remarks]
        self.item.ana_items[self.group]["resource_list"].append(entry)
        resource = self.item.resources[code]
        net = Currency(resource.rate * (100 + (resource.vat or 0)) * (100 - (resource.discount or 0)) / 10000)
        self.group_sum += Currency(Decimal(qty) * net)
        self.last_resource = entry

    def remark(self, text):
        if self.comment_up:
            self.pending_remarks.append(text)
        elif self.last_resource is not None:
            self.last_resource[2] = text if not self.last_resource[2] else self.last_resource[2] + "\n" + text

    def next_is_resource(self, index):
        # Skip blank and note-only rows (comments may sit above a resource).
        for row in self.rows[index + 1:index + 6]:
            if not row[1] and not row[3] and not any(row[4:]):
                continue
            return self.is_resource(row)
        return False

    @staticmethod
    def is_resource(row):
        _, code, description, unit, qty, rate, amount = row
        return bool(description) and bool(unit or code) and bool(qty or rate) and not _is_header(row)

    def next_numeric(self, index):
        for row in self.rows[index + 1:index + 6]:
            if row[6] and not row[3]:
                return row[2], row[6]
            if row[3] or row[4] or row[5]:
                return None
        return None

    def numeric_row(self, line, description, amount, following=None):
        """A row with only a description and an amount: total, weight, multiplier or rounding."""
        if self.group is not None:
            if _has(description, ("total",)) or _close(amount, self.group_sum):
                self.close_group()
                return
            self.close_group()
        if _has(description, ROUND_KEYS) and abs(amount - self.total) < 1:
            places = self.round_places if self.round_places != -1 else _round_rule(self.total, amount)
            self.item.add_ana_round(description, places)
            self.total = self.base = amount
            self.finished = True
            return
        if _close(amount, self.total) and (_has(description, SUM_KEYS) or not _has(description, WEIGHT_KEYS)):
            self.item.add_ana_sum(description)
            self.base = self.total
            return
        # A multiplier replaces the total ("Rate per cum", "Per meter cost"); a
        # following rounding row close to this amount confirms it numerically.
        rounds_this = following is not None and _has(following[0], ROUND_KEYS) and abs(following[1] - amount) < 1
        per_unit = _has(description, TIMES_KEYS) or re.search(r"\bper\b", description.lower())
        if self.base and not _has(description, ("@", "%")) and (per_unit or rounds_this):
            factor = _factor(amount, self.base)
            self.item.add_ana_times(description, factor)
            self.total = self.base = Currency(self.base * factor)
            return
        if self.base and amount < self.total:
            factor = _factor(amount, self.base)
            self.item.add_ana_weight(description, factor)
            self.total = Currency(self.total + Currency(self.base * factor))
            return
        if _close(amount, self.total):
            self.item.add_ana_sum(description)
            self.base = self.total
            return
        self.warn(line, f"'{description[:60]}' ({amount}) does not match the running total {self.total}; skipped")

    def parse(self):
        for index, row in enumerate(self.rows):
            line, code, description, unit, qty, rate, amount = row
            if self.finished:
                if any(row[4:]) and (unit or code):
                    self.warn(line, "row after the rounded rate ignored")
                continue
            if not (code or description or unit) and not (qty or rate or amount):
                continue
            if self.is_resource(row):
                self.add_resource(line, code, description, unit, qty, rate, amount)
                continue
            if not unit and not qty and not rate and not amount and description:
                if self.next_is_resource(index) and (_has(description, GROUP_KEYS) or description.isupper() or description.endswith(":")):
                    self.close_group()
                    self.start_group(description.rstrip(":").strip(), code)
                elif self.group is not None or self.last_resource is not None or self.comment_up:
                    self.remark(description)
                continue
            if amount and not unit:
                self.numeric_row(line, description, amount, self.next_numeric(index))
                continue
            if any(row[4:]):
                self.warn(line, f"'{(description or code)[:60]}' not understood; skipped")
        self.close_group()
        if not any(row.get("resource_list") for row in self.item.ana_items):
            return None
        self.item.evaluate_results()
        return self.item


def parse_analyses(rows, settings):
    """Analyses keyed by item code, plus warnings with worksheet row numbers."""
    warnings = []
    headers = [index for index, row in enumerate(rows) if _is_header(row)]
    blocks = []
    previous_end = 0
    for position, header in enumerate(headers):
        # The item code sits in the code column of a label row (no unit/numbers).
        start = next((i for i in range(header - 1, max(previous_end - 1, header - 6), -1)
                      if rows[i][1] and not rows[i][3] and not any(rows[i][4:])), None)
        if start is None:
            # "Item No. 1.2" written in the description column.
            for i in range(header - 1, max(previous_end - 1, header - 6), -1):
                match = re.match(r"^\s*item\s*(?:no\.?|number|code)?\s*[:.]?\s*([\w./-]+)", rows[i][2], re.IGNORECASE)
                if match:
                    start = i
                    code = match[1]
                    break
        else:
            code = rows[start][1]
        if start is None:
            warnings.append(f"Row {rows[header][0]}: analysis header without an item code above it; skipped")
            continue
        blocks.append((start, header, code))
        previous_end = header + 1
    drafts = {}
    for position, (start, header, code) in enumerate(blocks):
        end = blocks[position + 1][0] if position + 1 < len(blocks) else len(rows)
        block = _Block(code, header, rows[header + 1:end], settings, warnings)
        block.item.description = rows[start][2]
        between = [row[2] for row in rows[start + 1:header] if row[2]]
        block.item.ana_remarks = next((text for text in between if _has(text, REMARK_KEYS)), between[0] if len(between) == 1 else None)
        item = block.parse()
        if item is None:
            warnings.append(f"Row {rows[header][0]} ({code}): no analysis resources found; skipped")
            continue
        if code in drafts:
            raise ValueError(f"Duplicate workbook analysis code: {code}")
        worksheet_rate = next((row[6] for row in reversed(rows[header + 1:end]) if row[6] and not row[3]), None)
        if worksheet_rate is not None and item.get_ana_rate() is not None and abs(item.get_ana_rate() - worksheet_rate) > Decimal("0.011"):
            warnings.append(f"{code}: imported rate {item.get_ana_rate()} differs from the worksheet's {worksheet_rate}")
        drafts[code] = item
    return drafts, warnings
