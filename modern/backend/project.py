"""Project editors reuse the legacy ORM, CRUD and measurement template engine."""

import copy
import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import uuid4

from estimator import misc
from estimator.data.schedule import ScheduleItemModel

from . import libraries, library_import, measurements, project_edits, project_reports, project_tables
from .insertion import keep_sub_analysis_last
from .persistence import export_output
from .validation import text


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
        self._compound = False
        self.measurement_draft = None
        self.ensure_ids()
        if self.db is not None:
            from .editor_changes import EditorChanges

            self.changes = EditorChanges(self.db)

    @property
    def db(self):
        return self.owner.db

    def ensure_ids(self, meas=None):
        if self.db is None and meas is None:
            return
        items = (meas if meas is not None else self.get_measurement()).items
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

    def get_measurement(self):
        meas = self.db.get_measurement()
        draft = self.measurement_draft
        if draft and draft.identity in self.ids:
            meas.items[self.ids.index(draft.identity)] = copy.deepcopy(draft.item)
        return meas

    def set_measurement(self, meas):
        if self.measurement_draft:
            self.measurement_draft.item = copy.deepcopy(meas.items[self.ids.index(self.measurement_draft.identity)])
        else:
            self.db.set_measurement(meas)

    def records_operation(self, method, p):
        draft = self.measurement_draft
        return bool(
            draft
            and p.get("id") == draft.identity
            and (
                method.startswith("measurement.record_")
                or method in ("measurement.edit", "measurement.properties", "measurement.link", "measurement.userdata")
                or (method.startswith("clipboard.") and p.get("kind") == "records")
            )
        )

    def records_mutate(self, action):
        return self.measurement_draft.mutate(self, action)

    def draft_command(self, method, p):
        from .measurement_draft import MeasurementDraft

        draft = self.measurement_draft
        if method == "open":
            if not draft or draft.identity != p.get("id"):
                self.owner.guard_draft(p)
                if draft:
                    self.record_ids[draft.identity] = draft.saved_ids[:]
                self.measurement_draft = MeasurementDraft(self, p.get("id"))
                self.owner.revision += 1
        elif not draft:
            if method == "close":
                return dict(ok=True)
            raise ValueError("Open measurement records first")
        elif method == "apply":
            draft.accept(self)
        elif method in ("discard", "close"):
            if method == "close" and draft.dirty:
                raise ValueError("Apply or discard unsaved measurement records first")
            self.record_ids[draft.identity] = draft.saved_ids[:]
            self.measurement_draft = None
            self.owner.revision += 1
        elif method in ("undo", "redo"):
            draft.travel(self, redo=method == "redo")
        else:
            raise ValueError("Unknown measurement draft operation")
        return dict(ok=True)

    def restore(self, snapshot):
        active_id = self.db.get_item_key(self.owner.model.code) if self.owner.loaded else None
        path, self.ids, self.record_ids = snapshot
        with closing(sqlite3.connect(path)) as src:
            src.backup(self.db.database.connection())
        path.unlink()
        self.db.stack.clear()
        self.changes.invalidate()
        self.owner.workspace_dirty = True
        self.reload_analysis(active_id)

    def reload_analysis(self, active_id=None):
        if self.owner.loaded:
            code = self.db.get_item_code(active_id) if active_id is not None else self.owner.model.code
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

    def mutate(self, action, reload=True, preserve_records=False):
        if self.measurement_draft and not preserve_records:
            if self.measurement_draft.dirty:
                raise ValueError("Apply or discard unsaved measurement records first")
            self.record_ids[self.measurement_draft.identity] = self.measurement_draft.saved_ids[:]
            self.measurement_draft = None
        if self._compound:
            active_id = self.db.get_item_key(self.owner.model.code) if self.owner.loaded else None
            result = action()
            if reload:
                self.reload_analysis(active_id)
            return result
        before = self.snapshot()
        active_row = (
            self.db.ScheduleTable.get_or_none(self.db.ScheduleTable.code == self.owner.model.code)
            if self.owner.loaded
            else None
        )
        try:
            with self.db.database.atomic():
                result = action()
                keep_sub_analysis_last(self.db)
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

    def compound(self, action, preview=False):
        """One SQL transaction and undo entry, including the service's draft state.

        Nested application adapters still perform their normal validation and
        reloads, but cannot create snapshots inside an open SQLite transaction.
        Nothing is published to history until the outer operation commits.
        """
        if self._compound:
            if preview:
                raise ValueError("Nested previews are not supported")
            return action()
        owner = self.owner
        before = self.snapshot()
        state = {
            key: copy.deepcopy(getattr(owner, key))
            for key in (
                "model",
                "loaded",
                "history",
                "future",
                "saved_signature",
                "revision",
                "workspace_dirty",
                "clipboard",
            )
        }
        clipboard = copy.deepcopy(self.clipboard)
        measurement_draft = copy.deepcopy(self.measurement_draft)

        class PreviewRollback(Exception):
            pass

        self._compound = True
        try:
            try:
                with self.db.database.atomic():
                    result = action()
                    keep_sub_analysis_last(self.db)
                    if preview:
                        raise PreviewRollback()
            except PreviewRollback:
                pass
            if preview:
                for key, value in state.items():
                    setattr(owner, key, value)
                self.ids, self.record_ids = before[1:]
                self.clipboard = clipboard
                self.measurement_draft = measurement_draft
                before[0].unlink()
            else:
                self.history.append(before)
                for snapshot in self.future:
                    snapshot[0].unlink(missing_ok=True)
                self.future.clear()
                if len(self.history) > 30:
                    self.history.pop(0)[0].unlink(missing_ok=True)
                owner.workspace_dirty = True
                owner.revision = state["revision"] + 1
            return result
        except Exception:
            for key, value in state.items():
                setattr(owner, key, value)
            self.ids, self.record_ids = before[1:]
            self.clipboard = clipboard
            self.measurement_draft = measurement_draft
            before[0].unlink(missing_ok=True)
            raise
        finally:
            self._compound = False
            self.db.stack.clear()

    def insert_schedule_item(self, item, local_res_code=None):
        table = self.db.ScheduleTable
        parent = table.get(table.code == item.parent) if item.parent else None
        if parent:
            item.category = parent.category.description
        inserted = (
            self.db.insert_item(item)
            if local_res_code is None
            else self.db.insert_item_atomic(item, local_res_code=local_res_code)
        )
        if not inserted:
            return False
        if parent:
            inserted = table.get(table.code == item.code)
            self.relocate_schedule(inserted, parent, parent.category_id)
        return True

    def insert_schedule_items(self, items):
        if not items:
            return
        # Use GTK's batch insertion, retaining each model's category/parent.
        inserted, _ = self.db.insert_item_multiple_atomic(items, preserve_structure=True)
        if not {item.code for item in items}.issubset(set(inserted.values())):
            raise ValueError("Unable to import schedule items")
        table = self.db.ScheduleTable
        for item in items:
            if item.parent:
                row = table.get(table.code == item.code)
                parent = table.get(table.code == item.parent)
                self.relocate_schedule(row, parent, parent.category_id)

    def relocate_schedule(self, row, parent, category_id):
        table = self.db.ScheduleTable
        # The schedule has two levels (order, suborder): items and their subitems.
        if parent and parent.parent_id:
            raise ValueError(f"Subitem {parent.code} cannot have subitems; choose a main item as the parent")
        if parent and table.select().where(table.parent == row.id).exists():
            raise ValueError(f"Item {row.code} has subitems and cannot become a subitem")
        if parent:
            category_id = parent.category_id
        if row.category_id == category_id and row.parent_id == (parent.id if parent else None):
            return

        _, subtree = self.selection("schedule", [row.id])
        if parent and any(item.id == parent.id for item in subtree):
            raise ValueError("Schedule hierarchy cannot contain a cycle")
        new_siblings = (table.category == category_id) & (table.parent == (parent.id if parent else None))
        destination_order = table.suborder if parent else table.order
        last = table.select(destination_order).where(new_siblings).order_by(destination_order.desc()).scalar()
        next_order = 0 if last is None else last + 1
        table.update(
            category=category_id,
            parent=parent.id if parent else None,
            order=parent.order if parent else next_order,
            suborder=next_order if parent else None,
        ).where(table.id == row.id).execute()
        if row.category_id != category_id:
            descendants = [item.id for item in subtree if item.id != row.id]
            for start in range(0, len(descendants), 500):
                table.update(category=category_id).where(table.id.in_(descendants[start : start + 500])).execute()
        # Keep the legacy order field in sync with each top-level branch.
        self.normalize_schedule_order({row.category_id, category_id})

    def normalize_schedule_order(self, categories):
        table = self.db.ScheduleTable
        rows = list(
            table.select()
            .where(table.category.in_(categories))
            .order_by(table.category, table.order, table.suborder, table.id)
        )
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
                    stack.extend((child, index) for index, child in enumerate(children.get((category, item.id), [])))

    def rate_discrepancies(self):
        return project_reports.rate_discrepancies(self.db, self.owner.revision)

    def renumber_resources(self, exclude):
        if not isinstance(exclude, list) or any(not isinstance(v, str) for v in exclude):
            raise ValueError("Select library prefixes to exclude")
        table = self.db.ResourceTable
        categories = list(self.db.ResourceCategoryTable.select().order_by(self.db.ResourceCategoryTable.order))
        assigned = {}
        category_number = 1
        for category in categories:
            counter = 1
            for row in table.select().where(table.category == category.id).order_by(table.order, table.id):
                if category.description == misc.SUB_ANA_TITLE or (
                    ":" in row.code and row.code.split(":")[0] in exclude
                ):
                    assigned[row.id] = row.code
                    continue
                assigned[row.id] = (str(category_number) + "." if len(categories) > 1 else "") + str(counter).zfill(3)
                counter += 1
            if category.description != misc.SUB_ANA_TITLE:
                category_number += 1
        if len(set(assigned.values())) != len(assigned):
            raise ValueError("Generated numbers conflict with excluded resource codes")
        self.bulk_codes(table, {identity: "__renumber_" + uuid4().hex for identity in assigned})
        self.bulk_codes(table, assigned)

    def renumber_schedule(self):
        table = self.db.ScheduleTable
        category = self.db.ScheduleCategoryTable
        categories = list(
            category.select().where(category.description != misc.SUB_ANA_TITLE).order_by(category.order, category.id)
        )
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
        changes = {
            item.id: assigned[item.id] for item in items if item.id in assigned and item.code != assigned[item.id]
        }
        temporaries = {}
        for identity in changes:
            temporary = "__renumber_" + uuid4().hex
            while temporary in occupied:
                temporary = "__renumber_" + uuid4().hex
            occupied.add(temporary)
            temporaries[identity] = temporary
        self.bulk_codes(table, temporaries)
        self.bulk_codes(table, changes)

    def bulk_codes(self, table, codes):
        """One prepared UPDATE for many rows (renumbering touches every row)."""
        if codes:
            cursor = self.db.database.cursor()
            cursor.executemany(
                f'UPDATE "{table._meta.table_name}" SET "{table.code.column_name}" = ? WHERE "id" = ?',
                [(code, identity) for identity, code in codes.items()],
            )

    def state(self, kind, p):
        """Read the schedule or resource table without changing editor state."""
        return project_tables.state(self, kind, p)

    def attach_library(self, path):
        return libraries.attach(self, path)

    def attach_catalog(self):
        return libraries.attach_catalog(self)

    def sources(self):
        return libraries.sources(self)

    def library_notes(self, identity):
        return libraries.notes(self, identity)

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
                    table.update(rate=rate, vat=vat, discount=discount, reference=reference).where(
                        table.code == code
                    ).execute()
                self.owner.update_dependent_rates(self.db, resources=changes)

            self.mutate(update)
        return dict(changed=len(changes), unchanged=matched - len(changes), unmatched=len(records) - matched)

    def refresh_schedule_prices(self, params, apply):
        identity = params.get("library")
        if identity not in self.libraries:
            raise ValueError("Choose an attached database")
        _, records = self.selection("schedule", params.get("ids"))
        source = self.libraries[identity][1].ScheduleTable
        rates = {row.code: row.rate for row in source.select().where(source.code.in_([row.code for row in records]))}
        changes = {row.code: rates[row.code] for row in records if row.code in rates and row.rate != rates[row.code]}
        if apply and changes:

            def update():
                for code, rate in changes.items():
                    if not self.db.update_item_schedule(code, rate, 3):
                        raise ValueError("Unable to update database rate")

            self.mutate(update)
        return dict(changed=len(changes), unchanged=len(rates) - len(changes), unmatched=len(records) - len(rates))

    def resource_usage(self, params):
        return project_reports.resource_usage(self.db, params)

    def resource_dependents(self, params):
        return project_reports.resource_dependents(self.db, params)

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
                records.update((row.id, row) for row in table.select().where(table.category == cat.id))
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
                    for row in table.select().where(table.parent.in_(frontier[start : start + 500])):
                        if row.id not in records:
                            children[row.id] = row
                records.update(children)
                frontier = list(children)
        return list(categories.values()), list(records.values())

    def delete_preview(self, kind, p):
        categories, records = self.selection(kind, p.get("ids"))
        ids = {row.id for row in records}
        used = sorted(row.code for row in records if kind == "resources" and self.db.resource_has_dependency(row.code))
        references = 0
        if kind == "schedule":
            references = sum(key in ids for item in self.db.get_measurement().items for key in item.itemnos)
        return dict(
            items=len(records), categories=len(categories), used_resources=used, measurement_references=references
        )

    def delete_selection(self, kind, p):
        categories, records = self.selection(kind, p.get("ids"))
        resource = kind == "resources"
        policy = p.get("policy", "protect")
        if policy not in ("protect", "unused", "all"):
            raise ValueError("Invalid deletion policy")
        used = {row.id for row in records if resource and self.db.resource_has_dependency(row.code)}
        if used and policy == "protect":
            raise ValueError("Resources are used by schedule analysis; choose Delete unused or Delete including used")
        affected = set()
        if resource:
            records = [row for row in records if policy != "unused" or row.id not in used]
            for row in records:
                affected.update(reference.id_sch.code for reference in row.resourceitems)
                self.db.delete_resource_item_atomic(row.code)
        else:
            selected_ids = {row.id for row in records}
            meas = self.db.get_measurement()
            # Remove only associations: retain records/remarks, and prevent recycled SQLite
            # primary keys from silently linking these measurements to a future item.
            for item in meas.items:
                item.itemnos = [None if key in selected_ids else key for key in item.itemnos]
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
                    self.db.delete_resource_category_atomic if resource else self.db.delete_schedule_category_atomic
                )
                method(cat.description)
        if affected:
            self.owner.update_dependent_rates(self.db, schedules=affected)
        return dict(deleted=len(records))

    def from_library(self, kind, params, progress, *, review=False):
        return library_import.import_items(self, kind, params, progress, review=review)

    def call(self, method, p, progress):
        if method == "resources.editor.prefixes":
            return dict(
                prefixes=sorted({row.code.split(":")[0] for row in self.db.ResourceTable.select() if ":" in row.code})
            )
        if method == "schedule.editor.discrepancies":
            return self.rate_discrepancies()
        if method == "library.attach":
            return self.attach_library(p["path"])
        if method == "library.attach_catalog":
            return self.attach_catalog()
        if method == "library.list":
            return self.sources()
        if method == "library.notes":
            return self.library_notes(p.get("id"))
        if method == "project.import_analysis_preview":
            from .analysis_import import workbook_analyses

            return workbook_analyses(self, p)
        if method == "project.import_preview":
            from .importing import preview

            return preview(p)
        if method.endswith(".locate"):
            table = self.db.ResourceTable if method.startswith("resources.") else self.db.ScheduleTable
            row = table.get_or_none(table.code == text(p.get("code", "")))
            if row is None:
                raise ValueError("Item code not found")
            return dict(id=str(row.id))
        if method.endswith(".state") and not method.startswith("measurement."):
            return self.state(method.split(".")[0], p)
        if method in ("measurement.state", "measurement.detail"):
            return self.measurement_state(p, detail_only=method.endswith("detail"))
        if method == "measurement.templates":
            return self.templates()
        if method in ("schedule.editor.defaults", "resources.editor.defaults"):
            from .insertion import defaults

            return defaults(self, method.split(".")[0], p)
        if method == "resources.editor.usage":
            return self.resource_usage(p)
        if method == "resources.editor.dependents":
            return self.resource_dependents(p)
        if method == "measurement.record_import_preview":
            return self.record_import_preview(p)  # read-only
        if p.get("revision") != self.owner.revision and not method.startswith("project.export"):
            raise ValueError("Stale project edit; refresh the view")
        if method.startswith("measurement.draft."):
            return self.draft_command(method.rsplit(".", 1)[1], p)
        records = self.records_operation(method, p)
        self.owner.guard_draft(p, records=not records)
        mutate = self.records_mutate if records else self.mutate
        if self.measurement_draft and not records:
            # Other project mutations invalidate even a clean records snapshot.
            self.record_ids[self.measurement_draft.identity] = self.measurement_draft.saved_ids[:]
            self.measurement_draft = None
        if method == "project.enrichment.clear":
            from .metadata import clear

            def clear_enrichment():
                clear(self.db)
                self.changes.invalidate()

            self.mutate(clear_enrichment)
            return dict(ok=True)
        if method in ("schedule.editor.analysis_rules.preview", "schedule.editor.analysis_rules.apply"):
            from .analysis_rules import run

            return run(self, p, apply=method.endswith(".apply"))
        if method == "schedule.editor.library_rules_preview":
            from .analysis_rules import preview_in_copy

            return preview_in_copy(self, lambda scratch: scratch.from_library("schedule", p, progress, review=True))
        if method == "project.import_analysis_apply":
            from .analysis_import import workbook_analyses

            return self.mutate(lambda: workbook_analyses(self, p, apply=True))
        if method == "project.import_apply":
            from .importing import apply

            if p.get("dry_run"):
                # Counts for the import screen; everything is rolled back.
                return self.compound(lambda: apply(self, p, progress), preview=True)
            return self.mutate(lambda: apply(self, p, progress))
        if method in ("schedule.editor.edit_many", "resources.editor.edit_many", "measurement.record_edit_many"):
            edits = p.get("edits", [])
            if not isinstance(edits, list) or not 1 <= len(edits) <= 1000:
                raise ValueError("Paste between 1 and 1000 editable cells")
            if method == "measurement.record_edit_many":
                mutate(lambda: self.measurement_record_batch(p, edits))
                return dict(ok=True)

            def apply_cells():
                for index, edit in enumerate(edits):
                    if not isinstance(edit, dict):
                        raise ValueError("Invalid pasted cell")
                    if method.startswith("measurement."):
                        self.measurement_edit(
                            "record_edit",
                            dict(id=p.get("id"), record_id=edit["id"], field=edit["field"], value=edit["value"]),
                        )
                    else:
                        self.edit(method.split(".")[0], "edit", edit)
                    if index % 100 == 0:
                        progress("Applying pasted cells: " + str(index + 1))

            self.mutate(apply_cells)
            return dict(ok=True)
        if method in ("project.undo", "project.redo"):
            src, dst = (self.history, self.future) if method == "project.undo" else (self.future, self.history)
            if src:
                dst.append(self.snapshot())
                self.restore(src.pop())
            return dict(ok=True)
        if method == "project.reorder":
            # GTK Ctrl+Shift+R: renumber stored orders to repair insertion errors.
            self.mutate(self.db.reorder_items)
            return dict(ok=True)
        if method == "project.settings.edit":

            def update_settings():
                settings = self.db.get_project_settings()
                changes = p.get("settings", {})
                if not isinstance(changes, dict) or any(
                    key not in ("project_name", "project_item_code", "project_resource_code", "project_metadata")
                    for key in changes
                ):
                    raise ValueError("Invalid project setting")
                metadata = changes.get("project_metadata")
                if metadata is not None and (not isinstance(metadata, str) or len(metadata) > 100_000):
                    raise ValueError("Database notes must be text of at most 100,000 characters")
                settings.update(
                    {key: metadata if key == "project_metadata" else text(value) for key, value in changes.items()}
                )
                self.db.set_project_settings(settings)

            self.mutate(update_settings)
            return dict(ok=True)
        if method.startswith("project.export"):
            return self.export(p, progress)
        if method in ("measurement.copy", "measurement.record_copy"):
            self.measurement_edit(method.split(".")[1], p)
            return dict(ok=True)
        if method.startswith("measurement."):
            return mutate(lambda: self.measurement_edit(method.split(".")[1], p)) or dict(ok=True)
        kind, _, operation = method.split(".")
        if operation == "add_from_library":
            return self.mutate(lambda: self.from_library(kind, p, progress))
        if p.get("source"):
            raise ValueError("Attached libraries are read-only; import items to the project to edit them")
        if kind == "resources" and operation in ("price_preview", "price_update"):
            return self.refresh_resource_prices(p, apply=operation == "price_update")
        if kind == "schedule" and operation in ("price_preview", "price_update"):
            return self.refresh_schedule_prices(p, apply=operation == "price_update")
        if operation == "copy":
            self.edit(kind, operation, p)
            return dict(ok=True)
        if operation == "delete_preview":
            return self.delete_preview(kind, p)
        return self.mutate(lambda: self.edit(kind, operation, p)) or dict(ok=True)

    def gtk_path(self, kind, params):
        """GTK tree path of the last selected row, or None without a selection."""
        from .insertion import last_selected

        selected, is_category = last_selected(self, kind, params)
        if selected is None:
            return None
        if is_category:
            return [selected.order]
        if kind == "resources":
            return [selected.category.order, selected.order]
        if selected.parent_id:
            return [selected.category.order, selected.parent.order, selected.suborder]
        return [selected.category.order, selected.order]

    def selected_categories(self, kind, params):
        from .insertion import last_selected

        selected, is_category = last_selected(self, kind, params)
        if selected is None:
            return set()
        return {selected.id if is_category else selected.category_id}

    def paste_schedule(self, items, p, local=None):
        """GTK ScheduleView.paste_at_selection: insert after the selection,
        subitems under a selected heading, codes numbered from the position.
        Rows copied from another project get project-qualified resource codes."""
        db, table = self.db, self.db.ScheduleTable
        # GTK path insertion only touches the selected row's category.
        self.normalize_schedule_order(self.selected_categories("schedule", p))
        path = None if p.get("preserve_categories") else self.gtk_path("schedule", p)
        if path is not None:
            added, _ = db.insert_item_multiple_atomic(items, path=path, number_with_path=True, local_res_code=local)
            if len(added) - sum(len(key) == 1 for key in added) != len(items):
                raise ValueError("Unable to paste item")
            codes = [code for key, code in added.items() if len(key) > 1]
        else:
            renamed, codes = {}, []
            pending, ordered = {item.code: item for item in items}, []
            while pending:
                ready = [item for item in pending.values() if item.parent not in pending]
                if not ready:
                    raise ValueError("Copied schedule hierarchy contains a cycle")
                for item in ready:
                    ordered.append(pending.pop(item.code))
            for item in ordered:
                base = code = item.code
                counter = 1
                while table.select().where(table.code == code).exists() or code in renamed.values():
                    code = base + "-copy" + (str(counter) if counter > 1 else "")
                    counter += 1
                renamed[base] = code
                item.code = code
                if item.parent in renamed:
                    item.parent = renamed[item.parent]
                elif local is not None or not table.select().where(table.code == item.parent).exists():
                    item.parent = None
                # GTK's path-less insert only nests under headings; relocate instead.
                if not self.insert_schedule_item(item, local):
                    raise ValueError("Unable to paste item")
                codes.append(code)
        return dict(selected=[str(row.id) for row in table.select().where(table.code.in_(codes))])

    def move_resources(self, codes, p):
        """GTK ResourceView paste of a cut reference: move the resources after
        the selected resource, or to the start of a selected category."""
        from .insertion import last_selected

        db, table = self.db, self.db.ResourceTable
        target, is_category = last_selected(self, "resources", p)
        if target is None:
            raise ValueError("Select where to paste the cut resources")
        rows = [row for row in (table.get_or_none(table.code == code) for code in codes) if row is not None]
        if not rows:
            raise ValueError("The cut resources no longer exist")
        moved = {row.id for row in rows}
        if not is_category and target.id in moved:
            raise ValueError("Paste the cut resources at a different position")
        destination = target.id if is_category else target.category_id
        previous = {row.category_id for row in rows}
        siblings = [
            row
            for row in table.select().where(table.category == destination).order_by(table.order, table.id)
            if row.id not in moved
        ]
        index = 0 if is_category else next(i + 1 for i, row in enumerate(siblings) if row.id == target.id)
        siblings[index:index] = rows
        for order, row in enumerate(siblings):
            table.update(category=destination, order=order).where(table.id == row.id).execute()
        for category in previous - {destination}:
            for order, row in enumerate(
                table.select().where(table.category == category).order_by(table.order, table.id)
            ):
                if row.order != order:
                    table.update(order=order).where(table.id == row.id).execute()
        return dict(selected=[str(row.id) for row in rows])

    def paste_resources(self, items, p):
        """GTK ResourceView.add_resource_at_selection: new codes follow the
        selected resource and rows are inserted after it in its category."""
        db, table = self.db, self.db.ResourceTable
        path = None if p.get("preserve_categories") else self.gtk_path("resources", p)
        codes = []
        if path is None:
            for item in items:
                base = code = item.code
                counter = 1
                while table.select().where(table.code == code).exists():
                    code = base + "-copy" + (str(counter) if counter > 1 else "")
                    counter += 1
                item.code = code
                if not db.insert_resource_atomic(item):
                    raise ValueError("Unable to paste item")
                codes.append(code)
        else:
            near = None
            if len(path) == 2:
                selected = (
                    table.select()
                    .join(db.ResourceCategoryTable)
                    .where((db.ResourceCategoryTable.order == path[0]) & (table.order == path[1]))
                    .get()
                )
                near = None if ":" in selected.code else selected.code
            for index, item in enumerate(items):
                item.code = (
                    db.get_new_resource_code(near_item_code=near, shift=index) if near else db.get_new_resource_code()
                )
                added = db.insert_resource_atomic(item, path)
                if not added:
                    raise ValueError("Unable to paste item")
                path = added[0]
                codes.append(item.code)
        return dict(selected=[str(row.id) for row in table.select().where(table.code.in_(codes))])

    def edit(self, kind, op, p):
        """Apply a schedule or resource edit within the caller's transaction."""
        return project_edits.edit(self, kind, op, p)

    def templates(self):
        from .measurement_templates import catalog

        return catalog()

    def measurement_state(self, p, detail_only=False):
        return measurements.state(self, p, detail_only=detail_only)

    def measurement_record_batch(self, p, edits):
        return measurements.record_batch(self, p, edits)

    def record_import_preview(self, p):
        return measurements.record_import_preview(self, p)

    def measurement_edit(self, op, p):
        return measurements.edit(self, op, p)

    def export(self, p, progress):
        destination = Path(text(p["path"])).resolve()
        with export_output(destination, p.get("replace_selected") is True) as output:

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
            sheet.save(output)
        return dict(saved=str(destination))
