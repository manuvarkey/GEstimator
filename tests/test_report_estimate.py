"""Estimate metadata, grouped contents, templated pages and bundled report fonts."""

import base64
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from openpyxl import load_workbook

from estimator.data.measurement import MeasurementItemCustom, MeasurementItemHeading
from estimator.data.schedule import ResourceItemModel, ScheduleDatabase, ScheduleItemModel
from estimator.undo import Stack
from modern.backend.reporting import ReportSpec, build_document
from modern.backend.reporting.estimate_fields import default_specification, validate
from modern.backend.reporting.html import render_html
from modern.backend.reporting.narrative import render
from modern.backend.reporting.workbook import write_workbook
from modern.backend.service import Service


class EstimateReports(unittest.TestCase):
    """Check document behavior and persistence rather than UI implementation details."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.service = Service()
        self.addCleanup(self.service.close)
        self.defaults = dict(
            organization="Office",
            reference="REF",
            signoff_blocks=[dict(caption="Engineer", body="A. Person\nDivision")],
        )
        self.service.call("project.new", dict(estimate_defaults=self.defaults))
        self.db = self.service.db
        values = self.db.get_project_settings()
        values["project_name"] = "Test work"
        self.db.set_project_settings(values)
        for code, category in (("A", "Civil"), ("B", "Civil"), ("C", "Electrical")):
            model = ScheduleItemModel(code, code + " description", "m", 10, 2, category=category)
            model.resources = {"R": ResourceItemModel("R", "Material", "kg", 5, category="Materials")}
            model.add_ana_group("Materials")
            model.add_ana_res(["R", 2, ""], 0)
            model.add_ana_sum("Total")
            self.db.insert_item(model)
        measurement = self.db.get_measurement()
        for category in ("Civil", "Electrical"):
            heading = MeasurementItemHeading()
            heading.remark = category
            measurement.append_item(heading)
            for index in range(2):
                item = MeasurementItemCustom(plugin="_1_NLBH")
                item.remark = f"{category} sheet {index + 1}"
                measurement.append_item(item)
        self.db.set_measurement(measurement)

    def document(self, **changes):
        spec = default_specification(self.db)
        spec.update(changes)
        return build_document(self.db, self.service.revision, ReportSpec.parse(spec))

    def test_defaults_flow_project_and_saved_definition(self):
        values = self.service.call("project.settings", {})
        self.assertEqual(values["estimate"]["organization"], "Office")
        spec = self.service.call("report.settings", dict(revision=self.service.revision))["defaults"]
        self.assertEqual(
            [item["kind"] for item in spec["sections"]][:4], ["narrative", "abstract", "schedule", "signoff"]
        )
        self.assertFalse(spec["sections"][3]["new_page"])
        self.assertEqual(spec["organization"], "Office")
        self.assertEqual(spec["sections"][3]["signoff_blocks"], self.defaults["signoff_blocks"])
        self.service.call(
            "project.settings.edit",
            dict(
                revision=self.service.revision,
                settings=dict(estimate={**values["estimate"], "organization": "Changed"}),
            ),
        )
        self.assertEqual(default_specification(self.db)["organization"], "Changed")
        path = str(Path(self.temp.name) / "saved.eproj")
        self.service.call("project.save_copy", dict(path=path))
        self.service.call("project.open", dict(path=path))
        self.assertEqual(default_specification(self.service.db)["organization"], "Changed")

    def test_logo_and_office_are_saved_and_signoff_remains_escaped(self):
        def image(source):
            return "data:image/svg+xml;base64," + base64.b64encode(source.encode()).decode()

        logo = image('<svg xmlns="http://www.w3.org/2000/svg"><rect width="5" height="5"/></svg>')
        program = validate(dict(office="<Office>\nDivision", logo=logo, issue_date="Old default"))
        self.assertNotIn("issue_date", program)
        self.service.call(
            "project.settings.edit",
            dict(
                revision=self.service.revision,
                settings=dict(
                    estimate={
                        **program,
                        "issue_date": "Issued for tender",
                        "headings": {"signoff": "Approval"},
                        "signoff_intro": "Certified for {{ office }}",
                    }
                ),
            ),
        )
        path = str(Path(self.temp.name) / "embedded.eproj")
        self.service.call("project.save_copy", dict(path=path))
        self.service.call("project.open", dict(path=path))
        defaults = default_specification(self.service.db)
        self.assertEqual(defaults["logo"], logo)
        self.assertEqual(defaults["issue_date"], "Issued for tender")
        self.assertEqual(defaults["sections"][3]["title"], "Approval")
        html = render_html(build_document(self.service.db, self.service.revision, ReportSpec.parse(defaults)))
        self.assertIn(f'src="{logo}"', html)
        self.assertIn('class="cover-office">&lt;Office&gt;\nDivision', html)
        self.assertIn("Certified for &lt;Office&gt;\nDivision", html)
        for invalid in (
            "https://example.invalid/logo.svg",
            image('<svg xmlns="http://www.w3.org/2000/svg"><script/></svg>'),
            image(
                '<svg xmlns="http://www.w3.org/2000/svg"><path style="fill:url(https://example.invalid/logo)"/></svg>'
            ),
        ):
            with self.subTest(logo=invalid), self.assertRaises(ValueError):
                ReportSpec.parse(dict(logo=invalid))

    def test_categories_item_contents_and_independent_pages(self):
        document = self.document(
            sections=[dict(id=kind, kind=kind, each_item_page=True) for kind in ("analyses", "measurements")]
        )
        self.assertEqual([item.category for item in document.analyses], ["Civil", "Civil", "Electrical"])
        html = render_html(document)
        for target in (
            "analyses:category:0",
            "analyses:analysis:1",
            "measurements:category:1",
            "measurements:measurement:3",
        ):
            self.assertIn(f'href="#{target}"', html)
            self.assertIn(f'id="{target}"', html)
        self.assertIn('class="item-heading"', html)
        self.assertEqual(html.count('class="measurement-item item-page"'), 2)
        path = Path(self.temp.name) / "report.xlsx"
        write_workbook(document, path)
        with closing(load_workbook(path)) as workbook:
            self.assertEqual(len(workbook["Section 1"].row_breaks.brk), 2)
            self.assertEqual(len(workbook["Section 2"].row_breaks.brk), 3)
            heading = next(cell for row in workbook["Section 1"] for cell in row if cell.value == "A — A description")
            self.assertTrue(heading.font.bold)
            self.assertEqual(heading.font.sz, 10)

    def test_inline_and_separate_editable_signoffs_and_work_name(self):
        sections = [
            dict(id="schedule", kind="schedule", show_name_of_work=True),
            dict(id="signoff", kind="signoff", signoff_blocks=self.defaults["signoff_blocks"]),
        ]
        doc = self.document(sections=sections)
        html = render_html(doc)
        self.assertIn('class="section inline" id="signoff"', html)
        self.assertIn("Name of work: Test work", html)
        self.assertIn("<strong>Engineer</strong>", html)
        self.assertIn("A. Person\nDivision", html)
        path = Path(self.temp.name) / "report.xlsx"
        write_workbook(doc, path)
        workbook = load_workbook(path)
        self.assertEqual(workbook.sheetnames, ["Cover", "Contents", "Section 1"])
        self.assertTrue(any(cell.value == "Engineer" for row in workbook["Section 1"] for cell in row))
        workbook.close()
        sections[1]["new_page"] = True
        write_workbook(self.document(sections=sections), path)
        workbook = load_workbook(path)
        self.assertEqual(len(workbook.sheetnames), 4)
        workbook.close()

    def test_templated_notes_pages_and_literal_output(self):
        source = "Work: {{ name_of_work }}\n{{ organization | upper }}\n{{ estimate_total }}\f{% if reference %}Ref: {{ reference }}{% endif %}"
        doc = self.document(sections=[dict(id="notes", kind="narrative", body=source)])
        self.assertEqual(doc.narratives[0].pages, ("Work: Test work\nOFFICE\n60.00", "Ref: REF"))
        self.assertEqual(doc.specification.sections[0].body, source)
        path = Path(self.temp.name) / "notes.xlsx"
        write_workbook(doc, path)
        workbook = load_workbook(path)
        self.assertEqual(
            [workbook["Section 1"][f"A{row}"].value for row in (4, 5, 6)], doc.narratives[0].pages[0].split("\n")
        )
        self.assertEqual(len(workbook["Section 1"].row_breaks.brk), 1)
        workbook.close()
        for source in (
            "{{ unknown }}",
            '{{ "x" * 1000000 }}',
            "{% for x in range(10) %}x{% endfor %}",
            "{{ organization.__class__ }}",
            '{% include "file" %}',
        ):
            with self.subTest(source=source), self.assertRaises(ValueError):
                render(source, dict(organization="Office"))

    def test_bundled_font_is_embedded_only_for_default_or_iosevka(self):
        html = render_html(self.document(sections=[]))
        self.assertEqual(html.count("data:font/woff2;base64,"), 2)
        self.assertIn('font-family:"Iosevka"', html)
        self.assertLess(len(html.encode("utf-8")), 10_000_000)
        custom = render_html(self.document(sections=[], font_family="DejaVu Serif"))
        self.assertNotIn("data:font/", custom)

    def test_long_notes_are_not_truncated_by_excel_cell_limits(self):
        body = "x" * 40000
        document = self.document(sections=[dict(id="notes", kind="narrative", body=body)])
        path = Path(self.temp.name) / "long-notes.xlsx"
        write_workbook(document, path)
        with closing(load_workbook(path)) as workbook:
            sheet = workbook["Section 1"]
            restored = "".join(sheet.cell(row, 1).value or "" for row in range(4, sheet.max_row + 1))
            self.assertEqual(restored, body)
            self.assertTrue(all(len(sheet.cell(row, 1).value or "") <= 100 for row in range(4, sheet.max_row + 1)))
        six = "\f".join("abcdef")
        section = dict(id="notes", kind="narrative", body=six)
        self.assertEqual(ReportSpec.parse(dict(sections=[section])).sections[0].body, six)
        with self.assertRaises(ValueError):
            ReportSpec.parse(dict(sections=[{**section, "body": six + "\fg"}]))
