# Local MCP server

The server is off by default. **Program settings → AI assistants (MCP) → Enable the MCP server for AI assistants** shows the MCP tab and allows Start; the backend refuses `mcp.start` until it is enabled (`mcp.enable`), and disabling it stops a running server. Saved automatic startup applies only while the option is on. The MCP ribbon keeps the active editor in place. Configure port (1024–65535, default 8765), **Read only / Read and write**, optional automatic startup and token rotation. Save configuration before Start; stop before changing it. Existing saved settings retain read-only access until explicitly changed.

**Copy client configuration** copies an `mcpServers.gestimator` entry with the Streamable HTTP URL and Bearer header. Show token reveals selectable configuration text if the clipboard is unavailable. Clients must support HTTP/custom authorization headers. The listener binds to `127.0.0.1`; every request requires its token and valid local Host/Origin headers. The token grants the configured access, including file operations in write mode.

## Tools and responses

This is the breaking migration described in [MCP efficiency](mcp-efficiency.md). Read/write mode exposes exactly **19 tools**, all named in snake_case. Read-only mode exposes the eight reads. Old dotted operation names and the seven legacy aliases are no longer MCP tools. Desktop service methods remain available internally.

| Reads | Purpose |
|---|---|
| `get_state` | Project settings/path, dirty flags, counts, attached and available sources |
| `describe_source` | Overview, category summaries, dictionary, documented SQL view columns |
| `search_items` | Ranked keyword/abbreviation search, up to 50 matches. Children are indexed with their heading text (parent, and unpriced title headings above by code); `headings` gives the heading text of returned children (≤ 600 characters each) |
| `browse` | Paged category or parent hierarchy |
| `get_items` | Full definitions by code, with optional analysis/resources/relationships |
| `get_measurements` | Paged items/records or templates with real column fields and editability |
| `get_summary` | Category/grand totals and consistency checks |
| `query` | Bounded, read-only SQL fallback over reporting views |

| Writes | Purpose |
|---|---|
| `project` | New/open/save/save_copy/export_xlsx/set_settings/import_xlsx |
| `import_items` | Import definitions, dependencies and optional ancestors; resolve collisions |
| `upsert_items` | Create/edit/duplicate items and categories |
| `move_items` | Direct placement, category changes, reparenting and optional renumbering |
| `delete_items` | Preview/delete subtrees/categories with usage policies |
| `edit_analysis` | Load, edit and apply in one transaction |
| `apply_analysis_rules` | Ordered matching rules; preview defaults true |
| `edit_measurements` | Create/link/fill sheets and edit items/records atomically |
| `recalculate` | Rates, measurement quantities or source price refresh; optional preview |
| `batch` | Related writes in one transaction and project undo step |
| `history` | Project undo/redo |

`tools/list` is authoritative for input schemas and enums. Every tool declares an output schema. Successful tool results contain `structuredContent: {data, revision, warnings: []}` and one short text summary. The JSON payload is not repeated in text. Errors have `isError: true` and `structuredContent: {error: {code, message, field?, allowed?, hint?}}`. Validation, stale writes and failed compound operations leave project data unchanged. A recovery-checkpoint failure instead returns the committed result with a `recovery_failed` warning: do not repeat that write.

All writes accept optional integer `if_revision`. Supplying it rejects a stale write; omitting it applies to the latest state on the serialized owner thread. Each response returns the current revision, so clients can chain writes without additional state requests. Desktop stale-edit guards remain mandatory. Numeric inputs are decimal/arithmetic **strings**, never Python code or JSON floats. Integers such as offsets and revisions must be nonnegative. The default array bound is 500, default text bound 10,000 characters; specialized smaller/larger bounds appear in the schemas.

## Sources and placement

Items are identified by code within a source: `project` (default), an attached ID, `bundled:<file>.eproj`, or a filesystem `.eproj` path. Naming an unattached source attaches an isolated read-only snapshot. Reads of external databases also work without an open project. Sources do not need metadata, embeddings or user configuration. Source files are preserved by reads, search, imports and previews.

`browse` without `under` lists categories. With `under`, it lists children of that category or schedule parent code; `depth` defaults to 1. Listings return `{items, total, offset, next_offset}` and use short titles by default. `fields: "full"` includes full descriptions. `get_items` always returns full definitions. Measurement record pages use `record_offset` and return `next_offset`.

`import_items` includes ancestors by default, and returns `code_map` from source codes to destination codes. Collision choices are `error`, `skip`, `rename` (default), and `update`. `qty` uses source codes. `rate_mode` is `recalculate` (default) or `stored`; rate differences are reported as `{code, stored, recalculated}` warnings. Imported resource prefixes and sub-analysis dependencies use the original engine.

Insertion defaults to natural code order among siblings (`1.2` before `1.10`). Explicit placement is `{before: code}`, `{after: code}`, `{parent: code, index}`, or `{category: name, index}`; indices are zero-based. Whole selected subtrees retain their hierarchy. Categories use `kind: "category"`, `category_kind: "schedule" | "resource"`, and category **names** in `codes`. For category upserts, `description` names the new category and `code` optionally names the existing one to rename.

## Preparing an estimate

1. Start with `get_state`; create/open a project explicitly. Unsaved work requires explicit `discard: true` for new/open operations.
2. Use `describe_source` and `search_items` to find definitions. Import with `import_items`, or create with `upsert_items`.
3. Edit analyses with one `edit_analysis` call. Existing rows can be addressed as `r0`, `r1`, and resource entries as `r0:0`, `r0:1`; these refer to positions at the start of the call. Newly created rows can have `ref` labels used by later operations in that same call. Native IDs also work. For example:

   ```json
   {"code":"A","ops":[
     {"action":"add","kind":"Group","description":"Materials","ref":"materials"},
     {"action":"add","target":"resource","id":"materials","code":"R","qty":"2*3"}
   ]}
   ```

   A resource add without `rate` resolves an existing project/source resource; with `rate`, supply its custom definition (`description`, `unit`, etc.). `preview: true` executes the same edits and calculations, then rolls back. An existing dirty desktop draft produces `draft_conflict` unless `discard_draft: true`. Success leaves no agent draft and returns the desktop selection to stored data.
4. Discover real columns with `get_measurements section=templates`. Create/link/fill in one call:

   ```json
   {"ops":[{"action":"create","template":"_1_NLBH","description":"Dimensions",
     "links":[{"code":"A","remark":"Measured"}],
     "records":[{"No":"2*3","L":"4"}]}]}
   ```

   Record keys accept exact displayed titles, base template captions or editable `cN` fields. Ambiguous titles require a `cN` field. Computed columns such as `Breakup` remain read-only and errors list allowed fields. Record edits include each stable record `id`; new measurements can use `ref` labels in subsequent operations within the same call. Finish with `recalculate what=quantities` and an explicit rounding enum.
5. Group related writes with `batch`. It excludes project new/open/save/save_copy/export, undo/redo, nested batches and previews. Project settings and workbook data imports may be batched. All operations are validated first and either commit together or restore database, draft state, revisions, measurement IDs and history together. A successful compound write advances revision/change sequence once and creates one undo entry.
6. Check `get_summary`, export a workbook and save explicitly. Save Copy refuses overwrites. Save retains source-conflict checks and numbered backups. A transport timeout may occur after execution starts: read state before retrying.

## SQL fallback

Use typed tools first. `describe_source section=schema` documents `v_schedule`, `v_resources`, `v_analysis_rows`, `v_measurements`, `v_measurement_records`, and `v_links`. Reporting reflects **stored working-project data**, excluding unsaved desktop analysis drafts. Measurement calculations and amounts come from the original Python engine. Decimal columns are exact text: use `CAST(rate AS REAL)` for numeric SQL filters; use `get_summary` for original decimal totals.

Each query uses a disposable reporting projection, opened separately with SQLite URI `mode=ro` and `PRAGMA query_only=ON`. Its authorizer permits SELECT, approved views and a bounded set of scalar/aggregate functions. Raw tables, writes, ATTACH, PRAGMA, extension loading and multiple statements are rejected. A lexical guard also prevents a CTE from impersonating a view to read its backing table. Source database files are never altered to install views.

The progress handler enforces an instruction budget and a two-second execution deadline. Results are capped at 500 rows and 256 KiB. Exceeding a limit returns `too_large` with a hint to aggregate or page using SQL LIMIT/OFFSET. Successful results are `{columns, rows, truncated: false}`.

## Optional metadata and search

`meta_enrichment(scope TEXT PRIMARY KEY, data TEXT)` is optional; the `database` scope stores the schema-1 enrichment document in the efficiency brief. Missing or invalid enrichment uses deterministic summaries and titles. Descriptions, rates and original definitions remain authoritative. The desktop labels enrichment **AI-generated** and offers **Clear enrichment** on the working project; clearing is undoable and takes effect on disk only when saved. Attached sources display enrichment without permitting edits to their source files.

Search normalizes units/dimensions and expands a layered dictionary: optional `dictionary.user.json` beside the custom database directory, database enrichment, built-in field dictionaries, and automatically extracted abbreviations. Short abbreviations preserve case matching; `CP&OH` is not expanded as chrome plated. FTS5 is preferred, with Python BM25 fallback. Literal and expanded rankings are fused with greater weight on literal matches to limit synonym noise. Indexes live separately from source files, are cached per source, and invalidate after edits, imports, undo/redo, metadata changes and dictionary changes. Project changes dispose old caches.

Run `.venv/bin/python tools/evaluate_search.py --output docs/migration/mcp-search-report.json` for the committed 30-query-per-database evaluation. [Results](mcp-search-report.json) report recall@5 and MRR@5. Embeddings and bulk AI enrichment remain deferred pending measured benefit and human review.

## Desktop synchronization and transport

Every HTTP tool uses the same bounded, serialized service/SQLite owner thread as desktop requests. Reads wait at most 30 seconds and writes 110 seconds. The desktop polls change sequence, defers refresh during edits/dialogs, refreshes changed content and resets context after agent new/open operations. A human edit submitted against an older revision is rejected with its typed value preserved for correction/retry. Status polling omits tool schemas unless requested.

Closing settings leaves the server running. Stop and application shutdown release its listener. Listener generation is rechecked when queued requests execute; old requests cannot edit after restart. An already executing transaction finishes before Stop. Occupied ports and invalid saved configuration remain recoverable. Automatic startup restores the saved endpoint/token/access mode. Settings show request count and last method/tool without logging tokens, headers or project content. MCP tools cannot change their own listener configuration or execute shell commands.

The transport retains MCP 2025-11-25 Streamable HTTP JSON responses and negotiation for 2025-11-25/2025-06-18/2025-03-26. POST individual JSON-RPC messages to `/mcp` with `Accept: application/json, text/event-stream` and `Content-Type: application/json`. Notifications return 202; GET returns 405. No session IDs, unsolicited SSE, OAuth discovery, remote binding or standalone stdio hosting are provided.
