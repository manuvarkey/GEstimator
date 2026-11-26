"""Focused checks for the optional rendering experiment, run explicitly."""

import copy
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from PIL import Image
from weasyprint import HTML
from weasyprint.urls import URLFetchingError

from .library import embedded_asset
from .render import context, logo_uri, project_context, render_html


class ReportPrototypeTests(unittest.TestCase):
    """Prove report inputs remain data and section totals retain rounding."""

    def data(self, **kwargs):
        rows = [
            dict(
                category="Work",
                code=str(index),
                description="<script>alert(1)</script>",
                unit="m",
                quantity="1",
                rate="0.005",
            )
            for index in range(2)
        ]
        original = copy.deepcopy(rows)
        result = context(rows, project="<Project>", organization="Office", **kwargs)
        self.assertEqual(rows, original)
        return result

    def test_abstract_sums_rounded_items_and_does_not_mutate_inputs(self):
        data = self.data()
        self.assertEqual(data["total"], "0.02")
        self.assertEqual(data["abstract"], [dict(category="Work", amount="0.02")])

    def test_text_is_escaped_and_sections_follow_selection(self):
        html = render_html(self.data(sections=["schedule", "abstract"]))
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;Project&gt;", html)
        self.assertLess(html.index('id="schedule"'), html.index('id="abstract"'))
        self.assertNotIn('id="signoff"', html)

    def test_custom_facing_and_abstract_with_default_shell(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "facing.html").write_text("<header>Custom {{ organization }}</header>")
            Path(directory, "abstract.html").write_text("<h1>Custom abstract {{ total }}</h1>")
            html = render_html(self.data(), directory)
        self.assertIn("Custom Office", html)
        self.assertIn("Custom abstract 0.02", html)

    def test_invalid_sections_and_external_assets_are_rejected(self):
        for sections in (["unknown"], ["abstract", "abstract"]):
            with self.assertRaises(ValueError):
                self.data(sections=sections)
        for url in ("file:///etc/passwd", "https://example.com/logo.png", "data:image/svg+xml,<svg/>"):
            with self.assertRaises(URLFetchingError):
                embedded_asset(url)

    def test_embedded_logo_renders_in_paginated_pdf(self):
        with tempfile.TemporaryDirectory() as directory:
            logo = Path(directory, "logo.png")
            Image.new("RGB", (40, 20), "navy").save(logo)
            data = self.data(logo=logo_uri(logo))
        document = HTML(string=render_html(data), url_fetcher=embedded_asset).render()
        self.assertEqual(len(document.pages), 5)
        self.assertTrue(document.write_pdf().startswith(b"%PDF-"))

    def test_real_project_uses_snapshot_amounts_and_preserves_source(self):
        from estimator.data.schedule import ScheduleDatabase, ScheduleItemModel
        from estimator.undo import Stack

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "project.eproj")
            database = ScheduleDatabase(Stack())
            database.create_new_database(str(path))
            database.insert_item(
                ScheduleItemModel("A", "<Actual work>", "m", Decimal("0.05"), Decimal("0.1"), category="Work")
            )
            database.close_database()
            original = path.read_bytes()
            data = project_context(path, organization="<Office>", sections=["schedule", "abstract"])
            html = render_html(data)
            self.assertEqual(path.read_bytes(), original)
        self.assertEqual(data["total"], "0.01")
        self.assertEqual(data["schedule"][0]["amount"], "0.01")
        self.assertIn("&lt;Actual work&gt;", html)
        self.assertIn("&lt;Office&gt;", html)
        self.assertIn("Report from accepted project data", html)
        self.assertNotIn("illustrative quantities", html)
        self.assertLess(html.index('id="schedule"'), html.index('id="abstract"'))
        self.assertTrue(HTML(string=html, url_fetcher=embedded_asset).write_pdf().startswith(b"%PDF-"))


if __name__ == "__main__":
    unittest.main()
