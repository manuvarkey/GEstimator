"""Group measured quantities by accepted payable item for report cross-references."""

from dataclasses import dataclass
from decimal import Decimal
from textwrap import wrap

from .document import ScheduleRow
from .measurements import MeasurementOutput


@dataclass(frozen=True)
class BroughtForward:
    """One independently labelled output and its measurement sheet target."""

    index: int
    number: int
    output: MeasurementOutput
    output_index: int


@dataclass(frozen=True)
class MeasuredItem:
    """A selected schedule item, its linked sheets and its summed quantity."""

    item: ScheduleRow
    entries: tuple[BroughtForward, ...]
    total: str

    @property
    def category(self):
        return self.item.category

    @property
    def category_id(self):
        return self.item.category_id


def measured_items(document):
    """Join links to selected payable rows and preserve both stored orders."""
    entries = {}
    for index, sheet in enumerate(document.measurements):
        for output_index, output in enumerate(sheet.outputs):
            if output.code:
                entries.setdefault(output.code, []).append(BroughtForward(index, sheet.number, output, output_index))
    return tuple(
        MeasuredItem(
            row,
            tuple(entries[row.code]),
            str(sum((Decimal(entry.output.quantity) for entry in entries[row.code]), Decimal(0))),
        )
        for row in document.schedule
        if row.unit and row.code in entries
    )


def _middle(values, limit, joiner):
    """Keep the beginning and end of a description around a visible omission."""
    if not limit or len(values) <= limit:
        return joiner.join(values)
    front = (limit + 1) // 2
    back = limit - front
    return joiner.join(values[:front]) + " …" + (joiner + joiner.join(values[-back:]) if back else "")


def item_description(description, section):
    """Limit words and approximate printed lines, keeping both ends where space allows."""
    if section.description_words and len(description.split()) > section.description_words:
        description = _middle(description.split(), section.description_words, " ")
    if section.description_lines:
        lines = [part for line in description.splitlines() for part in (wrap(line, 64) or [""])]
        description = _middle(lines, section.description_lines, "\n")
    return description


def first_enabled(document, kind):
    """Repeated report sections use the first enabled corresponding destination."""
    return next(
        (section for section in document.specification.sections if section.enabled and section.kind == kind), None
    )
