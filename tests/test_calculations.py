"""Golden semantics; AST loader also runs against the unmodified GTK source."""

import ast
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import unittest


def legacy_classes():
    tree = ast.parse(Path("estimator/data/schedule.py").read_text())
    nodes = [
        n
        for n in tree.body
        if getattr(n, "name", "")
        in ("Currency", "ScheduleItemModel", "ResourceItemModel")
    ]
    namespace = dict(Decimal=Decimal, ROUND_HALF_UP=ROUND_HALF_UP)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "legacy", "exec"), namespace)
    return namespace


class CalculationBaseline(unittest.TestCase):
    def test_order_tax_discount_and_all_rows(self):
        ns = legacy_classes()
        m = ns["ScheduleItemModel"]("A", "Multiline\ndescription")
        m.resources["R"] = ns["ResourceItemModel"](
            "R", "Resource", "kg", Decimal("10.05"), Decimal("18"), Decimal("5")
        )
        m.add_ana_group("Material")
        m.add_ana_res(["R", Decimal("2.5"), ""], 0)
        m.add_ana_weight("10%", Decimal(".1"))
        m.add_ana_weight("20% of same group", Decimal(".2"))
        m.add_ana_sum("Subtotal")
        m.add_ana_times("Divide", Decimal(".5"))
        m.add_ana_round("Say", Decimal("0"))
        m.evaluate_results()
        self.assertEqual(
            m.results,
            [
                [[Decimal("11.27"), Decimal("28.18")], Decimal("28.18")],
                Decimal("2.82"),
                Decimal("5.64"),
                Decimal("36.64"),
                Decimal("18.32"),
                Decimal("18"),
            ],
        )
        m.update_rate()
        self.assertEqual(m.rate, Decimal("18"))

    def test_last_group_is_rate_and_half_up(self):
        ns = legacy_classes()
        m = ns["ScheduleItemModel"]("A", "")
        m.add_ana_group("Empty")
        m.evaluate_results()
        self.assertEqual(m.get_ana_rate(), 0)
        self.assertEqual(ns["Currency"]("1.005"), Decimal("1.01"))
        self.assertEqual(
            ns["Currency"](Decimal("12.26"), Decimal("1.5")), Decimal("12.5")
        )
