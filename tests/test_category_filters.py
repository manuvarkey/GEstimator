import unittest
from modern.backend.service import Service


class CategoryFilters(unittest.TestCase):
    def test_filtering_precedes_paging_and_preserves_hierarchy_and_empty_categories(self):
        service = Service()
        self.addCleanup(service.close)
        service.call("project.new", {})
        def add(method, **params):
            return service.call(method, dict(revision=service.revision, **params))
        for index in range(105):
            add("schedule.editor.add", data=dict(code="C" + str(index), description="Civil work", category="Civil"))
        add("schedule.editor.add", data=dict(code="E", description="Electrical", category="E&M"))
        add("schedule.editor.add", data=dict(code="E.1", description="Electrical child", category="E&M", parent="E"))
        add("schedule.editor.category_add", description="Empty")
        first = service.call("schedule.editor.state", dict(categories=["Civil"]))
        last = service.call("schedule.editor.state", dict(categories=["Civil"], offset=100))
        self.assertEqual((first["total"], len(first["rows"][0]["_children"]), len(last["rows"][0]["_children"])), (105, 100, 5))
        electrical = service.call("schedule.editor.state", dict(categories=["E&M"], query="child"))
        self.assertEqual(electrical["total"], 1)
        self.assertEqual(electrical["rows"][0]["_children"][0]["_children"][0]["code"], "E.1")
        empty = service.call("schedule.editor.state", dict(categories=["Empty"]))
        self.assertEqual((empty["total"], len(empty["rows"])), (0, 1))
        multiple = service.call("schedule.editor.state", dict(categories=["E&M", "Empty"]))
        self.assertEqual((multiple["total"], len(multiple["rows"])), (2, 2))
        for category in ("Materials", "Labour"):
            add("resources.editor.add", data=dict(code=category, category=category, rate="10"))
        resources = service.call("resources.editor.state", dict(categories=["Labour"]))
        self.assertEqual(resources["total"], 1)
        self.assertEqual(resources["rows"][0]["_children"][0]["code"], "Labour")
        for invalid in ("Civil", None, [True], ["Civil"] * 201):
            with self.assertRaises(ValueError):
                service.call("schedule.editor.state", dict(categories=invalid))
