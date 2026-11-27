"""Detached accepted measurement records and separately labelled template outputs."""

from dataclasses import dataclass

from estimator import misc
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
    numeric_columns: tuple[int, ...] = ()
    record_totals: tuple[tuple[str, ...], ...] = ()
    total_weights: tuple[str, ...] = ()
    sum_records: bool = False
    output_columns: tuple[int, ...] = ()


def build_measurements(db, schedule, specification):
    """Read accepted engine data without activating drafts or allocating editor IDs.

    Filter whole sheets by their schedule links. A multi-output sheet remains
    intact so its records and independently labelled totals can be understood.
    """
    if not any(
        section.enabled and section.kind in ("measurements", "measurement_abstract")
        for section in specification.sections
    ):
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
        numeric_columns = tuple(i for i, kind in enumerate(item.columntypes) if kind != misc.MEAS_DESC)
        record_totals, weights, sum_records = _record_totals(item)
        sheets.append(
            MeasurementSheet(
                number,
                category,
                item.remark,
                item.name,
                _columns(item),
                tuple(
                    tuple(str(value) if value is not None else "" for value in record.get_model_rendered(index))
                    for index, record in enumerate(item.records, 1)
                ),
                tuple((caption, str(value)) for caption, value in zip(item.captions_udata, item.user_data or [])),
                tuple(outputs),
                numeric_columns,
                record_totals,
                weights,
                sum_records,
                _output_columns(item),
            )
        )
    return tuple(sheets)


# These installed templates sum per-record outputs, with steel applying six
# independent unit weights after summing the corresponding lengths.
SUM_TEMPLATES = {
    "_1_NLBH",
    "_2_LLLLL",
    "_3_NNNNNNNN",
    "_4_nnnnnT",
    "elec_ac_rect_duct",
    "elec_ac_round_duct",
    "elec_tableofpoints",
    "civil_steel_table",
}


def _record_totals(item):
    """Capture the engine's record outputs for editable worksheet sums."""
    if item.itemtype not in SUM_TEMPLATES:
        return (), (), False
    records = tuple(tuple(str(value) for value in record.find_total()) for record in item.records)
    weights = ()
    if item.itemtype == "civil_steel_table":
        values = []
        for index in range(6, 12):
            try:
                values.append(str(float((item.user_data or [])[index])))
            except (IndexError, TypeError, ValueError):
                values.append("0")
        weights = tuple(values)
    return records, weights, True


def _output_columns(item):
    """Identify visible per-record outputs in templates that expose those values."""
    if item.itemtype in ("_2_LLLLL", "_3_NNNNNNNN"):
        return tuple(item.itemnos_mapping)
    if item.itemtype in SUM_TEMPLATES and item.itemtype != "civil_steel_table":
        return (len(item.captions) - 1,)
    return ()


def _columns(item):
    """Keep steel diameter labels and move linked-output remarks into the heading."""
    if item.itemtype == "civil_steel_table":
        return tuple(column_title(item, i) for i in range(len(item.captions)))
    return tuple(item.captions)
