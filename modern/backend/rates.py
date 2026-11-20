"""Bulk schedule-rate recalculation.

Gives ScheduleDatabase.update_rates' converged result (sub-analysis items
first, then the requested items) but reads the analyses in a few bulk queries
and evaluates each affected item once. update_rates rebuilds every item through
get_item (one query per resource row) SUB_ANA_SEARCH_DEPTH² times and only
propagates two sub-analysis levels per call; repeating it converges to the
values computed here.
"""

from estimator import misc
from estimator.data.schedule import ResourceItemModel, ScheduleItemModel


class Graph:
    """Codes and analysis links as plain integers/strings (raw SQL, no models)."""

    def __init__(self, db):
        S, R, RI = db.ScheduleTable, db.ResourceTable, db.ResourceItemTable
        sql = db.database.execute_sql
        self.schedule = {code: identity for identity, code in sql(f'SELECT "id", "{S.code.column_name}" FROM "{S._meta.table_name}"')}
        self.resource_code = dict(sql(f'SELECT "id", "{R.code.column_name}" FROM "{R._meta.table_name}"'))
        self.resource_id = {code: identity for identity, code in self.resource_code.items()}
        self.uses = {}
        for schedule_id, resource_id in sql(f'SELECT "{RI.id_sch.column_name}", "{RI.id_res.column_name}" FROM "{RI._meta.table_name}"'):
            self.uses.setdefault(schedule_id, set()).add(self.resource_code[resource_id])

    def dependents(self, resources=(), schedules=()):
        """Schedule codes whose rate depends on the given resources/schedules."""
        codes = {identity: code for code, identity in self.schedule.items()}
        users = {}
        for schedule_id, used in self.uses.items():
            for code in used:
                users.setdefault(code, set()).add(codes[schedule_id])
        affected, queue, seen = set(schedules), list(resources) + list(schedules), set()
        while queue:
            code = queue.pop()
            if code in seen:
                continue
            seen.add(code)
            for parent in users.get(code, ()):
                if parent not in affected:
                    affected.add(parent)
                    queue.append(parent)
        return affected

    def children(self, code):
        # A resource whose code is also a schedule item is a sub-analysis.
        return [child for child in self.uses.get(self.schedule.get(code), ()) if child in self.schedule and child != code]


def update_dependents(db, resources=(), schedules=()):
    graph = Graph(db)
    affected = graph.dependents(resources, schedules)
    if affected:
        recalculate_rates(db, affected, graph)


def recalculate_rates(db, codes, graph=None):
    codes = set(codes)
    if not codes:
        return
    graph = graph or Graph(db)
    S, R, RI, Q = db.ScheduleTable, db.ResourceTable, db.ResourceItemTable, db.SequenceTable
    # Sub-analysis closure, as get_sub_ana_items (bounded search depth).
    subs, frontier = set(), {code for code in codes if code in graph.schedule}
    for _ in range(misc.SUB_ANA_SEARCH_DEPTH):
        frontier = {child for code in frontier for child in graph.children(code)} - subs
        subs |= frontier
    # Children before parents so each sub-analysis sees updated resource rates.
    ordered, state = [], {}
    def visit(code):
        if state.get(code):
            return  # Done, or a cycle: keep the order reached.
        state[code] = 1
        for child in graph.children(code):
            if child in subs:
                visit(child)
        ordered.append(code)
    for code in sorted(subs):
        visit(code)
    targets = [code for code in sorted(codes) if code in graph.schedule]
    ids = list({graph.schedule[code] for code in ordered + targets})

    rates = {}
    for start in range(0, len(ids), 500):
        rates.update(S.select(S.id, S.rate).where(S.id.in_(ids[start:start + 500])).tuples())
    sequences, entries, used_ids = {}, {}, set()
    fields = [field.name for field in Q._meta.sorted_fields]
    for start in range(0, len(ids), 500):
        chunk = ids[start:start + 500]
        for values in Q.select().where(Q.id_sch.in_(chunk)).order_by(Q.id_sch, Q.id_seq).tuples():
            row = dict(zip(fields, values))
            sequences.setdefault(row["id_sch"], []).append(row)
        for sequence_id, resource_id, qty in RI.select(RI.id_seq, RI.id_res, RI.qty).where(RI.id_sch.in_(chunk)).order_by(RI.id).tuples():
            entries.setdefault(sequence_id, []).append((resource_id, qty))
            used_ids.add(resource_id)
    used_ids |= {graph.resource_id[code] for code in ordered if code in graph.resource_id}
    used_ids = list(used_ids)
    resources = {}
    for start in range(0, len(used_ids), 500):
        for identity, rate, vat, discount in R.select(R.id, R.rate, R.vat, R.discount).where(R.id.in_(used_ids[start:start + 500])).tuples():
            resources[identity] = [graph.resource_code[identity], rate, vat, discount]

    def evaluate(identity):
        model = ScheduleItemModel("", "", "", rates[identity])
        used = {}
        for seq in sequences.get(identity, []):
            kind = seq["itemtype"]
            if kind == ScheduleItemModel.ANA_GROUP:
                rows = []
                for resource_id, qty in entries.get(seq["id"], []):
                    code, rate, vat, discount = resources[resource_id]
                    rows.append([code, qty, ""])
                    used[code] = ResourceItemModel(code, "", "", rate, vat, discount)
                model.add_ana_group(seq["description"], rows, seq["code"])
            elif kind == ScheduleItemModel.ANA_SUM:
                model.add_ana_sum(seq["description"])
            elif kind == ScheduleItemModel.ANA_WEIGHT:
                model.add_ana_weight(seq["description"], seq["value"])
            elif kind == ScheduleItemModel.ANA_TIMES:
                model.add_ana_times(seq["description"], seq["value"])
            elif kind == ScheduleItemModel.ANA_ROUND:
                model.add_ana_round(seq["description"], seq["value"])
        model.resources = used
        model.evaluate_results()
        model.update_rate()
        return model.rate

    def store(identity):
        rate = evaluate(identity)
        if rate != rates[identity]:
            S.update(rate=rate).where(S.id == identity).execute()
            rates[identity] = rate
        return rate

    for code in ordered:
        rate = store(graph.schedule[code])
        resource_id = graph.resource_id.get(code)
        if resource_id is not None and resources[resource_id][1] != rate:
            R.update(rate=rate).where(R.id == resource_id).execute()
            resources[resource_id][1] = rate
    for code in targets:
        store(graph.schedule[code])
