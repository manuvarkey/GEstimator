"""Per-source FTS5 indexes, with a dependency-free BM25 fallback."""

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3

from . import dictionary, metadata


def tokens(text):
    return re.findall(r"\w+", dictionary.normalize(text))


class Index:
    def __init__(self, rows, texts):
        self.rows, self.texts = rows, texts
        self.connection = sqlite3.connect(":memory:")
        self.fts = True
        try:
            self.connection.execute("CREATE VIRTUAL TABLE items USING fts5(text)")
            self.connection.executemany("INSERT INTO items(rowid,text) VALUES (?,?)", enumerate(texts, 1))
        except sqlite3.OperationalError:
            self.fts = False
        # Term counts serve only the BM25 fallback when SQLite lacks FTS5.
        self.counts = None if self.fts else [Counter(tokens(text)) for text in texts]

    def close(self):
        self.connection.close()
        if hasattr(self, "original"):
            self.original.close()

    def rank(self, query, limit, category=None):
        words = list(dict.fromkeys(tokens(query)))[:64]
        if not words:
            return []
        if self.fts:
            expression = " OR ".join('"' + word.replace('"', '""') + '"' for word in words)
            ranked = [(row - 1, -score) for row, score in self.connection.execute("SELECT rowid,bm25(items) FROM items WHERE items MATCH ? ORDER BY bm25(items)", (expression,))]
        else:
            n = len(self.counts)
            avg = sum(sum(c.values()) for c in self.counts) / max(n, 1)
            dfs = {word: sum(word in c for c in self.counts) for word in words}
            ranked = []
            for i, counts in enumerate(self.counts):
                score = 0
                for word in words:
                    tf = counts[word]
                    if tf:
                        idf = math.log(1 + (n - dfs[word] + .5) / (dfs[word] + .5))
                        score += idf * tf * 2.2 / (tf + 1.2 * (.25 + .75 * sum(counts.values()) / max(avg, 1)))
                if score:
                    ranked.append((i, score))
        results = []
        for i, score in ranked:
            row = self.rows[i]
            if category is not None and row["category"] != category:
                continue
            score *= 1.05 if row["unit"] else 1
            results.append(dict(row, score=round(score, 8)))
        return sorted(results, key=lambda r: (-r["score"], r["code"]))[:limit]


def heading_codes(code):
    """Dotted code prefixes, nearest first: 30.7.3.4 -> 30.7.3, 30.7, 30."""
    parts = code.split(".")
    return [".".join(parts[:end]) for end in range(len(parts) - 1, 0, -1)]


def heading_texts(rows):
    """Descriptions of unpriced headings above each item by code prefix that are
    not its parent (e.g. the title heading 30.7 over 30.7.3 and its children),
    so a search for heading words finds the priced children."""
    headings = {row.code: row.description or "" for row in rows if not row.rate}
    result = {}
    for row in rows:
        parent = row.parent.code if row.parent_id else None
        own = row.parent.description or "" if row.parent_id else ""
        texts = [headings[code] for code in heading_codes(row.code)
                 if code in headings and code != parent and headings[code] not in own]
        if texts:
            result[row.code] = texts
    return result


def search(service, db, kind, query, limit=20, category=None, user_path=None, use_dictionary=True):
    from .mcp_workspace import item_rows
    cache = getattr(service, "_mcp_search", {})
    key = (db.database_filename, kind, use_dictionary)
    user_text = Path(user_path).read_bytes() if user_path and Path(user_path).is_file() else b""
    builtin_text = b"".join(path.read_bytes() for path in sorted((Path(__file__).parent / "data" / "dictionary").glob("*.json")))
    signature = (dictionary.VERSION, service.revision if db is service.db else None,
                 db.database.connection().total_changes,
                 hashlib.sha256(builtin_text + user_text).hexdigest())
    old_signature, index = cache.get(key, (None, None))
    if signature != old_signature:
        enrichment = metadata.read(db)
        rows = item_rows(db, kind)
        source_text = "\n".join(r.description or "" for r in rows)
        entries = dictionary.entries(source_text, enrichment, user_path) if use_dictionary else []
        context = " ".join(dict.fromkeys(r.category.description or "" for r in rows))
        records, texts, originals = [], [], []
        # Edits change few rows; reuse normalized/expanded text of unchanged rows.
        memos = getattr(service, "_search_text_memo", {})
        memo_key = (key, dictionary.fingerprint(entries), context)
        previous = memos.get(memo_key, {})
        memo = {}
        above = heading_texts(rows) if kind == "schedule" else {}
        for row in rows:
            parent = row.parent.description if kind == "schedule" and row.parent_id else ""
            extra = enrichment.get("items", {}).get(row.code, {})
            text = " ".join([row.code, row.category.description or "", *above.get(row.code, ()), parent or "", row.description or "", row.unit or "", metadata.short(row, enrichment), " ".join(extra.get("keywords", []))])
            if text not in memo:
                memo[text] = previous.get(text) or (dictionary.normalize(text), dictionary.normalize(dictionary.expand(text, entries, context)))
            original, expanded = memo[text]
            originals.append(original)
            texts.append(expanded)
            records.append(dict(code=row.code, short=metadata.short(row, enrichment), unit=row.unit or "", rate=str(row.rate or 0), category=row.category.description or "", parent_code=row.parent.code if kind == "schedule" and row.parent_id else None))
        if index:
            index.close()
        index = Index(records, texts)
        index.entries, index.context = entries, context
        if use_dictionary:
            index.original = Index(records, originals)
        cache[key] = (signature, index)
        service._mcp_search = cache
        memos = {k: v for k, v in memos.items() if k[0] != key}
        memos[memo_key] = memo
        service._search_text_memo = memos
    expanded = dictionary.normalize(dictionary.expand(query, index.entries, index.context))
    if use_dictionary:
        # Expansion broadens recall; it must not overwhelm the user's original
        # terms. Fuse both rankings, weighting literal evidence more strongly.
        scores, candidates = {}, {}
        candidate_limit = max(100, limit)
        for weight, ranked in ((3, index.original.rank(query, candidate_limit, category)), (1, index.rank(expanded, candidate_limit, category))):
            for rank, row in enumerate(ranked, 1):
                candidates[row["code"]] = row
                scores[row["code"]] = scores.get(row["code"], 0) + weight / (60 + rank)
        matches = [dict(candidates[code], score=round(score, 8)) for code, score in sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))[:limit]]
    else:
        matches = index.rank(expanded, limit, category)
    exact = next((r for r in index.rows if r["code"].casefold() == query.strip().casefold() and (category is None or r["category"] == category)), None)
    if exact:
        matches = [dict(exact, score=(matches[0]["score"] + 1 if matches else 1))] + [r for r in matches if r["code"] != exact["code"]]
    return dict(items=matches[:limit], engine="fts5" if index.fts else "bm25", dictionary_version=dictionary.fingerprint(index.entries))


def desktop_codes(service, db, kind, query):
    """Shared ranked search, with partial-code lookup and substring fallback.

    Return all matching codes so callers can paginate before loading full ORM
    rows. Empty-query browsing remains the caller's normal project ordering.
    """
    from .program_settings import library_directory
    resource = kind in ("resources", "resource")
    table = db.ResourceTable if resource else db.ScheduleTable
    category = db.ResourceCategoryTable if resource else db.ScheduleCategoryTable
    result = search(service, db, "resource" if resource else "schedule", query,
                    max(1, table.select().count()), user_path=library_directory().parent / "dictionary.user.json")
    folded = query.strip().casefold()
    code_matches = [row.code for row in table.select(table.code).where(table.code.contains(query.strip()))]
    code_matches.sort(key=lambda code: (code.casefold() != folded, not code.casefold().startswith(folded), code.casefold()))
    ranked = [row["code"] for row in result["items"]]
    # Retain infix matching for users entering only part of a word or category.
    fallback = [row.code for row in table.select(table.code).join(category).where(
        table.description.contains(query.strip()) | category.description.contains(query.strip())
    ).order_by(category.order, table.order, table.id)]
    return list(dict.fromkeys([*code_matches, *ranked, *fallback])), result["engine"]
