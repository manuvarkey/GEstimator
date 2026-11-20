import unittest
from modern.backend.service import Service


class ParityCommands(unittest.TestCase):
    def setUp(self):
        self.service = Service()
        self.service.call('project.new', {})

    def tearDown(self):
        self.service.close()

    def call(self, method, **params):
        return self.service.call(method, dict(revision=self.service.revision, **params))

    def test_renumber_exclusions_identity_and_undo(self):
        a = self.call('resources.editor.add', data=dict(code='OLD', category='Materials', rate='7'))['selected'][0]
        b = self.call('resources.editor.add', data=dict(code='LIB:R', category='Materials', rate='8'))['selected'][0]
        self.call('resources.editor.renumber', exclude=['LIB'])
        table = self.service.db.ResourceTable
        self.assertEqual(table.get_by_id(a).code, '001')
        self.assertEqual(table.get_by_id(b).code, 'LIB:R')
        self.call('project.undo')
        self.assertEqual(table.get_by_id(a).code, 'OLD')
        self.call('project.redo')
        self.assertEqual(table.get_by_id(a).code, '001')

    def test_schedule_sync_preserves_definition_and_undo(self):
        self.call('schedule.editor.add', data=dict(code='S', unit='m', rate='25'))
        a = self.call('resources.editor.add', data=dict(code='S', description='Keep', rate='7', vat='5'))['selected'][0]
        self.call('resources.editor.sync_schedule', ids=[a])
        row = self.service.db.ResourceTable.get_by_id(a)
        self.assertEqual(float(row.rate), 25)
        self.assertEqual(row.description, 'Keep')
        self.assertEqual(float(row.vat), 5)
        self.call('project.undo')
        self.assertEqual(float(self.service.db.ResourceTable.get_by_id(a).rate), 7)

    def test_missing_analysis_read_only(self):
        a = self.call('schedule.editor.add', data=dict(code='S', unit='m', rate='25', colour='#123456'))['selected'][0]
        revision = self.service.revision
        result = self.call('schedule.editor.discrepancies')
        self.assertEqual(result['counts']['missing'], 1)
        self.assertEqual(result['rows'][0]['band'], 'missing')
        self.assertEqual(self.service.revision, revision)
        self.assertEqual(float(self.service.db.ScheduleTable.get_by_id(a).rate), 25)

    def test_discrepancy_boundaries_and_saved_colours(self):
        from decimal import Decimal
        from estimator.data.schedule import ScheduleItemModel, ResourceItemModel
        for code, difference in [('equal', '0'), ('small', '.10'), ('medium', '1'), ('large', '1.01')]:
            item = ScheduleItemModel(code, code, 'm', Decimal('10') + Decimal(difference), Decimal('1'), category='Work')
            item.resources = {'R': ResourceItemModel('R', 'Material', 'kg', Decimal('10'), category='Materials')}
            item.add_ana_group('Materials', code='M')
            item.add_ana_res(['R', Decimal('1'), ''], 0)
            item.add_ana_sum('Total')
            self.service.db.insert_item(item)
            self.service.db.update_item_colour([code], '#123456')
        result = self.call('schedule.editor.discrepancies')
        self.assertEqual({r['code']: r['band'] for r in result['rows']}, {v: v for v in ['equal', 'small', 'medium', 'large']})
        self.assertEqual(result['counts']['mismatch'], 3)
        self.assertEqual(result['revision'], self.service.revision)
        self.assertTrue(all(row.colour == '#123456' for row in self.service.db.ScheduleTable.select()))

    def test_renumber_preserves_analysis_reference(self):
        from decimal import Decimal
        from estimator.data.schedule import ScheduleItemModel, ResourceItemModel
        item = ScheduleItemModel('A', 'Work', 'm', Decimal('20'), Decimal('1'), category='Work')
        item.resources = {'R': ResourceItemModel('R', 'Material', 'kg', Decimal('10'), category='Materials')}
        item.add_ana_group('Materials', code='M')
        item.add_ana_res(['R', Decimal('2'), ''], 0)
        item.add_ana_sum('Total')
        self.service.db.insert_item(item)
        resource_id = self.service.db.ResourceTable.get().id
        self.call('resources.editor.renumber', exclude=[])
        model = self.service.db.get_item('A', modify_res_code=False)
        self.assertIn('001', model.resources)
        self.assertEqual(model.get_ana_rate(), Decimal('20'))
        self.assertEqual(self.service.db.ResourceTable.get().id, resource_id)
        self.call('project.undo')
        self.assertIn('R', self.service.db.get_item('A', modify_res_code=False).resources)
