"""Tests for changed-file quality, correctness and advisory formatting checks."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import check_quality

ROOT = Path(__file__).resolve().parents[1]


class CheckQualityTests(unittest.TestCase):
    def test_invalid_base_reference_raises_system_exit(self):
        """Unusable base references must fail clearly rather than checking arbitrary files."""
        with self.assertRaises(SystemExit) as context:
            check_quality.changed_files(base="nonexistent_git_ref_12345")
        self.assertIn("Unable to find merge base for Git reference", str(context.exception))

    def test_empty_changed_files_succeeds_in_all_modes(self):
        """When no relevant files have changed, all modes should pass cleanly without work."""
        with patch.object(check_quality, "changed_files", return_value=[]):
            for mode in ("all", "correctness", "formatting"):
                with patch.object(sys, "argv", ["check_quality.py", "--mode", mode]):
                    # Should return cleanly without calling sys.exit with an error.
                    check_quality.main()

    def test_correctness_mode_detects_undefined_name(self):
        """High-confidence correctness linting must fail on undefined names."""
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_file = Path(temp_dir) / "sample_error.py"
            temp_file.write_text("print(nonexistent_variable_xyz)\n", encoding="utf-8")

            with patch.object(check_quality, "changed_files", return_value=[temp_file]):
                with patch.object(sys, "argv", ["check_quality.py", "--mode", "correctness"]):
                    with self.assertRaises(SystemExit) as context:
                        check_quality.main()
                    self.assertNotEqual(context.exception.code, 0)

    def test_correctness_mode_ignores_formatting_differences(self):
        """Correctness checks must pass even when formatting-only differences are present."""
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_file = Path(temp_dir) / "sample_style.py"
            # Import formatting issue (unnecessary blank line between standard library imports)
            temp_file.write_text("import os\n\nimport sys\n\nx = 1\n", encoding="utf-8")

            with patch.object(check_quality, "changed_files", return_value=[temp_file]):
                with patch.object(sys, "argv", ["check_quality.py", "--mode", "correctness"]):
                    # Correctness checks must pass cleanly.
                    check_quality.main()

    def test_strict_formatting_mode_fails_on_formatting_differences(self):
        """Strict local formatting checks must exit nonzero when code is unformatted."""
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_file = Path(temp_dir) / "sample_style.py"
            temp_file.write_text("import os\n\nimport sys\n\nx = 1\n", encoding="utf-8")

            with patch.object(check_quality, "changed_files", return_value=[temp_file]):
                with patch.object(sys, "argv", ["check_quality.py", "--mode", "formatting"]):
                    with self.assertRaises(SystemExit) as context:
                        check_quality.main()
                    self.assertEqual(context.exception.code, 1)

    def test_advisory_formatting_mode_succeeds_and_writes_summary(self):
        """Advisory formatting in CI must report violations, write summary, and exit zero."""
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_file = Path(temp_dir) / "sample_style.py"
            temp_file.write_text("import os\n\nimport sys\n\nx = 1\n", encoding="utf-8")
            summary_file = Path(temp_dir) / "step_summary.md"

            with patch.object(check_quality, "changed_files", return_value=[temp_file]):
                with patch.object(sys, "argv", ["check_quality.py", "--mode", "formatting", "--advisory"]):
                    with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(summary_file)}):
                        with self.assertRaises(SystemExit) as context:
                            check_quality.main()
                        # Must exit with code 0 in advisory mode
                        self.assertEqual(context.exception.code, 0)
                        self.assertTrue(summary_file.is_file())
                        summary_content = summary_file.read_text(encoding="utf-8")
                        self.assertIn("Advisory formatting differences detected", summary_content)
                        self.assertIn("python tools/check_quality.py --fix", summary_content)

    def test_correctness_mode_rejects_fix_flag(self):
        """Correctness checks do not modify source files and must reject --fix."""
        with patch.object(sys, "argv", ["check_quality.py", "--mode", "correctness", "--fix"]):
            with self.assertRaises(SystemExit) as context:
                check_quality.main()
            self.assertNotEqual(context.exception.code, 0)

    def test_correctness_mode_rejects_advisory_flag(self):
        """Correctness errors must never be advisory and must reject --advisory."""
        with patch.object(sys, "argv", ["check_quality.py", "--mode", "correctness", "--advisory"]):
            with self.assertRaises(SystemExit) as context:
                check_quality.main()
            self.assertNotEqual(context.exception.code, 0)

    def test_fix_flag_formats_source_and_subsequent_check_passes(self):
        """Running with --fix applies formatting and makes subsequent check pass."""
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_file = Path(temp_dir) / "sample_fix.py"
            temp_file.write_text("import os\n\nimport sys\n\nx = 1\n", encoding="utf-8")

            with patch.object(check_quality, "changed_files", return_value=[temp_file]):
                # Step 1: apply fix
                with patch.object(sys, "argv", ["check_quality.py", "--fix"]):
                    check_quality.main()

                # Step 2: verify strict check now passes
                with patch.object(sys, "argv", ["check_quality.py"]):
                    check_quality.main()


if __name__ == "__main__":
    unittest.main()
