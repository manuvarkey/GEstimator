"""Generated workbook calculations over fixed cells and validated numeric inputs."""

from dataclasses import dataclass, field
from decimal import Decimal

from openpyxl.utils import quote_sheetname


def sheet_ref(sheet, cell):
    """Use Excel's quoting rules for intra-workbook references."""
    return f"{quote_sheetname(sheet.title)}!{cell}"


@dataclass
class AnalysisFormulas:
    """Track the engine's previous item and running total as worksheet references."""

    previous: str = "0"
    total: list[str] = field(default_factory=list)
    resource_start: int = 0

    def amount(self, kind, row, factor):
        """Translate each flat analysis step using the same accumulator rules as the engine."""
        address = f"F{row}"
        if kind == "Group":
            self.resource_start = row + 1
            return None
        if kind == "Resource":
            return f"ROUND(D{row}*E{row},2)"
        if kind == "GroupTotal":
            self.previous = address
            self.total.append(address)
            return f"SUM(F{self.resource_start}:F{row - 1})" if self.resource_start < row else "0"
        if kind == "Subtotal":
            formula = self._sum()
            self.previous, self.total = address, [address]
            return formula
        if kind in ("Weight", "Multiply"):
            formula = f"ROUND(D{row}*{self.previous},2)"
            if kind == "Multiply":
                self.previous, self.total = address, [address]
            else:
                self.total.append(address)
            return formula
        if kind == "Round":
            # Engine rounding changes the running total but leaves the most
            # recent item intact for a following Weight or Multiply.
            precision = int(Decimal(factor))
            interval = int((Decimal(factor) - precision) * 10)
            total = self._sum()
            self.total = [address]
            if interval:
                step = Decimal(interval).scaleb(-precision)
                return f"ROUND(ROUND(({total})/({step}),0)*({step}),{precision})"
            return f"ROUND({total},D{row})"
        raise ValueError("Unknown report analysis row")

    def _sum(self):
        return "+".join(self.total) or "0"


def adjusted_rate(code, row, resources):
    """Reference catalog cells where present, otherwise use accepted numeric inputs."""
    basic = resources.get((code, "rate"), str(Decimal(row.basic_rate)))
    tax = resources.get((code, "tax"), str(Decimal(row.tax)))
    discount = resources.get((code, "discount"), str(Decimal(row.discount)))
    return f"ROUND({basic}*(1+{tax}/100)*(1-{discount}/100),2)"


def formula(sheet, row, column, expression, number_format="#,##0.00"):
    """Write an internally generated calculation onto a numeric worksheet cell."""
    cell = sheet.cell(row, column)
    cell.value = "=" + expression
    cell.number_format = number_format
    return cell


@dataclass
class WorkbookLinks:
    """Cell addresses shared by report sections that may appear in any order."""

    resources: dict = field(default_factory=dict)
    analyses: dict = field(default_factory=dict)
    schedule_amounts: dict = field(default_factory=dict)
    measurement_headings: dict = field(default_factory=dict)
    measurement_quantities: dict = field(default_factory=dict)
    abstract_headings: dict = field(default_factory=dict)
    analysis_rates: list = field(default_factory=list)
    category_amounts: list = field(default_factory=list)
    forward: list = field(default_factory=list)
    carry: list = field(default_factory=list)
    measured_codes: set = field(default_factory=set)
    measurement_sheets: set = field(default_factory=set)
    print_widths: dict = field(default_factory=dict)
    measurement_input_start: int = 8

    def finish(self):
        """Link formulas and destinations after all generated cell positions are known."""
        for cell, code, stored in self.analysis_rates:
            analysis = self.analyses.get(code)
            if analysis and Decimal(stored) == Decimal(analysis[1]):
                cell.value = "=" + analysis[0]
        for cell, category in self.category_amounts:
            if category in self.schedule_amounts:
                cell.value = f"=SUM({self.schedule_amounts[category]})"
        for label, quantity, index, output in self.forward:
            if index in self.measurement_headings:
                label.hyperlink = "#" + self.measurement_headings[index]
                quantity.value = "=" + self.measurement_quantities[index, output]
        for cell, code in self.carry:
            cell.hyperlink = "#" + self.abstract_headings[code]
