# MCP efficiency: rationalized tools, optional metadata and search

Implementation brief for AI coding tools. This brief covers changes to `modern/backend` only. It must work for **any** `.eproj` database: bundled, custom or user-made. Nothing here may require users to write metadata.

**This is a breaking change.** The current 120 tools (113 operations plus 7 legacy aliases) are replaced by the **19 tools** below. There is no backward-compatibility toolset. The application adapters in `mcp_operations.py` remain as internal functions; only the tools exposed to MCP clients change.

## Why

A trial session built an E&M estimate for a typical house through the current server. It needed about 150 tool calls and about 6–7M input tokens (mostly cached). The main causes were:

| Cause | Cost |
|---|---|
| `tools/list` has 120 tools and is about 61 KB; ~100 descriptions repeat the same revision sentence; several tools are duplicates or legacy aliases | ~14k tokens on every turn |
| Every result is sent twice, as `content[].text` and as `structuredContent` | ~2× result tokens |
| A `get_project` call is needed before every write to get the revision | 2× round trips |
| `add_from_library` drops parent items; new items go to the end of a category; `move` only steps ±1 | ~90 calls to rebuild the hierarchy |
| There is no search by meaning, so all 1,337 items were dumped to find the right ones | ~12k tokens |
| Trade abbreviations (TPN, RCCB, FRLS, DPC, SWG) don't match plain-language queries | missed matches |
| `measurement.templates` lists inputs that don't match the real `cN` fields (NLBH has a read-only `Breakup` at `c1`) | a failed build |
| One measurement sheet takes four calls (add, properties, record_add, record_edit_many) | many round trips |
| Errors are bare strings (`Cell is not editable`) | trial and error |
| Dotted tool names (`schedule.editor.add`) break the Claude API rule for tool names (`^[a-zA-Z0-9_-]{1,64}$`) | possible client-side renaming |

**Targets**
- `tools/list` is at most **4k tokens**.
- A typical estimate takes at most **20 calls**.
- No result is duplicated.
- Every listing is compact by default.

## Principles

1. **One small toolset.** 19 tools named in `snake_case`, each matching one thing an agent sets out to do. Variants become an `action`/`kind`/`ops` argument, not a separate tool.
2. **Codes are the identifiers.** Agents address schedule and resource items by `code` within a `source`. Measurement items use the stable IDs the server returns.
3. **A source is any database.** `source` is `"project"` (the default), an attached ID, `"bundled:<file>"` or a `.eproj` path. Naming one that isn't attached attaches it automatically as a read-only snapshot. Copying between projects uses `import_items` with another `.eproj` as the source.
4. **One call per intent.** Load + edit + apply an analysis, and create + link + fill a measurement sheet, each happen atomically. `batch` makes any list of writes one undo step.
5. **The revision check is optional.** Writes accept `if_revision`: when given, a stale write is rejected; when left out, the write applies to the latest state. Every write returns the new `revision`. This is stated once in the server instructions.
6. **Compact by default.** `fields: "compact" | "full"`. Compact rows leave out long descriptions.
7. **Files are read by the server.** Workbook imports pass a path and a range, so large sheets never go through the model.
8. **Metadata is optional everywhere** (see below). AI-generated content is labelled as such and never overrides the source data.
9. **No duplicate variants.** Each tool exists once: no aliases, no `_for_cli` copies, no legacy names. Client differences are handled in the transport, never by repeating tools.
10. **Typed tools first, one read-only fallback.** Common tasks have typed tools. Anything else that is read-only goes through `query` (tool 19) instead of a new tool. There is no general code or shell execution.
11. **Guidance comes from the server, documentation on request.** The server instructions are a short guide to which tool to use when (see Server instructions). Database documentation and dictionaries come from `describe_source` only when asked, never in tool descriptions.

Comparable MCP servers keep their tool lists small this way. Two Blender servers studied define 10 and 26 tools; the 26 include 6 `_for_cli` duplicates. Both rely on a general-purpose code tool described as a "last resort", fetch documentation with search tools, and guide tool choice in their instructions. GEstimator takes the same approach, but its fallback is read-only.

## The 19 tools

### Reads (8)

| # | Tool | Purpose | Key arguments |
|---|---|---|---|
| 1 | `get_state` | Project name, path, settings and code prefixes; revision and dirty flags; attached, bundled and custom sources with one-line summaries; counts | — |
| 2 | `describe_source` | Database overview, categories with summaries, conventions, dictionary entries (from metadata, or worked out from the data), and the columns of the `query` views | `source`, `section?` (`overview`/`categories`/`category:<name>`/`dictionary`/`schema`) |
| 3 | `search_items` | Ranked search with dictionary expansion (see Search) | `source?`, `query`, `kind` (`schedule`/`resource`), `category?`, `limit≤50` |
| 4 | `browse` | One page of the hierarchy under a category or parent code | `source?`, `kind`, `under?`, `depth=1`, `offset`, `limit`, `fields` |
| 5 | `get_items` | Full records by code | `source?`, `kind`, `codes[]`, `include?` (`analysis`, `resources`, `children`, `parent`, `usage`, `dependents`) |
| 6 | `get_measurements` | Measurement items, one item's records, or the templates with their **real** columns `[{field, title, editable, numeric}]` | `id?`, `section?` (`items`/`templates`), `record_offset?` |
| 7 | `get_summary` | Totals by category, grand total, checks: zero quantities, unlinked items, orphan children, unlinked measurements, rates that differ from stored | `fields` |
| 19 | `query` | Read-only fallback for questions the typed reads don't cover (e.g. "items whose rate changed by more than 5%", "resources used in more than 10 analyses") | `source?`, `sql`, `params?`, `limit≤500` |

### Writes (11)

| # | Tool | Purpose | Key arguments |
|---|---|---|---|
| 8 | `project` | `new`, `open`, `save`, `save_copy`, `export_xlsx`, `set_settings`, `import_xlsx` (with `preview`) | `action`, `path?`, `discard?`, `settings?`, `mapping?`, `duplicates?` |
| 9 | `import_items` | Copy schedule or resource items from a source; dependencies included | `source`, `kind`, `codes[]`, `include_parents=true`, `qty?{code:qty}`, `rate_mode` (`recalculate`/`stored`), `position?`, `on_conflict`, `settings?` (Modify & Add) |
| 10 | `upsert_items` | Create, edit or duplicate items and categories by code; leaving out `code` uses automatic numbering | `kind` (`schedule`/`resource`/`category`), `items[{code?, duplicate_from?, parent?, category?, description?, unit?, rate?, vat?, discount?, qty?, remarks?, colour?}]`, `position?` |
| 11 | `move_items` | Reorder, re-parent, change category, renumber | `kind`, `codes[]`, `position` (`{before\|after: code}` / `{parent: code, index}` / `{category, index}`), `renumber?` |
| 12 | `delete_items` | Delete items or categories with a usage policy | `kind`, `codes[]`, `policy` (`protect`/`unused`/`all`), `preview?` |
| 13 | `edit_analysis` | Load, apply operations and apply to the project in one step | `code`, `ops[]` (row/resource `add`, `edit`, `delete`, `move`, `duplicate`, `insert_template`, `import_xlsx`, `set_remarks`), `preview?`, `discard_draft?` |
| 14 | `apply_analysis_rules` | Ordered match/modify rules across many analyses; preview also checks the rules | `scope` (codes/categories/all), `rules[]`, `preview=true` |
| 15 | `edit_measurements` | All measurement writes | `ops[]`: `create` (template, description, after, links, records keyed by column **title**, user_data), `update`, `delete`, `move`, `duplicate`, `records_add`/`records_edit`/`records_delete`/`records_move`, `records_import` (path, range), `caption` |
| 16 | `recalculate` | Keep rates and quantities consistent | `what` (`rates`/`quantities`/`source_rates`), `codes?`, `rounding?` (enum), `source?`, `preview?` |
| 17 | `batch` | Atomic list of tool 8–16 calls (except file actions), one undo step | `ops[{tool, args}]`, `if_revision?` |
| 18 | `history` | Project undo/redo | `action` (`undo`/`redo`) |

Behaviour notes:
- **Placement.** `position` defaults to sorted insertion by code among siblings, never the end of the category.
- **Rate differences.** `import_items` and `recalculate` report any rate that differs from the stored value: `warnings[{code, stored, recalculated}]`.
- **Unsaved drafts.** `edit_analysis` never leaves an agent draft behind. If the desktop has an unsaved draft, it returns `draft_conflict` unless `discard_draft` is set.
- **Option labels.** Rounding, duplicate and policy labels are **enums** in the schema.

### `query` safeguards

- **No direct table access.** `query` runs against **documented read-only views**, not raw tables: `v_schedule`, `v_resources`, `v_analysis_rows`, `v_measurements`, `v_measurement_records`, `v_links`. The views are part of the tool contract; `describe_source section=schema` lists their columns. Internal tables can change without breaking agents.
- **Read-only, enforced in three layers:**
  - a separate connection opened with `mode=ro` (URI) and `PRAGMA query_only=ON`
  - an SQLite authorizer callback that allows only `SELECT` and reads of the documented views
  - one statement per call, with `ATTACH`, `PRAGMA` and extension loading rejected
- **Limits:** a step limit through the progress handler (about 2 s), a row cap (`limit`, at most 500) and a result size cap of 256 KB. Hitting any of them returns a `too_large` error with a hint to aggregate or page.
- **Results:** compact `{columns, rows, truncated}`. Available in read-only access mode.
- **Instructions:** the server instructions call `query` a fallback, to use only when no typed tool fits.

### What happens to each current tool

| Current tools | Replaced by |
|---|---|
| `state`, `get_project`, `project.settings`, `program.settings`, `program.libraries`, `library.list`, `list_databases` | `get_state` |
| `library.attach` | automatic attach through `source` |
| `database.inspect` | `describe_source` |
| `list_schedule`, `list_resources`, `schedule/resources.editor.state` | `browse`, `search_items` |
| `database.analysis`, `database.resource`, `get_analysis`, `resources.editor.usage`, `resources.editor.dependents` | `get_items` with `include` |
| `list_measurements`, `get_measurement`, `measurement.state/detail/templates` | `get_measurements` |
| `project.new/open/save/save_copy/export_xlsx/settings.edit/import_preview/import_apply` | `project` |
| `schedule/resources.editor.add_from_library`, `clipboard.export/paste` | `import_items` (another `.eproj` as source) |
| `*.editor.add/duplicate/edit/edit_many/category_add/colour`, `*.editor.defaults` | `upsert_items` (automatic numbering) |
| `*.editor.move`, `resources.editor.move_to`, `schedule.editor.renumber` | `move_items` |
| `*.editor.delete/delete_many/delete_preview` | `delete_items` |
| all `analysis.*` row, cell, resource, template, batch, import and apply tools | `edit_analysis` |
| `analysis.rules.validate`, `schedule.editor.analysis_rules.preview/apply` | `apply_analysis_rules` |
| all `measurement.*` write and record tools | `edit_measurements` |
| `schedule.editor.update_rates/update_quantities`, `measurement.update_quantities`, `resources.editor.rates`, `*.editor.price_preview/price_update` | `recalculate` |
| `project.undo/redo` | `history` |
| **Removed:** `recovery.*`, `*.copy/paste` and `analysis/measurement.*copy/paste` (session buffers), `analysis.undo/redo`, `analysis.export_xlsx`, `analysis.template_rows`, `program.settings.validate` | Recovery stays in the desktop UI. Atomic writes make draft undo and session buffers unnecessary. Settings are checked inside `import_items`. Template rows come from `edit_analysis` `insert_template`. |

## Server instructions

Keep these under about 300 tokens, sent once in the `initialize` response:

```
GEstimator estimate workspace. Items are addressed by code within a source
("project", an attached id, "bundled:<file>" or a .eproj path; naming a source attaches it).
1. Start with get_state. Use describe_source to understand an unfamiliar database.
2. Find items with search_items; use browse only to explore one category or parent.
3. Import with import_items (parents are included); create or edit with upsert_items.
4. Measurements: get_measurements section=templates for real columns, then edit_measurements
   with records keyed by column title; recalculate what=quantities to push totals.
5. Group related writes in batch. Writes accept optional if_revision; every write returns
   the new revision.
6. Verify with get_summary before project save/export.
7. query is a read-only SQL fallback over documented views; use it only when no typed tool fits.
Errors carry code, field, allowed values and a hint; fix the field rather than retrying.
Access mode: <read-only|read-write>.
```

## Response and error format

- **Success:** `structuredContent = {data, revision, warnings[]}`. `content[0].text` is a **one-line summary** (e.g. `"Imported 29 items (11 parents). revision 3"`), not the JSON again. Every tool declares an `outputSchema`.
- **Error:** `isError: true`, `structuredContent = {error: {code, message, field?, allowed?, hint?}}`. Example: `{"code":"not_editable","field":"c1","allowed":["c0","c2","c3","c4","c5"],"hint":"Breakup is computed"}`.
- **Paging:** `{items, total, offset, next_offset|null}`.

## Optional metadata layer

Store metadata in a new table inside the `.eproj` (`meta_enrichment`, one JSON blob per scope). Files without it keep working, and older app versions ignore the table.

```jsonc
{
  "schema": 1,
  "provenance": {"generator": "ai", "model": "<id>", "date": "YYYY-MM-DD", "reviewed": false},
  "database": {"summary": "…", "scope": ["…"], "excludes": ["…"], "rate_basis": "…", "conventions": ["…"]},
  "categories": {"<name>": {"summary": "…", "scope": "…", "see_also": ["<name>"]}},
  "items": {"<code>": {"short": "≤60-char title", "keywords": ["…"]}},
  "dictionary": [{"term": "DPC", "expand": ["damp proof course"], "case": true, "scope": "civil"}]
}
```

**Fallbacks when metadata is missing** (always available):
- **Database summary:** name, counts and list of categories.
- **Category summary:** item count, unit mix, and the first 3 parent descriptions trimmed to 80 characters.
- **Item short title:** the parent description's first clause plus the child label, trimmed to 60 characters.
- **Dictionary:** only the entries found automatically in the database text (see below).

**One-time generation for bundled databases** is a developer tool, never run by end users:
- Script: `tools/enrich_database.py <in.eproj> [--model …] [--embeddings] [--force]`
- It generates the summaries, item `short` titles, `keywords` and `dictionary` from category chunks, checks them against the schema, and can resume where it stopped.
- A human checks the result before release.

The desktop app only shows metadata, with an "AI-generated" badge, and offers a **Clear enrichment** action.

## Search pipeline

```
item text / query → normalize → expand with dictionary → FTS5 (always)
                                                      ↘ ONNX embedding (optional) → numpy cosine
                                     merge by reciprocal rank fusion (RRF) → compact results
```

1. **Indexed text per item:**
   - category
   - parent description
   - its own description
   - unit
   - `short` and `keywords` from metadata, if present

   Queries are processed the same way.
2. **Normalizer** (generic rules for every database):
   - unit spellings: `sq.mm`/`sqmm`/`mm²` → `sq mm`; `cu.m`/`cum` → `cum`
   - dimensions: `2X4` → `2 x 4`
   - current: `Amp`/`Amps`/`A` after a number → `amp`
   - common forms: `dia` → `diameter`; `nos`/`no.` → `number`
   - spacing and case
3. **Dictionary preprocessor**
   - **Append, don't replace:** `DPC` → `DPC (damp proof course)`. The original token stays searchable.
   - **Apply it to both** the indexed text and the query.
   - **Layers, in order of precedence:**
     1. An optional user file `dictionary.user.json`.
     2. The database's `meta_enrichment.dictionary`, AI-generated once for bundled databases.
     3. A built-in generic dictionary per field (civil, E&M, plumbing, HVAC), shipped in `modern/backend/data/dictionary/`.
     4. Entries found automatically in the database's own text with the pattern `Full Name (ABBR)`, e.g. "residual current circuit breaker (RCCB)". This needs no AI and works on custom databases.
   - **Synonym groups** are included: socket/outlet/receptacle, earthing/grounding, wire/cable.
   - **Ambiguity rules:**
     - expand only whole tokens
     - match terms of 3 characters or fewer case-sensitively
     - allow an entry to be limited to a field or category
     - allow several expansions per entry (CP → chrome plated / contractor profit)
     - keep expansions inside an embedding short (the first expansion only); keyword search gets all of them
   - **Version tag:** a hash of normalizer version + all dictionary layers. When it changes, the keyword index and any embeddings are rebuilt.
4. **FTS5:** an SQLite FTS5 index per source, ranked by BM25 with a small boost for leaf items. Fall back to BM25 in Python where FTS5 isn't available.
5. **Embeddings (optional add-on):**
   - A quantised ONNX model of about 384 dimensions (e.g. bge-small or MiniLM, or multilingual-e5-small), run with `onnxruntime` + `tokenizers` and installed as a separate optional download.
   - Vectors are stored as float16 BLOBs in `meta_embeddings` with `{model_id, dim, model_hash, index_fingerprint}`, loaded into numpy and compared directly.
   - **No sqlite-vec:** a database has about 1–2k vectors, so a full scan is under a millisecond.
   - Bundled databases ship with vectors already computed. Custom databases are embedded in the background when attached.
   - If the model id or version tag doesn't match, re-embed, or fall back to FTS5 only.
6. **Merge** FTS5 and embedding rankings with RRF (k=60). Results: `{code, short, unit, rate, category, parent_code, score}`.

**Test set:** `tests/data/search_eval.json` holds 30–50 queries per bundled database, each with the expected codes. Report recall@5 and MRR for five setups:
- FTS5
- FTS5 + dictionary
- embeddings
- embeddings + dictionary
- hybrid

Ship the embedding add-on only if hybrid clearly beats FTS5 + dictionary.

## Implementation steps

Each step is one PR with tests under `tests/`.

1. **Transport and format.** In `mcp_server.py`: one-line text summaries, `structuredContent` only, structured errors, `outputSchema`, and the server instructions from the section above.
2. **Replace the toolset (reads).**
   - Rewrite the `operation()` registry in `mcp_operations.py` to expose tools 1–7, delegating to the existing services.
   - Add `query` (tool 19): the read-only views, a read-only connection, the authorizer and the limits.

   *Tests for `query`:* `INSERT`, `UPDATE`, `ATTACH`, `PRAGMA` and multiple statements are rejected; raw tables are refused; a runaway query stops at the step limit.
   - Remove the old tools and aliases.
   - Port `tests/test_mcp_server.py` and `tests/test_mcp_editing.py` to the new names.
   - Update `docs/migration/mcp-server.md`.

   *Test:* `tools/list` ≤ 16 KB; all names match `^[a-zA-Z0-9_-]{1,64}$`.
3. **Replace the toolset (writes 8–18).**
   - Reuse the existing transactions: `import_items` = `add_from_library` + parent resolution + sorted placement + quantity map; `edit_measurements create` = add + properties + records in one transaction; `batch` wraps the existing undo transaction.

   *Test:* a golden test (`tests/test_mcp_canonical.py`) replays the trial estimate in ≤ 20 calls and reaches the same total.
4. **Metadata layer.** Add `modern/backend/metadata.py`: read/write `meta_enrichment`, fallbacks, used by `describe_source`, `browse` and `search_items`. Add the UI badge and Clear action.
   *Test:* every read works on a database without the table.
5. **Normalizer and dictionary.** Add `modern/backend/dictionary.py`:
   - the four layers, automatic `Full Name (ABBR)` extraction, synonym groups, ambiguity rules, version tag
   - built-in dictionaries per field in `modern/backend/data/dictionary/`

   *Test:* extraction finds RCCB and MCB in DSREM2022; `DPC` expands; `CP&OH` is not expanded as "chrome plated" in rate-breakdown text.
6. **FTS5 search.** Add `modern/backend/search.py`: an index per source with dictionary expansion, rebuilt when the version tag changes. Add the test harness and its report.
   *Test:* "modular switch light point PVC conduit" returns 1.10.x in the top 5 on DSREM2022.
7. **Optional embeddings.** ONNX add-on, numpy storage, RRF merge, fallback when the model is missing.
   *Test:* the five-setup report, and search still works with the add-on uninstalled.
8. **Developer enrichment tool.** Add `tools/enrich_database.py` (metadata, dictionary, optional embeddings). Run it on the bundled databases and commit the results after review.

**Acceptance for steps 1–3:**
- `tools/list` has exactly 19 tools, no duplicate or alias names, and is at most 16 KB.
- The server instructions are at most about 300 tokens.

## Prompt for an AI coding tool

> Read `docs/migration/mcp-efficiency.md` and `docs/migration/mcp-server.md`, then `modern/backend/mcp_server.py` and `modern/backend/mcp_operations.py`. Implement step N only. Reuse the existing service methods and transactions rather than new data paths; the old tools are removed from MCP exposure, not their underlying adapters. Add or port tests under `tests/` that cover the step's acceptance criteria, and run the full MCP test suite. Report `tools/list` size, test results and, for search steps, the test-set report.
