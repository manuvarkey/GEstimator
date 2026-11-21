import json
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from estimator import misc
from estimator.data.measurement import MeasurementItemCustom
from estimator.data.template_loader import _load, load_template
from modern.backend.service import Service


class EditorParity(unittest.TestCase):
    def setUp(self):
        self.service = Service()
        self.addCleanup(self.service.close)
        self.service.call("project.new", {})

    def call(self, method, **params):
        return self.service.call(method, dict(revision=self.service.revision, **params))

    def add(self, code, **data):
        return self.call("schedule.editor.add", data=dict(code=code, category="Work", **data))["selected"][0]

    def measure(self, template="_1_NLBH"):
        self.call("measurement.add", template=template, description="Test measurement")
        return self.call("measurement.state")["rows"][0]["id"]

    def test_suggested_codes_and_selection_placement_follow_legacy_numbering(self):
        first = self.add("1.1")
        last = self.add("1.3")
        before = self.service.state()
        defaults = self.call("schedule.editor.defaults", ids=[last, first])
        self.assertEqual(defaults["code"], self.service.db.get_next_item_code("1.3"))
        self.assertEqual(self.service.state(), before)
        added = self.call("schedule.editor.add", ids=[first], data=dict(code="", description="Inserted"))["selected"][0]
        table = self.service.db.ScheduleTable
        self.assertEqual([row.code for row in table.select().order_by(table.order)], ["1.1", "1.2", "1.3"])
        self.assertEqual(str(table.get(code="1.2").id), added)
        category = table.get(code="1.1").category
        head = self.call("schedule.editor.defaults", ids=["cat:" + str(category.id)])
        self.call("schedule.editor.add", id="cat:" + str(category.id), data=dict(code=head["code"], category="Work"))
        self.assertEqual(table.select().order_by(table.order).first().code, head["code"])
        self.call("project.undo")
        self.assertFalse(table.select().where(table.code == head["code"]).exists())
        trailing = self.call("schedule.editor.defaults", category="Work")
        self.assertEqual(trailing["code"], self.service.db.get_next_item_code("1.3"))
        root = self.call("schedule.editor.defaults", category="New category")
        self.assertEqual(root["code"], self.service.db.get_next_item_code(str(self.service.db.ScheduleCategoryTable.select().count() + 1), nextlevel=True))

    def test_schedule_keeps_two_levels(self):
        # The schedule stores items and subitems only (order, suborder).
        self.add("1", unit="m")
        first = self.add("1.1", parent="1")
        self.add("1.3", parent="1")
        other = self.add("2")
        self.add("2.1", parent="2")
        defaults = self.call("schedule.editor.defaults", ids=[first], child=True)
        self.assertEqual((defaults["code"], defaults["parent"]), ("1.2", "1"))
        self.call("schedule.editor.add", id=first, ids=[first], data=defaults)
        table = self.service.db.ScheduleTable
        parent = table.get(code="1")
        self.assertEqual([row.code for row in table.select().where(table.parent == parent.id).order_by(table.suborder)], ["1.1", "1.2", "1.3"])
        self.assertFalse(table.select().where(table.parent.in_(table.select(table.id).where(table.parent.is_null(False)))).exists())
        with self.assertRaisesRegex(ValueError, "Subitem 1.1 cannot have subitems"):
            self.add("9", parent="1.1")
        with self.assertRaisesRegex(ValueError, "Subitem 1.1 cannot have subitems"):
            self.call("schedule.editor.defaults", parent="1.1")
        with self.assertRaisesRegex(ValueError, "Subitem 1.1 cannot have subitems"):
            self.call("schedule.editor.edit_many", edits=[dict(id=str(table.get(code="1.3").id), field="parent", value="1.1")])
        with self.assertRaisesRegex(ValueError, "Item 2 has subitems and cannot become a subitem"):
            self.call("schedule.editor.edit_many", edits=[dict(id=other, field="parent", value="1")])
        self.assertIsNone(table.get(code="2").parent)

    def test_children_duplicate_and_paste_keep_sibling_positions(self):
        parent = self.add("1", unit="m")
        self.add("2")
        defaults = self.call("schedule.editor.defaults", ids=[parent], child=True)
        self.assertEqual((defaults["code"], defaults["parent"]), ("1.1", "1"))
        first = self.call("schedule.editor.add", id=parent, data=dict(defaults, code=""))["selected"][0]
        self.call("schedule.editor.add", id=parent, data=dict(code="1.0", parent="1"))
        self.call("schedule.editor.duplicate", id=first, data=dict(code="1.2"))
        table = self.service.db.ScheduleTable
        self.assertEqual([row.code for row in table.select().where(table.parent == int(parent)).order_by(table.suborder)], ["1.0", "1.1", "1.2"])
        state = self.call("schedule.editor.state")
        self.assertEqual([row["code"] for row in state["rows"][0]["_children"][0]["_children"]], ["1.0", "1.1", "1.2"])
        wire = self.call("clipboard.export", kind="schedule", ids=[first])
        self.call("clipboard.paste", kind="schedule", data=wire, id=parent)
        # GTK: a subitem pasted on a priced (non-heading) main item follows it as a
        # main item, numbered from the selection ("2" exists, so the "_" fallback).
        self.assertEqual([row.code for row in table.select().where(table.parent.is_null()).order_by(table.order)], ["1", "_1", "2"])
        self.call("project.undo")
        self.assertFalse(table.select().where(table.code == "_1").exists())

    def test_paste_follows_gtk_selection_rules(self):
        heading = self.add("1", unit="")
        child = self.call("schedule.editor.add", id=heading, data=dict(code="1.1", parent="1", unit="m"))["selected"][0]
        other = self.add("2", unit="m")
        table = self.service.db.ScheduleTable
        wire = self.call("clipboard.export", kind="schedule", ids=[child])
        # Selected heading: the copied subitem becomes its first child.
        self.call("clipboard.paste", kind="schedule", data=wire, id=heading, ids=[heading])
        children = [row.code for row in table.select().where(table.parent == int(heading)).order_by(table.suborder)]
        # "1.1" is taken, so GTK numbering falls back to "_1".
        self.assertEqual(children, ["_1", "1.1"])
        # Selected subitem: the paste follows it as the next sibling.
        self.call("clipboard.paste", kind="schedule", data=wire, ids=[child])
        children = [row.code for row in table.select().where(table.parent == int(heading)).order_by(table.suborder)]
        self.assertEqual(children, ["_1", "1.1", "1.3"])
        # Selected main item: a copied main item follows it; no -copy suffix.
        wire = self.call("clipboard.export", kind="schedule", ids=[other])
        self.call("clipboard.paste", kind="schedule", data=wire, ids=[other])
        roots = [row.code for row in table.select().where(table.parent.is_null()).order_by(table.order)]
        self.assertEqual(roots, ["1", "2", "3"])
        # Copy takes only the selected rows, not the heading's children.
        self.assertEqual(len(json.loads(self.call("clipboard.export", kind="schedule", ids=[heading]))["items"]), 1)

    def test_resources_generate_codes_and_insert_after_or_at_category_start(self):
        first = self.call("resources.editor.add", data=dict(code="R1", category="Materials"))["selected"][0]
        self.call("resources.editor.add", data=dict(code="R3", category="Materials"))
        defaults = self.call("resources.editor.defaults", ids=[first])
        self.assertEqual(defaults["code"], self.service.db.get_new_resource_code(near_item_code="R1"))
        self.call("resources.editor.add", id=first, data=dict(code="", category="Materials"))
        table = self.service.db.ResourceTable
        self.assertEqual([row.code for row in table.select().order_by(table.order)], ["R1", defaults["code"], "R3"])
        category = table.get(code="R1").category_id
        self.call("resources.editor.add", id="cat:" + str(category), data=dict(code="FIRST"))
        self.assertEqual(table.select().order_by(table.order).first().code, "FIRST")

    def test_inserted_row_can_be_revealed_on_another_page_without_scanning_in_python(self):
        identity = None
        for index in range(105):
            identity = self.call("resources.editor.add", data=dict(code="R" + str(index), category="Materials"))["selected"][0]
        state = self.call("resources.editor.state", reveal_id=identity)
        self.assertEqual((state["offset"], state["total"]), (100, 105))
        self.assertIn(identity, [row["id"] for category in state["rows"] for row in category["_children"]])

    def test_measurement_batches_load_once_save_once_and_undo_once(self):
        identity = self.measure()
        self.call("measurement.record_add", id=identity, count=120)
        detail = self.call("measurement.state", id=identity)["detail"]
        self.assertEqual((len(detail["rows"]), detail["total_records"]), (100, 120))
        edits = [dict(id=row["id"], field=field, value=value) for row in detail["rows"] for field, value in (("c2", "2*3"), ("c3", "4"))]
        db = self.service.db
        with patch.object(db, "get_measurement", wraps=db.get_measurement) as get, patch.object(db, "set_measurement", wraps=db.set_measurement) as put:
            self.call("measurement.record_edit_many", id=identity, edits=edits)
        self.assertEqual((get.call_count, put.call_count), (1, 1))
        self.assertEqual(self.call("measurement.state", id=identity)["detail"]["totals"], ["2400"])
        self.call("project.undo")
        self.assertEqual(self.call("measurement.state", id=identity)["detail"]["totals"], ["0"])
        before = self.call("measurement.state", id=identity)
        edits[-1]["value"] = "1/0"
        with self.assertRaises(ValueError):
            self.call("measurement.record_edit_many", id=identity, edits=edits)
        self.assertEqual(self.call("measurement.state", id=identity), before)
        page = self.call("measurement.detail", id=identity, record_offset=100)
        self.assertNotIn("rows", page)
        self.assertEqual((len(page["detail"]["rows"]), page["detail"]["offset"]), (20, 100))
        with self.assertRaises(ValueError):
            self.call("measurement.record_add", id=identity, count=1001)

    def test_properties_are_atomic_normalize_constants_and_update_linked_captions(self):
        self.add("A", description="Linked work", unit="kg")
        identity = self.measure("civil_steel_table")
        state = self.call("measurement.state", id=identity)
        properties = dict(description="Edited", links=[dict(code="A", remark="Rebar")], user_data=[field["value"] for field in state["detail"]["user_data"]])
        properties["user_data"][0] = "Custom label <b>"
        properties["user_data"][6] = "2*3"
        bad = copy.deepcopy(properties)
        bad["links"][0]["code"] = "MISSING"
        with self.assertRaises(ValueError):
            self.call("measurement.properties", id=identity, **bad)
        self.assertEqual(self.call("measurement.state", id=identity), state)
        self.call("measurement.properties", id=identity, **properties)
        detail = self.call("measurement.state", id=identity)["detail"]
        self.assertEqual(detail["user_data"][6]["value"], "6.000000")
        self.assertIn("Custom label <b>", detail["columns"][10]["title"])
        self.assertEqual((detail["links"][0]["description"], detail["links"][0]["unit"]), ("Linked work", "kg"))
        self.call("project.undo")
        self.assertEqual(self.call("measurement.state", id=identity)["detail"], state["detail"])
        identity = self.measure("_2_LLLLL")
        detail = self.call("measurement.state", id=identity)["detail"]
        links = [dict(code="", remark="") for _ in detail["links"]]
        links[0] = dict(code="A", remark="Concrete")
        self.call("measurement.properties", id=identity, description="Multi", links=links, user_data=[])
        self.assertEqual(self.call("measurement.state", id=identity)["detail"]["columns"][2]["title"], "L1 · Concrete")

    def test_template_modules_are_reused_but_mutable_defaults_are_independent(self):
        before = _load.cache_info().misses
        first = MeasurementItemCustom(plugin="civil_steel_table")
        first.user_data[0] = "Changed"
        for _ in range(20):
            item = MeasurementItemCustom(plugin="civil_steel_table")
            self.assertEqual(item.user_data[0], "8mm")
        self.assertLessEqual(_load.cache_info().misses - before, 1)
        catalog = self.call("measurement.templates")
        self.assertEqual(len(catalog), 8)
        self.assertTrue(all(row["summary"] and row["note"] and row["inputs"] for row in catalog))
        with tempfile.TemporaryDirectory() as folder:
            template = Path(folder) / "custom.py"
            template.write_text("VALUE = 1\n")
            with patch("estimator.data.template_loader.misc.abs_path", return_value=str(template)):
                self.assertEqual(load_template("custom").VALUE, 1)
                template.write_text("VALUE = 2\n")
                self.assertEqual(load_template("custom").VALUE, 2)
                template.write_text("VALUE = 222\n")
                self.assertEqual(load_template("custom").VALUE, 222)

    def test_record_multi_selection_copy_move_duplicate_and_delete_are_atomic(self):
        identity = self.measure()
        self.call("measurement.record_add", id=identity, count=3)
        ids = [row["id"] for row in self.call("measurement.state", id=identity)["detail"]["rows"]]
        self.call("measurement.record_edit_many", id=identity, edits=[dict(id=key, field="c0", value=value) for key, value in zip(ids, ("A", "B", "C"))])
        def descriptions():
            return [row["c0"] for row in self.call("measurement.state", id=identity)["detail"]["rows"]]
        wire = self.call("clipboard.export", kind="records", id=identity, record_ids=[ids[2], ids[0]])
        self.call("clipboard.paste", kind="records", id=identity, record_id=ids[1], data=wire)
        self.assertEqual(descriptions(), ["A", "B", "A", "C", "C"])
        self.call("project.undo")
        self.call("measurement.record_move", id=identity, record_ids=[ids[0], ids[2]], delta=1)
        self.assertEqual(descriptions(), ["B", "A", "C"])
        self.call("project.undo")
        self.call("measurement.record_duplicate", id=identity, record_ids=[ids[0], ids[2]])
        self.assertEqual(descriptions(), ["A", "B", "C", "A", "C"])
        self.call("project.undo")
        self.call("measurement.record_delete", id=identity, record_ids=[ids[0], ids[2]])
        self.assertEqual(descriptions(), ["B"])
        self.call("project.undo")
        self.assertEqual(descriptions(), ["A", "B", "C"])

    def test_resource_category_move_preserves_identity_and_undo(self):
        first = self.call("resources.editor.add", data=dict(code="R1", rate="2", category="Materials"))["selected"][0]
        second = self.call("resources.editor.add", data=dict(code="R2", rate="3", category="Materials"))["selected"][0]
        self.call("resources.editor.category_add", description="Moved")
        before = self.call("resources.editor.state")
        self.call("resources.editor.move_to", ids=[second, first], category="Moved")
        table = self.service.db.ResourceTable
        rows = list(table.select().order_by(table.order))
        self.assertEqual([(str(row.id), row.code, row.category.description) for row in rows], [(first, "R1", "Moved"), (second, "R2", "Moved")])
        self.call("project.undo")
        self.assertEqual(self.call("resources.editor.state")["rows"], before["rows"])

    def test_library_import_uses_working_selection_and_preserves_source(self):
        source = Service()
        self.addCleanup(source.close)
        source.call("project.new", {})
        source.call("schedule.editor.add", dict(revision=source.revision, data=dict(code="LIB", description="Library work", category="Library")))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "library.eproj"
            source.call("project.save_copy", dict(path=str(path)))
            original = path.read_bytes()
            first = self.add("A")
            self.add("B")
            library = self.call("library.attach", path=str(path))[-1]["id"]
            self.call("schedule.editor.add_from_library", source=library, ids=["1"], target_ids=[first])
            rows = list(self.service.db.ScheduleTable.select().order_by(self.service.db.ScheduleTable.order))
            # GTK numbers library items from the selection ("A" is not numeric: "_1")
            # and records the library code in remarks.
            self.assertEqual([row.code for row in rows], ["A", "_1", "B"])
            self.assertEqual(self.service.db.get_item("_1").remarks.split()[-1], "LIB")
            self.assertTrue(all(row.category.description == "Work" for row in rows))
            self.assertEqual(path.read_bytes(), original)


class ReorderTests(unittest.TestCase):
    def test_project_reorder_repairs_gaps_and_undoes(self):
        service = Service()
        self.addCleanup(service.close)
        call = lambda method, **params: service.call(method, dict(revision=service.revision, **params))
        call("project.new")
        for code in ("1", "2"):
            call("schedule.editor.add", data=dict(code=code, category="Work", unit="m"))
        table = service.db.ScheduleTable
        table.update(order=7).where(table.code == "2").execute()
        call("project.reorder")
        self.assertEqual([row.order for row in table.select().order_by(table.order)], [0, 1])
        call("project.undo")
        self.assertEqual(table.get(code="2").order, 7)
