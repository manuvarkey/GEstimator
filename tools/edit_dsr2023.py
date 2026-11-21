"""Edits applied to estimator/database/DSR2023.eproj after tools/build_dsr2023.py (kept for reference).

The database was not rebuilt: the user had already edited 2.5 and 2.25A in it. This script, run once
on that database on 2026-11-22, applies:
- basic rates 0006 (Rs 250) and 7512 (Rs 23) from the printed book (the source had 9750 and 0);
- analyses corrected to DAR 2023: 5.1.3A, 13.41.1, 13.46.1, 13.47.1, 17.7A, 18.53A, 7.16, water charges
  in 13.114, 13.116, 14.78; sub-analyses at schedule rate for 4.5.1A-4.7.1A (Sub A/R-1), 5.12A (Sub AR-2)
  and 5.48.3 (5.48.3X);
- carriage analyses as in DSR 2021 from DAR 2023 Data Sheet 1: trip sub-analyses 1.1.A-1.1.E, per-km
  1.1.X-1.1.Z, manual day rates 1.2.A-1.2.D, and the analyses of 1.1.1-1.1.17.12 and 1.2.1-1.2.17.10;
- 2.25A uses item 1.1.2 in place of its own sub-analysis.
Usage: python tools/edit_dsr2023.py <eproj>   (do not run twice)"""
import sys
from decimal import Decimal as D
sys.path.insert(0, '.')
from estimator import misc
from estimator.data.schedule import ScheduleDatabase, ScheduleItemModel as M, ResourceItemModel
from estimator.undo import Stack

db = ScheduleDatabase(Stack())
db.open_database(sys.argv[1])
R, RC, T = db.ResourceTable, db.ResourceCategoryTable, db.ScheduleTable
GST = D('0.2127')
log = []


def res(code):
    r = R.select(R, RC).join(RC).where(R.code == code).first()
    return ResourceItemModel(r.code, r.description, r.unit, r.rate, r.vat, r.discount, r.reference, r.category.description)


def sub_res(code, description, unit, rate):
    """Resource standing for a schedule item (category SUB ANALYSIS)."""
    row = R.get_or_none(R.code == code)
    if row:
        R.update(rate=rate, unit=unit).where(R.id == row.id).execute()
        return res(code)
    return ResourceItemModel(code, description, unit, rate, D(0), D(0), '', misc.SUB_ANA_TITLE)


def chain(m, water=True, label='W'):
    m.add_ana_sum(f'TOTAL ({label})')
    if water:
        m.add_ana_weight(f'Add 1 % water charges on "{label}"', D('0.01'))
        m.add_ana_sum('TOTAL (X)')
    m.add_ana_weight(f'Add GST on "X" (multiplying factor {GST})', GST)
    m.add_ana_sum('TOTAL (Y)')
    m.add_ana_weight('Add 15 % CP & OH on "Y"', D('0.15'))
    m.add_ana_sum('TOTAL (Z)')
    m.add_ana_weight('Add cess @ 1 % on "Z"', D('0.01'))
    m.add_ana_sum('TOTAL')


def save(code, groups, *, oh=True, water=True, a_rows=(), per=None, per_text=None, say=2.5, rate=None,
         ana_remarks=None, remarks=None, extra=None, new=None):
    """Replace the analysis of `code` (or insert `new`, a ScheduleItemModel without analysis).
    groups: [(name, [(resource, qty, remark)])], a_rows after the overheads, per: cost basis to divide by."""
    m = new or db.get_item(code, modify_res_code=False)
    m.ana_items, m.resources = [], {}
    resources = dict(extra or {})
    def rows(lst):
        out = []
        for c, q, rem in lst:
            if c not in resources:
                resources[c] = res(c)
            out.append([c, D(str(q)), rem or ''])
        return out
    for name, lst in groups:
        m.add_ana_group(name, rows(lst))
    if oh:
        chain(m, water, 'W-A' if a_rows else 'W')
    else:
        m.add_ana_sum(f'Cost for {per} {per_text}' if per else 'TOTAL')
    if a_rows:
        m.add_ana_group('ITEMS AT SCHEDULE RATES (A), INCLUSIVE OF OVERHEADS', rows(a_rows))
        m.add_ana_sum('TOTAL')
    if per is not None and per != 1:
        if oh or a_rows:
            m.add_ana_sum(f'Cost for {per} {per_text}')
        m.add_ana_times(f'Cost for 1 {m.unit}' if per_text else 'Cost for 1 unit', D(1) / D(str(per)))
    if say:
        m.add_ana_round('Say', say)
    m.resources = resources
    m.evaluate_results()
    value = D(m.get_ana_rate())
    m.rate = rate if rate is not None else value
    if ana_remarks is not None:
        m.ana_remarks = ana_remarks
    if remarks is not None:
        m.remarks = remarks
    if not db.insert_item_atomic(m, update=new is None):
        raise SystemExit(f'{code} not saved')
    log.append((code, m.rate, value))
    return value


def book(code):
    return T.get(T.code == code).rate


def clear_remark(code):
    T.update(remarks='').where((T.code == code) & (T.remarks.startswith('The analysis gives'))).execute()


# ---------------------------------------------------------------- basic rates (printed book)
R.update(rate=250).where(R.code == '0006').execute()
R.update(rate=23).where(R.code == '7512').execute()

# ---------------------------------------------------------------- water charges restored (13.114, 13.116, 14.78)
for code in ('13.114', '13.116', '14.78', '9.106.1'):
    m = db.get_item(code, modify_res_code=False)
    groups = [(e['description'], [(c, q, rem) for c, q, rem in e['resource_list']]) for e in m.ana_items if e['itemtype'] == 0]
    times = [e for e in m.ana_items if e['itemtype'] == 3]
    per = (D(1) / D(str(times[0]['value']))).quantize(D('0.001')).normalize() if times else None
    save(code, groups, per=per, per_text=m.unit, rate=book(code))
    clear_remark(code)

# ---------------------------------------------------------------- lines corrected to DAR 2023
m = db.get_item('5.1.3A', modify_res_code=False)
for e in m.ana_items:
    if e['itemtype'] == 0:
        e['resource_list'] = [[c, D('0.356') if c == '0982' else q, rem] for c, q, rem in e['resource_list']]
groups = [(e['description'], e['resource_list']) for e in m.ana_items if e['itemtype'] == 0]
save('5.1.3A', groups, rate=book('5.1.3A')); clear_remark('5.1.3A')

save('13.41.1', [('MATERIAL', [('0808', '0.70', ''), ('9988', '8.06', 'Sundries for brushes, sand paper and putty, including carriage for primer'),
                               ('0802', '1.25', ''), ('9988', '8.06', 'Sundries for brushes, sand paper, including carriage for distemper')]),
                 ('LABOUR', [('0131', '1', ''), ('0115', '0.5', '')])], per=10, per_text='sqm', rate=book('13.41.1'))
for code, paint, qty in (('13.46.1', '8505', '1.67'), ('13.47.1', '8506', '1.43')):
    save(code, [('MATERIAL', [(paint, qty, ''), ('0837', '0.90', ''), ('9977', '1.56', 'Carriage of material')]),
                ('LABOUR', [('0131', '0.60', ''), ('0115', '0.30', ''), ('0101', '0.05', ''),
                            ('9999', '8.06', 'Sundries for brushes, sand paper and putty for filling holes')])],
         per=10, per_text='sqm', rate=book(code))
for code in ('13.41.1', '13.46.1', '13.47.1'):
    clear_remark(code)

save('17.7A', [('MATERIAL', [('3229', 1, ''), ('9001', 1, ''), ('1951', 1, ''), ('1309', 1, ''),
                             ('9999', '16.12', 'Red lead, white lead and gasket'), ('9999', '13.39', 'Cement, sand and grit etc.'),
                             ('9999', '26.91', 'Painting of brackets, fittings etc.'), ('9977', '13.52', 'Carriage of materials'),
                             ('9999', '53.82', 'Fixing charges')])], rate=book('17.7A'))
clear_remark('17.7A')
save('18.53A', [('MATERIAL', [('0593', 1, ''), ('9999', '2.89', 'Sundries')])], rate=book('18.53A'))
clear_remark('18.53A')
save('7.16', [('MACHINERY', [('0037', '0.125', '')])], per='5.3', per_text='cum', rate=book('7.16'),
     ana_remarks='Details of cost for 5.3 cum per four floors')
clear_remark('7.16')

# ---------------------------------------------------------------- sub-analyses at schedule rate (DAR "A" items)
# Sub A/R-1 (ref 11.7): CC pavement with RCA 25 %, 4.1.2A + extra labour, overheads on the labour.
v = save('4.5.1A.SA1', [('EXTRA LABOUR FOR LAYING IN FLOORS ETC.', [('0124', '0.35', ''), ('0114', '0.18', ''), ('0101', '0.05', ''), ('9999', '19.76', 'Sundries')])],
         a_rows=[('4.1.2A', 1, 'Cement concrete 1:1.5:3')], extra={'4.1.2A': sub_res('4.1.2A', 'Rate as per item 4.1.2A', 'cum', book('4.1.2A'))},
         remarks='Sub A/R-1 of DAR 2023 (reference item 11.7), at schedule rate including overheads. Used in 4.5.1A, 4.6.1A, 4.7.1A.')
sub_res('4.5.1A.SA1', '', 'cum', v)
for code in ('4.5.1A', '4.6.1A', '4.7.1A'):
    m = db.get_item(code, modify_res_code=False)
    groups, a_rows, per = [], [], None
    for e in m.ana_items:
        if e['itemtype'] == 0:
            keep = [(c, q, rem) for c, q, rem in e['resource_list'] if c != '4.5.1A.SA1']
            moved = [(c, q, rem) for c, q, rem in e['resource_list'] if c == '4.5.1A.SA1']
            if e['description'].startswith('ITEMS AT SCHEDULE'):
                a_rows += keep + moved
            else:
                a_rows += moved
                if keep:
                    groups.append((e['description'], keep))
        elif e['itemtype'] == 3:
            per = (D(1) / D(str(e['value']))).quantize(D('0.001')).normalize()
    save(code, groups, a_rows=a_rows, per=per, per_text=m.unit, rate=book(code))
    clear_remark(code)

# Sub AR-2 (ref 4.5.1), RCA 20 %: per 4.5 cum, concrete 5.4A.SA1 (Sub AR-1 ref 4.1.2) and 5.12A.SA1.SA1 (Sub AR-3 ref 11.7)
# bare with the overheads on them, mould 10.1 and platform 11.1.2 at schedule rate.
v = save('5.12A.SA1', [('MATERIAL', [('5.4A.SA1', '4.5', 'Cement concrete 1:1.5:3 (Sub AR-1, reference item 4.1.2)'),
                                     ('0115', '5.1', 'Extra labour for lifting 4.5 x 0.75 x 1.50 = 5.1'),
                                     ('5.12A.SA1.SA1', '0.025', 'Moulding platform: 25 mm cement concrete, 1/40 of 1 cum (Sub AR-3, reference item 11.7)'),
                                     ('9999', '363', 'Mortar and labour for hoisting and finishing')])],
         a_rows=[('10.1', '2.1', 'Mould: steel for using once'), ('11.1.2', '1', 'Moulding platform: brick on edge for using once')],
         per='4.5', per_text='cum', extra={'10.1': sub_res('10.1', 'Rate as per item 10.1', 'kg', book('10.1')),
                                          '11.1.2': sub_res('11.1.2', 'Rate as per item 11.1.2', 'sqm', book('11.1.2'))},
         ana_remarks='Details of cost for plain window sills 150 nos. = 4.5 cum',
         remarks='Sub AR-2 of DAR 2023 (based on item 4.5.1, RCA up to 20 %), at schedule rate including overheads. Used in 5.12A.')
sub_res('5.12A.SA1', '', 'cum', v)
save('5.12A', [('LABOUR', [('0114', '0.10', 'Extra labour for laying CC in RCC work'), ('0101', '0.20', ''), ('0123', '0.04', ''),
                           ('0124', '0.04', ''), ('0128', '0.04', '')])],
     a_rows=[('5.12A.SA1', 1, 'Cement concrete 1:1.5:3 in string or lacing courses etc., including fixing (Sub AR-2)')], rate=book('5.12A'))
clear_remark('5.12A')

# 5.48.3X: M60 SCC per 120 cum = lot 5.48.3.SA1.SA1 (P) + 11 % formwork + 1.4 % extra lift, with overheads.
m = db.get_item('5.48.3.SA1.SA1', modify_res_code=False)
groups = [(e['description'], [(c, q, rem) for c, q, rem in e['resource_list'] if c != '8716']) for e in m.ana_items if e['itemtype'] == 0]
lot = save('5.48.3.SA1.SA1', groups, oh=False, say=None, remarks=m.remarks)
sub_res('5.48.3.SA1.SA1', '', m.unit, lot)
v = save('5.48.3.SA1', [('MATERIAL', [('5.48.3.SA1.SA1', 1, 'M 60 grade RCC data (lot) for 120 cum (P)'),
                                      ('5.48.3.SA1.SA1', '0.11', 'Add 11 % of P for formwork'),
                                      ('5.48.3.SA1.SA1', '0.014', 'Add 1.4 % of P for extra lift')])],
         per=120, per_text='cum', ana_remarks='Details of cost for 120 cum',
         remarks='Sub-analysis 5.48.3X of DAR 2023, at schedule rate including overheads. Used in 5.48.3.')
sub_res('5.48.3.SA1', '', 'cum', v)
save('5.48.3', [('MATERIAL', [('5.48.3.SA1', 1, 'M 60 grade self-compacting RCC (sub-analysis 5.48.3X)'),
                              ('5.48.2', -1, 'Deduct M 60 grade RCC (item 5.48.2)')])], oh=False, rate=book('5.48.3'))
clear_remark('5.48.3')

# ---------------------------------------------------------------- carriage, as DSR 2021: trip sub-analyses + items
TRIPS = {1: ('16.00', '7.11', '4.04'), 2: ('17.00', '6.48', '6.38'), 3: ('17.50', '5.96', '8.35'), 4: ('18.00', '5.54', '10.06'),
         5: ('18.50', '5.19', '11.58'), 10: ('21.00', '4.10', '17.60'), 20: ('26.00', '3.15', '26.40'), 30: ('31.00', '2.73', '33.96')}
TRUCK = lambda lead: [('LABOUR', [('0084', 1, 'Hire charges of truck without POL'), ('0114', 6, '')]),
                      ('MATERIAL', [('1235', TRIPS[lead][2], f'Diesel at 5 km per litre, average speed {TRIPS[lead][0]} km/h')])]


def new_item(code, description, unit, parent):
    return M(code, description, unit, 0, 1, category='CARRIAGE OF MATERIALS', parent=parent, remarks='')


subs = {}
for letter, lead in zip('ABCDE', (1, 2, 3, 4, 5)):
    code = f'1.1.{letter}'
    v = save(code, TRUCK(lead), oh=False, per=TRIPS[lead][1], per_text='trips', say=2,
             new=new_item(code, f'Rate of 1 trip for {lead} km lead (sub-analysis)', 'trip', '1.1'),
             ana_remarks=f'Details of cost for {TRIPS[lead][1]} trips of 9 tonne truck in an 8 hour day (DAR 2023 Data Sheet 1)')
    subs[code] = sub_res(code, f'Rate of 1 trip for {lead} km lead', 'trip', v)


def per_km(code, lead, deduct, step, text):
    groups = TRUCK(lead)
    m = new_item(code, text, 'km', '1.1')
    m.ana_items, resources = [], {c: res(c) for c in ('0084', '0114', '1235')}
    resources.update({c: subs[c] for c, _ in deduct})
    for name, lst in groups:
        m.add_ana_group(name, [[c, D(str(q)), r] for c, q, r in lst])
    m.add_ana_sum(f'Cost for {TRIPS[lead][1]} trips')
    m.add_ana_times(f'Cost per trip for {lead} km lead', D(1) / D(TRIPS[lead][1]))
    m.add_ana_group(f'DEDUCT COST PER TRIP FOR {lead - step} KM LEAD', [[c, D(str(q)), ''] for c, q in deduct])
    m.add_ana_sum('TOTAL')
    m.add_ana_times('Rate per km', D(1) / D(step))
    m.add_ana_round('Say', 2)
    m.resources = resources
    m.evaluate_results()
    m.rate = D(m.get_ana_rate())
    m.ana_remarks = f'Details of cost for {TRIPS[lead][1]} trips of 9 tonne truck for {lead} km lead (DAR 2023 Data Sheet 1)'
    if not db.insert_item_atomic(m):
        raise SystemExit(code)
    log.append((code, m.rate, m.rate))
    subs[code] = sub_res(code, text, 'km', m.rate)


per_km('1.1.X', 10, [('1.1.E', -1)], 5, 'Average cost per trip per additional km beyond 5 km up to 10 km lead (sub-analysis)')
per_km('1.1.Y', 20, [('1.1.E', -1), ('1.1.X', -5)], 10, 'Average cost per trip per additional km beyond 10 km up to 20 km lead (sub-analysis)')
per_km('1.1.Z', 30, [('1.1.E', -1), ('1.1.X', -5), ('1.1.Y', -10)], 10, 'Average cost per trip per additional km beyond 20 km lead (sub-analysis)')

MANUAL = {'1.2.A': ('0114', '7.67', 'Rate for manual carriage for first 50 m, per day (lime, earth, sand, aggregate, bricks, coal)'),
          '1.2.B': ('0115', '1.67', 'Rate for manual carriage for each additional 50 m, per day (lime, earth, sand, aggregate, bricks, coal)'),
          '1.2.C': ('0114', '9.20', 'Rate for manual carriage for first 50 m, per day (heavy materials, cement, steel, timber, pipes)'),
          '1.2.D': ('0114', '1.35', 'Rate for manual carriage for each additional 50 m, per day (heavy materials, cement, steel, timber, pipes)')}
for code, (labour, qty, text) in MANUAL.items():
    v = save(code, [('LABOUR', [(labour, qty, '')])], oh=False, say=2, new=new_item(code, text + ' (sub-analysis)', 'day', '1.2'),
             ana_remarks='Labour for an 8 hour day (DAR 2023 data sheet for 1.2)')
    subs[code] = sub_res(code, text, 'day', v)

MECH = {'1.1.1': (8, 8), '1.1.2': (8, '6.4'), '1.1.3': (8, '7.36'), '1.1.4': (8, 4), '1.1.5': (8, 8), '1.1.6': (8, '7.36'),
        '1.1.7': (8, '6.8'), '1.1.8': ('3000 bricks', 3), '1.1.9': ('5000 brick tiles', 5), '1.1.10': (9, 9), '1.1.11': (9, 9),
        '1.1.12': (7, 7), '1.1.13': (8, 8), '1.1.14': (80, 80), '1.1.15': (7, 7)}
for i, m_ in zip((1, 2, 3, 5, 6, 7, 8, 9, 10, 11), (600, 300, 180, 105, 84, 60, 42, 33, 30, 24)):
    MECH[f'1.1.16.{i}'] = (f'{m_} m', D(m_) / 100)
for i, m_ in enumerate(('366', '274', '219.6', '135', '95', '76.86', '54.9', '40.26', '32.94', '21.96', '14.64', '10.98'), 1):
    MECH[f'1.1.17.{i}'] = (f'{m_} m', D(m_) / 100)
mech_rows = [('1.1.A', 0), ('1.1.B', 0), ('1.1.C', 0), ('1.1.D', 0), ('1.1.E', 1), ('1.1.X', 0), ('1.1.Y', 0), ('1.1.Z', 0)]
for code, (capacity, net) in MECH.items():
    unit = T.get(T.code == code).unit
    save(code, [('RESOURCE', [(c, q, '') for c, q in mech_rows])], water=False, per=net, per_text=unit, say=2, rate=book(code),
         extra=subs, ana_remarks=f'Details of cost for one truck load of capacity {capacity}' + (f' {unit}' if isinstance(capacity, int) else '')
         + f' (net {net} {unit} after deduction for looseness). Lead: quantity 1 against the trip rate of the lead (1.1.A–1.1.E); '
         'beyond 5 km add the km beyond 5 against 1.1.X (up to 10 km), 1.1.Y (10–20 km), 1.1.Z (beyond 20 km).')

MAN = {'1.2.1': '35', '1.2.2': '28', '1.2.3': '32.2', '1.2.4': '17.5', '1.2.5': '28', '1.2.6': '25.9', '1.2.7': '23.8',
       '1.2.8': '15', '1.2.9': '24', '1.2.10': '30', '1.2.11': '46', '1.2.12': '57.99', '1.2.13': '27', '1.2.14': '42', '1.2.15': '46'}
for i, m_ in zip((1, 2, 3, 5, 6, 7, 8, 9, 10, 11), (2298, 1398, 999, 600, 420, 300, 240, 198, 162, 132)):
    MAN[f'1.2.16.{i}'] = D(m_) / 100
for i, m_ in enumerate((1702, 1391, 1208, 805, 458, 366, 256, 220, 165, 150), 1):
    MAN[f'1.2.17.{i}'] = D(m_) / 100
for code, net in MAN.items():
    unit = T.get(T.code == code).unit
    first, extra_ = ('1.2.A', '1.2.B') if int(code.split('.')[2]) <= 10 else ('1.2.C', '1.2.D')
    save(code, [('RESOURCE', [(first, 1, ''), (extra_, 0, '')])], water=False, per=net, per_text=unit, say=2, rate=book(code), extra=subs,
         ana_remarks=f'Details of cost for {net} {unit} carried in one 8 hour day for the first 50 m. For each additional 50 m '
         f'(up to 9) add 1 against {extra_}.')

# ---------------------------------------------------------------- 2.25A uses item 1.1.2 (as DAR 2023 and DSR 2021)
m = db.get_item('2.25A', modify_res_code=False)
item11 = sub_res('1.1.2', 'Rate as per item 1.1.2: carriage of earth by mechanical transport', 'cum', book('1.1.2'))
for e in m.ana_items:
    if e['itemtype'] == 0:
        e['resource_list'] = [['1.1.2' if c == '2.25A.SA1' else c, q, 'Carriage of earth up to 5 km (item 1.1.2)' if c == '2.25A.SA1' else rem]
                              for c, q, rem in e['resource_list']]
m.resources.pop('2.25A.SA1', None)
m.resources['1.1.2'] = item11
if not db.insert_item_atomic(m, update=True):
    raise SystemExit('2.25A')
T.get(T.code == '2.25A.SA1').delete_instance()
for code in ('2.25A.SA1', '3229A', '7407A'):
    row = R.get_or_none(R.code == code)
    if row and not db.ResourceItemTable.select().where(db.ResourceItemTable.id_res == row.id).exists():
        row.delete_instance()
        log.append((code, 'resource deleted', ''))

# Resources of edited sub-analyses take their item rates.
for code in ('4.5.1A.SA1', '5.12A.SA1', '5.48.3.SA1', '5.48.3.SA1.SA1', '1.1.2'):
    R.update(rate=T.get(T.code == code).rate).where(R.code == code).execute()

db.close_database()
for code, rate, value in log:
    flag = '' if not isinstance(value, D) or abs(D(str(rate)) - value) <= D('0.05') else '   <-- differs'
    print(f'{code:16} rate {rate}  analysis {value}{flag}')
