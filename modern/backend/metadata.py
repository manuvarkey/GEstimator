"""Optional enrichment; source definitions remain authoritative."""

import json
import re
from collections import Counter
from peewee import DatabaseError


CATEGORY_NOTE = re.compile(r"^## Category: *(.+?) *$", re.MULTILINE)


def notes(db):
    """Database notes (Markdown in project settings) split for AI clients:
    (general text, {category name: text}). A level-2 heading "## Category: NAME"
    starts the notes of that category and runs to the next level-2 heading."""
    text = db.get_project_settings().get("project_metadata") or ""
    general, categories, position = [], {}, 0
    for match in CATEGORY_NOTE.finditer(text):
        general.append(text[position:match.start()])
        following = re.compile(r"^## ", re.MULTILINE).search(text, match.end())
        end = following.start() if following else len(text)
        categories[match.group(1)] = text[match.end():end].strip()
        position = end
    general.append(text[position:])
    return "".join(general).strip(), categories


def read(db):
    if "meta_enrichment" not in db.database.get_tables():
        return {}
    try:
        result = {}
        for scope, payload in db.database.execute_sql("SELECT scope, data FROM meta_enrichment"):
            value = json.loads(payload)
            if isinstance(value, dict) and value.get("schema") == 1:
                if any(key in value and not isinstance(value[key], dict) for key in ("database", "categories", "items", "provenance")):
                    continue
                if any(not isinstance(item, dict) for item in value.get("items", {}).values()):
                    continue
                if any(not isinstance(item.get("keywords", []), list) or not all(isinstance(word, str) for word in item.get("keywords", [])) for item in value.get("items", {}).values()):
                    continue
                if not isinstance(value.get("database", {}).get("summary", ""), str):
                    continue
                if scope == "database":
                    result.update(value)
                else:
                    result.setdefault("scopes", {})[scope] = value
        return result
    except (ValueError, TypeError, KeyError, DatabaseError):
        return {}  # An invalid optional document must not hide real source data.


def presentation(db):
    value = read(db)
    if not value:
        return None
    return dict(ai_generated=True, summary=value.get("database", {}).get("summary", ""),
                provenance=value.get("provenance", {}))


def write(db, value, scope="database"):
    if not isinstance(value, dict) or value.get("schema") != 1:
        raise ValueError("Enrichment must be a schema 1 object")
    if value.get("provenance", {}).get("generator") != "ai":
        raise ValueError("Generated enrichment must declare AI provenance")
    encoded = json.dumps(value, ensure_ascii=False)
    if len(encoded.encode()) > 2_000_000:
        raise ValueError("Enrichment exceeds 2 MB")
    db.database.execute_sql("CREATE TABLE IF NOT EXISTS meta_enrichment(scope TEXT PRIMARY KEY, data TEXT NOT NULL)")
    db.database.execute_sql("INSERT OR REPLACE INTO meta_enrichment VALUES (?, ?)", (scope, encoded))


def clear(db):
    if "meta_enrichment" in db.database.get_tables():
        db.database.execute_sql("DELETE FROM meta_enrichment")
    if "meta_embeddings" in db.database.get_tables():
        db.database.execute_sql("DELETE FROM meta_embeddings")


def short(row, enrichment=None):
    custom = (enrichment or {}).get("items", {}).get(row.code, {}).get("short")
    if isinstance(custom, str) and custom:
        return custom[:60]
    if hasattr(row, "parent_id") and row.parent_id:
        child = (row.description or "").replace("\n", " ")[:36]
        parent = re.split(r"[.;\n]", row.parent.description or "", maxsplit=1)[0]
        return parent[:max(0, 58 - len(child))] + ": " + child
    return (row.description or "").replace("\n", " ")[:60]


def categories(db, kind, enrichment=None):
    resource = kind == "resource"
    table = db.ResourceTable if resource else db.ScheduleTable
    groups = db.ResourceCategoryTable if resource else db.ScheduleCategoryTable
    result = []
    for category in groups.select().order_by(groups.order, groups.id):
        rows = list(table.select().where(table.category == category.id))
        units = dict(Counter(row.unit or "" for row in rows))
        parents = [r.description[:80] for r in rows if resource or not r.parent_id][:3]
        item = dict(name=category.description or "", count=len(rows), units=units, examples=parents)
        extra = (enrichment or {}).get("categories", {}).get(category.description, {})
        if isinstance(extra, dict) and extra:
            item["enrichment"] = extra
            item["ai_generated"] = True
        result.append(item)
    return result
