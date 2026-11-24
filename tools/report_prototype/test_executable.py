"""Exercise the real CLI, including failure and process cleanup boundaries."""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from .executable import render_pdf
from .render import context, render_html


@unittest.skipUnless(shutil.which("weasyprint"), "WeasyPrint CLI is not on PATH")
class ExecutableReportTests(unittest.TestCase):
    """Use the installed renderer rather than a substitute transport."""

    def setUp(self):
        self.executable = Path(shutil.which("weasyprint"))

    def test_real_report_and_missing_assets(self):
        html = render_html(context([], project="CLI check", organization="Office"))
        pdf, diagnostics = render_pdf(html, self.executable)
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertEqual(diagnostics, "")
        for source in ("file:///etc/passwd", "https://example.invalid/logo.png"):
            with self.subTest(source=source), self.assertRaisesRegex(RuntimeError, "renderer failed"):
                render_pdf(f'<img src="{source}">', self.executable)

    def test_timeout_removes_scratch_output(self):
        with tempfile.TemporaryDirectory() as root:
            with patch("tempfile.tempdir", root):
                with self.assertRaisesRegex(RuntimeError, "exceeded"):
                    render_pdf("<p>Deadline check</p>", self.executable, timeout=0.0001)
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_bad_deadline_rejected(self):
        for deadline in (0, -1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                render_pdf("<p>test</p>", self.executable, deadline)
