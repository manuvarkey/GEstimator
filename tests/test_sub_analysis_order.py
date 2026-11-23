from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path
from openpyxl import load_workbook
from modern.backend.mcp_operations import execute
from modern.backend.service import Service

SOURCE = "bundled:DSR2023.eproj"


class SubAnalysisImports(unittest.TestCase):
    def setUp(self):
        self.s = Service()
        self.addCleanup(self.s.close)
        self.s.mcp.access = "read-write"
        execute(self.s, "project", dict(action="new"))
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.dir = Path(directory.name)

    def categories(self):
        return [row.get("name") or row.get("code") for row in execute(self.s, "browse", dict(kind="schedule"))["data"]["items"]]

    def test_selected_item_used_by_another_selected_item_is_imported_as_schedule_item(self):
        # 19.7.1.1 (manhole) uses 6.1.1 (brick work) in its analysis.
        result = execute(self.s, "import_items", dict(source=SOURCE, kind="schedule", codes=["6.1.1", "19.7.1.1"]))["data"]
        self.assertEqual(result["code_map"]["6.1.1"], "6.1.1")
        masonry = execute(self.s, "browse", dict(kind="schedule", under="MASONRY WORK", depth=3))["data"]["items"]
        self.assertEqual([(row["code"], row["rate"]) for row in masonry], [("6.1", "0"), ("6.1.1", "7370.65")])
        dependency = self.s.db.get_item("DC23:6.1.1")
        self.assertEqual(dependency.qty, 0)
        self.assertEqual(self.s.db.get_item("6.1.1").qty, 1)
        self.assertEqual(execute(self.s, "get_items", dict(kind="schedule", codes=["19.7.1.1"]))["data"]["items"][0]["rate"], "12770.55")

    def test_sub_analysis_category_stays_last_in_view_and_export(self):
        execute(self.s, "import_items", dict(source=SOURCE, kind="schedule", codes=["19.7.1.1"]))
        execute(self.s, "import_items", dict(source=SOURCE, kind="schedule", codes=["13.1.1"]))
        execute(self.s, "upsert_items", dict(kind="category", category_kind="schedule", items=[dict(description="ELECTRICAL")]))
        self.assertEqual(self.categories()[-1], "SUB ANALYSIS")
        workbook = self.dir / "boq.xlsx"
        execute(self.s, "project", dict(action="export_xlsx", path=str(workbook)))
        headings = [row[1] for row in load_workbook(workbook)["Schedule"].iter_rows(values_only=True)
                    if row[0] is None and isinstance(row[1], str) and row[1].isupper() and row[2] is None]
        self.assertEqual(headings[-2:], ["SUB ANALYSIS", "TOTAL"])

    def test_earlier_projects_show_sub_analysis_last_when_opened(self):
        execute(self.s, "import_items", dict(source=SOURCE, kind="schedule", codes=["19.7.1.1", "13.1.1"]))
        path = self.dir / "old.eproj"
        execute(self.s, "project", dict(action="save_copy", path=str(path)))
        with closing(sqlite3.connect(path)) as db, db:  # Order as earlier versions stored it.
            db.execute("UPDATE ScheduleCategoryTable SET \"order\" = \"order\" + 1")
            db.execute("UPDATE ScheduleCategoryTable SET \"order\" = 0 WHERE description = 'SUB ANALYSIS'")
        execute(self.s, "project", dict(action="open", path=str(path), discard=True))
        self.assertEqual(self.categories()[-1], "SUB ANALYSIS")
        self.assertFalse(self.s.workspace_dirty)


if __name__ == "__main__":
    unittest.main()
