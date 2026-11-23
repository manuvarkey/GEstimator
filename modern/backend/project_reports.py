"""Read-only schedule rate and resource usage reports for project editors."""

from decimal import Decimal

from estimator import misc
from estimator.data.schedule import Currency

from .validation import text


def rate_discrepancies(db, revision):
    """Compare stored rates with their analysis totals and classify each difference."""
    rows = []
    counts = dict(items=0, mismatch=0, small=0, medium=0, large=0, missing=0)
    colours = dict(
        small=misc.MEAS_COLOR_LOCKED,
        medium=misc.MEAS_COLOR_LOCKED_L1,
        large=misc.MEAS_COLOR_LOCKED_L2,
        missing=misc.MEAS_COLOR_MISSING,
    )
    for row in db.ScheduleTable.select():
        if not row.unit:
            continue
        counts["items"] += 1
        model = db.get_item(row.code, modify_res_code=False)
        calculated = Currency(model.get_ana_rate()) if model.results else None
        delta = abs(calculated - Currency(row.rate)) if calculated is not None else None
        band = (
            "missing"
            if delta is None
            else "equal"
            if delta == 0
            else "small"
            if delta <= Decimal("0.1")
            else "medium"
            if delta <= 1
            else "large"
        )
        if band != "equal":
            counts[band] += 1
            if band != "missing":
                counts["mismatch"] += 1
        rows.append(
            dict(
                id=str(row.id),
                code=row.code,
                stored=str(row.rate),
                calculated=None if calculated is None else str(calculated),
                band=band,
                colour=colours.get(band),
            )
        )
    return dict(rows=rows, counts=counts, revision=revision)


def resource_usage(db, params):
    """Return a page of resource totals matching the search words."""
    offset = params.get("offset", 0)
    if type(offset) is not int or offset < 0:
        raise ValueError("Invalid resource usage page")
    words = text(params.get("query", "")).casefold().split()
    rows = []
    for category, items in db.get_res_usage().items():
        for code, (_, description, unit, quantity, base, vat, discount) in sorted(items.items()):
            haystack = " ".join((code, description, unit, category)).casefold()
            if not all(word in haystack for word in words):
                continue
            rate = Currency(base * (1 + (vat or Decimal(0)) / 100) * (1 - (discount or Decimal(0)) / 100))
            rows.append(
                dict(
                    code=code,
                    description=description,
                    unit=unit,
                    category=category,
                    quantity=str(quantity),
                    rate=str(rate),
                    amount=str(Currency(rate * quantity)),
                )
            )
    return dict(rows=rows[offset : offset + 50], total=len(rows))


def resource_dependents(db, params):
    """Return analyses that depend on a resource directly or through sub-analysis."""
    code = text(params["code"])
    offset = params.get("offset", 0)
    if type(offset) is not int or offset < 0:
        raise ValueError("Invalid analysis page")
    schedule = db.ScheduleTable
    resource = db.ResourceTable
    entry = db.ResourceItemTable
    references = {}
    edges = entry.select(resource.code, schedule.code).join(resource).switch(entry).join(schedule).distinct().tuples()
    for resource_code, analysis_code in edges:
        references.setdefault(resource_code, set()).add(analysis_code)
    direct = references.get(code, set())
    reached = set(direct)
    pending = list(direct)
    while pending:
        via = pending.pop()
        new = references.get(via, set()) - reached
        reached.update(new)
        pending.extend(new)
    matches = [
        dict(code=item.code, description=item.description, indirect=item.code not in direct)
        for item in schedule.select(schedule.code, schedule.description).order_by(
            schedule.order, schedule.suborder, schedule.id
        )
        if item.code in reached
    ]
    return dict(rows=matches[offset : offset + 50], total=len(matches))
