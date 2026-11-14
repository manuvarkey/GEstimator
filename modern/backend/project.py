"""Project editors reuse the legacy ORM, CRUD and measurement template engine."""

from contextlib import closing
import copy
from decimal import Decimal
from pathlib import Path
import re
import sqlite3
from uuid import uuid4
from estimator import misc
from estimator.data import measurement
from estimator.data.schedule import Currency, ScheduleItemModel, ResourceItemModel
from .numbers import decimal
from estimator.data.schedule import ScheduleDatabase
from estimator.undo import Stack


def text(value):
    if not isinstance(value, str) or len(value) > 10000:
        raise ValueError("Invalid text")
    return value


class ProjectEditor:
    def __init__(self, owner):
        self.owner = owner
        self.history = []
        self.future = []
        self.ids = []
        self.record_ids = {}
        self.clipboard = None
        self.libraries = {}
        self.library_paths = {}
        self.ensure_ids()

    @property
    def db(self):
        return self.owner.db

    def ensure_ids(self):
        items = self.db.get_measurement().items
        while len(self.ids) < len(items):
            self.ids.append(uuid4().hex)
        self.ids = self.ids[: len(items)]
        for identity, item in zip(self.ids, items):
            ids = self.record_ids.setdefault(identity, [])
            while len(ids) < len(item.records):
                ids.append(uuid4().hex)
            self.record_ids[identity] = ids[: len(item.records)]

    def snapshot(self):
        target = Path(self.owner.temp.name) / (uuid4().hex + ".undo")
        with closing(sqlite3.connect(target)) as dst:
            self.db.database.connection().backup(dst)
        return (target, copy.deepcopy(self.ids), copy.deepcopy(self.record_ids))

    def restore(self, snapshot):
        active_id = (
            self.db.get_item_key(self.owner.model.code) if self.owner.loaded else None
        )
        path, self.ids, self.record_ids = snapshot
        with closing(sqlite3.connect(path)) as src:
            src.backup(self.db.database.connection())
        path.unlink()
        self.db.stack.clear()
        self.owner.workspace_dirty = True
        self.reload_analysis(active_id)

    def reload_analysis(self, active_id=None):
        if self.owner.loaded:
            code = (
                self.db.get_item_code(active_id)
                if active_id is not None
                else self.owner.model.code
            )
            model = self.db.get_item(code, modify_res_code=False)
            if model:
                self.owner.model = model
                self.owner.identify()
            else:
                self.owner.loaded = False
                self.owner.model = ScheduleItemModel("", "Select a schedule item")
            self.owner.history.clear()
            self.owner.future.clear()
            self.owner.saved_signature = copy.deepcopy(self.owner.signature())
        self.owner.revision += 1

    def mutate(self, action, reload=True):
        before = self.snapshot()
        active_row = (
            self.db.ScheduleTable.get_or_none(
                self.db.ScheduleTable.code == self.owner.model.code
            )
            if self.owner.loaded
            else None
        )
        try:
            with self.db.database.atomic():
                result = action()
        except Exception:
            self.ids, self.record_ids = before[1:]
            before[0].unlink()
            self.db.stack.clear()
            raise
        self.history.append(before)
        for snapshot in self.future:
            snapshot[0].unlink(missing_ok=True)
        self.future.clear()
        if len(self.history) > 30:
            self.history.pop(0)[0].unlink(missing_ok=True)
        self.db.stack.clear()
        self.owner.workspace_dirty = True
        if reload:
            self.reload_analysis(active_row.id if active_row else None)
        return result

    def relocate_schedule(self, row, parent, category_id):
        table = self.db.ScheduleTable
        if parent:
            category_id = parent.category_id
        if row.category_id == category_id and row.parent_id == (parent.id if parent else None):
            return

        _, subtree = self.selection("schedule", [row.id])
        if parent and any(item.id == parent.id for item in subtree):
            raise ValueError("Schedule hierarchy cannot contain a cycle")
        new_siblings = (table.category == category_id) & (table.parent == (parent.id if parent else None))
        destination_order = table.suborder if parent else table.order
        last = (table.select(destination_order).where(new_siblings)
                .order_by(destination_order.desc()).scalar())
        next_order = 0 if last is None else last + 1
        table.update(
            category=category_id, parent=parent.id if parent else None,
            order=parent.order if parent else next_order,
            suborder=next_order if parent else None,
        ).where(table.id == row.id).execute()
        if row.category_id != category_id:
            descendants = [item.id for item in subtree if item.id != row.id]
            for start in range(0, len(descendants), 500):
                table.update(category=category_id).where(
                    table.id.in_(descendants[start : start + 500])
                ).execute()
        # Keep the legacy order field in sync with each top-level branch.
        self.normalize_schedule_order({row.category_id, category_id})

    def normalize_schedule_order(self, categories):
        table = self.db.ScheduleTable
        rows = list(table.select().where(table.category.in_(categories)).order_by(
            table.category, table.order, table.suborder, table.id
        ))
        children = {}
        for item in rows:
            children.setdefault((item.category_id, item.parent_id), []).append(item)
        for category in categories:
            for order, root in enumerate(children.get((category, None), [])):
                stack = [(root, None)]
                while stack:
                    item, suborder = stack.pop()
                    if (item.category_id, item.order, item.suborder) != (category, order, suborder):
                        table.update(category=category, order=order, suborder=suborder).where(
                            table.id == item.id
                        ).execute()
                    stack.extend((child, index) for index, child in enumerate(
                        children.get((category, item.id), [])
                    ))

    def renumber_schedule(self):
        table = self.db.ScheduleTable
        category = self.db.ScheduleCategoryTable
        categories = list(category.select().where(
            category.description != misc.SUB_ANA_TITLE
        ).order_by(category.order, category.id))
        items = list(table.select().order_by(table.order, table.suborder, table.id))
        children = {}
        for item in items:
            children.setdefault((item.category_id, item.parent_id), []).append(item)
        assigned = {}
        for index, group in enumerate(categories, 1):
            prefix = f"{index}." if len(categories) > 1 else ""
            stack = [(None, prefix)]
            while stack:
                parent, prefix = stack.pop()
                for position, item in enumerate(children.get((group.id, parent), []), 1):
                    code = f"{prefix}{position}"
                    assigned[item.id] = code
                    stack.append((item.id, code + "."))
        untouched = {item.code for item in items if item.id not in assigned}
        if untouched.intersection(assigned.values()):
            raise ValueError("A schedule number conflicts with an existing sub-analysis code")
        occupied = {item.code for item in items}
        occupied.update(assigned.values())
        changes = {item.id: assigned[item.id] for item in items
                   if item.id in assigned and item.code != assigned[item.id]}
        for identity in changes:
            temporary = "__renumber_" + uuid4().hex
            while temporary in occupied:
                temporary = "__renumber_" + uuid4().hex
            occupied.add(temporary)
            table.update(code=temporary).where(table.id == identity).execute()
        for identity, code in changes.items():
            table.update(code=code).where(table.id == identity).execute()

    def state(self, kind, p):
        if p.get("source") and p["source"] not in self.libraries:
            raise ValueError("Library is no longer attached")
        db = (
            self.libraries[p["source"]][1]
            if p.get("source") in self.libraries
            else self.db
        )
        resource = kind == "resources"
        table = db.ResourceTable if resource else db.ScheduleTable
        category = db.ResourceCategoryTable if resource else db.ScheduleCategoryTable
        query = text(p.get("query", ""))
        offset = p.get("offset", 0)
        limit = p.get("limit", 100)
        if (
            type(offset) is not int
            or offset < 0
            or type(limit) is not int
            or not 1 <= limit <= 200
        ):
            raise ValueError("Invalid page")
        records = (
            table.select()
            .join(category)
            .where(
                table.code.contains(query)
                | table.description.contains(query)
                | category.description.contains(query)
            )
            .order_by(category.order, table.order, table.id)
        )
        total = records.count()
        values = list(records.offset(offset).limit(limit))
        nodes = {}
        categories = {}
        # Empty categories remain editable, including before the first item is added.
        for cat in (
            category.select()
            .where(
                category.id.not_in(
                    table.select(table.category).where(table.category.is_null(False))
                )
            )
            .order_by(category.order)
        ):
            if not query or query.lower() in cat.description.lower():
                categories[cat.id] = dict(
                    id="cat:" + str(cat.id),
                    rowtype="Category",
                    code="",
                    description=cat.description,
                    _children=[],
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
            values.sort(
                key=lambda r: (
                    r.category.order,
                    r.order,
                    -1 if r.suborder is None else r.suborder,
                    r.id,
                )
            )
        for row in values:
            cat = row.category
            if cat.id not in categories:
                group = dict(
                    id="cat:" + str(cat.id),
                    rowtype="Category",
                    code="",
                    description=cat.description,
                    _children=[],
                )
                categories[cat.id] = group
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
                data.update(
                    vat=str(row.vat or 0),
                    discount=str(row.discount or 0),
                    reference=row.reference or "",
                )
            else:
                data.update(
                    qty=str(row.qty or 0),
                    colour=row.colour,
                    amount=(
                        str(Currency((row.rate or 0) * (row.qty or 0)))
                        if row.unit
                        else ""
                    ),
                    parent=row.parent.code if row.parent else "",
                    _children=[],
                )
            nodes[row.id] = data
        for row in values:
            data = nodes[row.id]
            parent = nodes.get(row.parent_id) if not resource else None
            (
                parent["_children"]
                if parent
                else categories[row.category_id]["_children"]
            ).append(data)
        category_order = {cat.id: cat.order for cat in category.select()}
        rows = [
            group
            for identity, group in sorted(
                categories.items(), key=lambda entry: category_order[entry[0]]
            )
        ]
        return dict(
            rows=rows,
            total=total,
            offset=offset,
            undo=bool(self.history),
            redo=bool(self.future),
            revision=self.owner.revision,
            categories=[
                r.description for r in category.select().order_by(category.order)
            ],
        )

    def attach_library(self, path):
        path = text(path)
        if path.startswith("bundled:"):
            name = path[len("bundled:"):]
            if not name or Path(name).name != name or "/" in name or "\\" in name or Path(name).suffix.lower() != ".eproj":
                raise ValueError("Invalid bundled database name")
            source = Path(misc.abs_path("database", name)).resolve(strict=True)
        else:
            source = Path(path).resolve(strict=True)
        if source in self.library_paths:
            selected = self.library_paths[source]
            return [dict(item, attached=item["id"] == selected) for item in self.sources()]
        target = Path(self.owner.temp.name) / (uuid4().hex + ".library")
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as src:
            version = src.execute(
                "SELECT value FROM projecttable WHERE key='file_version'"
            ).fetchone()
            if version not in (
                (misc.PROJECT_FILE_VER,),
                ("GESTIMATOR_FILE_REFERENCE_VER_1",),
            ):
                raise ValueError("Unsupported library version")
            with closing(sqlite3.connect(target)) as dst:
                src.backup(dst)
        db = ScheduleDatabase(Stack())
        if version == ("GESTIMATOR_FILE_REFERENCE_VER_1",):
            result = db.validate_database(str(target))
            if not result[0]:
                raise ValueError(result[1])
        db.open_database(str(target))
        name = db.get_project_settings().get("project_name") or source.stem
        identity = uuid4().hex
        self.libraries[identity] = (name, db)
        self.library_paths[source] = identity
        return [dict(item, attached=item["id"] == identity) for item in self.sources()]

    def sources(self):
        return [dict(id=key, name=value[0]) for key, value in self.libraries.items()]

    def refresh_resource_prices(self, params, apply):
        identity = params.get("library")
        if not isinstance(identity, str) or identity not in self.libraries:
            raise ValueError("Choose an attached library")
        source = self.libraries[identity][1]
        _, records = self.selection("resources", params.get("ids"))
        prefix = source.get_project_settings().get("project_resource_code")
        catalog = source.get_resource_table(flat=True, modify_code=bool(prefix))
        changes = {}
        matched = 0
        for row in records:
            entry = catalog.get(row.code)
            if entry is None:
                continue
            matched += 1
            current = (row.rate, row.vat, row.discount, row.reference)
            replacement = tuple(entry[3:7])
            if current != replacement:
                changes[row.code] = replacement

        if apply and changes:
            def update():
                table = self.db.ResourceTable
                for code, (rate, vat, discount, reference) in changes.items():
                    table.update(
                        rate=rate, vat=vat, discount=discount, reference=reference
                    ).where(table.code == code).execute()
                self.owner.update_dependent_rates(self.db, resources=changes)

            self.mutate(update)
        return dict(
            changed=len(changes),
            unchanged=matched - len(changes),
            unmatched=len(records) - matched,
        )

    def resource_usage(self, params):
        offset = params.get("offset", 0)
        if type(offset) is not int or offset < 0:
            raise ValueError("Invalid resource usage page")
        words = text(params.get("query", "")).casefold().split()
        rows = []
        for category, items in self.db.get_res_usage().items():
            for code, (_, description, unit, quantity, base, vat, discount) in sorted(
                items.items()
            ):
                haystack = " ".join((code, description, unit, category)).casefold()
                if not all(word in haystack for word in words):
                    continue
                rate = Currency(
                    base * (1 + (vat or Decimal(0)) / 100)
                    * (1 - (discount or Decimal(0)) / 100)
                )
                rows.append(dict(
                    code=code, description=description, unit=unit, category=category,
                    quantity=str(quantity), rate=str(rate), amount=str(Currency(rate * quantity)),
                ))
        return dict(rows=rows[offset:offset + 50], total=len(rows))

    def resource_dependents(self, params):
        code = text(params["code"])
        offset = params.get("offset", 0)
        if type(offset) is not int or offset < 0:
            raise ValueError("Invalid analysis page")
        schedule = self.db.ScheduleTable
        resource = self.db.ResourceTable
        entry = self.db.ResourceItemTable
        references = {}
        edges = (entry.select(resource.code, schedule.code)
                 .join(resource).switch(entry).join(schedule).distinct().tuples())
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
            for item in schedule.select(schedule.code, schedule.description)
            .order_by(schedule.order, schedule.suborder, schedule.id)
            if item.code in reached
        ]
        return dict(rows=matches[offset : offset + 50], total=len(matches))

    def close(self):
        for name, db in self.libraries.values():
            db.close_database()
        self.libraries.clear()
        self.library_paths.clear()

    def selection(self, kind, ids, db=None, *, include_descendants=True):
        """Resolve stable IDs independently of paging and expand selected categories."""
        db = db or self.db
        resource = kind == "resources"
        table = db.ResourceTable if resource else db.ScheduleTable
        category = db.ResourceCategoryTable if resource else db.ScheduleCategoryTable
        if not isinstance(ids, list) or not ids or len(ids) > 1000:
            raise ValueError("Select between 1 and 1000 rows")
        categories, records = {}, {}
        for identity in ids:
            identity = str(identity)
            key = int(identity[4:] if identity.startswith("cat:") else identity)
            if not 0 < key < 2**63:
                raise ValueError("Invalid row identifier")
            if identity.startswith("cat:"):
                cat = category.get_or_none(category.id == key)
                if cat is None:
                    raise ValueError("Category no longer exists; refresh the view")
                categories[cat.id] = cat
                records.update(
                    (row.id, row)
                    for row in table.select().where(table.category == cat.id)
                )
            else:
                row = table.get_or_none(table.id == key)
                if row is None:
                    raise ValueError("Item no longer exists; refresh the view")
                records[row.id] = row
        if not resource and include_descendants:
            frontier = list(records)
            while frontier:
                children = {}
                for start in range(0, len(frontier), 500):
                    for row in table.select().where(
                        table.parent.in_(frontier[start : start + 500])
                    ):
                        if row.id not in records:
                            children[row.id] = row
                records.update(children)
                frontier = list(children)
        return list(categories.values()), list(records.values())

    def delete_preview(self, kind, p):
        categories, records = self.selection(kind, p.get("ids"))
        ids = {row.id for row in records}
        used = sorted(
            row.code
            for row in records
            if kind == "resources" and self.db.resource_has_dependency(row.code)
        )
        references = 0
        if kind == "schedule":
            references = sum(
                key in ids
                for item in self.db.get_measurement().items
                for key in item.itemnos
            )
        return dict(
            items=len(records),
            categories=len(categories),
            used_resources=used,
            measurement_references=references,
        )

    def delete_selection(self, kind, p):
        categories, records = self.selection(kind, p.get("ids"))
        resource = kind == "resources"
        policy = p.get("policy", "protect")
        if policy not in ("protect", "unused", "all"):
            raise ValueError("Invalid deletion policy")
        used = {
            row.id
            for row in records
            if resource and self.db.resource_has_dependency(row.code)
        }
        if used and policy == "protect":
            raise ValueError(
                "Resources are used by schedule analysis; choose Delete unused or Delete including used"
            )
        affected = set()
        if resource:
            records = [
                row for row in records if policy != "unused" or row.id not in used
            ]
            for row in records:
                affected.update(
                    reference.id_sch.code for reference in row.resourceitems
                )
                self.db.delete_resource_item_atomic(row.code)
        else:
            selected_ids = {row.id for row in records}
            meas = self.db.get_measurement()
            # Remove only associations: retain records/remarks, and prevent recycled SQLite
            # primary keys from silently linking these measurements to a future item.
            for item in meas.items:
                item.itemnos = [
                    None if key in selected_ids else key for key in item.itemnos
                ]
            self.db.set_measurement(meas)

            def depth(row):
                seen = {row.id}
                parent = row.parent
                while parent and parent.id not in seen:
                    seen.add(parent.id)
                    parent = parent.parent
                return len(seen)

            for row in sorted(records, key=depth, reverse=True):
                self.db.delete_item_atomic(row.code)
        table = self.db.ResourceTable if resource else self.db.ScheduleTable
        for cat in categories:
            if not table.select().where(table.category == cat.id).exists():
                method = (
                    self.db.delete_resource_category_atomic
                    if resource
                    else self.db.delete_schedule_category_atomic
                )
                method(cat.description)
        if affected:
            self.owner.update_dependent_rates(self.db, schedules=affected)
        return dict(deleted=len(records))

    def from_library(self, kind, params, progress):
        modify = params.get("modify", False)
        if type(modify) is not bool or (modify and kind != "schedule"):
            raise ValueError("Modify & Add applies only to schedule items")
        if modify:
            from .program_settings import validate, legacy_rows
            settings = validate(params.get("settings", {}))
            replacement = legacy_rows(settings["ana_copy_rows"])
        identity = params.get("source")
        if identity not in self.libraries:
            raise ValueError("Choose an attached library")
        source = self.libraries[identity][1]
        categories, records = self.selection(kind, params.get("ids"), source)
        destination_category = (
            self.db.ResourceCategoryTable
            if kind == "resources"
            else self.db.ScheduleCategoryTable
        )
        for cat in categories:
            if (
                not destination_category.select()
                .where(destination_category.description == cat.description)
                .exists()
            ):
                method = (
                    self.db.insert_resource_category_atomic
                    if kind == "resources"
                    else self.db.insert_schedule_category_atomic
                )
                if method(cat.description, [-1]) is False:
                    raise ValueError("Unable to import category")
        prefix = source.get_project_settings().get("project_resource_code") or ""
        renamed = {}

        def order(row):
            ancestors = []
            current = row
            seen = set()
            while current and current.id not in seen:
                seen.add(current.id)
                ancestors.append(
                    current.suborder if current.parent_id else current.order
                )
                current = current.parent
            return (row.category.order, tuple(reversed(ancestors)), row.id)

        records.sort(
            key=(
                (lambda row: (row.category.order, row.order, row.id))
                if kind == "resources"
                else order
            )
        )
        dependency_codes = set()
        if kind == "schedule":
            pending = [row.code for row in records]
            visited = set()
            while pending:
                code = pending.pop()
                if code in visited:
                    continue
                visited.add(code)
                model = source.get_item(code, modify_res_code=False)
                for resource_code in model.resources:
                    if source.get_item_key(resource_code) is not None:
                        dependency_codes.add(resource_code)
                        pending.append(resource_code)
            for code in sorted(dependency_codes):
                item = source.get_item(code, modify_res_code=True)
                item.code = f"{prefix}:{code}" if prefix and ":" not in code else code
                item.category = misc.SUB_ANA_TITLE
                item.parent = None
                existing = self.db.get_item(item.code, copy_ana=False)
                if existing:
                    if existing.category != misc.SUB_ANA_TITLE:
                        raise ValueError(f"Sub-analysis code conflicts with schedule item {item.code}")
                elif not self.db.insert_item(item):
                    raise ValueError(f"Unable to import sub-analysis {item.code}")
                renamed[code] = item.code
        imported = 0
        modified_rates = {}
        for index, row in enumerate(records):
            if index % 100 == 0:
                progress("Importing library items: " + str(index + 1))
            if kind == "resources":
                item = source.get_resource(row.code, modify_code=bool(prefix))
                if self.db.get_resource(item.code):
                    continue
                if not self.db.insert_resource(item):
                    raise ValueError("Unable to import resource")
            else:
                if row.code in dependency_codes:
                    imported += 1
                    continue
                item = source.get_item(row.code, modify_res_code=True)
                if modify:
                    item.rate *= Currency(decimal(settings["sch_rate_mult_factor"]), 5)
                    count = settings["ana_copy_delete_rows"]
                    if count and replacement and len(item.ana_items) > count:
                        item.ana_items = item.ana_items[:-count] + copy.deepcopy(replacement)
                    item.remarks = source.get_project_settings().get("project_item_code", "") + " " + item.code
                code = item.code
                counter = 1
                while (
                    self.db.ScheduleTable.select()
                    .where(self.db.ScheduleTable.code == code)
                    .exists()
                ):
                    code = item.code + "-copy" + (str(counter) if counter > 1 else "")
                    counter += 1
                renamed[item.code] = code
                item.code = code
                item.parent = renamed.get(item.parent)
                if modify:
                    modified_rates[item.code] = item.rate
                if not self.db.insert_item(item):
                    raise ValueError("Unable to import schedule item")
            imported += 1
        if renamed:
            self.owner.update_dependent_rates(self.db, schedules=set(renamed.values()))
        # GTK Modify & Add retains the selected library item's multiplied stored rate,
        # even when its replacement calculation rows produce a different analysis rate.
        for code, rate in modified_rates.items():
            if not self.db.update_item_schedule(code, rate, 3):
                raise ValueError("Unable to retain the modified library rate")
        return dict(imported=imported, skipped=len(records) - imported)

    def call(self, method, p, progress):
        if method == "library.attach":
            return self.attach_library(p["path"])
        if method == "library.list":
            return self.sources()
        if method == "project.import_preview":
            from .importing import preview

            return preview(p)
        if method.endswith(".state") and not method.startswith("measurement."):
            return self.state(method.split(".")[0], p)
        if method == "measurement.state":
            return self.measurement_state(p)
        if method == "measurement.templates":
            return self.templates()
        if method == "resources.editor.usage":
            return self.resource_usage(p)
        if method == "resources.editor.dependents":
            return self.resource_dependents(p)
        if p.get("revision") != self.owner.revision and not method.startswith(
            "project.export"
        ):
            raise ValueError("Stale project edit; refresh the view")
        self.owner.guard_draft(p)
        if method == "project.import_apply":
            from .importing import apply

            return self.mutate(lambda: apply(self, p, progress))
        if method in (
            "schedule.editor.edit_many",
            "resources.editor.edit_many",
            "measurement.record_edit_many",
        ):
            edits = p.get("edits", [])
            if not isinstance(edits, list) or not 1 <= len(edits) <= 1000:
                raise ValueError("Paste between 1 and 1000 editable cells")

            def apply_cells():
                for index, edit in enumerate(edits):
                    if not isinstance(edit, dict):
                        raise ValueError("Invalid pasted cell")
                    if method.startswith("measurement."):
                        self.measurement_edit(
                            "record_edit",
                            dict(
                                id=p.get("id"),
                                record_id=edit["id"],
                                field=edit["field"],
                                value=edit["value"],
                            ),
                        )
                    else:
                        self.edit(method.split(".")[0], "edit", edit)
                    if index % 100 == 0:
                        progress("Applying pasted cells: " + str(index + 1))

            self.mutate(apply_cells)
            return dict(ok=True)
        if method in ("project.undo", "project.redo"):
            src, dst = (
                (self.history, self.future)
                if method == "project.undo"
                else (self.future, self.history)
            )
            if src:
                dst.append(self.snapshot())
                self.restore(src.pop())
            return dict(ok=True)
        if method == "project.settings.edit":

            def update_settings():
                settings = self.db.get_project_settings()
                changes = p.get("settings", {})
                if not isinstance(changes, dict) or any(
                    key
                    not in (
                        "project_name",
                        "project_item_code",
                        "project_resource_code",
                    )
                    for key in changes
                ):
                    raise ValueError("Invalid project setting")
                settings.update({key: text(value) for key, value in changes.items()})
                self.db.set_project_settings(settings)

            self.mutate(update_settings)
            return dict(ok=True)
        if method.startswith("project.export"):
            return self.export(p, progress)
        if method in ("measurement.copy", "measurement.record_copy"):
            self.measurement_edit(method.split(".")[1], p)
            return dict(ok=True)
        if method.startswith("measurement."):
            return self.mutate(
                lambda: self.measurement_edit(method.split(".")[1], p)
            ) or dict(ok=True)
        kind, _, operation = method.split(".")
        if operation == "add_from_library":
            return self.mutate(lambda: self.from_library(kind, p, progress))
        if p.get("source"):
            raise ValueError(
                "Attached libraries are read-only; import items to the project to edit them"
            )
        if kind == "resources" and operation in ("price_preview", "price_update"):
            return self.refresh_resource_prices(p, apply=operation == "price_update")
        if operation == "copy":
            self.edit(kind, operation, p)
            return dict(ok=True)
        if operation == "delete_preview":
            return self.delete_preview(kind, p)
        return self.mutate(lambda: self.edit(kind, operation, p)) or dict(ok=True)

    def edit(self, kind, op, p):
        db = self.db
        resource = kind == "resources"
        table = db.ResourceTable if resource else db.ScheduleTable
        category = db.ResourceCategoryTable if resource else db.ScheduleCategoryTable
        if not resource and op == "renumber":
            return self.renumber_schedule()
        if not resource and op in ("colour", "update_quantities", "update_rates"):
            ids = p.get("ids")
            if not isinstance(ids, list) or not 1 <= len(ids) <= 1000:
                raise ValueError("Select between 1 and 1000 schedule items")
            item_ids = [identity for identity in ids if not str(identity).startswith("cat:")]
            _, rows = self.selection(kind, item_ids, include_descendants=False)
            codes = [row.code for row in rows]
            if op == "colour":
                colour = p["colour"]
                if colour is not None:
                    if not re.fullmatch(r"#[0-9a-fA-F]{6}", text(colour)):
                        raise ValueError("Choose a six-digit RGB colour")
                    colour = colour.upper()
                if not db.update_item_colour(codes, colour):
                    raise ValueError("Unable to update schedule colours")
            elif op == "update_rates":
                self.owner.update_dependent_rates(db, schedules=codes)
            elif not db.update_qty(codes, text(p["rounding"])):
                raise ValueError("Unable to update schedule quantities")
            return
        if op == "copy":
            ids = p.get("ids", [])
            if not isinstance(ids, list) or len(ids) > 1000:
                raise ValueError("Invalid selection")
            records = [
                table.get_by_id(int(identity))
                for identity in ids
                if not str(identity).startswith("cat:")
            ]
            if not records:
                raise ValueError("Select one or more items")
            selected = {row.id for row in records}
            if not resource:
                for row in list(records):
                    if row.parent_id in selected:
                        records.remove(row)

                def collect(row):
                    return [db.get_item(row.code, modify_res_code=False)] + [
                        item
                        for child in row.children.order_by(table.suborder)
                        for item in collect(child)
                    ]

                models = [model for row in records for model in collect(row)]
            else:
                models = [db.get_resource(row.code) for row in records]
            self.clipboard = (kind, copy.deepcopy(models))
            return
        if op == "paste":
            if not self.clipboard or self.clipboard[0] != kind:
                raise ValueError("Copy items from this editor first")
            renamed = {}
            for original in self.clipboard[1]:
                item = copy.deepcopy(original)
                base = item.code
                code = base
                counter = 1
                while (
                    table.select().where(table.code == code).exists()
                    or code in renamed.values()
                ):
                    code = base + "-copy" + (str(counter) if counter > 1 else "")
                    counter += 1
                renamed[base] = code
                item.code = code
                if not resource and item.parent in renamed:
                    item.parent = renamed[item.parent]
                method = db.insert_resource if resource else db.insert_item
                if not method(item):
                    raise ValueError("Unable to paste item")
            return
        if op == "delete_many":
            return self.delete_selection(kind, p)
        if op == "category_add":
            name = text(p["description"])
            method = (
                db.insert_resource_category_atomic
                if resource
                else db.insert_schedule_category_atomic
            )
            if method(name) is False:
                raise ValueError("Category could not be added")
            return
        if op == "rates":
            db.update_rates([r.code for r in db.ScheduleTable.select()])
            return
        identity = str(p.get("id", ""))
        if identity.startswith("cat:"):
            cat = category.get_by_id(int(identity[4:]))
            if op == "edit" and p["field"] == "description":
                method = (
                    db.update_resource_category
                    if resource
                    else db.update_schedule_category
                )
                if not method(cat.description, text(p["value"])):
                    raise ValueError("Category could not be renamed")
                return
            if op == "move":
                delta = p["delta"]
                if type(delta) is not int or delta not in (-1, 1):
                    raise ValueError("Invalid direction")
                siblings = list(category.select().order_by(category.order, category.id))
                index = siblings.index(cat)
                other = index + delta
                if 0 <= other < len(siblings):
                    target = siblings[other]
                    category.update(order=target.order).where(
                        category.id == cat.id
                    ).execute()
                    category.update(order=cat.order).where(
                        category.id == target.id
                    ).execute()
                return
            if op == "delete":
                return self.delete_selection(kind, dict(p, ids=[identity]))
            raise ValueError("Unsupported category operation")
        row = table.get_by_id(int(identity)) if identity else None
        if op == "delete":
            return self.delete_selection(kind, dict(p, ids=[identity]))
        if op in ("add", "duplicate"):
            data = p.get("data", {})
            code = text(data["code"])
            if not code or table.select().where(table.code == code).exists():
                raise ValueError("Choose a new code")
            if op == "duplicate" and row:
                item = (
                    db.get_resource(row.code)
                    if resource
                    else db.get_item(row.code, modify_res_code=False)
                )
                item.code = code
            elif resource:
                item = ResourceItemModel(
                    code,
                    text(data.get("description", "")),
                    text(data.get("unit", "")),
                    decimal(data.get("rate", "0")),
                    decimal(data.get("vat", "0")),
                    decimal(data.get("discount", "0")),
                    text(data.get("reference", "")),
                    text(data.get("category", "")),
                )
            else:
                parent = text(data.get("parent", "")) or None
                if parent and not table.select().where(table.code == parent).exists():
                    raise ValueError("Parent schedule item not found")
                item = ScheduleItemModel(
                    code,
                    text(data.get("description", "")),
                    text(data.get("unit", "")),
                    decimal(data.get("rate", "0")),
                    decimal(data.get("qty", "0")),
                    category=text(data.get("category", "")),
                    parent=parent,
                )
            method = db.insert_resource if resource else db.insert_item
            if not method(item):
                raise ValueError("Item could not be inserted")
            return
        if op == "move":
            delta = p["delta"]
            if type(delta) is not int or delta not in (-1, 1):
                raise ValueError("Invalid direction")
            if resource:
                siblings = list(
                    table.select()
                    .where(table.category == row.category)
                    .order_by(table.order, table.id)
                )
                index = siblings.index(row)
                new = index + delta
                if 0 <= new < len(siblings):
                    next(
                        db.update_resource_path(
                            row.code,
                            [
                                row.category.order,
                                siblings[new].order - (1 if delta < 0 else 0),
                            ],
                        )
                    )
            else:
                siblings = list(
                    table.select()
                    .where(
                        (table.category == row.category)
                        & (table.parent == row.parent_id)
                    )
                    .order_by(
                        table.suborder if row.parent_id else table.order, table.id
                    )
                )
                index = siblings.index(row)
                new = index + delta
                if 0 <= new < len(siblings):
                    other = siblings[new]
                    if row.parent_id:
                        table.update(suborder=other.suborder).where(
                            table.id == row.id
                        ).execute()
                        table.update(suborder=row.suborder).where(
                            table.id == other.id
                        ).execute()
                    else:
                        table.update(order=other.order).where(
                            (table.id == row.id) | (table.parent == row.id)
                        ).execute()
                        table.update(order=row.order).where(
                            (table.id == other.id) | (table.parent == other.id)
                        ).execute()
                    self.normalize_schedule_order({row.category_id})
            return
        if op != "edit":
            raise ValueError("Unknown project operation")
        field = p["field"]
        value = p["value"]
        if field == "code" and (
            not value
            or table.select()
            .where((table.code == value) & (table.id != row.id))
            .exists()
        ):
            raise ValueError("Choose an unused code")
        if field in ("rate", "vat", "discount"):
            value = Currency(decimal(value))
        elif field == "qty":
            value = round(decimal(value), 4)
        else:
            value = text(value)
        if not resource and field in ("category", "parent"):
            if field == "parent":
                parent = table.get_or_none(table.code == value) if value else None
                if value and parent is None:
                    raise ValueError("Parent not found")
                return self.relocate_schedule(row, parent, row.category_id)
            destination = category.get_or_none(category.description == value)
            if destination is None:
                if db.insert_schedule_category_atomic(value, [-1]) is False:
                    raise ValueError("Unable to create schedule category")
                destination = category.get(description=value)
            if row.category_id != destination.id:
                self.relocate_schedule(row, None, destination.id)
            return
        if field in ("category", "parent"):
            if field == "parent":
                raise ValueError("Resources do not have parents")
            item = db.get_resource(row.code)
            item.category = value or None
            result = db.update_resource(row.code, res_model=item)
        else:
            columns = (
                ["code", "description", "unit", "rate", "vat", "discount", "reference"]
                if resource
                else ["code", "description", "unit", "rate", "qty", None, "remarks"]
            )
            if field not in columns:
                raise ValueError("Field is not editable")
            result = (
                db.update_resource(
                    row.code, newvalue=value, column=columns.index(field)
                )
                if resource
                else db.update_item_schedule(row.code, value, columns.index(field))
            )
        if not result:
            raise ValueError("Update rejected by database")
        if resource and field in ("rate", "vat", "discount"):
            self.owner.update_dependent_rates(db, resources={row.code})

    def templates(self):
        rows = []
        for path in sorted(Path(misc.abs_path("meas_templates")).glob("*.py")):
            if path.stem == "__init__":
                continue
            item = measurement.MeasurementItemCustom(plugin=path.stem)
            rows.append(dict(code=path.stem, name=item.name))
        return rows

    def measurement_state(self, p):
        self.ensure_ids()
        meas = self.db.get_measurement()
        rows = []
        for identity, item in zip(self.ids, meas.items):
            heading = isinstance(item, measurement.MeasurementItemHeading)
            rows.append(
                dict(
                    id=identity,
                    description=item.remark,
                    type="Heading" if heading else item.name,
                    totals=(
                        "" if heading else ", ".join(str(v) for v in item.get_total())
                    ),
                    count=len(item.records),
                )
            )
        detail = None
        if p.get("id") in self.ids:
            index = self.ids.index(p["id"])
            item = meas.items[index]
            heading = isinstance(item, measurement.MeasurementItemHeading)
            if not heading:
                detail = dict(
                    id=p["id"],
                    description=item.remark,
                    template=item.itemtype,
                    columns=[
                        dict(
                            title=cap, field="c" + str(i), editable=t != misc.MEAS_CUST,
                            width=item.dimensions[0][i],
                            expand=bool(item.dimensions[1][i]),
                            numeric=t in (misc.MEAS_L, misc.MEAS_NO),
                        )
                        for i, (cap, t) in enumerate(
                            zip(item.captions, item.columntypes)
                        )
                    ],
                    rows=[
                        dict(
                            id=identity,
                            **{
                                "c" + str(i): str(value if value is not None else "")
                                for i, value in enumerate(
                                    record.get_model_rendered(n + 1)
                                )
                            }
                        )
                        for n, (identity, record) in enumerate(
                            zip(self.record_ids[p["id"]], item.records)
                        )
                    ],
                    links=[
                        dict(
                            code=(
                                (self.db.get_item_code(key) or "")
                                if key is not None
                                else ""
                            ),
                            missing=key is not None
                            and self.db.get_item_code(key) is None,
                            remark=remark,
                        )
                        for key, remark in zip(item.itemnos, item.item_remarks)
                    ],
                    user_data=[
                        dict(caption=cap, value=str(value), numeric=kind in (misc.MEAS_L, misc.MEAS_NO))
                        for cap, value, kind in zip(item.captions_udata, item.user_data, item.columntypes_udata)
                    ],
                    totals=[str(v) for v in item.get_total()],
                )
                # Raw editable strings preserve measurement expressions and description text.
                for row, record in zip(detail["rows"], item.records):
                    for i, t in enumerate(item.columntypes):
                        if t != misc.MEAS_CUST:
                            row["c" + str(i)] = record.data_string[i]
        return dict(
            rows=rows,
            detail=detail,
            caption=meas.caption,
            revision=self.owner.revision,
            undo=bool(self.history),
            redo=bool(self.future),
        )

    def measurement_edit(self, op, p):
        meas = self.db.get_measurement()
        self.ensure_ids()
        index = self.ids.index(p["id"]) if p.get("id") in self.ids else None
        item = meas.items[index] if index is not None else None
        if op in ("copy", "duplicate", "delete", "move"):
            ids = p.get("ids", [p.get("id")])
            if not isinstance(ids, list) or not ids or any(
                not isinstance(identity, str) or identity not in self.ids for identity in ids
            ):
                raise ValueError("Select one or more measurement items")
            selection = set(ids)
            indexes = [position for position, identity in enumerate(self.ids) if identity in selection]
            if op == "copy":
                self.clipboard = ("measurement", [copy.deepcopy(meas.items[i]) for i in indexes])
                return
            if op == "duplicate":
                pos = indexes[-1] + 1
                items = [copy.deepcopy(meas.items[i]) for i in indexes]
                for offset, new in enumerate(items):
                    meas.insert_item(pos + offset, new)
                    self.ids.insert(pos + offset, uuid4().hex)
            elif op == "delete":
                for position in reversed(indexes):
                    meas.remove_item(position)
                    self.record_ids.pop(self.ids.pop(position), None)
            else:
                delta = p["delta"]
                if type(delta) is not int or delta not in (-1, 1):
                    raise ValueError("Invalid move")
                for position in (indexes if delta < 0 else reversed(indexes)):
                    other = position + delta
                    if 0 <= other < len(self.ids) and self.ids[other] not in selection:
                        meas.items[position], meas.items[other] = meas.items[other], meas.items[position]
                        self.ids[position], self.ids[other] = self.ids[other], self.ids[position]
            self.db.set_measurement(meas)
            self.ensure_ids()
            return
        if op == "paste":
            if not self.clipboard or self.clipboard[0] != "measurement":
                raise ValueError("Copy a measurement item first")
            pos = index + 1 if index is not None else 0
            for offset, copied in enumerate(self.clipboard[1]):
                meas.insert_item(pos + offset, copy.deepcopy(copied))
                self.ids.insert(pos + offset, uuid4().hex)
        elif op == "caption":
            meas.caption = text(p["value"])
        elif op == "add":
            if p.get("template"):
                if p["template"] not in [r["code"] for r in self.templates()]:
                    raise ValueError("Unknown measurement template")
                new = measurement.MeasurementItemCustom(plugin=p["template"])
                new.remark = text(p.get("description", ""))
            else:
                new = measurement.MeasurementItemHeading(
                    [text(p.get("description", "Heading"))]
                )
            pos = index + 1 if index is not None else 0
            meas.insert_item(pos, new)
            self.ids.insert(pos, uuid4().hex)
        elif op == "edit":
            if item is None:
                raise ValueError("Select a measurement item")
            item.remark = text(p["value"])
        elif op == "link":
            slot = p["slot"]
            if (
                item is None
                or type(slot) is not int
                or not 0 <= slot < len(item.itemnos)
            ):
                raise ValueError("Invalid link slot")
            code = text(p.get("code", ""))
            key = self.db.get_item_key(code) if code else None
            if code and key is None:
                raise ValueError("Schedule code not found")
            item.itemnos[slot] = key
            item.item_remarks[slot] = text(p.get("remark", ""))
        elif op == "userdata":
            slot = p["slot"]
            if (
                item is None
                or type(slot) is not int
                or not 0 <= slot < len(item.user_data)
            ):
                raise ValueError("Invalid user-data slot")
            value = text(p["value"])
            if item.columntypes_udata[slot] in (misc.MEAS_L, misc.MEAS_NO):
                decimal(value)
            item.user_data[slot] = value
        elif op == "update_quantities":
            self.db.update_qty(rounding=p.get("rounding", "Round to .000"))
            return
        elif op.startswith("record_"):
            if not isinstance(item, measurement.MeasurementItemCustom):
                raise ValueError("Select a custom measurement item")
            ids = self.record_ids[p["id"]]
            record_index = (
                ids.index(p["record_id"]) if p.get("record_id") in ids else None
            )
            if op == "record_copy":
                if record_index is None:
                    raise ValueError("Select a record")
                self.clipboard = (
                    "records",
                    item.itemtype,
                    copy.deepcopy(item.records[record_index].data_string),
                )
                return
            if op == "record_import":
                from .importing import selected_rows

                fields = [i for i, kind in enumerate(item.columntypes) if kind != misc.MEAS_CUST]
                records = selected_rows(p, len(fields), cached=True)
                pos = record_index + 1 if record_index is not None else len(item.records)
                imported = 0
                for values in records:
                    if all(value is None for value in values):
                        continue
                    raw = [""] * len(item.columntypes)
                    for column, value in zip(fields, values):
                        if value is not None:
                            raw[column] = text(str(value))
                            if item.columntypes[column] in (misc.MEAS_L, misc.MEAS_NO):
                                decimal(raw[column])
                    item.insert_record(pos, measurement.RecordCustom(
                        raw, item.cust_funcs, item.total_func_item, item.columntypes
                    ))
                    ids.insert(pos, uuid4().hex)
                    pos += 1
                    imported += 1
                if not imported:
                    raise ValueError("No measurement records found in the selected range")
                self.db.set_measurement(meas)
                return dict(imported=imported)
            if op == "record_paste":
                if not self.clipboard or self.clipboard[:2] != (
                    "records",
                    item.itemtype,
                ):
                    raise ValueError(
                        "Copy a record from the same measurement template first"
                    )
                pos = (
                    record_index + 1 if record_index is not None else len(item.records)
                )
                item.insert_record(
                    pos,
                    measurement.RecordCustom(
                        copy.deepcopy(self.clipboard[2]),
                        item.cust_funcs,
                        item.total_func_item,
                        item.columntypes,
                    ),
                )
                ids.insert(pos, uuid4().hex)
            elif op in ("record_add", "record_duplicate"):
                values = (
                    [""] * item.model_width()
                    if op == "record_add"
                    else copy.deepcopy(item.records[record_index].data_string)
                )
                pos = (
                    record_index + 1 if record_index is not None else len(item.records)
                )
                item.insert_record(
                    pos,
                    measurement.RecordCustom(
                        values, item.cust_funcs, item.total_func_item, item.columntypes
                    ),
                )
                ids.insert(pos, uuid4().hex)
            elif op == "record_delete":
                if record_index is None:
                    raise ValueError("Select a record")
                item.remove_record(record_index)
                ids.pop(record_index)
            elif op == "record_move":
                delta = p["delta"]
                if (
                    type(delta) is not int
                    or delta not in (-1, 1)
                    or record_index is None
                ):
                    raise ValueError("Invalid move")
                other = record_index + delta
                if 0 <= other < len(ids):
                    item.records[record_index], item.records[other] = (
                        item.records[other],
                        item.records[record_index],
                    )
                    ids[record_index], ids[other] = ids[other], ids[record_index]
            elif op == "record_edit":
                field = p["field"]
                col = (
                    int(field[1:])
                    if isinstance(field, str) and field.startswith("c")
                    else -1
                )
                if (
                    record_index is None
                    or not 0 <= col < item.model_width()
                    or item.columntypes[col] == misc.MEAS_CUST
                ):
                    raise ValueError("Cell is not editable")
                value = text(p["value"])
                if value and item.columntypes[col] in (misc.MEAS_L, misc.MEAS_NO):
                    decimal(value)
                values = copy.deepcopy(item.records[record_index].data_string)
                values[col] = value
                item.records[record_index] = measurement.RecordCustom(
                    values, item.cust_funcs, item.total_func_item, item.columntypes
                )
            else:
                raise ValueError("Unknown record operation")
        else:
            raise ValueError("Unknown measurement operation")
        self.db.set_measurement(meas)
        self.ensure_ids()

    def export(self, p, progress):
        destination = Path(text(p["path"])).resolve()
        with destination.open("xb"):
            pass
        try:

            class Progress:
                def add_message(self, message):
                    progress(str(message))

                def set_fraction(self, value):
                    pass

                def pulse(self, *args, **kwargs):
                    pass

            sheet = misc.Spreadsheet()
            progress("Exporting schedule")
            self.db.export_sch_spreadsheet(sheet, p.get("break_lines", False))
            progress("Exporting resources")
            self.db.export_res_spreadsheet(sheet)
            progress("Exporting measurements")
            self.db.export_meas_spreadsheet(sheet, p.get("break_lines", False))
            progress("Exporting resource usage")
            self.db.export_res_usage_spreadsheet(sheet)
            progress("Exporting analyses")
            self.db.export_ana_spreadsheet(sheet, Progress(), [0.3, 0.9])
            sheet.save(destination)
        except Exception:
            destination.unlink()
            raise
        return dict(saved=str(destination))
