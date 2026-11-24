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
| `describe_source` | Overview (notes first), category summaries and notes, dictionary, documented SQL view columns; `section=skills`, `skill:<library>/<skill>[/<path>]` or a `gestimator://skills/...` link reads the estimation skills |
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

`tools/list` is authoritative for input schemas and enums. Every tool declares an output schema. Successful tool results contain `structuredContent: {data, revision, warnings: []}` and the same compact JSON in `content[0].text` for clients that only display text. Errors have `isError: true` and `structuredContent: {error: {code, message, field?, allowed?, hint?}}`. The text content repeats the field, up to 12 allowed values and the hint in one line, because many clients show only the text. Validation, stale writes and failed compound operations leave project data unchanged. A recovery-checkpoint failure instead returns the committed result with a `recovery_failed` warning: do not repeat that write.

All writes accept optional integer `if_revision`. Supplying it rejects a stale write; omitting it applies to the latest state on the serialized owner thread. Each response returns the current revision, so clients can chain writes without additional state requests. Desktop stale-edit guards remain mandatory. Numeric inputs are decimal/mathematical-expression **strings**, never Python code or JSON floats. The [shared expression contract](backend.md#numeric-evaluation) applies, including named functions and constants. Integers such as offsets and revisions must be nonnegative. The default array bound is 500, default text bound 10,000 characters; specialized smaller/larger bounds appear in the schemas.

## Estimation skills (resources)

Select **Program settings → General → AI assistants (MCP) → Estimation skillset**.
The choices come from discovered manifests. **Generic** (`generic`) is the default
and follows project-specific measurement rules. **IN** (`in`) provides Indian
building and infrastructure takeoff, preliminary lighting and LV distribution design, and schedule matching. The selected
library is published together with the bundled `shared` library, which contains
the rate-analysis skill. Shared is included automatically with any selection.

### Library folders and manifest

Bundled libraries live under
[`modern/backend/data/skills/`](../../modern/backend/data/skills). **MCP → Open user
skill folder** opens the application’s per-user data folder at `mcp/skills/`.
Place one folder per library in either root. The user data path is independent of
the installed program version. Each library needs `library.json`:

```json
{
  "schema_version": 1,
  "id": "office",
  "name": "Office estimating",
  "description": "Office takeoff and estimating guidance."
}
```

The ID is a stable lowercase identifier formed from letters, digits and hyphens,
up to 64 characters. The folder name can change without changing the ID. The
display name is required and up to 120 characters. The optional description is
up to 400 characters. The packaged IDs take precedence over user IDs. When two
user folders declare the same ID, the first valid library in folder-name order
is used and the duplicate is reported. The IDs `generic` and `shared` are reserved
for bundled libraries. A library needs at least one readable skill.

Inside the library, create one subfolder per skill using the same identifier
syntax. The folder needs a `SKILL.md` with front matter:

```markdown
---
name: office-takeoff
description: Take off building work using the office measurement rules.
---
```

The `name` must match the skill folder. Supporting files such as
`references/checklist.md` have only a required `description` in their front
matter. Reference paths use lowercase letters, digits and hyphens in each
segment and end in `.md`. They may be up to three levels deep inside the skill.
Files must be UTF-8, at most 256 KiB, and contained in their own package. The
scanner rejects symbolic links in library and package entries and files.
Link to references with their full qualified URIs. For example:

- Skill document: `gestimator://skills/office/office-takeoff`
- Supporting document: `gestimator://skills/office/office-takeoff/references/checklist.md`
- Shared rate analysis: `gestimator://skills/shared/rate-analysis`

A skill ID can appear in multiple libraries. The library segment in the URI
identifies the document unambiguously. The PyInstaller sidecar bundles
`modern/backend/data`, and the Flatpak copies `modern/backend`, so packaged
manifest and skill additions ship with the next build.

### Selection, refresh and serving

The Python application scans both roots on startup. Program Settings stores
`estimation_skill_library` as the chosen manifest ID. If that ID is unavailable,
Generic serves the catalog and the desktop reports the unavailable library.
A subsequent refresh restores the requested selection if its library returns.

**MCP → Refresh skills** scans both roots and publishes the resulting
catalog. **Configure server → Estimation skill libraries** shows the active
library, user folder and scan diagnostics. Changing the selection or refreshing
files affects subsequent requests on the running listener. Clients with cached
resource listings can refresh their connection.

The MCP service owns one application-wide catalog. The owner thread builds
each replacement snapshot from validated manifests and Markdown, then publishes
it once. The HTTP thread reads the published metadata and content directly,
with no filesystem or project access on resource requests. The same snapshot
feeds tool reads on the owner thread. Sources and project databases are
independent of the skill library selection.

Resources are available in both server access modes and without a project.
`resources/list` returns the active and shared documents. `resources/read`
returns `{contents: [{uri, mimeType, text}]}`. Each listing entry has `uri`,
`name`, `title`, `description`, `mimeType: text/markdown`, `size` and
`annotations`. Skill entries have assistant priority 1.0 and references have
priority 0.5. `resources/templates/list` returns an empty list. An unknown,
inactive or invalid URI returns `-32002` with `data.uri`. A missing or non-string
URI returns `-32602`.

Clients can use tools for the same discovery and content:

- `get_state` lists available skills with their library IDs and a
  `describe_source` call for each document.
- `describe_source section=skills` lists the active library and available
  skills with their references. Read a document by passing its full URI as
  `section`, or use `skill:<library>/<skill>[/<path>]`.
- Read source overview and category notes before choosing schedule items.
  `describe_source` puts the notes first and `import_items` warns about relevant
  unread notes tracked since the listener started.

Each measurement record can identify a drawing, schedule, user statement or
IFC quantity supplied by an external tool. Direct IFC import is deferred.

## Sources and placement

Items are identified by code within a source: `project` (default), an attached ID, `bundled:<file>.eproj`, or a filesystem `.eproj` path. Naming an unattached source attaches an isolated read-only snapshot. Reads of external databases also work without an open project. Sources do not need metadata, embeddings or user configuration. Source files are preserved by reads, search, imports and previews.

`browse` without `under` lists categories. With `under`, it lists children of that category or schedule parent code; `depth` defaults to 1. Listings return `{items, total, offset, next_offset}` and use short titles by default. `fields: "full"` includes full descriptions. `get_items` always returns full definitions. Measurement record pages use `record_offset` and return `next_offset`.

`import_items` includes ancestors by default, and returns `code_map` from source codes to destination codes. Collision choices are `error`, `skip`, `rename` (default), and `update`. `qty` uses source codes. `rate_mode` is `recalculate` (default) or `stored`; rate differences are reported as `{code, stored, recalculated}` warnings. Imported resource prefixes and sub-analysis dependencies use the original engine. Analysis dependencies go to the SUB ANALYSIS category under the source's resource prefix (for example `DC23:6.1.1`); an item selected together with an item whose analysis uses it is imported as a schedule item as well. The SUB ANALYSIS category is kept after all other categories (schedule view, resources and workbook export), also when an earlier project is opened.

Insertion defaults to natural code order among siblings (`1.2` before `1.10`). Explicit placement is `{before: code}`, `{after: code}`, `{parent: code, index}`, or `{category: name, index}`; indices are zero-based. Whole selected subtrees retain their hierarchy. Categories use `kind: "category"`, `category_kind: "schedule" | "resource"`, and category **names** in `codes`. For category upserts, `description` names the new category and `code` optionally names the existing one to rename.

## Preparing an estimate

1. Start with `get_state`; create/open a project explicitly. Unsaved work requires explicit `discard: true` for new/open operations.
2. Use `available_sources` from `get_state`, then `describe_source` and `search_items` to find project and library definitions. Read full items, analyses and resources with `get_items`. Search treats dotted and undotted initialisms such as R.C.C. and RCC alike. Import suitable library items with `import_items`. Use `upsert_items` with `duplicate_from` to retain a project item’s analysis and apply the supplied field overrides to the copy. Create custom definitions for gaps.
3. Edit analyses with one `edit_analysis` call. Existing rows can be addressed as `r0`, `r1`, and resource entries as `r0:0`, `r0:1`; these refer to positions at the start of the call. Newly created rows can have `ref` labels used by later operations in that same call. Native IDs also work. For example:

   ```json
   {"code":"A","ops":[
     {"action":"add","kind":"Group","description":"Materials","ref":"materials"},
     {"action":"add","target":"resource","id":"materials","code":"R","qty":"2*3"}
   ]}
   ```

   A resource add without `rate` resolves an existing project/source resource; with `rate`, supply its custom definition (`description`, `unit`, etc.). `preview: true` executes the same edits and calculations, then rolls back. An existing dirty desktop draft produces `draft_conflict` unless `discard_draft: true`. Success leaves no agent draft and returns the desktop selection to stored data.
4. Read the measurement list with `get_measurements`. Reuse the ID of an existing
   category (a row with `type: "Heading"`) or create one with a description and
   no template. Group sheets by work package, phase or location. Set each new
   sheet's `category` to the heading ID or to a same-call reference such as
   `$first-floor`. The `$ref:first-floor` spelling also works. This appends to
   that group in request order and cannot be combined with `after` on the same sheet. Use `after` for explicit insertion
   after a heading or sheet. On a new heading, `after` places it after the anchor's
   whole group. Check the sheet's `category_id` in the paged measurement list.
   Record individual storeys, rooms, elements or circuit routes where the source
   supports them. Include each record's source and the basis of provisional inputs.

   Discover editable columns and the number of outputs with
   `get_measurements section=templates`. When related items share the same
   takeoff rows, use one multi-output sheet. The five lengths in
   `_2_LLLLL` map to `links` in L1–L5 order. The eight quantities in
   `_3_NNNNNNNN` map to `links` in N1–N8 order. Omit trailing unused links
   and use `{"code":""}` to skip an intervening slot. Each linked column
   contributes its own total to the corresponding schedule item.

   ```json
   {"ops":[
     {"action":"create","description":"First floor electrical","ref":"first-floor"},
     {"action":"create","template":"_2_LLLLL","description":"Cable runs","category":"$first-floor",
      "links":[{"code":"A","remark":"Lighting"},{"code":"B","remark":"Power"}],
      "records":[{"Description":"North corridor, drawing E-01","L1":"2*4","L2":"6"}]}]}
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
| Skill manifests, discovery and resource snapshots | [`mcp_skills.py`](../../modern/backend/mcp_skills.py) |
| Serialized dispatch and active document selection | [`runtime.py`](../../modern/backend/runtime.py) |
| Desktop skill controls and catalog preferences | [`MCPRibbon.vue`](../../modern/src/components/MCPRibbon.vue), [`skillLibraries.ts`](../../modern/src/skillLibraries.ts) |
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
resource reads independent of projects and validate manifest and package paths.

Relevant suites: [server lifecycle](../../tests/test_mcp_server.py),
[editing](../../tests/test_mcp_editing.py), [canonical contracts](../../tests/test_mcp_canonical.py),
[SQL](../../tests/test_mcp_query.py), [search](../../tests/test_mcp_search.py),
[skill resources](../../tests/test_mcp_skills.py) and
[desktop refresh](../../tests/test_desktop_refresh.py). Discovery and instruction
budgets are asserted by tests; do not increase them to accommodate an accidental
schema expansion. See [testing](../testing.md) for full commands and native limits.
