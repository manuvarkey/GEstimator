"""The same bounded math syntax works in measurements and modern numeric entry."""

import math
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from estimator.arithmetic import evaluate_number
from modern.backend.importing import loose_number
from modern.backend.mcp_workspace import Workspace
from modern.backend.numbers import decimal
from modern.backend.service import Service


class MathExpressionTests(unittest.TestCase):
    def test_requested_functions_and_constants_in_both_numeric_modes(self):
        cases = [
            ("abs(-2.5)", 2.5),
            ("max(1, 3, -2)", 3),
            ("min(1, 3, -2)", -2),
            ("sqrt(9)", 3),
            ("cbrt(-8)", -2),
            ("cbrt(0)", 0),
            ("ceil(1.2)", 2),
            ("floor(-1.2)", -2),
            ("trunc(-1.9)", -1),
            ("round(2.5)", 2),
            ("round(1234, -2)", 1200),
            ("round(1.2345, 2)", 1.23),
            ("sin(pi/2)", 1),
            ("cos(pi)", -1),
            ("tan(pi/4)", 1),
            ("asin(1)", math.pi / 2),
            ("acos(-1)", math.pi),
            ("atan(1)", math.pi / 4),
            ("exp(1)", math.e),
            ("log(e)", 1),
            ("log(8, 2)", 3),
            ("log10(1000)", 3),
            ("degrees(pi)", 180),
            ("radians(180)", math.pi),
            ("pi", math.pi),
            ("e", math.e),
            ("9**0.5", 3),
            ("2**-3", 0.125),
            ("max(abs(-4), sqrt(9)) + sin(radians(30))", 4.5),
        ]
        for source, expected in cases:
            with self.subTest(source=source, mode="template"):
                self.assertAlmostEqual(evaluate_number(source), expected, places=10)
            with self.subTest(source=source, mode="decimal"):
                self.assertAlmostEqual(float(decimal(source)), expected, places=6)

    def test_decimal_operations_preserve_exact_entry_precision(self):
        for source, expected in [
            ("0.1 + 0.2", "0.300000"),
            ("max(0.1 + 0.2, 0.3)", "0.300000"),
            ("sqrt(0.09)", "0.300000"),
            ("round(2.675, 2)", "2.680000"),
            ("0.123456789012", "0.123456789012"),
            ("-0.123456789012", "-0.123456789012"),
            ("log10(100)", "2.000000"),
            ("floor(-1.01)", "-2.000000"),
            ("-5//2", "-3.000000"),
            ("-5%2", "1.000000"),
            ("5%-2", "-1.000000"),
        ]:
            with self.subTest(source=source):
                result = decimal(source)
                self.assertIsInstance(result, Decimal)
                self.assertEqual(str(result), expected)
        self.assertEqual(evaluate_number("round(2.675, 2)"), 2.67)
        with self.assertRaises(ValueError):
            decimal("0.1234567890123")
        for source in ("asin(1+1e-30)", "acos(-1-1e-30)", "1//1e-999999", "1%1e-999999"):
            with self.subTest(source=source), self.assertRaises(ValueError):
                decimal(source)

    def test_rejects_unsafe_calls_invalid_domains_and_excessive_work(self):
        for source in [
            "__import__('os')",
            "math.sqrt(4)",
            "sqrt.__call__(4)",
            "(lambda: 1)()",
            "max([1, 2])",
            "max(*(1, 2))",
            "round(1, ndigits=2)",
            "pi()",
            "sqrt",
            "unknown",
            "pi=3",
            "sqrt(-1)",
            "acos(2)",
            "asin(-2)",
            "log(0)",
            "log(-1)",
            "log(4, 0)",
            "log(4, -2)",
            "log(4, 1)",
            "log10(0)",
            "exp(1000)",
            "tan(pi/2)",
            "round(1, 1.5)",
            "round(1, -1000000000000)",
            "2**1000000",
            "9**9**9",
            "(-1)**0.5",
            "1e309",
            "1e12*10",
            "sqrt()",
            "sqrt(1, 2)",
            "max()",
            "min()",
            "log(1, 2, 3)",
            "round(1, 2, 3)",
            "1+" * 40 + "1",
            "1" * 201,
        ]:
            for evaluate in (evaluate_number, decimal):
                with self.subTest(source=source, mode=evaluate.__name__), self.assertRaises(ValueError):
                    evaluate(source)

    def test_measurement_functions_survive_apply_save_and_reopen(self):
        with tempfile.TemporaryDirectory() as folder:
            service = Service()
            self.addCleanup(service.close)

            def call(method, **params):
                return service.call(method, dict(revision=service.revision, **params))

            call("project.new")
            identity = call("measurement.add", template="_1_NLBH", description="Math functions")["selected"][0]
            call("measurement.draft.open", id=identity)
            call("measurement.record_add", id=identity)
            record = call("measurement.detail", id=identity)["detail"]["rows"][0]["id"]
            expression = "max(sqrt(9), abs(-4)) + sin(pi/2)"
            call("measurement.record_edit", id=identity, record_id=record, field="c3", value=expression)
            self.assertEqual(call("measurement.detail", id=identity)["detail"]["totals"], ["5.0"])
            call("measurement.draft.apply")
            path = Path(folder) / "math.eproj"
            call("project.save_copy", path=str(path))
            call("project.open", path=str(path), discard=True)
            identity = call("measurement.state")["rows"][0]["id"]
            detail = call("measurement.detail", id=identity)["detail"]
            self.assertEqual(detail["rows"][0]["c3"], expression)
            self.assertEqual(detail["totals"], ["5.0"])

    def test_mcp_measurement_adapter_accepts_the_same_functions(self):
        service = Service()
        self.addCleanup(service.close)
        service.call("project.new", {})
        result = Workspace(service).call(
            "edit_measurements",
            {
                "ops": [
                    {
                        "action": "create",
                        "template": "_1_NLBH",
                        "records": [{"No": "ceil(1.2)", "L": "sqrt(9) + sin(pi/2)"}],
                    }
                ]
            },
            [],
        )
        identity = result["results"][0]["id"]
        detail = service.call("measurement.detail", {"id": identity})["detail"]
        self.assertEqual(detail["totals"], ["8.0"])
        self.assertEqual(detail["rows"][0]["c3"], "sqrt(9) + sin(pi/2)")

    def test_worksheet_functions_preserve_argument_commas_and_grouped_numbers(self):
        for source, expected in [
            ("1,234.50", "1234.50"),
            ("Rs. 1,234.50", "1234.50"),
            ("1,00,000", "100000"),
            ("max(1, 2)", "2"),
            ("((min))(1, 2)", "1"),
            ("=round(1.2345, 2)", "1.23"),
            ("log(8, 2)", "3"),
            ("2*1,000", "2000"),
        ]:
            with self.subTest(source=source):
                self.assertEqual(loose_number(source), Decimal(expected))
        self.assertIsNone(loose_number("round(1, ndigits=2)"))
