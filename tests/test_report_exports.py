"""Report preview/export parity, literal text and failure publication boundaries."""

import tempfile
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch

from openpyxl import load_workbook

from modern.backend.reporting.export_jobs import jobs
from modern.backend.reporting.pdf import find_renderer
from modern.backend.service import Service


class ReportExports(unittest.TestCase):
    """Use real Service operations and disposable report destinations."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.service = Service()
        self.addCleanup(self.service.close)
        self.service.call("project.new", {})
        self.service.call(
            "schedule.editor.add",
            dict(
                revision=self.service.revision,
                data=dict(
                    code="A",
                    description='=HYPERLINK("evil") <script>x</script>',
                    unit="m",
                    rate="7.13",
                    qty="2",
                    category="Work",
                ),
            ),
        )
        self.spec = dict(
            title="<Title>",
            organization="=1+1",
            sections=[
                dict(id="approval", kind="signoff", title="Signoff"),
                dict(id="work", kind="schedule", title="Work"),
                dict(id="totals", kind="abstract", title="Totals"),
                dict(id="hidden", kind="abstract", enabled=False),
            ],
        )

    def call(self, method, **params):
        return self.service.call(method, dict(revision=self.service.revision, specification=self.spec, **params))

    def export(self, format, path=None):
        return self.call("report.export", format=format, path=str(path or self.root / f"report.{format}"))

    def test_preview_and_html_share_sections_amounts_and_escaped_text(self):
        before = list(self.service.db.database.connection().iterdump())
        revision = self.service.revision
        preview = self.call("report.preview")
        self.export("html")
        html = (self.root / "report.html").read_text(encoding="utf-8")
        self.assertEqual(preview["html"], html)
        self.assertEqual(preview["document"]["total"], "14.26")
        self.assertIn("&lt;script&gt;x&lt;/script&gt;", html)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;Title&gt;", html)
        self.assertNotIn('id="hidden"', html)
        self.assertLess(html.index('id="approval"'), html.index('id="work"'))
        self.assertLess(html.index('id="work"'), html.index('id="totals"'))
        self.assertEqual(before, list(self.service.db.database.connection().iterdump()))
        self.assertEqual(self.service.revision, revision)

    def test_excel_recalculates_amounts_and_preserves_literal_author_text(self):
        self.export("xlsx")
        workbook = load_workbook(self.root / "report.xlsx")
        self.addCleanup(workbook.close)
        self.assertEqual(workbook.sheetnames, ["Cover", "Contents", "Section 1", "Section 2", "Section 3"])
        self.assertEqual(workbook["Cover"]["A3"].value, "=1+1")
        self.assertEqual(workbook["Cover"]["A3"].data_type, "s")
        schedule = workbook["Section 2"]
        self.assertTrue(schedule["B4"].value.startswith("=HYPERLINK"))
        self.assertEqual(schedule["B4"].data_type, "s")
        self.assertEqual(schedule["F4"].value, "=ROUND(D4*E4,2)")
        self.assertEqual(schedule["F6"].value, "=SUM(F4:F4)")
        self.assertEqual(workbook["Section 3"]["B4"].value, "=SUM('Section 2'!F4:F4)")
        self.assertEqual(workbook["Contents"]["A3"].hyperlink.target, "#'Section 2'!A1")
        self.assertEqual(schedule.print_title_rows, "$1:$3")
        self.assertEqual(schedule["D4"].value, 2)
        self.assertEqual(schedule["E4"].value, 7.13)

    def test_background_export_detaches_rendering_from_current_project(self):
        entered, release = Event(), Event()
        captured = {}

        def render(snapshot, *_):
            captured["revision"] = snapshot.revision
            captured["title"] = snapshot.specification.title
            entered.set()
            if not release.wait(5):
                raise RuntimeError("Test did not release renderer")
            return dict(saved="background.html", revision=snapshot.revision, warnings=[])

        with patch("modern.backend.reporting._render_export", side_effect=render):
            revision = self.service.revision
            token = self.call("report.export.start", format="html", path=str(self.root / "background.html"))["token"]
            try:
                self.assertTrue(entered.wait(5))
                self.assertIsNone(self.service.call("report.export.status", dict(token=token))["result"])
                self.call("report.settings.apply")
                self.assertGreater(self.service.revision, revision)
            finally:
                release.set()
            future = jobs[token]
            self.assertEqual(future.result(timeout=5)["revision"], revision)
            self.assertEqual(
                self.service.call("report.export.status", dict(token=token))["result"]["saved"], "background.html"
            )
            self.assertEqual(captured, dict(revision=revision, title="<Title>"))

    def test_stale_drafts_and_invalid_formats_never_create_output(self):
        with self.assertRaisesRegex(ValueError, "Stale report"):
            self.service.call(
                "report.export",
                dict(
                    revision=self.service.revision - 1,
                    specification=self.spec,
                    format="html",
                    path=str(self.root / "stale.html"),
                ),
            )
        for format in (None, "exe", [], "PDF"):
            with self.subTest(format=format), self.assertRaises(ValueError):
                self.export(format)
        with self.assertRaisesRegex(ValueError, "filename"):
            self.export("html", self.root / "project.eproj")
        self.service.call("analysis.load", dict(code="A"))
        self.service.call("analysis.edit", dict(revision=self.service.revision, field="ana_remarks", value="Draft"))
        for method in ("report.preview", "report.export"):
            with self.subTest(method=method), self.assertRaisesRegex(ValueError, "Unsaved analysis"):
                self.call(method, format="html", path=str(self.root / "draft.html"), discard=True)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_missing_pdf_renderer_and_render_failure_preserve_destination(self):
        path = self.root / "existing.pdf"
        path.write_bytes(b"original")
        with patch("modern.backend.reporting.find_renderer", return_value=None):
            self.assertFalse(self.call("report.preview")["pdf_available"])
            with self.assertRaisesRegex(ValueError, "WeasyPrint"):
                self.export("pdf", path)
        with (
            patch("modern.backend.reporting.find_renderer", return_value=Path("trusted")),
            patch("modern.backend.reporting.render_pdf", side_effect=RuntimeError("renderer failed")),
        ):
            with self.assertRaisesRegex(RuntimeError, "renderer failed"):
                self.export("pdf", path)
        self.assertEqual(path.read_bytes(), b"original")

    def test_workbook_failure_removes_partial_files_and_preserves_portal_replacements(self):
        path = self.root / "report.xlsx"

        def fail(document, target):
            target.write_bytes(b"partial")
            raise OSError("write failed")

        with patch("modern.backend.reporting.write_workbook", side_effect=fail):
            with self.assertRaisesRegex(OSError, "write failed"):
                self.export("xlsx")
            self.assertFalse(path.exists())
            path.write_bytes(b"original")
            with patch("modern.backend.persistence.flatpak_document", return_value=True):
                with self.assertRaisesRegex(OSError, "write failed"):
                    self.call("report.export", format="xlsx", path=str(path), replace_selected=True)
            self.assertEqual(path.read_bytes(), b"original")
            self.assertEqual(list(self.root.iterdir()), [path])
        with self.assertRaises(FileExistsError):
            self.export("xlsx")
        self.assertEqual(path.read_bytes(), b"original")

    def test_real_pdf_when_renderer_is_installed(self):
        if find_renderer() is None:
            self.skipTest("WeasyPrint 70+ executable is not installed")
        self.export("pdf")
        self.assertTrue((self.root / "report.pdf").read_bytes().startswith(b"%PDF-"))
