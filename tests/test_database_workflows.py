import tempfile
import unittest
from pathlib import Path
from decimal import Decimal
from estimator import misc
from estimator.data.measurement import MeasurementItemCustom, RecordCustom
from modern.backend.service import Service


class DatabaseWorkflows(unittest.TestCase):
    def setUp(self):
        self.service = Service()
        self.addCleanup(self.service.close)
        self.service.call("project.new", {})

    def call(self, method, **params):
        return self.service.call(method, dict(revision=self.service.revision, **params))

    def test_catalog_attaches_bundled_databases_once(self):
        result = self.call("library.attach_catalog")
        names = {source["name"] for source in result["sources"]}
        self.assertTrue({"DSR 2023", "DSR E&M 2025"} <= names)
        self.assertEqual(self.call("library.attach_catalog")["sources"], result["sources"])

    def test_selected_schedule_database_rates_preview_undo_and_source_preservation(self):
        first = self.call("schedule.editor.add", data=dict(code="A", description="Project description", rate="20", category="Work"))["selected"][0]
        other = self.call("schedule.editor.add", data=dict(code="B", rate="7", category="Work"))["selected"][0]
        source = Service()
        self.addCleanup(source.close)
        source.call("project.new", {})
        source.call("schedule.editor.add", dict(revision=source.revision, data=dict(code="A", description="Database description", rate="50", category="Work")))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "rates.eproj"
            source.call("project.save_copy", dict(path=str(path)))
            original = path.read_bytes()
            library = self.call("library.attach", path=str(path))[0]["id"]
            before = self.call("schedule.editor.state")
            params = dict(library=library, ids=[first, other])
            self.assertEqual(self.call("schedule.editor.price_preview", **params), dict(changed=1, unchanged=0, unmatched=1))
            self.assertEqual(self.call("schedule.editor.state"), before)
            self.call("schedule.editor.price_update", **params)
            item = self.service.db.get_item("A")
            self.assertEqual((item.rate, item.description), (Decimal("50"), "Project description"))
            self.assertEqual(self.service.db.get_item("B").rate, Decimal("7"))
            self.call("project.undo")
            self.assertEqual(self.service.db.get_item("A").rate, Decimal("20"))
            self.assertEqual(path.read_bytes(), original)

    def test_all_measurement_cells_retain_expressions_and_original_rendered_breakups(self):
        for template in self.call("measurement.templates"):
            model = MeasurementItemCustom(plugin=template["code"])
            result = self.call("measurement.add", template=template["code"], description=template["name"])
            identity = result["selected"][0]
            self.call("measurement.record_add", id=identity)
            record = self.call("measurement.state", id=identity)["detail"]["rows"][0]["id"]
            values = ["2*3" if kind in (misc.MEAS_L, misc.MEAS_NO) else "Description\nSecond line" if kind == misc.MEAS_DESC else "" for kind in model.columntypes]
            self.call("measurement.record_edit_many", id=identity, edits=[dict(id=record, field="c" + str(index), value=value) for index, value in enumerate(values) if model.columntypes[index] != misc.MEAS_CUST])
            expected = RecordCustom(values, model.cust_funcs, model.total_func_item, model.columntypes).get_model_rendered(1)
            row = self.call("measurement.state", id=identity)["detail"]["rows"][0]
            for index, value in enumerate(expected):
                self.assertEqual(row["_display"]["c" + str(index)], "" if value is None else str(value))
                if model.columntypes[index] != misc.MEAS_CUST:
                    self.assertEqual(row["c" + str(index)], values[index])

    def test_nlbh_blank_factors_support_count_length_area_and_volume(self):
        identity = self.call("measurement.add", template="_1_NLBH")["selected"][0]
        self.call("measurement.record_add", id=identity, count=5)
        rows = self.call("measurement.state", id=identity)["detail"]["rows"]
        cases = [("5", "", "", ""), ("", "2*3", "", ""), ("", "2", "3", ""), ("2", "3", "4", "5"), ("", "", "", "")]
        self.call("measurement.record_edit_many", id=identity, edits=[dict(id=row["id"], field="c" + str(index + 2), value=value) for row, values in zip(rows, cases) for index, value in enumerate(values)])
        detail = self.call("measurement.state", id=identity)["detail"]
        self.assertEqual([Decimal(row["_display"]["c6"]) for row in detail["rows"]], list(map(Decimal, ("5", "6", "6", "120", "0"))))
        self.assertEqual(detail["rows"][1]["_display"]["c1"], "[,2*3,,]")
        self.assertEqual(Decimal(detail["totals"][0]), Decimal("137"))

    def test_template_groups_are_general_civil_and_em(self):
        groups = {entry["code"]: entry["group"] for entry in self.call("measurement.templates")}
        self.assertEqual(groups["_1_NLBH"], "General")
        self.assertEqual(groups["civil_steel_table"], "Civil")
        self.assertEqual(groups["elec_ac_round_duct"], "E&M")
