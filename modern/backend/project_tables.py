"""Build read-only Schedule and Resources table pages and incremental updates."""

from decimal import Decimal

from peewee import fn

from estimator import misc
from estimator.data.schedule import Currency

from .metadata import presentation
from .numbers import tax_text
from .search import desktop_codes
from .validation import text


def state(editor, kind, p):
    """Return a project or library page, or a delta for visible project rows."""
    # Step 1: select the source and check whether a full page is needed.
    if p.get("source") and p["source"] not in editor.libraries:
        raise ValueError("Library is no longer attached")
    db = editor.libraries[p["source"]][1] if p.get("source") in editor.libraries else editor.db
    resource = kind == "resources"
    table = db.ResourceTable if resource else db.ScheduleTable
    category = db.ResourceCategoryTable if resource else db.ScheduleCategoryTable
    query, filters, offset, limit = _page_request(p)
    summary = {} if resource else _schedule_summary(table, category)
    if not p.get("source") and "since" in p and not p.get("reveal_id"):
        delta = _row_delta(editor, kind, p, query, db, table, resource, summary)
        if delta is not None:
            return delta

    # Step 2: find the page in the filtered, optionally ranked listing.
    records = (
        table.select(table, category)
        .join(category)
        .order_by(category.order, table.order, *([] if resource else [table.suborder]), table.id)
    )
    if filters:
        criterion = category.description.in_(filters)
        if "" in filters:
            criterion |= category.description.is_null(True)
        records = records.where(criterion)
    ranks = None
    search_engine = None
    if query.strip():
        ranked, search_engine = desktop_codes(editor.owner, db, kind, query)
        if filters:
            allowed = {row.code for row in records.select(table.code)}
            ranked = [code for code in ranked if code in allowed]
        ranks = {code: index for index, code in enumerate(ranked)}
        total = len(ranked)
        if p.get("reveal_id"):
            revealed = table.get_or_none(table.id == int(p["reveal_id"]))
            if revealed is None or revealed.code not in ranks:
                raise ValueError("Inserted row is no longer available")
            offset = ranks[revealed.code] // limit * limit
        values = list(records.where(table.code.in_(ranked[offset : offset + limit])))
        values.sort(key=lambda row: ranks[row.code])
    else:
        total = records.count()
    found_id = None
    if p.get("find") is not None:
        found_id = _find_row(records, table, ranks, p)
        if found_id is not None:
            p = dict(p, reveal_id=str(found_id))
            if ranks is not None:
                offset = ranks[table.get_by_id(found_id).code] // limit * limit
                values = list(records.where(table.code.in_(ranked[offset : offset + limit])))
                values.sort(key=lambda row: ranks[row.code])
    if ranks is None and p.get("reveal_id"):
        offset = _reveal_offset(records, table, category, resource, p["reveal_id"], limit)
    if ranks is None:
        values = list(records.offset(offset).limit(limit))
    # Step 3: render categories, ancestors and row metadata.
    rows = _project_tree(table, category, resource, values, filters, query, ranked=ranks is not None)
    if ranks is not None:
        _rank_tree(rows, ranks, total)
    return dict(
        **summary,
        rows=rows,
        total=total,
        offset=offset,
        **({"found_id": None if found_id is None else str(found_id)} if p.get("find") is not None else {}),
        undo=bool(editor.history),
        redo=bool(editor.future),
        revision=editor.owner.revision,
        view_seq=editor.changes.sequence if not p.get("source") else 0,
        enrichment=presentation(db),
        search_engine=search_engine,
        categories=[r.description or "" for r in category.select().order_by(category.order)],
    )


def _page_request(p):
    """Validate the search, category filters and page bounds."""
    query = text(p.get("query", ""))
    filters = p.get("categories", [])
    if (
        not isinstance(filters, list)
        or len(filters) > 200
        or any(not isinstance(value, str) or len(value) > 10000 for value in filters)
    ):
        raise ValueError("Choose up to 200 category names")
    offset = p.get("offset", 0)
    limit = p.get("limit", 100)
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError("Invalid page")
    return query, filters, offset, limit


def _schedule_summary(table, category):
    """Total all billable schedule rows using a tuple query."""
    # Tuples, not models: hydrating every schedule row dominated this request.
    return dict(
        grand_total=str(
            Currency(
                sum(
                    (
                        Currency((rate or 0) * (qty or 0))
                        for rate, qty, unit, description in table.select(
                            table.rate, table.qty, table.unit, category.description
                        )
                        .join(category)
                        .tuples()
                        if unit and description != misc.SUB_ANA_TITLE
                    ),
                    Decimal(0),
                )
            )
        )
    )


def _row_delta(editor, kind, p, query, db, table, resource, summary):
    """Return changed visible rows when the change sequence can be applied."""
    changed = editor.changes.changed_ids(kind, p["since"], query)
    visible = p.get("visible_ids", [])
    if not isinstance(visible, list) or len(visible) > 2000 or any(not isinstance(value, str) for value in visible):
        raise ValueError("Invalid visible row selection")
    if changed is not None:
        ids = changed.intersection(int(value) for value in visible if value.isdecimal())
        updates = []
        parents = frozenset() if resource else _parent_ids(table)
        for row in table.select().where(table.id.in_(ids)):
            data = _serialize_row(row, resource, parents)
            data.pop("_children", None)
            updates.append(data)
        return dict(
            delta=True,
            updates=updates,
            view_seq=editor.changes.sequence,
            revision=editor.owner.revision,
            undo=bool(editor.history),
            redo=bool(editor.future),
            enrichment=presentation(db),
            **summary,
        )


def _find_row(records, table, ranks, p):
    """Find the next type-ahead match, wrapping around the current listing."""
    # Type-ahead across pages: the next row, in listing order, whose
    # code, description and unit contain every word of `find`.
    words = text(p["find"]).lower().split()
    direction = p.get("find_direction", 1)
    start = p.get("find_from")
    if (
        not words
        or direction not in (1, -1)
        or (start is not None and (not isinstance(start, str) or not start.isdecimal()))
    ):
        raise ValueError("Invalid find request")
    listing = records.select(table.id, table.code, table.description, table.unit)
    if ranks is not None:
        listing = sorted(listing.where(table.code.in_(list(ranks))).tuples(), key=lambda row: ranks[row[1]])
    else:
        listing = list(listing.tuples())
    ids = [row[0] for row in listing]
    begin = ids.index(int(start)) if start is not None and int(start) in ids else (-1 if direction == 1 else 0)
    for step in range(1, len(listing) + 1):
        identity, code, description, unit = listing[(begin + direction * step) % len(listing)]
        haystack = " ".join((code or "", description or "", unit or "")).lower()
        if all(word in haystack for word in words):
            return identity


def _reveal_offset(records, table, category, resource, reveal_id, limit):
    """Locate a row's page under the unranked listing order."""
    revealed = table.get_or_none(table.id == int(reveal_id))
    if revealed is None:
        raise ValueError("Inserted row is no longer available")
    keys = [(category.order, revealed.category.order), (table.order, revealed.order)]
    if not resource:
        keys.append((fn.COALESCE(table.suborder, -1), revealed.suborder if revealed.suborder is not None else -1))
    keys.append((table.id, revealed.id))
    earlier, equal = None, None
    for field, value in keys:
        less = field < value
        earlier = (earlier | (equal & less)) if earlier is not None else less
        equal = (equal & (field == value)) if equal is not None else field == value
    return records.where(earlier).count() // limit * limit


def _project_tree(table, category, resource, values, filters, query, *, ranked):
    """Render rows with empty categories and any missing schedule ancestors."""
    nodes = {}
    categories = {}
    # Empty categories remain editable, including before the first item is added.
    for cat in (
        category.select()
        .where(category.id.not_in(table.select(table.category).where(table.category.is_null(False))))
        .order_by(category.order)
    ):
        if (not filters or (cat.description or "") in filters) and (
            not query or query.lower() in (cat.description or "").lower()
        ):
            categories[cat.id] = dict(
                id="cat:" + str(cat.id), rowtype="Category", code="", description=cat.description, _children=[]
            )
    # Include missing ancestors so filtered/paged child rows retain their context.
    if not resource:
        for row in list(values):
            parent = row.parent
            seen = {row.id}
            while parent and parent.id not in seen:
                seen.add(parent.id)
                if all(r.id != parent.id for r in values):
                    values.append(parent)
                parent = parent.parent
        if not ranked:
            values.sort(key=lambda r: (r.category.order, r.order, -1 if r.suborder is None else r.suborder, r.id))
    parents = frozenset() if resource else _parent_ids(table)
    for row in values:
        cat = row.category
        if cat.id not in categories:
            group = dict(
                id="cat:" + str(cat.id), rowtype="Category", code="", description=cat.description, _children=[]
            )
            categories[cat.id] = group
        data = _serialize_row(row, resource, parents)
        nodes[row.id] = data
    for row in values:
        data = nodes[row.id]
        parent = nodes.get(row.parent_id) if not resource else None
        (parent["_children"] if parent else categories[row.category_id]["_children"]).append(data)
    category_order = {cat.id: cat.order for cat in category.select()}
    rows = [group for identity, group in sorted(categories.items(), key=lambda entry: category_order[entry[0]])]
    return rows


def _rank_tree(nodes, ranks, total):
    """Order each group by the earliest ranked row in it."""
    ranked_nodes = []
    for node in nodes:
        child_rank = _rank_tree(node.get("_children", []), ranks, total)
        ranked_nodes.append((min(ranks.get(node.get("code"), total), child_rank), node))
    ranked_nodes.sort(key=lambda pair: pair[0])
    nodes[:] = [node for _, node in ranked_nodes]
    return ranked_nodes[0][0] if ranked_nodes else total


def _parent_ids(table):
    """Ids of schedule items that have subitems, in one query."""
    return {parent for (parent,) in table.select(table.parent).where(table.parent.is_null(False)).distinct().tuples()}


def _serialize_row(row, resource, parents=frozenset()):
    cat = row.category
    data = dict(
        id=str(row.id),
        rowtype="Resource" if resource else "Schedule",
        code=row.code,
        description=row.description,
        unit=row.unit or "",
        rate=str(row.rate or 0),
        category=cat.description,
        remarks=getattr(row, "remarks", None) or "",
    )
    if resource:
        data.update(vat=tax_text(row.vat), discount=str(row.discount or 0), reference=row.reference or "")
    else:
        data.update(
            qty=str(row.qty or 0),
            colour=row.colour,
            amount=(str(Currency((row.rate or 0) * (row.qty or 0))) if row.unit else ""),
            parent=row.parent.code if row.parent else "",
            # Items with subitems are priced through their subitems.
            has_children=row.id in parents,
            _children=[],
        )
    return data
