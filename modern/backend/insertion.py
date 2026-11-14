"""Selection-aware placement; numbering stays with the original database helpers."""


def tables(editor, kind):
    db = editor.db
    return (db.ResourceTable, db.ResourceCategoryTable) if kind == "resources" else (db.ScheduleTable, db.ScheduleCategoryTable)


def last_selected(editor, kind, params):
    table, category = tables(editor, kind)
    ids = params.get("ids") or ([params["id"]] if params.get("id") else [])
    if not isinstance(ids, list) or len(ids) > 1000:
        raise ValueError("Invalid insertion selection")
    entries = []
    for identity in ids:
        identity = str(identity)
        if identity.startswith("cat:"):
            row = category.get_by_id(int(identity[4:]))
            entries.append(((row.order, ()), row, True))
        else:
            row = table.get_by_id(int(identity))
            path, current, seen = [], row, set()
            while current:
                if current.id in seen:
                    raise ValueError("Schedule hierarchy contains a cycle")
                seen.add(current.id)
                path.append(current.suborder if kind == "schedule" and current.parent_id else current.order)
                current = current.parent if kind == "schedule" else None
            entries.append(((row.category.order, tuple(reversed(path))), row, False))
    return max(entries, key=lambda entry: entry[0])[1:] if entries else (None, False)


def defaults(editor, kind, params):
    table, category_table = tables(editor, kind)
    selected, category = last_selected(editor, kind, params)
    had_selection = selected is not None
    parent = None
    near = None
    category_name = params.get("category") or "UNCATEGORISED"
    if not isinstance(category_name, str):
        raise ValueError("Invalid insertion category")
    if not selected:
        group = category_table.get_or_none(category_table.description == category_name)
        if group:
            condition = table.category == group.id
            if kind == "schedule":
                condition &= table.parent.is_null()
            selected = table.select().where(condition).order_by(table.order.desc(), table.id.desc()).first()
            if not selected:
                selected, category = group, True
        elif kind == "schedule":
            near = str(category_table.select().count() + 1)
            category = True
    if selected:
        near = str(selected.order + 1) if category else selected.code
        if kind == "schedule" and not category:
            if params.get("child"):
                parent = selected
            else:
                while selected.parent_id:
                    selected = selected.parent
                near = selected.code
    if kind == "schedule" and params.get("parent"):
        parent = table.get_or_none(table.code == params["parent"])
        if parent is None:
            raise ValueError("Parent schedule item not found")
        near = parent.code
    if kind == "resources":
        code = editor.db.get_new_resource_code(near_item_code=near if had_selection and near and ":" not in near and not category else None)
    else:
        code = editor.db.get_next_item_code(near_item_code=near, nextlevel=bool(parent) or category)
    return dict(code=code, category=parent.category.description if parent else (selected.description if category else selected.category.description) if selected else category_name,
                parent=parent.code if parent else "")


def prepare(editor, kind, item, params):
    """A selected destination supplies the category; an explicit parent takes precedence."""
    selected, is_category = last_selected(editor, kind, params)
    if selected and not (kind == "schedule" and item.parent):
        destination = selected if is_category else selected.category
        if not item.category or params.get("destination"):
            item.category = destination.description


def place(editor, kind, codes, params):
    """Place each new sibling block once, retaining copied subtrees and their order."""
    if not codes:
        return
    selected, is_category = last_selected(editor, kind, params)
    if not selected:
        return
    table, _ = tables(editor, kind)
    inserted = list(table.select().where(table.code.in_(codes)))
    by_code = {row.code: row for row in inserted}
    inserted_ids = {row.id for row in inserted}
    groups = {}
    for code in codes:
        row = by_code[code]
        if kind == "schedule" and row.parent_id in inserted_ids:
            continue
        groups.setdefault((row.category_id, row.parent_id if kind == "schedule" else None), []).append(row)
    for (category_id, parent_id), new in groups.items():
        target = selected
        first = is_category
        if kind == "schedule" and not is_category:
            if parent_id == selected.id:
                first = True
            else:
                while target.parent_id and target.parent_id != parent_id:
                    target = target.parent
        destination_category = selected.id if is_category else selected.category_id
        if category_id != destination_category:
            continue
        condition = table.category == category_id
        order = table.order
        if kind == "schedule":
            condition &= table.parent == parent_id
            order = table.suborder if parent_id else table.order
            if not first and target.parent_id != parent_id:
                continue
        siblings = list(table.select().where(condition & table.code.not_in(codes)).order_by(order, table.id))
        index = 0 if first else next((i + 1 for i, row in enumerate(siblings) if row.id == target.id), len(siblings))
        siblings[index:index] = new
        for index, row in enumerate(siblings):
            if getattr(row, order.name) != index:
                table.update({order: index}).where(table.id == row.id).execute()
        if kind == "schedule":
            editor.normalize_schedule_order({category_id})
