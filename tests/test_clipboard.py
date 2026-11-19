import copy
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from estimator import misc
from estimator.data.measurement import MeasurementItemCustom
from estimator.data.schedule import ScheduleDatabase, ScheduleItemModel, ResourceItemModel
from estimator.undo import Stack
from modern.backend.service import Service


class ClipboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "source.eproj"
        db = ScheduleDatabase(Stack())
        db.create_new_database(str(self.source))
        resource = ResourceItemModel("R", "Material\nDescription", "kg", Decimal("10"), category="Materials")
        db.insert_resource(resource)
        for code, parent, quantity in [("A", None, "2"), ("A.1", "A", "1")]:
            item = ScheduleItemModel(code, code + " work", "m", Decimal(quantity) * 10, Decimal("1"), category="Work", parent=parent, remarks="Schedule note", colour="#AABBCC")
            item.resources = {"R": resource}
            item.add_ana_group("Materials", code=None if code == "A" else "M")
            item.add_ana_res(["R", Decimal(quantity), "Entry note"], 0)
            item.add_ana_sum("Total")
            db.insert_item(item)
        db.close_database()
        self.original = self.source.read_bytes()
        self.a, self.b = Service(), Service()
        self.addCleanup(self.a.close)
        self.addCleanup(self.b.close)
        self.call(self.a, "project.open", path=str(self.source))
        child = self.a.db.ScheduleTable.get(code="A.1")
        self.call(self.a, "schedule.editor.edit", id=str(child.id), field="parent", value="A")
        self.call(self.b, "project.new")

    def call(self, service, method, **params):
        return service.call(method, dict(revision=service.revision, **params))

    def transfer(self, kind, **params):
        before = self.a.state()
        data = self.call(self.a, "clipboard.export", kind=kind, **params)
        self.assertEqual(self.a.state(), before)
        self.assertEqual(self.source.read_bytes(), self.original)
        return data

    def add_destination_item(self, code):
        self.call(self.b, "schedule.editor.add", data=dict(code=code, description=code, unit="m", rate="0", qty="0", category="Work"))

    def source_measurement(self):
        self.call(self.a, "measurement.add", description="Heading")
        heading = self.call(self.a, "measurement.state")["rows"][0]["id"]
        self.call(self.a, "measurement.add", id=heading, template="_1_NLBH", description="Dimensions")
        identity = self.call(self.a, "measurement.state")["rows"][1]["id"]
        self.call(self.a, "measurement.record_add", id=identity)
        record = self.call(self.a, "measurement.state", id=identity)["detail"]["rows"][0]["id"]
        self.call(self.a, "measurement.record_edit_many", id=identity, edits=[dict(id=record, field="c0", value="Row note"), dict(id=record, field="c2", value="2*3"), dict(id=record, field="c3", value="4")])
        self.call(self.a, "measurement.link", id=identity, slot=0, code="A", remark="Linked remark")
        return heading, identity, record

    def test_analysis_cross_instance_uses_destination_definitions_and_atomic_undo(self):
        source = self.call(self.a, "analysis.load", code="A")
        ids = [row["id"] for row in source["rows"]] + [source["rows"][0]["_children"][0]["id"]]
        data = self.transfer("analysis", ids=ids)
        self.call(self.b, "resources.editor.add", data=dict(code="R", description="Destination", unit="kg", rate="20", category="Materials"))
        self.add_destination_item("TARGET")
        self.call(self.b, "analysis.load", code="TARGET")
        before = self.b.state()
        state = self.call(self.b, "clipboard.paste", kind="analysis", data=data)
        self.assertEqual(state["rate"], "40.00")
        resource = state["rows"][0]["_children"][0]
        self.assertEqual((resource["description"], resource["remarks"], resource["value"]), ("Destination", "Entry note", "2"))
        self.assertNotIn(state["rows"][0]["id"], ids)
        self.call(self.b, "undo")
        self.assertEqual(self.b.state()["rows"], before["rows"])
        self.call(self.b, "redo")
        self.assertEqual(self.b.state()["rate"], "40.00")

    def test_schedule_categories_hierarchy_collisions_and_resource_paste(self):
        category = self.a.db.ScheduleCategoryTable.get(description="Work")
        child = self.a.db.ScheduleTable.get(code="A.1")
        data = self.transfer("schedule", ids=["cat:" + str(category.id), str(child.id)])
        self.assertEqual(len(json.loads(data)["items"]), 2)
        self.add_destination_item("A")
        self.call(self.b, "clipboard.paste", kind="schedule", data=data)
        copied = self.b.db.get_item("A-copy", modify_res_code=False)
        nested = self.b.db.get_item("A.1", modify_res_code=False)
        self.assertEqual((copied.colour, copied.remarks, nested.parent), ("#AABBCC", "Schedule note", "A-copy"))
        # GTK: resources from another project are qualified by its instance code.
        local = self.a.instance_code() + ".R"
        self.assertEqual(copied.resources[local].description, "Material\nDescription")
        self.assertIsNone(self.b.db.get_resource("R"))
        self.call(self.b, "project.undo")
        self.assertIsNone(self.b.db.get_item("A-copy"))
        self.assertIsNone(self.b.db.get_item("A.1"))
        resource_id = str(self.a.db.ResourceTable.get(code="R").id)
        resource_data = self.transfer("resources", ids=[resource_id])
        self.call(self.b, "clipboard.paste", kind="resources", data=resource_data)
        self.call(self.b, "clipboard.paste", kind="resources", data=resource_data)
        self.assertEqual(self.b.db.get_resource("R-copy").rate, Decimal("10"))
        # With a selected resource, GTK numbers pasted resources after it.
        first = str(self.b.db.ResourceTable.get(code="R").id)
        pasted = self.call(self.b, "clipboard.paste", kind="resources", data=resource_data, ids=[first])
        code = self.b.db.ResourceTable.get_by_id(int(pasted["selected"][0])).code
        self.assertNotIn(code, ("R", "R-copy"))
        self.assertTrue(code.startswith("MR."))
        self.call(self.a, "schedule.editor.category_add", description="Empty")
        empty = self.a.db.ScheduleCategoryTable.get(description="Empty")
        self.call(self.b, "clipboard.paste", kind="schedule", data=self.transfer("schedule", ids=["cat:" + str(empty.id)]))
        self.assertTrue(self.b.db.ScheduleCategoryTable.select().where(self.b.db.ScheduleCategoryTable.description == "Empty").exists())
        self.call(self.b, "project.undo")
        self.assertFalse(self.b.db.ScheduleCategoryTable.select().where(self.b.db.ScheduleCategoryTable.description == "Empty").exists())

    def test_measurement_links_remap_by_code_and_missing_links_do_not_reuse_ids(self):
        heading, identity, _ = self.source_measurement()
        data = self.transfer("measurement", ids=[identity, heading])
        self.add_destination_item("OTHER")
        self.add_destination_item("A")
        result = self.call(self.b, "clipboard.paste", kind="measurement", data=data)
        self.assertEqual(result["unlinked"], 0)
        state = self.call(self.b, "measurement.state")
        self.assertEqual([row["description"] for row in state["rows"]], ["Heading", "Dimensions"])
        copied = self.b.db.get_measurement().items[1]
        self.assertEqual(copied.itemnos, [self.b.db.get_item_key("A")])
        self.assertNotEqual(copied.itemnos, [self.a.db.get_item_key("A")])
        self.assertEqual(copied.item_remarks, ["Linked remark"])
        self.assertEqual(Decimal(str(copied.get_total()[0])), Decimal("24"))
        self.call(self.b, "project.undo")
        self.assertFalse(self.b.db.get_measurement().items)
        self.call(self.b, "project.new", discard=True)
        self.add_destination_item("OTHER")
        result = self.call(self.b, "clipboard.paste", kind="measurement", data=data)
        self.assertEqual(result["unlinked"], 1)
        copied = self.b.db.get_measurement().items[1]
        self.assertEqual(copied.itemnos, [None])
        self.assertEqual(copied.item_remarks, ["Linked remark"])
        self.assertEqual(copied.records[0].data_string[2], "2*3")

    def test_record_template_guard_and_untrusted_arithmetic_never_executes(self):
        _, identity, record = self.source_measurement()
        data = self.transfer("records", id=identity, record_id=record)
        self.call(self.b, "measurement.add", template="_1_NLBH", description="Target")
        target = self.call(self.b, "measurement.state")["rows"][0]["id"]
        self.call(self.b, "clipboard.paste", kind="records", data=data, id=target)
        detail = self.call(self.b, "measurement.state", id=target)["detail"]
        self.assertEqual(Decimal(detail["totals"][0]), Decimal("24"))
        self.call(self.b, "project.undo")
        self.assertFalse(self.call(self.b, "measurement.state", id=target)["detail"]["rows"])
        self.call(self.b, "measurement.add", template="_2_LLLLL", description="Different")
        other = self.call(self.b, "measurement.state")["rows"][0]["id"]
        before = self.b.state()
        with self.assertRaisesRegex(ValueError, "same measurement template"):
            self.call(self.b, "clipboard.paste", kind="records", data=data, id=other)
        self.assertEqual(self.b.state(), before)
        document = json.loads(data)
        document["items"][0]["values"][2] = "__import__('os').getcwd()"
        with patch("estimator.data.measurement.RecordCustom") as constructor, self.assertRaises(ValueError):
            self.call(self.b, "clipboard.paste", kind="records", data=json.dumps(document), id=target)
        constructor.assert_not_called()
        self.assertEqual(self.b.state(), before)

    def test_invalid_documents_are_rejected_before_any_mutation(self):
        self.call(self.a, "analysis.load", code="A")
        row = self.a.state()["rows"][0]
        data = self.transfer("analysis", ids=[row["id"]])
        original = json.loads(data)
        before = self.b.state()
        samples = ["not JSON", "cos\nsystem\n(S'bad'\ntR.", "x" * 500001]
        for update in [dict(version=2), dict(version=True), dict(kind="resources"), dict(items=[dict(type="row", row=dict(kind="Round", value="2.01", description="Bad"))])]:
            samples.append(json.dumps(dict(original, **update)))
        for sample in samples:
            with self.assertRaises(ValueError):
                self.call(self.b, "clipboard.paste", kind="analysis", data=sample)
            self.assertEqual(self.b.state(), before)
        with self.assertRaisesRegex(ValueError, "Stale"):
            self.b.call("clipboard.paste", dict(revision=-1, kind="analysis", data=data))
        with self.assertRaisesRegex(ValueError, "read-only"):
            self.call(self.b, "clipboard.paste", kind="schedule", data=data, source="library")

    def test_sub_analysis_definitions_transfer_and_conflicts_roll_back(self):
        self.call(self.a, "schedule.editor.add", data=dict(code="SUB", description="Sub-analysis", unit="m", rate="0", qty="0", category=misc.SUB_ANA_TITLE))
        state = self.call(self.a, "analysis.load", code="SUB")
        self.call(self.a, "add", kind="Group")
        group = self.a.state()["rows"][0]["id"]
        self.call(self.a, "resource.add", id=group, library=True, code="R", qty="3")
        self.call(self.a, "analysis.apply")
        self.call(self.a, "resources.editor.add", data=dict(code="SUB", description="Sub-analysis", unit="m", rate="30", category=misc.SUB_ANA_TITLE))
        state = self.call(self.a, "analysis.load", code="A")
        self.call(self.a, "edit", id=state["rows"][0]["_children"][0]["id"], field="code", value="SUB")
        self.call(self.a, "analysis.apply")
        identity = str(self.a.db.ScheduleTable.get(code="A").id)
        data = self.transfer("schedule", ids=[identity])
        self.assertEqual([item["code"] for item in json.loads(data)["dependencies"]], ["SUB"])
        self.call(self.b, "clipboard.paste", kind="schedule", data=data)
        sub = self.a.instance_code() + ".SUB"
        self.assertEqual(self.b.db.get_item(sub).category, misc.SUB_ANA_TITLE)
        self.assertIn(sub, self.b.db.get_item("A").resources)
        self.call(self.b, "project.undo")
        self.assertIsNone(self.b.db.get_item(sub))
        # Pasting into the same project reuses the existing definitions.
        same = self.call(self.a, "clipboard.paste", kind="schedule", data=data)
        pasted = self.a.db.ScheduleTable.get_by_id(int(same["selected"][0])).code
        self.assertIn("SUB", self.a.db.get_item(pasted).resources)
        self.add_destination_item(sub)
        before = self.b.state()
        with self.assertRaisesRegex(ValueError, "conflicts"):
            self.call(self.b, "clipboard.paste", kind="schedule", data=data)
        self.assertEqual(self.b.state(), before)
        self.assertIsNone(self.b.db.get_item("A"))

    def test_all_measurement_templates_retain_raw_values_userdata_and_totals(self):
        templates = self.call(self.a, "measurement.templates")
        self.assertEqual(len(templates), 8)
        for template in templates:
            expected = MeasurementItemCustom(plugin=template["code"])
            self.call(self.a, "measurement.add", template=template["code"], description=template["name"])
            identity = self.call(self.a, "measurement.state")["rows"][0]["id"]
            self.call(self.a, "measurement.record_add", id=identity)
            record = self.call(self.a, "measurement.state", id=identity)["detail"]["rows"][0]["id"]
            edits = [dict(id=record, field="c" + str(index), value="2*3" if kind in (misc.MEAS_L, misc.MEAS_NO) else "Copied note")
                     for index, kind in enumerate(expected.columntypes) if kind != misc.MEAS_CUST]
            self.call(self.a, "measurement.record_edit_many", id=identity, edits=edits)
        rows = self.call(self.a, "measurement.state")["rows"]
        data = self.transfer("measurement", ids=[row["id"] for row in rows])
        original = self.a.db.get_measurement()
        self.call(self.b, "clipboard.paste", kind="measurement", data=data)
        copied = self.b.db.get_measurement()
        self.assertEqual(copied.get_model(), original.get_model())
        self.assertEqual([item.get_total() for item in copied.items], [item.get_total() for item in original.items])

    def test_partial_insert_failure_rolls_back_rows_categories_and_history(self):
        category = self.a.db.ScheduleCategoryTable.get(description="Work")
        data = self.transfer("schedule", ids=["cat:" + str(category.id)])
        before = self.call(self.b, "schedule.editor.state")
        old_clipboard = ("resources", [])
        self.b.project_editor.clipboard = old_clipboard
        insert = self.b.project_editor.insert_schedule_item
        count = 0
        def fail_second(item, *args):
            nonlocal count
            count += 1
            if count == 2:
                raise ValueError("Injected insertion failure")
            return insert(item, *args)
        with patch.object(self.b.project_editor, "insert_schedule_item", side_effect=fail_second), self.assertRaisesRegex(ValueError, "Injected"):
            self.call(self.b, "clipboard.paste", kind="schedule", data=data)
        self.assertEqual(count, 2)
        self.assertEqual(self.call(self.b, "schedule.editor.state"), before)
        self.assertIs(self.b.project_editor.clipboard, old_clipboard)
        self.assertEqual(self.b.db.ResourceTable.select().count(), 0)

    def test_invalid_hierarchies_plugins_and_userdata_are_rejected_before_insertion(self):
        category = self.a.db.ScheduleCategoryTable.get(description="Work")
        document = json.loads(self.transfer("schedule", ids=["cat:" + str(category.id)]))
        document["items"][0]["parent"] = "A.1"
        before = self.b.state()
        with self.assertRaisesRegex(ValueError, "cycle"):
            self.call(self.b, "clipboard.paste", kind="schedule", data=json.dumps(document))
        self.assertEqual(self.b.state(), before)
        self.call(self.a, "measurement.add", template="civil_steel_table", description="Steel")
        identity = self.call(self.a, "measurement.state")["rows"][0]["id"]
        original = json.loads(self.transfer("measurement", ids=[identity]))
        for change in (dict(template="../backend/service"), dict(user_data=["8mm"] * 6 + ["__import__('os')"] * 6)):
            document = copy.deepcopy(original)
            document["items"].insert(0, dict(heading=True, description="Must not be inserted"))
            document["items"][1].update(change)
            with self.assertRaises(ValueError):
                self.call(self.b, "clipboard.paste", kind="measurement", data=json.dumps(document))
            self.assertEqual(self.b.state(), before)
            self.assertFalse(self.b.db.get_measurement().items)


class ResourceCutTests(unittest.TestCase):
    def test_cut_moves_resources_within_project_only(self):
        a, b = Service(), Service()
        self.addCleanup(a.close)
        self.addCleanup(b.close)
        call = lambda service, method, **params: service.call(method, dict(revision=service.revision, **params))
        call(a, "project.new")
        call(b, "project.new")
        for code, category in [("R1", "Materials"), ("R2", "Materials"), ("L1", "Labour"), ("L2", "Labour")]:
            call(a, "resources.editor.add", data=dict(code=code, description=code, unit="kg", rate="1", category=category))
        table = a.db.ResourceTable
        ident = lambda code: str(table.get(code=code).id)
        data = call(a, "clipboard.export", kind="resources", ids=[ident("R1")], cut=True)
        with self.assertRaisesRegex(ValueError, "project they were cut from"):
            call(b, "clipboard.paste", kind="resources", data=data, ids=[])
        result = call(a, "clipboard.paste", kind="resources", data=data, ids=[ident("L1")])
        self.assertTrue(result["moved"])
        labour = table.get(code="L1").category_id
        self.assertEqual([row.code for row in table.select().where(table.category == labour).order_by(table.order)], ["L1", "R1", "L2"])
        self.assertEqual(table.get(code="R2").order, 0)
        self.assertEqual(table.select().count(), 4)
        call(a, "project.undo")
        self.assertNotEqual(table.get(code="R1").category_id, labour)
        # A category target moves the resources to its start.
        cat = "cat:" + str(table.get(code="R2").category_id)
        data = call(a, "clipboard.export", kind="resources", ids=[ident("L2")], cut=True)
        call(a, "clipboard.paste", kind="resources", data=data, ids=[cat])
        self.assertEqual(table.get(code="L2").order, 0)
        self.assertEqual(table.get(code="L2").category_id, table.get(code="R2").category_id)
