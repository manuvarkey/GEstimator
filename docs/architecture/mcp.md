# MCP architecture and public contract

Current contract, checked against source on 2026-11-23.
Navigation: [index](../README.md) · [architecture](README.md) · [backend](backend.md)
· [database format](database-format.md) · [verification](../testing.md).

The server is off by default. **Program settings → AI assistants (MCP) → Enable the MCP server for AI assistants** shows the MCP tab and allows Start; the backend refuses `mcp.start` until it is enabled (`mcp.enable`), and disabling it stops a running server. Saved automatic startup applies only while the option is on. The MCP ribbon keeps the active editor in place. Configure port (1024–65535, default 8765), **Read only / Read and write**, optional automatic startup and token rotation. Save configuration before Start; stop before changing it. Existing saved settings retain read-only access until explicitly changed.

**Copy client configuration** copies an `mcpServers.gestimator` entry with the Streamable HTTP URL and Bearer header. Show token reveals selectable configuration text if the clipboard is unavailable. Clients must support HTTP/custom authorization headers. The listener binds to `127.0.0.1`; every request requires its token and valid local Host/Origin headers. The token grants the configured access, including file operations in write mode.

## Tools and responses

Read/write mode exposes exactly **19 tools**, all named in snake_case. Read-only mode exposes the eight reads. Old dotted operation names and the seven legacy aliases are no longer MCP tools. Desktop service methods remain available internally.

| Reads | Purpose |
|---|---|
| `get_state` | `start_here` estimating steps, the estimation `skills`, project settings/path, dirty flags, counts, attached and available sources |
| `describe_source` | Overview (notes first), category summaries and notes, dictionary, documented SQL view columns; `section=skills`, `skill:<id>[/<path>]` or a `gestimator://skills/...` link reads the estimation skills |
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

`tools/list` is authoritative for input schemas and enums. Every tool declares an output schema. Successful tool results contain `structuredContent: {data, revision, warnings: []}` and one short text summary. The JSON payload is not repeated in text. Errors have `isError: true` and `structuredContent: {error: {code, message, field?, allowed?, hint?}}`. The text content repeats the field, up to 12 allowed values and the hint in one line, because many clients show only the text. Validation, stale writes and failed compound operations leave project data unchanged. A recovery-checkpoint failure instead returns the committed result with a `recovery_failed` warning: do not repeat that write.

All writes accept optional integer `if_revision`. Supplying it rejects a stale write; omitting it applies to the latest state on the serialized owner thread. Each response returns the current revision, so clients can chain writes without additional state requests. Desktop stale-edit guards remain mandatory. Numeric inputs are decimal/mathematical-expression **strings**, never Python code or JSON floats. The [shared expression contract](backend.md#numeric-evaluation) applies, including named functions and constants. Integers such as offsets and revisions must be nonnegative. The default array bound is 500, default text bound 10,000 characters; specialized smaller/larger bounds appear in the schemas.

## Estimation skills (resources)

The server also declares the `resources` capability and serves estimation skills as read-only Markdown resources. They are packaged files, so they are readable in both access modes and without an open project. `resources/list` and `resources/read` run on the HTTP thread and never touch the project or the owner thread. `resources/templates/list` returns an empty list. The server instructions tell clients to read the skill that fits the work before using the project and rate tools.

**Reaching clients that ignore instructions and resources.** Many clients never show server instructions or resources to the model, and an agent may even call the endpoint from its own script. The skills are therefore also reachable through tools, without adding a tool (the discovery payload is at its 16 KB budget):

- `get_state`, the documented first call, starts with `start_here` (read the skill, read the notes before choosing items, record quantities as measurements rather than in a separate spreadsheet, present a draft first) and `skills` (id, description and the `describe_source` call that reads it). It works without a project.
- `describe_source section=skills` lists skills with their reference paths; `section=skill:<id>` returns `SKILL.md` and its references; `section=skill:<id>/<path>` or the `gestimator://skills/...` link from a skill returns a reference. These sections need no project or source.
- `describe_source` overview returns the notes (`metadata`) first, so a client that truncates a long response still keeps them.
- `import_items` adds a `notes_not_read` warning naming the overview and `category:<name>` sections of the source whose notes were not read since the server started, so the agent checks its choices against them. Reads are tracked per source name on the running server.

| Resource | Purpose |
|---|---|
| `gestimator://skills/civil-measurement-estimation` | Civil takeoff to IS 1200, the project specification and the adopted item; design inputs and checks; record format; item matching; apply on request |
| `gestimator://skills/electrical-measurement-estimation` | Electrical takeoff: points, equipment and ratings, wiring and cable runs; DSR (E&M) counting rules; design inputs and checks |
| `gestimator://skills/preliminary-lighting-design` | Lumen-method preliminary design when explicitly requested; provisional handoff to electrical measurement |
| `gestimator://skills/<skill>/references/<file>.md` | Supporting references linked from each skill (masonry, concrete, finishes, earthwork, wiring, distribution, luminaires, worked example, standards registers) |

Each listing entry has `uri`, `name`, `title` (first heading), `description` (from front matter), `mimeType: text/markdown`, `size` and `annotations` (`audience: ["assistant"]`; priority 1.0 for a skill, 0.5 for a reference). A read returns `{contents: [{uri, mimeType, text}]}`. An unknown or invalid URI returns JSON-RPC error `-32002` (resource not found) with `data.uri`; a missing or non-string `uri` returns `-32602`.

**Adding a skill package.** Add a directory `modern/backend/data/skills/<skill-id>/` (lowercase letters, digits and hyphens) with a `SKILL.md` and, optionally, Markdown references in subfolders such as `references/`. Every file starts with front matter:

```markdown
---
name: <skill-id>
description: <one line telling a client when to read this file>
---
```

`name` appears in `SKILL.md` only and must equal the directory name. References need only `description`.

Link references from `SKILL.md` by their full `gestimator://skills/<skill-id>/<path>` URIs. No code changes are needed: the listing scans the directory, and only files it finds can be read. Names must be lowercase with hyphens and end in `.md`, at most three levels deep. Files without a description, packages whose `name` differs from the directory, and symlinks that leave the skills directory are skipped. `tests/test_mcp_skills.py` checks that every link resolves and every reference is linked. The PyInstaller sidecar bundles all of `modern/backend/data`, and the Flatpak copies `modern/backend`, so a new package ships with the next build.

The measurement record format is independent of where quantities come from (drawings, schedules, user statements or, later, IFC model quantities); each line records its source. IFC input is deferred.

## Sources and placement

Items are identified by code within a source: `project` (default), an attached ID, `bundled:<file>.eproj`, or a filesystem `.eproj` path. Naming an unattached source attaches an isolated read-only snapshot. Reads of external databases also work without an open project. Sources do not need metadata, embeddings or user configuration. Source files are preserved by reads, search, imports and previews.

`browse` without `under` lists categories. With `under`, it lists children of that category or schedule parent code; `depth` defaults to 1. Listings return `{items, total, offset, next_offset}` and use short titles by default. `fields: "full"` includes full descriptions. `get_items` always returns full definitions. Measurement record pages use `record_offset` and return `next_offset`.

`import_items` includes ancestors by default, and returns `code_map` from source codes to destination codes. Collision choices are `error`, `skip`, `rename` (default), and `update`. `qty` uses source codes. `rate_mode` is `recalculate` (default) or `stored`; rate differences are reported as `{code, stored, recalculated}` warnings. Imported resource prefixes and sub-analysis dependencies use the original engine. Analysis dependencies go to the SUB ANALYSIS category under the source's resource prefix (for example `DC23:6.1.1`); an item selected together with an item whose analysis uses it is imported as a schedule item as well. The SUB ANALYSIS category is kept after all other categories (schedule view, resources and workbook export), also when an earlier project is opened.

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
6. Check `get_summary` and save explicitly. Export a workbook only when requested. Save Copy refuses overwrites. Save retains source-conflict checks and numbered backups. A transport timeout may occur after execution starts: read state before retrying.

## SQL fallback

Use typed tools first. `describe_source section=schema` documents `v_schedule`, `v_resources`, `v_analysis_rows`, `v_measurements`, `v_measurement_records`, and `v_links`. Reporting reflects **stored working-project data**, excluding unsaved desktop analysis drafts. Measurement calculations and amounts come from the original Python engine. Decimal columns are exact text: use `CAST(rate AS REAL)` for numeric SQL filters; use `get_summary` for original decimal totals.

Each query uses a disposable reporting projection, opened separately with SQLite URI `mode=ro` and `PRAGMA query_only=ON`. Its authorizer permits SELECT, approved views and a bounded set of scalar/aggregate functions. Raw tables, writes, ATTACH, PRAGMA, extension loading and multiple statements are rejected. A lexical guard also prevents a CTE from impersonating a view to read its backing table. Source database files are never altered to install views.

The progress handler enforces an instruction budget and a two-second execution deadline. Results are capped at 500 rows and 256 KiB. Exceeding a limit returns `too_large` with a hint to aggregate or page using SQL LIMIT/OFFSET. Successful results are `{columns, rows, truncated: false}`.

## Optional metadata and search

`meta_enrichment(scope TEXT PRIMARY KEY, data TEXT)` is optional; the `database` scope stores a schema-1 enrichment document validated by [`metadata.py`](../../modern/backend/metadata.py). Missing or invalid enrichment uses deterministic summaries and titles. Descriptions, rates and original definitions remain authoritative. The desktop labels enrichment **AI-generated** and offers **Clear enrichment** on the working project; clearing is undoable and takes effect on disk only when saved. Attached sources display enrichment without permitting edits to their source files.

Search normalizes units/dimensions and expands a layered dictionary: optional `dictionary.user.json` beside the custom database directory, database enrichment, built-in field dictionaries, and automatically extracted abbreviations. Short abbreviations preserve case matching; `CP&OH` is not expanded as chrome plated. FTS5 is preferred, with Python BM25 fallback. Literal and expanded rankings are fused with greater weight on literal matches to limit synonym noise. Indexes live separately from source files, are cached per source, and invalidate after edits, imports, undo/redo, metadata changes and dictionary changes. Project changes dispose old caches.

Run `.venv/bin/python tools/evaluate_search.py --output docs/migration/mcp-search-report.json` for the committed 30-query-per-database evaluation. [Results](../migration/mcp-search-report.json) report recall@5 and MRR@5. Embeddings and bulk AI enrichment remain deferred pending measured benefit and human review.

## Desktop synchronization and transport

Every HTTP tool uses the same bounded, serialized service/SQLite owner thread as desktop requests. Reads wait at most 30 seconds and writes 110 seconds. The desktop polls change sequence, defers refresh during edits/dialogs, refreshes changed content and resets context after agent new/open operations. A human edit submitted against an older revision is rejected with its typed value preserved for correction/retry. Status polling omits tool schemas unless requested.

Closing settings leaves the server running. Stop and application shutdown release its listener. Listener generation is rechecked when queued requests execute; old requests cannot edit after restart. An already executing transaction finishes before Stop. Occupied ports and invalid saved configuration remain recoverable. Automatic startup restores the saved endpoint/token/access mode. Settings show request count and last method/tool without logging tokens, headers or project content. MCP tools cannot change their own listener configuration or execute shell commands.

The transport retains MCP 2025-11-25 Streamable HTTP JSON responses and negotiation for 2025-11-25/2025-06-18/2025-03-26. POST individual JSON-RPC messages to `/mcp` with `Accept: application/json, text/event-stream` and `Content-Type: application/json`. Notifications return 202; GET returns 405. No MCP HTTP session IDs, unsolicited SSE, OAuth discovery, remote binding or standalone stdio hosting are provided. Internal desktop document-session IDs belong to the separate runtime protocol.


## Implementation ownership and extension checks

| Concern | Source |
| --- | --- |
| HTTP authentication, protocol negotiation, listener generations and response envelopes | [`mcp_server.py`](../../modern/backend/mcp_server.py) |
| Tool schemas, access/revision validation, preview classification and compound execution | [`mcp_operations.py`](../../modern/backend/mcp_operations.py) |
| Code-addressed reads and source/selection adapters | [`mcp_workspace.py`](../../modern/backend/mcp_workspace.py) |
| Write intents reusing application commands | [`mcp_writes.py`](../../modern/backend/mcp_writes.py) |
| Disposable read-only SQL projections | [`mcp_query.py`](../../modern/backend/mcp_query.py) |
| Packaged skill discovery and safe resource reads | [`mcp_skills.py`](../../modern/backend/mcp_skills.py) |
| Serialized dispatch and active document selection | [`runtime.py`](../../modern/backend/runtime.py) |
| UI connection controls and preference restoration | [`mcp.ts`](../../modern/src/mcp.ts) |
| Mounted workspace change polling and authoritative refresh | [`useWorkspaceMCP.ts`](../../modern/src/useWorkspaceMCP.ts) |

The schema registry is authoritative for public names, enums and size bounds.
Do not expose another desktop method as a tool without reviewing the existing
intent surface and discovery budget. The [efficiency design record](../migration/mcp-efficiency.md)
explains the consolidation; its old tool counts and implementation steps are
historical. It is not an instruction to restore removed aliases or repeat work.

A new write must reuse the [backend mutation boundary](backend.md#revisions-and-write-boundaries),
protect drafts, enforce access on the owner thread and handle previews without
publishing data or history. Do not make an HTTP handler a second ORM owner.
A new read must preserve stored/draft separation and source files. Keep static
resource reads independent of projects and validate packaged paths/metadata.

Relevant suites: [server lifecycle](../../tests/test_mcp_server.py),
[editing](../../tests/test_mcp_editing.py), [canonical contracts](../../tests/test_mcp_canonical.py),
[SQL](../../tests/test_mcp_query.py), [search](../../tests/test_mcp_search.py),
[skill resources](../../tests/test_mcp_skills.py) and
[desktop refresh](../../tests/test_desktop_refresh.py). Discovery and instruction
budgets are asserted by tests; do not increase them to accommodate an accidental
schema expansion. See [testing](../testing.md) for full commands and native limits.
