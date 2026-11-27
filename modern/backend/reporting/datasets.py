"""Batched report adapters for accepted analyses, resource catalog and usage."""

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from estimator.data.schedule import Currency, ResourceItemModel, ScheduleItemModel


@dataclass(frozen=True)
class ResourceRow:
    """Catalog rate and adjustments, with no mutable ORM/model objects."""

    code: str
    description: str
    unit: str
    category: str
    rate: str
    tax: str
    discount: str
    reference: str


@dataclass(frozen=True)
class UsageRow:
    """Direct resource quantity from the engine's usage aggregation."""

    code: str
    description: str
    unit: str
    category: str
    quantity: str
    rate: str
    amount: str


@dataclass(frozen=True)
class AnalysisRow:
    """A flat analysis line, retaining kind, factors, remarks and calculated values."""

    kind: str
    code: str = ""
    description: str = ""
    unit: str = ""
    quantity: str = ""
    rate: str = ""
    amount: str = ""
    remarks: str = ""


@dataclass(frozen=True)
class Analysis:
    """Stored rate and independently evaluated analysis rate may intentionally differ."""

    code: str
    description: str
    unit: str
    remarks: str
    stored_rate: str
    calculated_rate: str
    rows: tuple[AnalysisRow, ...]
    category: str = ""


def build_datasets(db, schedule, specification):
    """Load only enabled datasets; financial calculations remain engine-owned."""
    enabled = {section.kind for section in specification.sections if section.enabled}
    codes = [row.code for row in schedule if row.unit]
    usage = _usage(db, codes) if "resource_usage" in enabled else ()
    if not enabled.intersection(("analyses", "resources")):
        return (), (), usage
    # Step 1: batch related accepted rows; no per-analysis/resource ORM lookups.
    S, Q, RI, R, C = (
        db.ScheduleTable,
        db.SequenceTable,
        db.ResourceItemTable,
        db.ResourceTable,
        db.ResourceCategoryTable,
    )
    resources = list(R.select(R, C.description.alias("category_name")).join(C).order_by(C.order, R.order).dicts())
    sequences = list(Q.select(Q, S.code.alias("schedule_code")).join(S).where(S.code.in_(codes)).order_by(Q.id).dicts())
    entries = list(
        RI.select(RI, S.code.alias("schedule_code")).join(S).where(S.code.in_(codes)).order_by(RI.id).dicts()
    )
    by_id = {row["id"]: row for row in resources}
    filtered = specification.item_ids is not None or specification.category_ids is not None
    referenced = {row["id_res"] for row in entries}
    catalog = (
        tuple(_resource(row) for row in resources if not filtered or row["id"] in referenced)
        if "resources" in enabled
        else ()
    )
    if "analyses" not in enabled:
        return (), catalog, usage
    grouped_sequences, grouped_entries = defaultdict(list), defaultdict(list)
    for row in sequences:
        grouped_sequences[row["schedule_code"]].append(row)
    for row in entries:
        grouped_entries[row["id_seq"]].append(row)
    remarks = dict(S.select(S.code, S.ana_remarks).where(S.code.in_(codes)).tuples())
    # Step 2: evaluate detached models, never updating stored project rates.
    analyses = []
    for row in schedule:
        if not row.unit or not grouped_sequences[row.code]:
            continue
        model = ScheduleItemModel(row.code, row.description, row.unit)
        for sequence in grouped_sequences[row.code]:
            _append_sequence(model, sequence, grouped_entries[sequence["id"]], by_id)
        model.evaluate_results()
        analyses.append(
            Analysis(
                row.code,
                row.description,
                row.unit,
                remarks.get(row.code) or "",
                row.rate,
                str(model.get_ana_rate()),
                _analysis_rows(model),
                row.category,
            )
        )
    return tuple(analyses), catalog, usage


def _resource(row):
    """Keep catalog basic rates separate from usage/analysis adjusted rates."""
    return ResourceRow(
        row["code"],
        row["description"],
        row["unit"],
        row["category_name"] or "UNCATEGORISED",
        str(row["rate"]),
        str(row["vat"] or 0),
        str(row["discount"] or 0),
        row["reference"] or "",
    )


def _append_sequence(model, sequence, entries, resources):
    """Reconstruct the engine's accepted analysis model from batched database rows."""
    kind, description, value = sequence["itemtype"], sequence["description"], sequence["value"]
    if kind == ScheduleItemModel.ANA_GROUP:
        group = []
        for entry in entries:
            row = resources[entry["id_res"]]
            resource = ResourceItemModel(
                row["code"],
                row["description"],
                row["unit"],
                row["rate"],
                row["vat"],
                row["discount"],
                row["reference"],
                row["category_name"],
            )
            model.resources[resource.code] = resource
            group.append([resource.code, entry["qty"], entry["remarks"]])
        model.add_ana_group(description, group, sequence["code"])
    else:
        handlers = {
            ScheduleItemModel.ANA_SUM: model.add_ana_sum,
            ScheduleItemModel.ANA_WEIGHT: model.add_ana_weight,
            ScheduleItemModel.ANA_TIMES: model.add_ana_times,
            ScheduleItemModel.ANA_ROUND: model.add_ana_round,
        }
        if kind == ScheduleItemModel.ANA_SUM:
            model.add_ana_sum(description)
        else:
            handlers[kind](description, value)


def _analysis_rows(model):
    """Flatten engine results without reproducing its rounding or arithmetic."""
    rows = []
    labels = {
        model.ANA_SUM: "Subtotal",
        model.ANA_WEIGHT: "Weight",
        model.ANA_TIMES: "Multiply",
        model.ANA_ROUND: "Round",
    }
    for item, result in zip(model.ana_items, model.results):
        if item["itemtype"] == model.ANA_GROUP:
            rows.append(AnalysisRow("Group", item.get("code") or "", item["description"] or ""))
            for (code, quantity, remarks), (rate, amount) in zip(item["resource_list"], result[:-1]):
                resource = model.resources[code]
                rows.append(
                    AnalysisRow(
                        "Resource",
                        code,
                        _resource_description(resource),
                        resource.unit,
                        str(quantity),
                        str(rate),
                        str(amount),
                        remarks or "",
                    )
                )
            rows.append(
                AnalysisRow(
                    "GroupTotal",
                    description="TOTAL of " + (item.get("code") or item["description"] or "group"),
                    amount=str(result[-1]),
                )
            )
        else:
            rows.append(
                AnalysisRow(
                    labels[item["itemtype"]],
                    description=item["description"] or "",
                    quantity=str(item.get("value", "")),
                    amount=str(result),
                )
            )
    return tuple(rows)


def _usage(db, codes):
    """Use engine selection/multipliers; match the existing usage view's adjusted rate."""
    rows = []
    for category, items in db.get_res_usage(codes=codes).items():
        for code, (_, description, unit, quantity, base, tax, discount) in sorted(items.items()):
            rate = Currency(base * (1 + (tax or Decimal(0)) / 100) * (1 - (discount or Decimal(0)) / 100))
            rows.append(
                UsageRow(
                    code,
                    description,
                    unit,
                    category or "UNCATEGORISED",
                    str(quantity),
                    str(rate),
                    str(Currency(rate * quantity)),
                )
            )
    return tuple(rows)


def _resource_description(resource):
    """Retain catalog adjustments/reference alongside the analysis's net rate."""
    if not (resource.vat or resource.discount or resource.reference):
        return resource.description
    details = "Basic rate " + str(resource.rate)
    if resource.reference:
        details += " [" + resource.reference + "]"
    if resource.vat:
        details += " + Tax @" + str(resource.vat) + "%"
    if resource.discount:
        details += " - Discount @" + str(resource.discount) + "%"
    return resource.description + "\n(" + details + ")"
