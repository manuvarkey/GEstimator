import copy
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from estimator.data.schedule import ScheduleDatabase, ScheduleItemModel, ResourceItemModel
from estimator.undo import Stack
from modern.backend.service import Service
from modern.backend.mcp_operations import execute as mcp


def rule(kind="Weight", action="set", field="value", value="0.2", conditions=None, **extra):
    return dict(match=dict(kind=kind, conditions=conditions or []), action=action, field=field, value=value, **extra)


class AnalysisRules(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "rules.eproj"
        db = ScheduleDatabase(Stack())
        db.create_new_database(str(self.path))
        resource = ResourceItemModel("R", "Material", "kg", Decimal(10), category="Materials")
        db.insert_resource(ResourceItemModel("R2", "Replacement", "kg", Decimal(5), category="Materials"))
        for code, qty in (("A", 2), ("B", 3)):
            item = ScheduleItemModel(code, "Work " + code, "m3", qty=1, category="Work")
            item.resources = {"R": resource}
            item.add_ana_group("Materials", code="M")
            item.add_ana_res(["R", Decimal(qty), "old remark"], 0)
            item.add_ana_sum("TOTAL")
            item.add_ana_weight("OH", Decimal("0.1"))
            item.add_ana_round("Say", Decimal(2))
            item.evaluate_results()
            item.update_rate()
            db.insert_item(item)
        dependent = ScheduleItemModel("D", "Dependent", "m3", qty=1, category="Other")
        dependent.resources = {"A": ResourceItemModel("A", "Work A", "m3", Decimal(22), category="Work")}
        dependent.add_ana_group("Subanalysis")
        dependent.add_ana_res(["A", Decimal(2), ""], 0)
        dependent.add_ana_sum("TOTAL")
        dependent.evaluate_results()
        dependent.update_rate()
        db.insert_item(dependent)
        db.close_database()
        self.original = self.path.read_bytes()
        self.s = Service()
        self.s.call("project.open", dict(path=str(self.path)))
        self.ids = [str(self.s.db.get_item_key(code)) for code in ("A", "B")]

    def tearDown(self):
        self.s.close()
        self.temp.cleanup()

    def call(self, action, **params):
        return self.s.call("schedule.editor.analysis_rules." + action, dict(revision=self.s.revision, ids=self.ids, **params))

    def rates(self):
        return {row.code: row.rate for row in self.s.db.ScheduleTable.select()}

    def test_ordered_preview_apply_dependencies_and_one_project_undo(self):
        rules = [rule(conditions=[dict(field="description", operator="contains", value="oh"), dict(field="value", operator="gte", value="1/10")]),
                 rule(action="replace_text", field="description", find="OH", value="Overhead"),
                 rule("Resource", "multiply", value="2", conditions=[dict(field="code", operator="glob", value="R*")])]
        self.s.call("analysis.load", dict(code="A"))
        before, rates = copy.deepcopy(self.s.state()), self.rates()
        history = len(self.s.project_editor.history)
        preview = self.call("preview", rules=rules)
        self.assertEqual((preview["changed"], preview["affected"], preview["rule_matches"]), (2, 3, [2, 2, 2]))
        self.assertEqual(self.s.state(), before)
        self.assertEqual(self.rates(), rates)
        self.assertEqual(len(self.s.project_editor.history), history)
        result = self.call("apply", rules=rules)
        self.assertEqual(result["items"], preview["items"])
        self.assertEqual(self.rates(), dict(A=Decimal(48), B=Decimal(72), D=Decimal(96)))
        self.assertEqual(len(self.s.project_editor.history), history + 1)
        self.assertFalse(self.s.dirty)
        self.s.call("project.undo", dict(revision=self.s.revision))
        self.assertEqual(self.rates(), rates)
        self.s.call("project.redo", dict(revision=self.s.revision))
        self.assertEqual(self.rates()["A"], Decimal(48))
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_category_scope_insert_replace_remove_and_resource_swap(self):
        category = self.s.db.ScheduleCategoryTable.get(description="Work")
        rules = [rule("Resource", value="R2", field="code"),
                 rule("Round", "replace", rows=[dict(kind="Round", description="Rounded", value="0")]),
                 rule("Weight", "insert_after", rows=[dict(kind="Weight", description="Extra", value="0.05")]),
                 rule("Weight", "delete", conditions=[dict(field="description", operator="equals", value="OH")]),
                 rule(action="prepend", rows=[dict(kind="Group", description="First", code="", value="")]),
                 rule(action="append", rows=[dict(kind="Subtotal", description="Last", value="")])]
        params = dict(revision=self.s.revision, ids=["cat:" + str(category.id), self.ids[0]], rules=rules)
        result = self.s.call("schedule.editor.analysis_rules.apply", params)
        self.assertEqual((result["selected"], result["changed"]), (2, 2))
        item = self.s.db.get_item("A", modify_res_code=False)
        self.assertEqual(item.ana_items[0]["description"], "First")
        self.assertEqual(item.ana_items[-1]["description"], "Last")
        self.assertEqual(item.ana_items[1]["resource_list"][0][0], "R2")
        self.assertNotIn("OH", [row["description"] for row in item.ana_items])
        self.assertEqual(self.s.db.get_resource("R").rate, Decimal(10))
        count = len(self.s.project_editor.history)
        self.assertEqual(self.call("apply", rules=[rule(conditions=[dict(field="description", operator="equals", value="Missing")])])["changed"], 0)
        self.assertEqual(len(self.s.project_editor.history), count)

    def test_invalid_batch_dirty_and_stale_guards_preserve_database(self):
        rates = self.rates()
        state = copy.deepcopy(self.s.state())
        for action in ("preview", "apply"):
            for rules in ([], [rule(), rule(value="1/0")], [rule(), rule("Resource", field="description", value="global change")], [rule("Round", value="100")], [rule("Resource", "insert_before", rows=[dict(kind="Subtotal", description="Bad", value="")])]):
                with self.assertRaises(ValueError):
                    self.call(action, rules=rules)
                self.assertEqual(self.s.state(), state)
                self.assertEqual(self.rates(), rates)
        revision = self.s.revision
        self.call("apply", rules=[rule()])
        with self.assertRaisesRegex(ValueError, "Stale"):
            self.s.call("schedule.editor.analysis_rules.apply", dict(revision=revision, ids=self.ids, rules=[rule()]))
        self.s.call("analysis.load", dict(code="A"))
        self.s.call("analysis.edit", dict(revision=self.s.revision, field="ana_remarks", value="Draft"))
        for action in ("preview", "apply"):
            with self.assertRaisesRegex(ValueError, "Unsaved analysis"):
                self.call(action, rules=[rule()])

    def test_first_last_any_conditions_and_mcp_contract(self):
        rules = [rule(action="append", rows=[dict(kind="Weight", description="OH second", value="0.1")]), rule(value="0.3")]
        rules[1]["match"].update(occurrence="last", mode="any", conditions=[dict(field="description", operator="starts_with", value="OH"), dict(field="value", operator="lt", value="0")])
        self.s.mcp.access = "read-write"
        preview = mcp(self.s, "schedule.editor.analysis_rules.preview", dict(revision=self.s.revision, ids=self.ids, rules=rules))
        self.assertEqual(preview["data"]["rule_matches"], [2, 2])
        mcp(self.s, "schedule.editor.analysis_rules.apply", dict(revision=self.s.revision, ids=self.ids, rules=rules))
        item = self.s.db.get_item("A")
        weights = [row["value"] for row in item.ana_items if row["itemtype"] == 2]
        self.assertEqual(weights, [Decimal("0.1"), Decimal("0.3")])

    def test_nested_groups_numeric_ranges_and_negative_empty_operators(self):
        nested = rule(value="0.25", conditions=[
            dict(mode="any", conditions=[dict(field="description", operator="contains", value="profit"), dict(field="description", operator="equals", value="OH")]),
            dict(field="value", operator="between", value="0.05", value2="1/5"),
            dict(field="description", operator="not_contains", value="exclude"),
        ])
        self.s.mcp.access = "read-write"
        preview = mcp(self.s, "schedule.editor.analysis_rules.preview", dict(revision=self.s.revision, ids=self.ids, rules=[nested]))
        self.assertEqual(preview["data"]["rule_matches"], [2])
        self.call("apply", rules=[nested])
        self.assertEqual(self.rates(), dict(A=Decimal(25), B=Decimal("37.5"), D=Decimal(50)))
        no_match = copy.deepcopy(nested)
        no_match["match"]["conditions"][0]["conditions"][1]["value"] = "missing"
        self.assertEqual(self.call("preview", rules=[no_match])["changed"], 0)
        empty = rule("Resource", field="remarks", value="filled", conditions=[dict(field="remarks", operator="is_empty")])
        self.assertEqual(self.call("preview", rules=[empty])["changed"], 0)
        empty["match"]["conditions"][0]["operator"] = "not_empty"
        self.assertEqual(self.call("preview", rules=[empty])["changed"], 2)
        numeric_ne = rule(conditions=[dict(field="value", operator="numeric_ne", value="0.25")])
        self.assertEqual(self.call("preview", rules=[numeric_ne])["changed"], 0)

    def test_presets_validate_without_project_and_bound_nested_conditions(self):
        service = Service()
        try:
            nested = rule(conditions=[dict(mode="any", conditions=[dict(mode="all", conditions=[dict(field="description", operator="not_equals", value="Other")])])])
            self.assertEqual(mcp(service, "analysis.rules.validate", dict(rules=[nested]))["data"], [nested])
            self.assertFalse(service.state()["project_open"])
            original = copy.deepcopy(service.state())
            too_deep = copy.deepcopy(nested)
            too_deep["match"]["conditions"][0]["conditions"][0]["conditions"] = [dict(mode="all", conditions=[])]
            bad_range = rule(conditions=[dict(field="value", operator="between", value="2", value2="1")])
            for invalid in (too_deep, bad_range):
                with self.assertRaises(ValueError):
                    service.call("analysis.rules.validate", dict(rules=[invalid]))
                self.assertEqual(service.state(), original)
        finally:
            service.close()
