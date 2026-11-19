"""Compound MCP write intents; all edits reuse the application adapters."""

import copy
from decimal import Decimal

from estimator import misc
from .mcp_operations import ToolError, OPERATIONS, validate, is_preview
from .numbers import decimal


class Writes:
    def project(self, args, warnings):
        action = args["action"]
        if action == "set_settings":
            self.app("project.settings.edit", dict(settings=args.get("settings", {})))
            return self.service.call("project.settings", {})
        if action == "import_xlsx":
            if "path" not in args or "kind" not in args:
                raise ToolError("invalid_arguments", "Workbook import requires path and kind")
            params = dict(args, kind="resources" if args["kind"] == "resource" else "schedule")
            if args.get("preview", False):
                return self.app("project.import_preview", params)
            if "mapping" not in args:
                raise ToolError("invalid_arguments", "Import requires a column mapping", "mapping", hint="Call project import_xlsx with preview=true first.")
            return self.app("project.import_apply", params)
        if action in ("open", "save_copy", "export_xlsx") and not args.get("path"):
            raise ToolError("invalid_arguments", "This action requires a path", "path")
        result = self.app("project." + action, {k: v for k, v in args.items() if k not in ("action", "if_revision")})
        if action == "new":
            return dict(project_open=True, settings=self.service.call("project.settings", {}))
        return result

    def upsert_items(self, args, warnings):
        self.service.guard_draft({})
        if not args["items"]:
            raise ToolError("invalid_arguments", "Provide at least one item", "items")
        kind = args["kind"]
        if kind == "category":
            actual = args.get("category_kind", "schedule")
            prefix = "resources" if actual == "resource" else "schedule"
            table = self.service.db.ResourceCategoryTable if actual == "resource" else self.service.db.ScheduleCategoryTable
            result = []
            for item in args["items"]:
                old = table.get_or_none(table.description == item.get("code", item.get("description", "")))
                name = item.get("description", item.get("code", ""))
                if not name:
                    raise ToolError("invalid_arguments", "Category needs a description", "description")
                if old:
                    self.app(prefix + ".editor.edit", dict(id="cat:" + str(old.id), field="description", value=name))
                else:
                    self.app(prefix + ".editor.category_add", dict(description=name))
                result.append(name)
            if args.get("position"):
                self.place_categories(actual, result, args["position"])
            return dict(categories=result)
        prefix = "resources" if kind == "resource" else "schedule"
        result, inserted = [], []
        table = self.service.db.ResourceTable if kind == "resource" else self.service.db.ScheduleTable
        for item in args["items"]:
            data = {key: (value or "" if key == "parent" else value) for key, value in item.items() if key not in ("duplicate_from", "colour")}
            row = table.get_or_none(table.code == item.get("code")) if item.get("code") else None
            if "duplicate_from" in item:
                source = self.row(kind, item["duplicate_from"])
                # Empty code delegates numbering to the same application helper.
                params = dict(id=str(source.id), data=data)
                response = self.app(prefix + ".editor.duplicate", params)
                row = table.get_by_id(int(response["selected"][0]))
                inserted.append(row.code)
            elif row:
                for field, value in data.items():
                    if field == "code":
                        continue
                    self.app(prefix + ".editor.edit", dict(id=str(row.id), field=field, value=value))
                row = table.get_by_id(row.id)
            else:
                response = self.app(prefix + ".editor.add", dict(data=data))
                row = table.get_by_id(int(response["selected"][0]))
                inserted.append(row.code)
                # The legacy constructor doesn't accept schedule remarks.
                if kind == "schedule" and "remarks" in data:
                    self.app(prefix + ".editor.edit", dict(id=str(row.id), field="remarks", value=data["remarks"]))
            if "colour" in item:
                if kind != "schedule":
                    raise ToolError("invalid_arguments", "Only schedule items have colours", "colour")
                self.app("schedule.editor.colour", dict(ids=[str(row.id)], colour=item["colour"]))
            result.append(row.code)
        if inserted or args.get("position"):
            self.place_items(kind, result if args.get("position") else inserted, args.get("position", {}))
        return dict(codes=result)

    def place_categories(self, kind, names, position):
        from .mcp_workspace import natural
        table = self.service.db.ResourceCategoryTable if kind == "resource" else self.service.db.ScheduleCategoryTable
        selected = [table.get(table.description == name) for name in names]
        siblings = [r for r in table.select().order_by(table.order, table.id) if r.description not in names]
        self.insert_position(siblings, selected, position, lambda r: r.description, natural)
        for index, row in enumerate(siblings):
            table.update(order=index).where(table.id == row.id).execute()

    def insert_position(self, siblings, selected, position, code, natural):
        if "before" in position or "after" in position:
            anchor = position.get("before", position.get("after"))
            index = next((i for i, r in enumerate(siblings) if code(r) == anchor), None)
            if index is None:
                raise ToolError("invalid_position", "Placement anchor must be an unselected sibling", "position")
            index += "after" in position
            siblings[index:index] = selected
        elif "index" in position:
            index = position["index"]
            if index > len(siblings):
                raise ToolError("invalid_position", "Index is beyond the sibling list", "position.index")
            siblings[index:index] = selected
        else:
            for row in sorted(selected, key=lambda r: natural(code(r))):
                index = next((i for i, other in enumerate(siblings) if natural(code(other)) > natural(code(row))), len(siblings))
                siblings.insert(index, row)

    def place_items(self, kind, codes, position):
        from .mcp_workspace import natural
        if not codes:
            return
        if "before" in position and "after" in position:
            raise ToolError("invalid_position", "Choose before or after", "position")
        table = self.service.db.ResourceTable if kind == "resource" else self.service.db.ScheduleTable
        categories = self.service.db.ResourceCategoryTable if kind == "resource" else self.service.db.ScheduleCategoryTable
        anchor = self.row(kind, position.get("before", position.get("after"))) if "before" in position or "after" in position else None
        if anchor and ("parent" in position or "category" in position):
            raise ToolError("invalid_position", "An anchor already determines category and parent", "position")
        prefix = "resources" if kind == "resource" else "schedule"
        original = [self.row(kind, code) for code in codes]
        selected_ids = {row.id for row in original}
        def selected_ancestor(row):
            parent = row.parent if kind == "schedule" and row.parent_id else None
            seen = set()
            while parent:
                if parent.id in seen:
                    raise ToolError("invalid_position", "Hierarchy contains a cycle", "position")
                seen.add(parent.id)
                if parent.id in selected_ids:
                    return True
                parent = parent.parent if parent.parent_id else None
            return False
        original_roots = [row for row in original if not selected_ancestor(row)]
        for row in original_roots:
            parent = None
            if anchor or "parent" in position or "category" in position:
                if kind == "schedule":
                    parent = anchor.parent.code if anchor and anchor.parent_id else position.get("parent")
                    if anchor or "parent" in position:
                        self.app(prefix + ".editor.edit", dict(id=str(row.id), field="parent", value=parent or ""))
                category = anchor.category.description if anchor else position.get("category")
                if category and not (kind == "schedule" and parent):
                    self.app(prefix + ".editor.edit", dict(id=str(row.id), field="category", value=category))
                elif category and self.row(kind, parent).category.description != category:
                    raise ToolError("invalid_position", "Parent and category disagree", "position")
        selected = [self.row(kind, code) for code in codes]
        selected_ids = {r.id for r in selected}
        # A selected subtree moves as one block; don't reposition its children.
        roots = [r for r in selected if kind == "resource" or r.parent_id not in selected_ids]
        groups = {}
        for row in roots:
            groups.setdefault((row.category_id, row.parent_id if kind == "schedule" else None), []).append(row)
        for (category_id, parent_id), values in groups.items():
            condition = table.category == category_id
            ordering = table.order
            if kind == "schedule":
                condition &= table.parent == parent_id
                ordering = table.suborder if parent_id else table.order
            siblings = list(table.select().where(condition & table.id.not_in([r.id for r in values])).order_by(ordering, table.id))
            self.insert_position(siblings, values, position, lambda r: r.code, natural)
            for index, row in enumerate(siblings):
                table.update({ordering: index}).where(table.id == row.id).execute()
        if kind == "schedule":
            self.editor.normalize_schedule_order({r.category_id for r in selected})

    def move_items(self, args, warnings):
        self.service.guard_draft({})
        if args["kind"] == "category":
            self.ids("category", args["codes"], args.get("category_kind", "schedule"))
            self.place_categories(args.get("category_kind", "schedule"), args["codes"], args["position"])
        else:
            self.ids(args["kind"], args["codes"])
            self.place_items(args["kind"], args["codes"], args["position"])
        if args.get("renumber"):
            if args["kind"] != "schedule":
                raise ToolError("invalid_arguments", "Only schedule items can be renumbered", "renumber")
            self.app("schedule.editor.renumber")
        return dict(codes=args["codes"])

    def delete_items(self, args, warnings):
        kind = args.get("category_kind", "schedule") if args["kind"] == "category" else args["kind"]
        ids = self.ids(args["kind"], args["codes"], kind)
        prefix = "resources" if kind == "resource" else "schedule"
        params = dict(ids=ids, policy=args.get("policy", "protect"))
        return self.app(prefix + ".editor." + ("delete_preview" if args.get("preview") else "delete_many"), params)

    def import_items(self, args, warnings):
        self.service.guard_draft({})
        source_id, db = self.source(args["source"])
        if db is self.service.db:
            raise ToolError("invalid_arguments", "Import source must be another database", "source")
        kind = args["kind"]
        rows = [self.row(kind, code, db) for code in args["codes"]]
        if not rows:
            raise ToolError("invalid_arguments", "Select at least one code", "codes")
        prefix = "resources" if kind == "resource" else "schedule"
        params = dict(source=source_id, ids=[str(r.id) for r in rows], include_parents=args.get("include_parents", True), on_conflict=args.get("on_conflict", "rename"),
                      recalculate=kind == "schedule" and args.get("rate_mode", "recalculate") == "recalculate")
        if "settings" in args:
            from .program_settings import validate as validate_settings
            params.update(modify=True, settings=validate_settings(args["settings"]))
        data = self.app(prefix + ".editor.add_from_library", params)
        code_map = data["code_map"]
        table = self.service.db.ResourceTable if kind == "resource" else self.service.db.ScheduleTable
        codes = [table.get_by_id(int(identity)).code for identity in data["selected"]]
        changed_codes = set(codes)
        if args.get("qty") and kind != "schedule":
            raise ToolError("invalid_arguments", "Only schedule items have quantities", "qty")
        for code, qty in args.get("qty", {}).items():
            if code not in code_map:
                raise ToolError("not_found", "Quantity code was not imported", "qty", list(code_map))
            if code_map[code] not in changed_codes:
                continue
            row = self.row(kind, code_map[code])
            self.app("schedule.editor.edit", dict(id=str(row.id), field="qty", value=qty))
        if kind == "schedule":
            for original, imported in code_map.items():
                if imported not in changed_codes:
                    continue
                stored = db.get_item(original, modify_res_code=False).rate
                if args.get("rate_mode", "recalculate") == "stored":
                    # The import kept the stored rate; report what analysis would give.
                    current = self.service.db.get_item(imported, modify_res_code=False).get_ana_rate()
                else:
                    current = self.row(kind, imported).rate
                if current is not None and current != stored:
                    warnings.append(dict(code=imported, stored=str(stored), recalculated=str(current)))
        self.place_items(kind, codes, args.get("position", {}))
        return dict(imported=data["imported"], skipped=data["skipped"], parents=len(set(code_map) - set(args["codes"])), code_map=code_map)

    def history(self, args, warnings):
        return self.app("project." + args["action"])

    def batch(self, args, warnings):
        if not args["ops"]:
            raise ToolError("invalid_arguments", "Provide at least one write", "ops")
        # Validate every operation before starting, including the batch boundary.
        for index, op in enumerate(args["ops"]):
            name, params = op["tool"], op["args"]
            validate(params, OPERATIONS[name]["definition"]["inputSchema"], f"ops[{index}].args")
            if name == "project" and params.get("action") not in ("set_settings", "import_xlsx"):
                raise ToolError("invalid_batch", "File/context actions cannot be batched", f"ops[{index}].tool")
            if is_preview(name, params):
                raise ToolError("invalid_batch", "Preview operations cannot be batched", f"ops[{index}].args.preview")
            if "if_revision" in params and params["if_revision"] != self.service.revision:
                raise ToolError("stale_revision", "Batch operation has a stale revision", f"ops[{index}].args.if_revision")
        return dict(results=[dict(tool=op["tool"], data=self.call(op["tool"], op["args"], warnings)) for op in args["ops"]])

    def edit_analysis(self, args, warnings):
        from .clipboard import schedule_data
        service = self.service
        if service.records_dirty:
            raise ToolError("draft_conflict", "The desktop has unsaved measurement records. Apply or discard the records draft first.")
        if service.dirty and not args.get("discard_draft", False):
            raise ToolError("draft_conflict", "The desktop has an unsaved analysis draft", "discard_draft", hint="Apply the desktop draft or explicitly discard it.")
        previous_code = service.model.code if service.loaded else None
        previous_clipboard = copy.deepcopy(service.clipboard)
        self.app("analysis.load", dict(code=args["code"], discard=args.get("discard_draft", False)))
        refs = {}
        for i, row in enumerate(service.model.ana_items):
            refs["r" + str(i)] = row["_id"]
            for j, identity in enumerate(row.get("_resource_ids", [])):
                refs[f"r{i}:{j}"] = identity
        cursor = service.model.ana_items[-1]["_id"] if service.model.ana_items else None
        def resolve(identity):
            return refs.get(identity.lstrip("$"), identity) if identity else None
        for op in args["ops"]:
            action = op["action"]
            params = {key: value for key, value in op.items() if key not in ("action", "target", "ref")}
            if "id" in params:
                params["id"] = resolve(params["id"])
            if "ids" in params:
                params["ids"] = [resolve(identity) for identity in params["ids"]]
            old_ids = {row["_id"] for row in service.model.ana_items} | {identity for row in service.model.ana_items for identity in row.get("_resource_ids", [])}
            if action == "set_remarks":
                service.edit("analysis.edit", dict(field="ana_remarks", value=op.get("value", op.get("remarks", ""))))
            elif action == "add":
                params.setdefault("id", cursor)
                if op.get("target", "row") == "resource":
                    if params.get("source"):
                        source_id, _ = self.source(params["source"])
                        params["source"] = source_id
                    params["library"] = "rate" not in params
                    service.edit("resource.add", params)
                else:
                    service.edit("add", params)
            elif action == "edit":
                service.edit("edit", params)
            elif action == "delete":
                params.setdefault("ids", [params.get("id")])
                service.edit("delete", params)
            elif action == "duplicate":
                if op.get("target") == "resource" and "code" in op:
                    service.edit("resource.duplicate", params)
                else:
                    params.setdefault("ids", [params.get("id")])
                    selection = list(params["ids"])
                    for identity in params["ids"]:
                        row_index, resource_index = service.locate(identity)
                        if resource_index is None:
                            selection.extend(service.model.ana_items[row_index].get("_resource_ids", []))
                    params["ids"] = selection
                    service.edit("duplicate", params)
            elif action == "move":
                params["delta"] = -1 if op.get("delta") == "up" else 1
                service.edit("move", params)
            else:
                if action == "import_xlsx" and not params.get("path"):
                    raise ToolError("invalid_arguments", "Workbook import requires a path", "path")
                service.edit("analysis." + action, params)
            service.model.evaluate_results()
            new_ids = [row["_id"] for row in service.model.ana_items if row["_id"] not in old_ids]
            new_ids += [identity for row in service.model.ana_items for identity in row.get("_resource_ids", []) if identity not in old_ids]
            if new_ids:
                cursor = new_ids[-1]
                if op.get("ref"):
                    if op["ref"] in refs:
                        raise ToolError("invalid_arguments", "Analysis ref is already used", "ref")
                    refs[op["ref"]] = cursor
        self.app("analysis.apply")
        definition = schedule_data(service.model)
        data = dict(code=args["code"], rate=definition["rate"], refs={key: value for key, value in refs.items() if not key.startswith("r") or not key[1:].replace(":", "").isdigit()})
        # Return to the desktop selection with stored data. The outer transaction
        # restores the complete original draft on failure or preview.
        if previous_code and service.db.get_item_key(previous_code) is not None:
            service.model = service.db.get_item(previous_code, modify_res_code=False)
            service.loaded = True
        else:
            from estimator.data.schedule import ScheduleItemModel
            service.model = ScheduleItemModel("", "Select a schedule item")
            service.loaded = False
        service.identify()
        service.saved_signature = copy.deepcopy(service.signature())
        service.history.clear()
        service.future.clear()
        service.clipboard = previous_clipboard
        return data

    def apply_analysis_rules(self, args, warnings):
        from .analysis_rules import execute, validate as validate_rules
        validate_rules(args["rules"])
        self.service.guard_draft({})
        scope = args["scope"]
        if scope.get("all"):
            if scope.get("codes") or scope.get("categories"):
                raise ToolError("invalid_arguments", "Choose all or a selection", "scope")
            params = dict(scope="all", rules=args["rules"])
        else:
            ids = self.ids("schedule", scope["codes"]) if scope.get("codes") else []
            ids += self.ids("category", scope["categories"], "schedule") if scope.get("categories") else []
            if not ids:
                raise ToolError("invalid_arguments", "Rule scope is empty", "scope")
            params = dict(scope="selected", ids=ids, rules=args["rules"])
        result = execute(self.editor, params)
        if result["changed"]:
            self.editor.reload_analysis()
        result.pop("revision", None)
        return result

    def edit_measurements(self, args, warnings):
        self.service.guard_draft({})
        if self.editor.measurement_draft:
            self.editor.draft_command("close", {})
        refs, results = {}, []
        for op in args["ops"]:
            action = op["action"]
            identity = refs.get(op.get("id", "").lstrip("$"), op.get("id"))
            params = dict(id=identity)
            if action == "caption":
                results.append(self.app("measurement.caption", dict(value=op.get("value", ""))))
                continue
            if action == "create":
                params = dict(template=op.get("template", ""), description=op.get("description", ""))
                if op.get("after"):
                    params["id"] = refs.get(op["after"].lstrip("$"), op["after"])
                data = self.app("measurement.add", params)
                identity = data["selected"][0]
                if op.get("ref"):
                    if op["ref"] in refs:
                        raise ToolError("invalid_arguments", "Measurement ref is already used", "ref")
                    refs[op["ref"]] = identity
                params = dict(id=identity)
            if action in ("create", "update"):
                if "description" in op and action == "update":
                    self.app("measurement.edit", dict(params, value=op["description"]))
                if "links" in op or "user_data" in op:
                    detail = self.editor.measurement_state(params, detail_only=True)["detail"]
                    if not detail:
                        raise ToolError("not_found", "Select a custom measurement item", "id")
                    links = op.get("links", [dict(code=l["code"], remark=l["remark"]) for l in detail["links"]])
                    if len(links) > len(detail["links"]):
                        raise ToolError("invalid_arguments", "Too many measurement links", "links")
                    links = [dict(code=l["code"], remark=l.get("remark", "")) for l in links]
                    links += [dict(code="", remark="") for _ in range(len(detail["links"]) - len(links))]
                    self.app("measurement.properties", dict(params, description=op.get("description", detail["description"]), links=links, user_data=op.get("user_data", [p["value"] for p in detail["user_data"]])))
                records = self.add_records(identity, op.get("records", []))
                results.append(dict(id=identity, record_ids=records))
            elif action == "records_add":
                records = op.get("records", [])
                if not records:
                    raise ToolError("invalid_arguments", "Provide records to add", "records")
                results.append(dict(id=identity, record_ids=self.add_records(identity, records, op.get("record_id"))))
            elif action == "records_edit":
                self.edit_records(identity, op.get("records", []))
                results.append(dict(id=identity))
            elif action in ("delete", "move", "duplicate"):
                params["ids"] = [refs.get(v.lstrip("$"), v) for v in op.get("ids", [identity])]
                params["delta"] = -1 if op.get("delta") == "up" else 1
                self.app("measurement." + action, params)
                results.append(dict(ids=params["ids"]))
            else:
                method = dict(records_delete="record_delete", records_move="record_move", records_import="record_import")[action]
                params.update({key: value for key, value in op.items() if key not in ("action", "id", "ref")})
                params["delta"] = -1 if op.get("delta") == "up" else 1
                self.app("measurement." + method, params)
                results.append(dict(id=identity))
        return dict(results=results, refs=refs)

    def add_records(self, identity, records, after=None):
        if not records:
            return []
        data = self.app("measurement.record_add", dict(id=identity, count=len(records), record_id=after))
        ids = data["selected_records"]
        self.edit_records(identity, [dict(record, id=record_id) for record_id, record in zip(ids, records)])
        return ids

    def edit_records(self, identity, records):
        if not records:
            raise ToolError("invalid_arguments", "Provide records to edit", "records")
        detail = self.editor.measurement_state(dict(id=identity), detail_only=True)["detail"]
        if not detail:
            raise ToolError("not_found", "Measurement item was not found", "id")
        columns = detail["columns"]
        template = self.service.db.get_measurement().items[self.editor.ids.index(identity)]
        editable = [col["field"] for col in columns if col["editable"]]
        edits = []
        for record in records:
            if "id" not in record:
                raise ToolError("invalid_arguments", "Record edit requires an id", "records.id")
            for title, value in record.items():
                if title == "id":
                    continue
                matches = [col for i, col in enumerate(columns) if col["title"] == title or col["field"] == title or template.captions[i] == title]
                if len(matches) != 1:
                    raise ToolError("invalid_column", "Unknown or ambiguous column title", title, [col["title"] for col in columns if col["editable"]], "Use the exact title or cN field from get_measurements.")
                column = matches[0]
                if not column["editable"]:
                    raise ToolError("not_editable", "This measurement column is computed", column["field"], editable, column["title"] + " is computed")
                edits.append(dict(id=record["id"], field=column["field"], value=value))
        if edits:
            self.app("measurement.record_edit_many", dict(id=identity, edits=edits))

    def recalculate(self, args, warnings):
        self.service.guard_draft({})
        what, db = args["what"], self.service.db
        codes = args.get("codes")
        if what == "source_rates":
            before = {row.code: str(row.rate or 0) for row in db.ScheduleTable.select()}
            if not args.get("source"):
                raise ToolError("invalid_arguments", "Source rates require a source", "source")
            source_id, _ = self.source(args["source"])
            if source_id is None:
                raise ToolError("invalid_arguments", "Choose another database", "source")
            kind = args.get("kind", "schedule")
            table = db.ResourceTable if kind == "resource" else db.ScheduleTable
            codes = codes if codes is not None else [row.code for row in table.select()]
            if not codes:
                return dict(changed=0)
            prefix = "resources" if kind == "resource" else "schedule"
            result = self.app(prefix + ".editor.price_update", dict(library=source_id, ids=self.ids(kind, codes)))
            warnings.extend(dict(code=row.code, stored=before[row.code], recalculated=str(row.rate or 0)) for row in db.ScheduleTable.select() if str(row.rate or 0) != before[row.code])
        else:
            codes = codes if codes is not None else [row.code for row in db.ScheduleTable.select()]
            if not codes:
                return dict(changed=0)
            ids = self.ids("schedule", codes)
            before = {row.code: str(row.rate or 0) for row in db.ScheduleTable.select()}
            if what == "rates":
                self.app("schedule.editor.update_rates", dict(ids=ids))
            else:
                self.app("schedule.editor.update_quantities", dict(ids=ids, rounding=args.get("rounding", "Round to .000")))
            differences = [dict(code=row.code, stored=before[row.code], recalculated=str(row.rate or 0)) for row in db.ScheduleTable.select() if str(row.rate or 0) != before[row.code]]
            warnings.extend(differences)
            result = dict(changed=len(differences) if what == "rates" else len(codes))
        return result
