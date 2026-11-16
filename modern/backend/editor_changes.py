"""Connection-local change journal for incremental desktop table refreshes.

TEMP triggers observe the original engine's writes without changing the .eproj
format. Entries roll back with failed transactions; backup restores explicitly
invalidate cached views because SQLite backup does not fire row triggers.
"""


class EditorChanges:
    def __init__(self, db):
        self.db = db
        self.sql("CREATE TEMP TABLE IF NOT EXISTS editor_changes(seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, row_id INTEGER, structural INTEGER)")
        for kind, model, structure in (
            ("schedule", db.ScheduleTable, ("code", "unit", "category_id", "parent_id", "order", "suborder")),
            ("resources", db.ResourceTable, ("code", "category_id", "order")),
            ("schedule", db.ScheduleCategoryTable, None),
            ("resources", db.ResourceCategoryTable, None),
        ):
            name = model._meta.table_name
            columns = [field.column_name for field in model._meta.sorted_fields if field.column_name != "id"]
            changed = " OR ".join(f'old."{column}" IS NOT new."{column}"' for column in columns)
            structural = "1" if structure is None else " OR ".join(f'old."{column}" IS NOT new."{column}"' for column in structure)
            for event, row, condition, flag in (("INSERT", "new", "1", "1"), ("DELETE", "old", "1", "1"), ("UPDATE", "new", changed, structural)):
                self.sql(f'''CREATE TEMP TRIGGER IF NOT EXISTS "editor_{name}_{event}" AFTER {event} ON main."{name}" WHEN {condition}
                    BEGIN INSERT INTO editor_changes(kind,row_id,structural) VALUES ('{kind}',{row}.id,({flag})); END''')

    def sql(self, sql, params=()):
        return self.db.database.execute_sql(sql, params)

    @property
    def sequence(self):
        return self.sql("SELECT coalesce(max(seq),0) FROM editor_changes").fetchone()[0]

    def invalidate(self):
        for kind in ("schedule", "resources"):
            self.sql("INSERT INTO editor_changes(kind,row_id,structural) VALUES (?,-1,1)", (kind,))

    def changed_ids(self, kind, since, query):
        if type(since) is not int or since < 0 or since > self.sequence:
            return None
        rows = self.sql("SELECT row_id,structural FROM editor_changes WHERE kind=? AND seq>?", (kind, since)).fetchall()
        if any(structural for _, structural in rows) or query and rows:
            return None
        return {identity for identity, _ in rows}
