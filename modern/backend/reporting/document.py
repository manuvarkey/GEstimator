"""Capture ordered schedule rows and Decimal totals in an immutable document."""

from dataclasses import asdict, dataclass, replace
from decimal import Decimal

from estimator import misc
from estimator.data.schedule import Currency

from .datasets import Analysis, ResourceRow, UsageRow, build_datasets
from .measurements import MeasurementSheet, build_measurements
from .specification import ReportSpec


@dataclass(frozen=True)
class ScheduleRow:
    """Detached accepted row; headings have no financial amount."""

    id: str
    category_id: str
    category: str
    parent_id: str | None
    code: str
    description: str
    unit: str
    quantity: str
    rate: str
    amount: str | None
    remarks: str


@dataclass(frozen=True)
class CategoryTotal:
    """Sum of rounded payable amounts, never a floating-point SQL total."""

    category_id: str
    category: str
    amount: str


@dataclass(frozen=True)
class ReportDocument:
    """One revision's report data, safe to keep after later project edits."""

    revision: int
    project: str
    specification: ReportSpec
    schedule: tuple[ScheduleRow, ...]
    abstract: tuple[CategoryTotal, ...]
    total: str
    analyses: tuple[Analysis, ...] = ()
    resources: tuple[ResourceRow, ...] = ()
    resource_usage: tuple[UsageRow, ...] = ()
    measurements: tuple[MeasurementSheet, ...] = ()

    def to_dict(self):
        """Return independent JSON-compatible containers and decimal strings."""
        result = _json_values(asdict(self))
        result["schema_version"] = 1
        result["specification"]["schema_version"] = 1
        return result


def _json_values(value):
    """Convert nested frozen tuples to detached lists at the IPC boundary."""
    if isinstance(value, dict):
        return {key: _json_values(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_values(item) for item in value]
    return value


def build_document(db, revision, specification):
    """Capture all enabled datasets inside one owner-thread read transaction."""
    with db.database.atomic():
        snapshot = _schedule_document(db, revision, specification)
        analyses, resources, usage = build_datasets(db, snapshot.schedule, specification)
        return replace(
            snapshot,
            analyses=analyses,
            resources=resources,
            resource_usage=usage,
            measurements=build_measurements(db, snapshot.schedule, specification),
        )


def _schedule_document(db, revision, specification):
    """Batch-read one consistent project revision without model evaluation/writes.

    Call on the runtime owner thread. As with the schedule view total, stored
    rates are authoritative and SUB ANALYSIS dependencies never count as work.
    Selection order does not replace the project's category/parent/child order.
    """
    # Step 1: materialize related rows in one read transaction; no ORM escapes.
    with db.database.atomic():
        categories = list(db.ScheduleCategoryTable.select().order_by(db.ScheduleCategoryTable.order).dicts())
        items = list(db.ScheduleTable.select().order_by(db.ScheduleTable.order, db.ScheduleTable.suborder).dicts())
        project = db.get_project_settings().get("project_name", "")
    selected_items = _selection(specification.item_ids, items, "schedule item")
    selected_categories = _selection(specification.category_ids, categories, "category")
    roots = {}
    children = {}
    for item in items:
        if item["parent"] is None:
            roots.setdefault(item["category"], []).append(item)
        else:
            children.setdefault(item["parent"], []).append(item)

    # Step 2: preserve visible hierarchy while excluding dependency-only work.
    rows = []
    totals = []
    for category in categories:
        identity = category["id"]
        if category["description"] == misc.SUB_ANA_TITLE or identity not in selected_categories:
            continue
        name = category["description"] or "UNCATEGORISED"
        amount = Decimal(0)
        count = 0
        for parent in roots.get(identity, []):
            for item in (parent, *children.get(parent["id"], [])):
                if item["id"] not in selected_items:
                    continue
                row = _row(item, identity, name)
                rows.append(row)
                if row.amount is not None:
                    amount += Decimal(row.amount)
                    count += 1
        if count:
            totals.append(CategoryTotal(str(identity), name, str(Currency(amount))))
    # Step 3: freeze primitives so later project/draft edits cannot alter a preview.
    total = Currency(sum((Decimal(row.amount) for row in totals), Decimal(0)))
    return ReportDocument(revision, project, specification, tuple(rows), tuple(totals), str(total))


def _selection(identities, records, label):
    """Reject stale/foreign selections rather than silently dropping requested rows."""
    known = {record["id"] for record in records}
    if identities is None:
        return known
    selected = {int(identity) for identity in identities}
    if selected - known:
        raise ValueError(f"Unknown report {label} ID; refresh the selection")
    return selected


def _row(item, category_id, category):
    """Use exactly the schedule view's stored-rate and per-item rounding rules."""
    rate, quantity = item["rate"] or Decimal(0), item["qty"] or Decimal(0)
    return ScheduleRow(
        str(item["id"]),
        str(category_id),
        category,
        str(item["parent"]) if item["parent"] is not None else None,
        item["code"],
        item["description"] or "",
        item["unit"] or "",
        str(quantity),
        str(rate),
        str(Currency(rate * quantity)) if item["unit"] else None,
        item["remarks"] or "",
    )
