"""Selection-based placement and project undo across editor lists."""

import unittest

from modern.backend.service import Service


class InsertionSelectionTests(unittest.TestCase):
    def setUp(self):
        self.service = Service()
        self.addCleanup(self.service.close)
        self.call("project.new")

    def call(self, method, **params):
        return self.service.call(method, dict(revision=self.service.revision, **params))

    def test_category_insertion_follows_last_selected_category_and_is_undoable(self):
        for kind, original in (("schedule", "Work"), ("resources", "Materials")):
            with self.subTest(kind=kind):
                prefix = kind + ".editor."
                self.call(prefix + "add", data=dict(code="A", category=original))
                item = self.call(prefix + "state")["rows"][0]["_children"][0]
                front = self.call(prefix + "category_add", description="Front")["selected"][0]
                new = self.call(prefix + "category_add", ids=[item["id"], front], description="After")
                rows = self.call(prefix + "state")["rows"]
                self.assertEqual([row["description"] for row in rows], ["Front", original, "After"])
                self.assertEqual(rows[-1]["id"], new["selected"][0])
                self.call("project.undo")
                self.assertEqual(
                    [row["description"] for row in self.call(prefix + "state")["rows"]], ["Front", original]
                )

    def test_measurement_insertion_preserves_category_boundaries_and_uses_last_selection(self):
        def add(label, *, item=False, **selection):
            return self.call("measurement.add", description=label, template="_1_NLBH" if item else None, **selection)[
                "selected"
            ][0]

        def labels():
            return [row["description"] for row in self.call("measurement.state")["rows"]]

        loose = add("Uncategorised item", item=True)
        first = add("First")
        one = add("One", item=True, id=first)
        three = add("Three", item=True, id=one)
        second = add("Second", id=one)
        add("Two", item=True, ids=[one, first])
        self.assertEqual(labels(), ["Uncategorised item", "First", "One", "Two", "Three", "Second"])
        self.call("measurement.copy", ids=[loose])
        self.call("measurement.paste", ids=[one, first])
        self.assertEqual(labels()[2:5], ["One", "Uncategorised item", "Two"])
        self.call("project.undo")
        self.call("measurement.paste", ids=[second, three])
        self.assertEqual(labels()[-2:], ["Second", "Uncategorised item"])
        self.call("measurement.copy", ids=[first, one])
        self.call("measurement.paste", id=one)
        self.assertEqual(labels()[4:8], ["Three", "First", "One", "Second"])
