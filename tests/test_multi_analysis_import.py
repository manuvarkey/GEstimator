"""Real XLSX / SQLite regression coverage for PARITY-004."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from openpyxl import Workbook
from modern.backend.service import Service
from modern.backend.importing import import_analysis, selected_rows
from estimator.data.schedule import ScheduleItemModel


class MultiAnalysisImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.s = Service()
        self.addCleanup(self.s.close)
        self.s.call('project.open', {'path': 'estimator/database/DSREM2022.eproj'})
        self.codes = [row.code for row in self.s.db.ScheduleTable.select().join(self.s.db.SequenceTable).distinct().limit(2)]
        self.path = Path(self.temp.name) / 'multi.xlsx'

    def workbook(self, codes=None, rate_first=False):
        book = Workbook()
        for code in codes or self.codes + ['UNMATCHED']:
            rows = [[code, 'Workbook description'], ['', 'Description', 'Unit', 'Qty', 'Rate', 'Amount'],
                    ['', 'MATERIALS'], ['', 'above note'],
                    ['NEW-IMPORT-RESOURCE', 'Imported material', 'kg', 2, 10.23, 20.46],
                    ['', 'below note'], ['', 'Total', '', 0, 0, 20.46],
                    ['', 'Say', '', 0, 0, 20]]
            for row in rows:
                row += [None] * (6 - len(row))
                if rate_first:
                    row[3], row[4] = row[4], row[3]
                book.active.append(row)
        book.save(self.path)
        book.close()
        return {'path': str(self.path), 'rate_first': rate_first}

    def call(self, method, params=None):
        return self.s.call(method, dict(revision=self.s.revision, **(params or {})))

    def snapshot(self):
        db = self.s.db
        return {table._meta.table_name: list(table.select().order_by(table.id).dicts())
                for table in (db.ScheduleTable, db.ResourceTable, db.SequenceTable)}

    def test_preview_apply_metadata_and_single_undo_redo(self):
        params = self.workbook()
        before = self.snapshot()
        history = len(self.s.project_editor.history)
        result = self.call('project.import_analysis_preview', params)
        self.assertEqual({k: result[k] for k in ('matched', 'unmatched')}, dict(matched=self.codes, unmatched=['UNMATCHED']))
        self.assertEqual([row['code'] for row in result['analyses'] if row['matched']], self.codes)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(len(self.s.project_editor.history), history)
        metadata = {code: copy.deepcopy(self.s.db.ScheduleTable.get(code=code).__data__) for code in self.codes}
        self.assertEqual(self.call('project.import_analysis_apply', params), result)
        for code in self.codes:
            after = self.s.db.ScheduleTable.get(code=code).__data__
            for key, value in metadata[code].items():
                if key not in ('rate', 'ana_remarks'):
                    self.assertEqual(after[key], value, key)
            item = self.s.db.get_item(code, modify_res_code=False)
            self.assertEqual(item.ana_items[0]['resource_list'][0][0], 'NEW-IMPORT-RESOURCE')
        applied = self.snapshot()
        self.assertEqual(len(self.s.project_editor.history), history + 1)
        self.call('project.undo')
        self.assertEqual(self.snapshot(), before)
        self.call('project.redo')
        self.assertEqual(self.snapshot(), applied)

    def test_second_item_failure_rolls_back_first_and_resources(self):
        params = self.workbook()
        before = self.snapshot()
        history = len(self.s.project_editor.history)
        original = self.s.db.insert_item_atomic
        def insert(item, **kwargs):
            if item.code == self.codes[1]:
                raise RuntimeError('injected second item failure')
            return original(item, **kwargs)
        with patch.object(self.s.db, 'insert_item_atomic', side_effect=insert):
            with self.assertRaisesRegex(RuntimeError, 'second item'):
                self.call('project.import_analysis_apply', params)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(len(self.s.project_editor.history), history)

    def test_parser_comments_rounding_and_rate_column_order(self):
        params = self.workbook([self.codes[0]], rate_first=True)
        for position, note in ((0, 'above note'), (1, 'below note')):
            for rounding in (-1, 0, 1, 2, 1.5, 2.5):
                draft = import_analysis(ScheduleItemModel('target', 'Metadata', 'm'), dict(params, comment_position=position, rounding=rounding))
                self.assertEqual(draft.ana_items[0]['resource_list'][0][1:], [2, note])
                self.assertEqual(draft.ana_items[-1]['value'], 0 if rounding == -1 else rounding)

    def test_duplicates_unmatched_and_bounds(self):
        params = self.workbook([self.codes[0], self.codes[0]])
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            self.call('project.import_analysis_preview', params)
        params = self.workbook(['UNKNOWN'])
        preview = self.call('project.import_analysis_preview', params)
        self.assertEqual({k: preview[k] for k in ('matched', 'unmatched')}, dict(matched=[], unmatched=['UNKNOWN']))
        before = self.snapshot()
        history = len(self.s.project_editor.history)
        with self.assertRaisesRegex(ValueError, 'No workbook item codes match'):
            self.call('project.import_analysis_apply', params)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(len(self.s.project_editor.history), history)
        for invalid in ({'first_row': 0}, {'first_row': True}, {'first_column': 96}, {'last_row': 10001}):
            with self.assertRaises(ValueError):
                selected_rows(dict(params, **invalid), 6)

    def test_missing_sheet_oversize_and_invalid_number(self):
        params = self.workbook()
        with self.assertRaisesRegex(ValueError, 'Worksheet not found'):
            self.call('project.import_analysis_preview', dict(params, sheet='Absent'))
        book = Workbook()
        book.active.cell(10001, 1, 'too far')
        book.save(self.path)
        book.close()
        with self.assertRaisesRegex(ValueError, '10,000'):
            self.call('project.import_analysis_preview', params)
        self.workbook()
        from openpyxl import load_workbook
        book = load_workbook(self.path)
        book.active.cell(5, 4, 'invalid quantity')
        book.save(self.path)
        book.close()
        # Text in a number column no longer stops the import; it reads as 0.
        result = self.call('project.import_analysis_apply', params)
        self.assertTrue(result['matched'])

    def test_multiple_tables_without_say_terminators(self):
        params = self.workbook()
        from openpyxl import load_workbook
        book = load_workbook(self.path)
        for row in (24, 16, 8):
            book.active.delete_rows(row)
        book.save(self.path)
        book.close()
        preview = self.call('project.import_analysis_preview', params)
        self.assertEqual({k: preview[k] for k in ('matched', 'unmatched')}, dict(matched=self.codes, unmatched=['UNMATCHED']))
        self.call('project.import_analysis_apply', params)
        for code in self.codes:
            self.assertEqual(len(self.s.db.get_item(code, modify_res_code=False).resources), 1)
