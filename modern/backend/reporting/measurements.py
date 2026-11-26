"""Detached accepted measurement records and separately labelled template outputs."""

from dataclasses import dataclass

from estimator.data.measurement import MeasurementItemHeading

from ..measurement_templates import column_title, link_label


@dataclass(frozen=True)
class MeasurementOutput:
    """One template output; unlike units are never added together."""

    label: str
    code: str
    description: str
    unit: str
    quantity: str
    remarks: str


@dataclass(frozen=True)
class MeasurementSheet:
    """Printable sheet retaining project order, headings and template constants."""

    number: int
    category: str
    description: str
    template: str
    columns: tuple[str, ...]
    records: tuple[tuple[str, ...], ...]
    properties: tuple[tuple[str, str], ...]
    outputs: tuple[MeasurementOutput, ...]


def build_measurements(db, schedule, specification):
    """Read accepted engine data without activating drafts or allocating editor IDs.

    Filter whole sheets by their schedule links. A multi-output sheet remains
    intact so its records and independently labelled totals can be understood.
    """
    if not any(section.enabled and section.kind == "measurements" for section in specification.sections):
        return ()
    selected = {int(row.id) for row in schedule if row.unit}
    filtered = specification.item_ids is not None or specification.category_ids is not None
    linked = {row.id: row for row in db.ScheduleTable.select()}
    category = ""
    sheets = []
    for number, item in enumerate(db.get_measurement().items, 1):
        if isinstance(item, MeasurementItemHeading):
            category = item.remark
            continue
        if filtered and not selected.intersection(item.itemnos):
            continue
        outputs = []
        for index, quantity in enumerate(item.get_total()):
            key = item.itemnos[index]
            row = linked.get(key)
            outputs.append(
                MeasurementOutput(
                    link_label(item, index),
                    row.code if row else "",
                    row.description if row else "",
                    row.unit if row else "",
                    str(quantity),
                    item.item_remarks[index],
                )
            )
        sheets.append(
            MeasurementSheet(
                number,
                category,
                item.remark,
                item.name,
                tuple(column_title(item, i) for i in range(len(item.captions))),
                tuple(
                    tuple(str(value) if value is not None else "" for value in record.get_model_rendered(index))
                    for index, record in enumerate(item.records, 1)
                ),
                tuple((caption, str(value)) for caption, value in zip(item.captions_udata, item.user_data or [])),
                tuple(outputs),
            )
        )
    return tuple(sheets)
