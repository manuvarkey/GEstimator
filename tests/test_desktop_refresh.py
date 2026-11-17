import tempfile
from pathlib import Path
import unittest
from modern.backend.service import Service


class DesktopRefreshTests(unittest.TestCase):
    def setUp(self):
        self.s = Service()
        self.addCleanup(self.s.close)
        self.s.call("project.new", {})
        self.call("resources.editor.add", data=dict(code="R", description="Material", unit="kg", rate="10", category="Materials"))
        for code in ("A", "B"):
            self.call("schedule.editor.add", data=dict(code=code, description=code, unit="m", category="Work"))

    def call(self, method, **params):
        return self.s.call(method, dict(revision=self.s.revision, **params))

    def flat(self, rows):
        return [row for parent in rows for row in [parent, *self.flat(parent.get("_children", []))]]

    def test_draft_navigation_is_empty_delta_and_apply_only_updates_affected_item(self):
        baseline = self.call("schedule.editor.state")
        ids = [r["id"] for r in self.flat(baseline["rows"])]
        self.call("analysis.load", code="A")
        draft = self.call("schedule.editor.state", since=baseline["view_seq"], visible_ids=ids)
        self.assertTrue(draft["delta"])
        self.assertEqual(draft["updates"], [])
        group = self.call("add", kind="Group")["rows"][0]["id"]
        self.call("resource.add", id=group, code="R", library=True, qty="3")
        self.call("analysis.apply")
        delta = self.call("schedule.editor.state", since=baseline["view_seq"], visible_ids=ids)
        self.assertTrue(delta["delta"])
        self.assertEqual([r["code"] for r in delta["updates"]], ["A"])
        self.assertEqual(delta["updates"][0]["rate"], "30")
        self.assertNotIn("_children", delta["updates"][0])
        self.assertEqual(delta["revision"], self.s.revision)

    def test_structure_undo_and_failed_edits_invalidate_correctly(self):
        baseline = self.call("schedule.editor.state")
        a = self.s.db.get_item_key("A")
        with self.assertRaises(ValueError):
            self.call("schedule.editor.edit_many", edits=[dict(id=str(a), field="description", value="Changed"), dict(id=str(a), field="rate", value="1/0")])
        self.assertEqual(self.call("schedule.editor.state", since=baseline["view_seq"], visible_ids=[str(a)])["updates"], [])
        self.call("schedule.editor.add", data=dict(code="C", category="Work"))
        self.assertNotIn("delta", self.call("schedule.editor.state", since=baseline["view_seq"], visible_ids=[str(a)]))
        now = self.call("schedule.editor.state")
        self.call("project.undo")
        self.assertNotIn("delta", self.call("schedule.editor.state", since=now["view_seq"], visible_ids=[str(a)]))

    def test_custom_resource_code_optional_and_multiple_add_is_one_draft_undo(self):
        self.call("analysis.load", code="A")
        group = self.call("add", kind="Group")["rows"][0]["id"]
        result = self.call("resource.add", id=group, code="", description="Custom", unit="kg", rate="2")
        self.assertEqual(result["rows"][0]["_children"][0]["code"], "MR.1")
        result = self.call("resource.add", id=group, description="Another", unit="kg", rate="3")
        self.assertEqual(result["rows"][0]["_children"][0]["code"], "MR.2")
        ids = [str(row.id) for row in self.s.db.ResourceTable.select()]
        before = self.s.state()
        after = self.call("analysis.resources_add", id=group, ids=ids)
        self.assertEqual(len(after["rows"][0]["_children"]), 3)
        self.call("undo")
        self.assertEqual(self.s.state()["rows"], before["rows"])

    def test_selecting_library_parent_does_not_implicitly_select_children(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Service()
            try:
                source.call("project.new", {})
                for code, parent in (("P", ""), ("C", "P")):
                    source.call("schedule.editor.add", dict(revision=source.revision, data=dict(code=code, parent=parent, category="Library")))
                path = Path(folder) / "source.eproj"
                source.call("project.save_copy", dict(path=str(path)))
            finally:
                source.close()
            library = self.call("library.attach", path=str(path))[0]["id"]
            db = self.s.project_editor.libraries[library][1]
            self.call("schedule.editor.add_from_library", source=library, ids=[str(db.get_item_key("P"))])
            self.assertIsNotNone(self.s.db.get_item_key("P"))
            self.assertIsNone(self.s.db.get_item_key("C"))
            result = self.call("schedule.editor.add_from_library", source=library, ids=[str(db.get_item_key(code)) for code in ("P", "C")])
            child = self.s.db.get_item(result["code_map"]["C"], modify_res_code=False)
            self.assertEqual(child.parent, result["code_map"]["P"])

    def test_debug_traces_include_mcp_write_access_without_tokens(self):
        from modern.backend.runtime import Runtime
        runtime = Runtime()
        self.addCleanup(runtime.close)
        token = runtime.call("mcp.configure", dict(access="read-write"))["token"]
        with self.assertLogs("gestimator.actions", level="DEBUG") as capture:
            runtime.call("mcp.read", dict(name="project", arguments=dict(action="new")))
            runtime.call("mcp.read", dict(name="get_state", arguments={}))
        output = "\n".join(capture.output)
        self.assertIn("tool=project write=True access=read-write", output)
        self.assertIn("tool=get_state write=False", output)
        self.assertIn("action.done", output)
        self.assertNotIn(token, output)
        with self.assertRaises((ValueError, TypeError)):
            runtime.call("mcp.read", dict(name=[], arguments={}), timeout=2)
        self.assertIsInstance(runtime.call("state", timeout=2), dict)

    def test_measurement_categories_create_and_move_with_their_contents(self):
        def add(description, **params):
            return self.call("measurement.add", description=description, **params)["selected"][0]

        first = add("First category", category=True)
        one = add("One", id=first, template="_1_NLBH")
        two = add("Two", id=one, template="_1_NLBH")
        second = add("Second category", id=one, category=True)
        three = add("Three", id=second, template="_1_NLBH")
        before = self.call("measurement.state")["rows"]
        self.assertEqual([row["id"] for row in before], [first, one, two, second, three])
        self.call("measurement.move", id=first, ids=[first, one, two], category=True, delta=1)
        self.assertEqual([row["id"] for row in self.call("measurement.state")["rows"]], [second, three, first, one, two])
        self.call("project.undo")
        self.assertEqual(self.call("measurement.state")["rows"], before)

    def test_desktop_ranked_search_expands_terms_and_preserves_partial_codes(self):
        self.call("schedule.editor.add", data=dict(code="C.10", description="Polyvinyl chloride conduit", unit="m", category="Electrical"))
        self.call("schedule.editor.add", data=dict(code="C.100", description="Other conduit", unit="m", category="Electrical"))
        found = self.call("schedule.editor.state", query="PVC")
        self.assertIn(found["search_engine"], ("fts5", "bm25"))
        self.assertEqual([row["code"] for row in self.flat(found["rows"]) if row["rowtype"] != "Category"], ["C.10"])
        self.assertEqual(self.call("schedule.list", query="C.10")[0]["code"], "C.10")
        self.assertEqual(self.call("schedule.list", query=".100")[0]["code"], "C.100")
        self.assertEqual(self.call("schedule.list", query="vinyl")[0]["code"], "C.10")
        self.call("resources.editor.add", data=dict(code="SW", description="Residual current circuit breaker", unit="each", category="Electrical"))
        self.assertEqual(self.call("resources.search", query="RCCB")[0]["code"], "SW")
        self.assertEqual(self.call("resources.editor.state", query="RCCB", categories=["Materials"])["total"], 0)
        self.call("resources.editor.edit", id=str(self.s.db.ResourceTable.get(code="SW").id), field="description", value="Unrelated material")
        self.assertEqual(self.call("resources.search", query="RCCB"), [])

    def test_ranked_desktop_search_paginates_beyond_first_hundred_results(self):
        from estimator.data.schedule import ResourceItemModel
        for index in range(105):
            self.s.db.insert_resource(ResourceItemModel(f"P{index}", "PVC cable", "m", 0, category="Electrical"))
        page = self.call("resources.editor.state", query="polyvinyl chloride", offset=100, limit=20)
        self.assertEqual(page["total"], 105)
        self.assertEqual(len([row for row in self.flat(page["rows"]) if row["rowtype"] != "Category"]), 5)

    def test_four_place_tax_survives_analysis_apply_save_and_reopen(self):
        from decimal import Decimal
        resource = self.s.db.ResourceTable.get(code="R")
        self.call("resources.editor.edit_many", edits=[dict(id=str(resource.id), field="rate", value="10000"), dict(id=str(resource.id), field="vat", value="1.2345")])
        self.call("analysis.load", code="A")
        group = self.call("add", kind="Group")["rows"][0]["id"]
        draft = self.call("resource.add", id=group, code="R", library=True, qty="1")
        self.assertEqual(draft["rate"], "10123.45")
        self.call("analysis.apply")
        schema = self.s.db.database.execute_sql("SELECT sql FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "tax.eproj"
            self.call("project.save_copy", path=str(path))
            self.call("project.open", path=str(path))
            self.assertEqual(self.s.db.ResourceTable.get(code="R").vat, Decimal("1.2345"))
            self.assertEqual(self.s.db.ScheduleTable.get(code="A").rate, Decimal("10123.45"))
            self.assertEqual(self.s.db.database.execute_sql("SELECT sql FROM sqlite_master WHERE type='table' ORDER BY name").fetchall(), schema)
            before = path.read_bytes()
            self.call("analysis.load", code="A")
            row = self.s.state()["rows"][0]["_children"][0]
            changed = self.call("edit", id=row["id"], field="vat", value="2.34567")
            self.assertEqual(changed["rows"][0]["_children"][0]["vat"], "2.3457")
            self.call("undo")
            self.assertEqual(self.s.state()["rows"][0]["_children"][0]["vat"], "1.2345")
            self.assertEqual(path.read_bytes(), before)

    def test_custom_resource_tax_uses_four_places(self):
        self.call("analysis.load", code="A")
        group = self.call("add", kind="Group")["rows"][0]["id"]
        draft = self.call("resource.add", id=group, code="TAX", description="Taxed resource", unit="each", rate="10000", qty="1", vat="1.23456")
        self.assertEqual(draft["rows"][0]["_children"][0]["vat"], "1.2346")
        self.assertEqual(draft["rate"], "10123.46")

    def test_four_place_tax_in_legacy_project_preserves_schema_and_source(self):
        from decimal import Decimal
        source = Path(__file__).resolve().parents[1] / "estimator/database/DSREM2022.eproj"
        original = source.read_bytes()
        self.call("project.open", path=str(source), discard=True)
        schema = self.s.db.database.execute_sql("SELECT sql FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        self.call("resources.editor.add", data=dict(code="TAX.4.TEST", description="Four-place tax", unit="each", rate="10000", vat="0.1234", category="Tax verification"))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "legacy-with-tax.eproj"
            self.call("project.save_copy", path=str(path))
            self.call("project.open", path=str(path))
            self.assertEqual(self.s.db.ResourceTable.get(code="TAX.4.TEST").vat, Decimal("0.1234"))
            self.assertEqual(self.s.db.database.execute_sql("SELECT sql FROM sqlite_master WHERE type='table' ORDER BY name").fetchall(), schema)
        self.assertEqual(source.read_bytes(), original)

    def test_tax_percent_spreadsheet_header_imports_and_exports_four_places(self):
        from decimal import Decimal
        from openpyxl import Workbook, load_workbook
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "tax-input.xlsx"
            book = Workbook()
            book.active.append(["Code", "Description", "Unit", "Rate", "Tax %", "Category"])
            book.active.append(["TX", "Taxed resource", "each", "10000", "1.2345", "Tax verification"])
            book.save(path)
            book.close()
            preview = self.call("project.import_preview", path=str(path))
            self.assertEqual(preview["mapping"]["vat"], 4)
            self.call("project.import_apply", path=str(path), kind="resources", mapping=preview["mapping"])
            self.assertEqual(self.s.db.ResourceTable.get(code="TX").vat, Decimal("1.2345"))
            exported = Path(folder) / "tax-output.xlsx"
            self.call("project.export_xlsx", path=str(exported))
            book = load_workbook(exported, data_only=True)
            try:
                rows = [row for sheet in book for row in sheet.values if row and row[0] == "TX"]
                self.assertTrue(any(Decimal(str(row[4])) == Decimal("1.2345") for row in rows if len(row) > 4 and row[4] is not None))
            finally:
                book.close()
