"""Arithmetic remains compatible with templates without executing project text."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from estimator import misc
from estimator.arithmetic import evaluate_number
from estimator.data.measurement import MeasurementItemCustom, RecordCustom
from estimator.data.template_loader import load_template


class ArithmeticTests(unittest.TestCase):
    def test_legacy_arithmetic_types_and_rounding(self):
        for source, expected in [
            ("2*(3+4)", 14),
            ("1/3", 1 / 3),
            ("-5//2", -3),
            ("7%3", 1),
            ("2**-3", 0.125),
            ("1_000 + .5", 1000.5),
            ("1e3", 1000.0),
        ]:
            with self.subTest(source=source):
                result = evaluate_number(source)
                self.assertEqual(result, expected)
                self.assertIs(type(result), type(expected))

    def test_rejects_code_and_unbounded_expressions(self):
        for source in [
            "__import__('os').getcwd()",
            "open('unexpected', 'w')",
            "(1).__class__",
            "[1][0]",
            "True",
            "'4'",
            "2**1000000",
            "9**9**9",
            "1e309",
            "1e12*10",
            "1/0",
            "(-1)**.5",
            "1+" * 40 + "1",
            "1" * 201,
            "",
            None,
        ]:
            with self.subTest(source=source), self.assertRaises(ValueError):
                evaluate_number(source)

    def test_template_totals_match_pre_refactor_golden_values(self):
        # Captured from the original engine and templates before replacing eval.
        expected = {
            "_1_NLBH": [3.562],
            "_2_LLLLL": [1.25, 4.75, 7.25, 7.333, 3.833],
            "_3_NNNNNNNN": [1.333, 1.25, 4.75, 7.25, 7.333, 3.833, 1.333, 1.25],
            "_4_nnnnnT": [21.916],
            "civil_steel_table": [-115.357],
            "elec_tableofpoints": [20],
            "elec_ac_round_duct": [0.0],
            "elec_ac_rect_duct": [0.0],
        }
        expressions = ["2*3", "1/3", "-2.5", "(3+4)/2", "2**-2", "7%3"]
        for template, totals in expected.items():
            with self.subTest(template=template):
                item = MeasurementItemCustom(plugin=template)
                for shift in range(3):
                    raw = [
                        expressions[(index + shift) % len(expressions)]
                        if kind in (misc.MEAS_L, misc.MEAS_NO)
                        else "Reference"
                        for index, kind in enumerate(item.columntypes)
                    ]
                    item.append_record(RecordCustom(raw, item.cust_funcs, item.total_func_item, item.columntypes))
                self.assertEqual(item.get_total(), totals)

        # Millimetre dimensions also exercise nonzero duct areas after rounding.
        for template, totals in [("elec_ac_round_duct", [2.212]), ("elec_ac_rect_duct", [5.693])]:
            with self.subTest(template=template):
                item = MeasurementItemCustom(plugin=template)
                raw = [
                    str(250 * (index + 1)) + "+0.5" if kind in (misc.MEAS_L, misc.MEAS_NO) else "Reference"
                    for index, kind in enumerate(item.columntypes)
                ]
                item.append_record(RecordCustom(raw, item.cust_funcs, item.total_func_item, item.columntypes))
                self.assertEqual(item.get_total(), totals)

    def test_loaded_records_and_template_callbacks_do_not_execute_text(self):
        # Loading a project bypasses desktop input validation, including callbacks.
        for template in [
            "_1_NLBH",
            "_4_nnnnnT",
            "civil_steel_table",
            "elec_tableofpoints",
            "elec_ac_round_duct",
            "elec_ac_rect_duct",
        ]:
            with self.subTest(template=template):
                item = MeasurementItemCustom(plugin=template)
                raw = ["__import__('builtins').open('unexpected', 'w')"] * item.model_width()
                with patch("builtins.open", side_effect=AssertionError("Executed project text")) as opened:
                    record = RecordCustom(raw, item.cust_funcs, item.total_func_item, item.columntypes)
                    self.assertTrue(all(value == 0 for value in record.data))
                    with self.assertLogs(level="WARNING"):
                        self.assertEqual(len(record.get_model_rendered()), item.model_width())
                    opened.assert_not_called()

    def test_worksheet_formulas_keep_arithmetic_and_reject_code(self):
        sheet = misc.Spreadsheet()
        sheet.sheet.cell(1, 1, "=2*(3+4)")
        sheet.sheet.cell(2, 1, "=__import__('builtins').open('unexpected', 'w')")
        with patch("builtins.open", side_effect=AssertionError("Executed worksheet text")) as opened:
            self.assertEqual(sheet.read_rows([float], allow_formula=True), [["2*(3+4)"], ["0"]])
            opened.assert_not_called()

    def test_template_symlink_guard_runs_before_reading_source(self):
        with patch.object(Path, "is_symlink", return_value=True), patch.object(Path, "read_bytes") as read:
            with self.assertRaisesRegex(ValueError, "installed file"):
                load_template("_1_NLBH")
            read.assert_not_called()

    def test_template_names_cannot_escape_the_installed_directory(self):
        for name in ["../outside", "..\\outside", "/tmp/outside", "C:\\outside", "name.py", "", None]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                load_template(name)

    def test_template_symlinks_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "outside.py"
            target.write_text("raise AssertionError('Loaded outside template')", encoding="utf-8")
            installed = root / "templates"
            installed.mkdir()
            try:
                (installed / "escape.py").symlink_to(target)
            except OSError:
                self.skipTest("Creating symlinks is unavailable")
            with patch.object(misc, "abs_path", return_value=str(installed)), self.assertRaises(ValueError):
                load_template("escape")
