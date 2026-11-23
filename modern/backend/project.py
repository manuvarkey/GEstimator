"""Project editors reuse the legacy ORM, CRUD and measurement template engine."""

import copy
import re
import sqlite3
from contextlib import closing
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from peewee import fn

from estimator import misc
from estimator.data.schedule import Currency, ResourceItemModel, ScheduleItemModel

from . import libraries, library_import, measurements
from .insertion import keep_sub_analysis_last
from .numbers import decimal, tax_text
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
        rows = []
        counts = dict(items=0, mismatch=0, small=0, medium=0, large=0, missing=0)
        colours = dict(
            small=misc.MEAS_COLOR_LOCKED,
            medium=misc.MEAS_COLOR_LOCKED_L1,
            large=misc.MEAS_COLOR_LOCKED_L2,
            missing=misc.MEAS_COLOR_MISSING,
        )
        for row in self.db.ScheduleTable.select():
            if not row.unit:
                continue
            counts["items"] += 1
            model = self.db.get_item(row.code, modify_res_code=False)
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
        return dict(rows=rows, counts=counts, revision=self.owner.revision)

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

    @staticmethod
    def parent_ids(table):
        """Ids of schedule items that have subitems, in one query."""
        return {
            parent for (parent,) in table.select(table.parent).where(table.parent.is_null(False)).distinct().tuples()
        }

    def serialize_row(self, row, resource, parents=frozenset()):
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

    def state(self, kind, p):
        from .metadata import presentation

        if p.get("source") and p["source"] not in self.libraries:
            raise ValueError("Library is no longer attached")
        db = self.libraries[p["source"]][1] if p.get("source") in self.libraries else self.db
        resource = kind == "resources"
        table = db.ResourceTable if resource else db.ScheduleTable
        category = db.ResourceCategoryTable if resource else db.ScheduleCategoryTable
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
        # Tuples, not models: hydrating every schedule row dominated this request.
        summary = (
            {}
            if resource
            else dict(
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
        )
        if not p.get("source") and "since" in p and not p.get("reveal_id"):
            changed = self.changes.changed_ids(kind, p["since"], query)
            visible = p.get("visible_ids", [])
            if (
                not isinstance(visible, list)
                or len(visible) > 2000
                or any(not isinstance(value, str) for value in visible)
            ):
                raise ValueError("Invalid visible row selection")
            if changed is not None:
                ids = changed.intersection(int(value) for value in visible if value.isdecimal())
                updates = []
                parents = frozenset() if resource else self.parent_ids(table)
                for row in table.select().where(table.id.in_(ids)):
                    data = self.serialize_row(row, resource, parents)
                    data.pop("_children", None)
                    updates.append(data)
                return dict(
                    delta=True,
                    updates=updates,
                    view_seq=self.changes.sequence,
                    revision=self.owner.revision,
                    undo=bool(self.history),
                    redo=bool(self.future),
                    enrichment=presentation(db),
                    **summary,
                )
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
            from .search import desktop_codes

            ranked, search_engine = desktop_codes(self.owner, db, kind, query)
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
                listing = sorted(listing.where(table.code.in_(ranked)).tuples(), key=lambda row: ranks[row[1]])
            else:
                listing = list(listing.tuples())
            ids = [row[0] for row in listing]
            begin = ids.index(int(start)) if start is not None and int(start) in ids else (-1 if direction == 1 else 0)
            for step in range(1, len(listing) + 1):
                identity, code, description, unit = listing[(begin + direction * step) % len(listing)]
                haystack = " ".join((code or "", description or "", unit or "")).lower()
                if all(word in haystack for word in words):
                    found_id = identity
                    break
            if found_id is not None:
                p = dict(p, reveal_id=str(found_id))
                if ranks is not None:
                    offset = ranks[table.get_by_id(found_id).code] // limit * limit
                    values = list(records.where(table.code.in_(ranked[offset : offset + limit])))
                    values.sort(key=lambda row: ranks[row.code])
        if ranks is None and p.get("reveal_id"):
            revealed = table.get_or_none(table.id == int(p["reveal_id"]))
            if revealed is None:
                raise ValueError("Inserted row is no longer available")
            keys = [(category.order, revealed.category.order), (table.order, revealed.order)]
            if not resource:
                keys.append(
                    (fn.COALESCE(table.suborder, -1), revealed.suborder if revealed.suborder is not None else -1)
                )
            keys.append((table.id, revealed.id))
            earlier, equal = None, None
            for field, value in keys:
                less = field < value
                earlier = (earlier | (equal & less)) if earlier is not None else less
                equal = (equal & (field == value)) if equal is not None else field == value
            offset = records.where(earlier).count() // limit * limit
        if ranks is None:
            values = list(records.offset(offset).limit(limit))
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
            if ranks is None:
                values.sort(key=lambda r: (r.category.order, r.order, -1 if r.suborder is None else r.suborder, r.id))
        parents = frozenset() if resource else self.parent_ids(table)
        for row in values:
            cat = row.category
            if cat.id not in categories:
                group = dict(
                    id="cat:" + str(cat.id), rowtype="Category", code="", description=cat.description, _children=[]
                )
                categories[cat.id] = group
            data = self.serialize_row(row, resource, parents)
            nodes[row.id] = data
        for row in values:
            data = nodes[row.id]
            parent = nodes.get(row.parent_id) if not resource else None
            (parent["_children"] if parent else categories[row.category_id]["_children"]).append(data)
        category_order = {cat.id: cat.order for cat in category.select()}
        rows = [group for identity, group in sorted(categories.items(), key=lambda entry: category_order[entry[0]])]
        if ranks is not None:

            def rank_tree(nodes):
                ranked_nodes = []
                for node in nodes:
                    child_rank = rank_tree(node.get("_children", []))
                    ranked_nodes.append((min(ranks.get(node.get("code"), total), child_rank), node))
                ranked_nodes.sort(key=lambda pair: pair[0])
                nodes[:] = [node for _, node in ranked_nodes]
                return ranked_nodes[0][0] if ranked_nodes else total

            rank_tree(rows)
        return dict(
            **summary,
            rows=rows,
            total=total,
            offset=offset,
            **({"found_id": None if found_id is None else str(found_id)} if p.get("find") is not None else {}),
            undo=bool(self.history),
            redo=bool(self.future),
            revision=self.owner.revision,
            view_seq=self.changes.sequence if not p.get("source") else 0,
            enrichment=presentation(db),
            search_engine=search_engine,
            categories=[r.description or "" for r in category.select().order_by(category.order)],
        )

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
        offset = params.get("offset", 0)
        if type(offset) is not int or offset < 0:
            raise ValueError("Invalid resource usage page")
        words = text(params.get("query", "")).casefold().split()
        rows = []
        for category, items in self.db.get_res_usage().items():
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

    def resource_dependents(self, params):
        code = text(params["code"])
        offset = params.get("offset", 0)
        if type(offset) is not int or offset < 0:
            raise ValueError("Invalid analysis page")
        schedule = self.db.ScheduleTable
        resource = self.db.ResourceTable
        entry = self.db.ResourceItemTable
        references = {}
        edges = (
            entry.select(resource.code, schedule.code).join(resource).switch(entry).join(schedule).distinct().tuples()
        )
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
        db = self.db
        resource = kind == "resources"
        table = db.ResourceTable if resource else db.ScheduleTable
        category = db.ResourceCategoryTable if resource else db.ScheduleCategoryTable
        if resource and op == "move_to":
            _, records = self.selection(kind, p.get("ids"), include_descendants=False)
            destination = category.get_or_none(category.description == text(p.get("category", "")))
            if not records or destination is None:
                raise ValueError("Select resources and an existing destination category")
            records.sort(key=lambda row: (row.category.order, row.order, row.id))
            previous = {row.category_id for row in records}
            table.update(category=destination.id).where(table.id.in_([row.id for row in records])).execute()
            from .insertion import place

            place(self, kind, [row.code for row in records], dict(id="cat:" + str(destination.id)))
            for category_id in previous - {destination.id}:
                for order, row in enumerate(
                    table.select().where(table.category == category_id).order_by(table.order, table.id)
                ):
                    table.update(order=order).where(table.id == row.id).execute()
            return dict(selected=[str(row.id) for row in records])
        if resource and op == "renumber":
            return self.renumber_resources(p.get("exclude", []))
        if resource and op == "sync_schedule":
            _, rows = self.selection(kind, p.get("ids"), include_descendants=False)
            if not rows:
                raise ValueError("Select resources to synchronize")
            changed = set()
            for row in rows:
                schedule = db.ScheduleTable.get_or_none(db.ScheduleTable.code == row.code)
                if schedule is not None and Currency(row.rate) != Currency(schedule.rate):
                    table.update(rate=Currency(schedule.rate)).where(table.id == row.id).execute()
                    changed.add(row.code)
            if changed:
                self.owner.update_dependent_rates(db, resources=changed)
            return
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
            records = [table.get_by_id(int(identity)) for identity in ids if not str(identity).startswith("cat:")]
            if not records:
                raise ValueError("Select one or more items")
            if not resource:
                # GTK copies exactly the selected rows; a subitem keeps its parent
                # code so paste can place it under the selected heading.
                from .clipboard import order as tree_order

                records.sort(key=tree_order)
                models = [db.get_item(row.code, modify_res_code=False) for row in records]
            else:
                models = [db.get_resource(row.code) for row in records]
            self.clipboard = (kind, copy.deepcopy(models))
            return
        if op == "paste":
            if not self.clipboard or self.clipboard[0] != kind:
                raise ValueError("Copy items from this editor first")
            items = copy.deepcopy(self.clipboard[1])
            local = p.get("_local_res_code")
            if local is not None and not (isinstance(local, str) and re.fullmatch(r"[0-9A-F]{1,16}", local)):
                raise ValueError("Invalid clipboard instance code")
            if resource:
                return self.paste_resources(items, p)
            return self.paste_schedule(items, p, local)
        if op == "delete_many":
            return self.delete_selection(kind, p)
        if op == "category_add":
            name = text(p["description"])
            method = db.insert_resource_category_atomic if resource else db.insert_schedule_category_atomic
            if method(name) is False:
                raise ValueError("Category could not be added")
            return
        if op == "rates":
            from .rates import recalculate_rates

            recalculate_rates(db, [r.code for r in db.ScheduleTable.select()])
            return
        identity = str(p.get("id", ""))
        if identity.startswith("cat:") and op != "add":
            cat = category.get_by_id(int(identity[4:]))
            if op == "edit" and p["field"] == "description":
                method = db.update_resource_category if resource else db.update_schedule_category
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
                    category.update(order=target.order).where(category.id == cat.id).execute()
                    category.update(order=cat.order).where(category.id == target.id).execute()
                return
            if op == "delete":
                return self.delete_selection(kind, dict(p, ids=[identity]))
            raise ValueError("Unsupported category operation")
        row = table.get_by_id(int(identity)) if identity and not identity.startswith("cat:") else None
        if op == "delete":
            return self.delete_selection(kind, dict(p, ids=[identity]))
        if op in ("add", "duplicate"):
            from .insertion import defaults, place, prepare

            data = p.get("data", {})
            code = (
                text(data.get("code", ""))
                or defaults(self, kind, dict(p, category=data.get("category"), parent=data.get("parent")))["code"]
            )
            if not code or table.select().where(table.code == code).exists():
                raise ValueError("Choose a new code")
            if op == "duplicate" and row:
                item = db.get_resource(row.code) if resource else db.get_item(row.code, modify_res_code=False)
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
            method = db.insert_resource if resource else self.insert_schedule_item
            prepare(self, kind, item, p)
            if not method(item):
                raise ValueError("Item could not be inserted")
            place(self, kind, [item.code], p)
            return dict(selected=[str(table.get(code=item.code).id)])
        if op == "move":
            delta = p["delta"]
            if type(delta) is not int or delta not in (-1, 1):
                raise ValueError("Invalid direction")
            if resource:
                siblings = list(table.select().where(table.category == row.category).order_by(table.order, table.id))
                index = siblings.index(row)
                new = index + delta
                if 0 <= new < len(siblings):
                    next(
                        db.update_resource_path(
                            row.code, [row.category.order, siblings[new].order - (1 if delta < 0 else 0)]
                        )
                    )
            else:
                siblings = list(
                    table.select()
                    .where((table.category == row.category) & (table.parent == row.parent_id))
                    .order_by(table.suborder if row.parent_id else table.order, table.id)
                )
                index = siblings.index(row)
                new = index + delta
                if 0 <= new < len(siblings):
                    other = siblings[new]
                    if row.parent_id:
                        table.update(suborder=other.suborder).where(table.id == row.id).execute()
                        table.update(suborder=row.suborder).where(table.id == other.id).execute()
                    else:
                        table.update(order=other.order).where((table.id == row.id) | (table.parent == row.id)).execute()
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
            not value or table.select().where((table.code == value) & (table.id != row.id)).exists()
        ):
            raise ValueError("Choose an unused code")
        if field in ("rate", "vat", "discount"):
            value = Currency(decimal(value), 4 if field == "vat" else 2)
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
                db.update_resource(row.code, newvalue=value, column=columns.index(field))
                if resource
                else db.update_item_schedule(row.code, value, columns.index(field))
            )
        if not result:
            raise ValueError("Update rejected by database")
        if resource and field in ("rate", "vat", "discount"):
            self.owner.update_dependent_rates(db, resources={row.code})

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
