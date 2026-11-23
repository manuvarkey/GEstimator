"""Library import staging using the project editor's transaction and engine.

The coordinator keeps batch conflict/placement/rate policies together; helpers
resolve dependency stages without creating commits or additional undo history.
"""

import copy
from decimal import Decimal

from estimator import misc
from estimator.data.schedule import Currency

from .insertion import place, prepare
from .numbers import decimal


def _schedule_order(row):
    """Keep parents before children within the source's category order."""
    ancestors = []
    current = row
    seen = set()
    while current and current.id not in seen:
        seen.add(current.id)
        ancestors.append(current.suborder if current.parent_id else current.order)
        current = current.parent
    return (row.category.order, tuple(reversed(ancestors)), row.id)


def _import_dependencies(editor, source, records, prefix):
    """Stage prefixed, zero-quantity sub-analyses before the selected items."""
    # Step 1: follow resource references to collect transitive sub-analysis codes.
    renamed = {}
    dependency_codes = set()
    dependencies = []
    pending = [row.code for row in records]
    visited = set()
    source_codes = {code for (code,) in source.ScheduleTable.select(source.ScheduleTable.code).tuples()}
    while pending:
        code = pending.pop()
        if code in visited:
            continue
        visited.add(code)
        model = source.get_item(code, modify_res_code=False)
        for resource_code in model.resources:
            if resource_code in source_codes:
                dependency_codes.add(resource_code)
                pending.append(resource_code)
    # Step 2: insert separate prefixed copies without turning dependencies into billable quantities.
    for code in sorted(dependency_codes):
        item = source.get_item(code, modify_res_code=True)
        item.code = f"{prefix}:{code}" if prefix and ":" not in code else code
        item.category = misc.SUB_ANA_TITLE
        item.parent = None
        item.qty = Decimal(0)
        existing = editor.db.get_item(item.code, copy_ana=False)
        if existing:
            if existing.category != misc.SUB_ANA_TITLE:
                raise ValueError(f"Sub-analysis code conflicts with schedule item {item.code}")
        else:
            dependencies.append(item)
        renamed[code] = item.code
    editor.insert_schedule_items(dependencies)
    return renamed


def import_items(editor, kind, params, progress, *, review=False):
    """Coordinate one staged batch; the caller owns its transaction and undo entry.

    Conflict handling, selected-row numbering and final rate policy share the
    staged batch. Keep their ordering explicit rather than publishing per row.
    """
    # Step 1: validate rate/rule policies before creating destination rows.
    modify = params.get("modify", False)
    if type(modify) is not bool or (modify and kind != "schedule"):
        raise ValueError("Modify & Add applies only to schedule items")
    rules = None
    rate_policy = None
    if "analysis_rules" in params:
        # Rule validation imports service helpers; defer it for snapshot-only use.
        from .analysis_rules import transform
        from .analysis_rules import validate as validate_rules

        if kind != "schedule" or modify:
            raise ValueError("Library analysis rules require a schedule import")
        rules = [] if params["analysis_rules"] == [] else validate_rules(params["analysis_rules"])
        rate_policy = params.get("rate_policy")
        if rate_policy not in ("stored", "calculated"):
            raise ValueError("Choose how to set the imported schedule rate")
        if rate_policy == "stored":
            rate_factor = Currency(decimal(params.get("rate_factor", "1")), 5)
    if review and rules is None:
        raise ValueError("Choose analysis rules or a rate policy to preview")
    # GTK keeps the stored library rate on import. Recalculating every
    # imported analysis is opt-in (MCP "recalculate" mode, calculated rule policy).
    recalculate = params.get("recalculate", False)
    if type(recalculate) is not bool:
        raise ValueError("Invalid recalculation option")
    recalculate = recalculate or rate_policy == "calculated"
    if modify:
        from .program_settings import legacy_rows, validate

        settings = validate(params.get("settings", {}))
        replacement = legacy_rows(settings["ana_copy_rows"])
    # Step 2: resolve the source selection and retain parent/category placement.
    identity = params.get("source")
    if identity not in editor.libraries:
        raise ValueError("Choose an attached library")
    source = editor.libraries[identity][1]
    categories, records = editor.selection(kind, params.get("ids"), source, include_descendants=False)
    if kind == "schedule" and params.get("include_parents", False):
        selected = {row.id: row for row in records}
        for row in list(records):
            current, seen = row.parent, {row.id}
            while current:
                if current.id in seen:
                    raise ValueError("Schedule hierarchy contains a cycle")
                seen.add(current.id)
                selected[current.id] = current
                current = current.parent
        records = list(selected.values())
    destination_category = editor.db.ResourceCategoryTable if kind == "resources" else editor.db.ScheduleCategoryTable
    for cat in categories:
        if not destination_category.select().where(destination_category.description == cat.description).exists():
            method = (
                editor.db.insert_resource_category_atomic
                if kind == "resources"
                else editor.db.insert_schedule_category_atomic
            )
            if method(cat.description, [-1]) is False:
                raise ValueError("Unable to import category")
    prefix = source.get_project_settings().get("project_resource_code") or ""
    renamed = {}

    records.sort(
        key=((lambda row: (row.category.order, row.order, row.id)) if kind == "resources" else _schedule_order)
    )
    # Step 3: dependencies are distinct from selected schedule items, even when both are imported.
    if kind == "schedule":
        renamed = _import_dependencies(editor, source, records, prefix)
        sub_analysis_codes = set(renamed.values())
    imported = 0
    modified_rates = {}
    rule_matches = [0] * len(rules or [])
    rule_changes = []
    reviewed = []
    changed_count = unmatched = reviewed_count = 0
    target = dict(ids=params.get("target_ids", []), destination=not categories)
    inserted_codes = []
    updated_resources = []
    conflict = params.get("on_conflict")
    code_map = {}
    additions = []
    subitem = {}
    # GTK places library items at the selection and numbers them from it
    # (insert_item_multiple, number_with_path=True). Sub-analyses keep their
    # codes. Category imports and MCP conflict policies keep library codes.
    gtk_path = (
        editor.gtk_path("schedule", dict(ids=target["ids"]))
        if kind == "schedule" and not categories and conflict is None and target["ids"] and not review
        else None
    )
    reserved = set()
    # Step 4: stage selected definitions and resolve conflicts without per-row commits.
    for index, row in enumerate(records):
        if index % 100 == 0:
            progress("Importing library items: " + str(index + 1))
        if kind == "resources":
            item = source.get_resource(row.code, modify_code=bool(prefix))
            staged = next((value for value in additions if value.code == item.code), None)
            existing = editor.db.get_resource(item.code) or staged
            code_map[row.code] = item.code
            if existing:
                if conflict == "error":
                    raise ValueError("Resource code already exists: " + item.code)
                if conflict in (None, "skip"):
                    continue
                if conflict == "update":
                    if staged:
                        additions[additions.index(staged)] = item
                    elif not editor.db.update_resource(item.code, res_model=item):
                        raise ValueError("Unable to update resource")
                    updated_resources.append(item.code)
                    inserted_codes.append(item.code)
                    imported += 1
                    continue
                base, counter = item.code, 1
                while editor.db.get_resource(item.code) or item.code in reserved:
                    item.code = base + "-copy" + (str(counter) if counter > 1 else "")
                    counter += 1
                code_map[row.code] = item.code
            prepare(editor, kind, item, target)
            additions.append(item)
            reserved.add(item.code)
        else:
            # A selected item that another selected item's analysis uses
            # is imported as a schedule item too; the analyses reference
            # its prefixed SUB ANALYSIS copy, as when imported separately.
            item = source.get_item(row.code, modify_res_code=True)
            subitem[id(item)] = item.parent is not None
            if modify:
                item.rate *= Currency(decimal(settings["sch_rate_mult_factor"]), 5)
                count = settings["ana_copy_delete_rows"]
                if count and replacement and len(item.ana_items) > count:
                    item.ana_items = item.ana_items[:-count] + copy.deepcopy(replacement)
            # GTK SelectScheduleDialog records the library reference in remarks.
            item.remarks = (source.get_project_settings().get("project_item_code") or "") + " " + item.code
            code = item.code
            existing = editor.db.get_item(code, copy_ana=False)
            if existing and conflict == "error":
                raise ValueError("Schedule code already exists: " + code)
            if existing and conflict == "skip":
                renamed[row.code] = code
                code_map[row.code] = code
                continue
            if rules is not None:
                analysis_changed, matches, changes = transform(editor.owner, item, rules) if rules else (False, [], [])
                if rate_policy == "stored":
                    item.rate *= rate_factor
                if review:
                    reviewed_count += 1
                    changed_count += int(analysis_changed)
                    unmatched += int(bool(rules) and not any(matches))
                    rule_matches = [total + count for total, count in zip(rule_matches, matches)]
                    rule_changes.extend(
                        dict(code=code, **change) for change in changes[: max(0, 500 - len(rule_changes))]
                    )
            counter = 1
            while conflict != "update" and (
                code in reserved
                or editor.db.ScheduleTable.select().where(editor.db.ScheduleTable.code == code).exists()
            ):
                code = item.code + "-copy" + (str(counter) if counter > 1 else "")
                counter += 1
            renamed[item.code] = code
            code_map[row.code] = code
            item.code = code
            item.parent = renamed.get(item.parent)
            if modify or rate_policy == "stored":
                modified_rates[item.code] = item.rate
            if review and len(reviewed) < 200:
                reviewed.append((row.code, item.code, str(row.rate or 0)))
            prepare(editor, kind, item, target)
            if existing and conflict == "update":
                inserted = editor.db.insert_item_atomic(item, update=True)
                if not inserted:
                    raise ValueError("Unable to import schedule item")
            else:
                parent = next((value for value in additions if value.code == item.parent), None)
                if parent:
                    item.category = parent.category
                additions.append(item)
                reserved.add(item.code)
        inserted_codes.append(item.code)
        imported += 1
    # Step 5: publish the batch, restore requested rates and build the review result.
    if kind == "resources" and additions:
        inserted = editor.db.insert_resource_multiple_atomic(additions, preserve_structure=True)
        if not {item.code for item in additions}.issubset(set(inserted.values())):
            raise ValueError("Unable to import resources")
    elif kind == "schedule" and gtk_path is not None and additions:
        editor.normalize_schedule_order(editor.selected_categories("schedule", dict(ids=target["ids"])))
        for item in additions:
            item.parent = item.parent or ("SUBITEM" if subitem.get(id(item)) else None)
        added, _ = editor.db.insert_item_multiple_atomic(additions, path=gtk_path, number_with_path=True)
        numbered = [code for key, code in added.items() if len(key) > 1]
        if len(numbered) != len(additions):
            raise ValueError("Unable to import schedule items")
        moved = {item.code: code for item, code in zip(additions, numbered)}
        renumber = lambda code: moved.get(code, code)
        inserted_codes = [renumber(code) for code in inserted_codes]
        renamed = {key: renumber(value) for key, value in renamed.items()}
        code_map = {key: renumber(value) for key, value in code_map.items()}
        modified_rates = {renumber(code): rate for code, rate in modified_rates.items()}
    elif kind == "schedule":
        editor.insert_schedule_items(additions)
    if gtk_path is None:
        place(editor, kind, inserted_codes, target)
    # Only replaced definitions can have dependants; new resources have none.
    if kind == "resources" and updated_resources:
        editor.owner.update_dependent_rates(editor.db, resources=updated_resources)
    if renamed and recalculate:
        editor.owner.update_dependent_rates(
            editor.db, schedules=set(renamed.values()) | (sub_analysis_codes if kind == "schedule" else set())
        )
    # GTK Modify & Add retains the selected library item's multiplied stored rate,
    # even when its replacement calculation rows produce a different analysis rate.
    for code, rate in modified_rates.items():
        if not editor.db.update_item_schedule(code, rate, 3):
            raise ValueError("Unable to retain the modified library rate")
    if review:
        items = []
        for source_code, code, before in reviewed:
            item = editor.db.get_item(code, modify_res_code=False)
            analysis_rate = item.get_ana_rate()
            items.append(
                dict(
                    code=code,
                    source_code=source_code,
                    description=item.description,
                    before=before,
                    after=str(item.rate or 0),
                    calculated=None if analysis_rate is None else str(analysis_rate),
                )
            )
        return dict(
            selected=reviewed_count,
            imported=imported,
            changed=changed_count,
            unmatched=unmatched,
            rule_matches=rule_matches,
            changes=rule_changes,
            items=items,
            truncated=reviewed_count > len(items) or len(rule_changes) >= 500,
        )
    table = editor.db.ResourceTable if kind == "resources" else editor.db.ScheduleTable
    return dict(
        imported=imported,
        skipped=len(records) - imported,
        code_map=code_map,
        selected=[str(row.id) for row in table.select().where(table.code.in_(inserted_codes))],
    )
