# Backend architecture and command contracts

Current contract, checked against source on 2026-11-23.
Navigation: [index](../README.md) · [architecture](README.md) ·
[database format](database-format.md) · [frontend](frontend.md) · [MCP](mcp.md).

## Ownership and module map

The backend is headless Python. Calculations, input validation, numbering,
placement and persistence are not frontend responsibilities. Desktop commands
and MCP adapters reuse the same service/editor operations.

| Concern | Owner |
| --- | --- |
| JSON Lines transport and error envelopes | [`__main__.py`](../../modern/backend/__main__.py) |
| Owner thread, bounded queue and document routing | [`runtime.py`](../../modern/backend/runtime.py) |
| Project lifecycle, analysis draft history, revisions and orchestration | [`service.py`](../../modern/backend/service.py) |
| Project file open, close, save, canonical paths and recovery open | [`project_files.py`](../../modern/backend/project_files.py) |
| Draft analysis row edits, resource insertion and worksheet import | [`analysis_edits.py`](../../modern/backend/analysis_edits.py) |
| Project transactions, compound operations and snapshot undo | [`project.py`](../../modern/backend/project.py) |
| Schedule and resource edit dispatch and row operations | [`project_edits.py`](../../modern/backend/project_edits.py) |
| Schedule and resource table pages, type-ahead, row deltas and totals | [`project_tables.py`](../../modern/backend/project_tables.py) |
| Rate discrepancies, resource usage and dependent analyses | [`project_reports.py`](../../modern/backend/project_reports.py) |
| Read-only library attachment, catalog and notes | [`libraries.py`](../../modern/backend/libraries.py) |
| Library import policies, staging and dependencies | [`library_import.py`](../../modern/backend/library_import.py) |
| Measurement list/detail and item operations | [`measurements.py`](../../modern/backend/measurements.py) |
| Record edits and record identities | [`measurement_records.py`](../../modern/backend/measurement_records.py) |
| Records draft history and acceptance | [`measurement_draft.py`](../../modern/backend/measurement_draft.py) |
| Mapped worksheet helpers/import | [`importing.py`](../../modern/backend/importing.py) |
| Analysis workbook parsing/import | [`analysis_import.py`](../../modern/backend/analysis_import.py) |
| Rate dependencies and recalculation | [`rates.py`](../../modern/backend/rates.py) |
| Ordered insertion and dependency-category placement | [`insertion.py`](../../modern/backend/insertion.py) |
| Versioned row-transfer payloads | [`clipboard.py`](../../modern/backend/clipboard.py) |
| Search, notes and optional enrichment | [`search.py`](../../modern/backend/search.py), [`metadata.py`](../../modern/backend/metadata.py) |
| Saves, fingerprints, backups and recovery locks | [`persistence.py`](../../modern/backend/persistence.py) |
| Reporting changes/deltas | [`editor_changes.py`](../../modern/backend/editor_changes.py) |
| Analysis rules and template/settings validation | [`analysis_rules.py`](../../modern/backend/analysis_rules.py), [`program_settings.py`](../../modern/backend/program_settings.py) |
| ORM and analysis/measurement models | [`estimator/data/`](../../estimator/data) |
| Schedule database connection lifecycle and version-one migration | [`database_lifecycle.py`](../../estimator/data/database_lifecycle.py) |
| Workbook layout, formulas and progress reporting | [`workbook_export.py`](../../estimator/data/workbook_export.py) |

`Service` and `ProjectEditor` are already large. A new domain concern belongs in
a named handler with explicit editor/service context, not another unrelated
branch in a router. Helpers must not create their own commit/history system.
See the [quality audit](../code-quality-audit.md) for remaining extraction work.

`ProjectEditor.edit` forwards schedule and resource operations to
`project_edits`. Revision and draft checks, transaction entry points, undo
and clipboard lifetime remain with the editor. Edit handlers reuse its
selection, deletion and numbering operations and share insertion placement
with other project workflows.

Category creation in Schedule and Resources uses the tree's last selected
row in project order. It inserts after that row's category, or first when
there is no selection. The reserved SUB ANALYSIS category stays last.
Measurements use the same rule for stored headings,
placing them between category blocks so existing measurements retain their
category. An item inserted or pasted into Measurements goes after the last
selected item, at the start of a selected category, or at the top without a
selection. A pasted or duplicated block containing a heading starts at a
category boundary.

`ProjectEditor.state` forwards read-only table presentation to
`project_tables`. The editor retains its working and attached database
handles and provides the history and change sequence used in the response.
Read-only rate and resource reports use the editor's current database and
revision. File operations use the same service through `project_files`, with
project draft guards and working snapshot acceptance still owned by `Service`.
`Service.edit` forwards draft model changes to `analysis_edits`. The service
still owns revision validation, preview restoration, rollback, acceptance and
draft undo.

The schedule database export methods delegate to `workbook_export`. The
writers use the shared engine reads and currency rules for schedule,
resources, analyses, resource usage and measurements. Scratch copies and
safe publication follow the existing
[persistence boundary](database-format.md#working-copies-save-and-recovery).

Library attachment/import methods on `ProjectEditor` are compatibility forwards.
The editor retains attachment handles, selection helpers and transaction/history
ownership. `library_import` stages the complete batch before placement and final
rate policy; its dependency helper preserves prefixed, zero-quantity SUB ANALYSIS
copies even when the corresponding source item is explicitly selected too.

## Runtime and document sessions

One `Runtime` owns a queue (capacity 128) and a worker thread. Each open document
has a separate `Service`, working database, drafts, revision and recovery identity.
The runtime supports up to 32 sessions and keeps at least one open. Desktop
requests identify their session. MCP dispatch selects the runtime's active
session; switching the active document advances the MCP project epoch.

HTTP request threads may parse/authenticate transport messages and serve static
skill files. They must not call the ORM directly. Reads and writes that access
projects join the owner queue. A queued timeout can cancel a request that has
not started; an already executing write may still finish. Clients must read
state before retrying after an uncertain transport result.

## Desktop JSON Lines protocol

The sidecar accepts UTF-8 JSON objects, one per line. For example:

```json
{"id":"request-1","method":"state","params":{},"session":"main"}
```

Responses contain the same `id` and either `result` or
`error: {code, message}`. Long commands can emit
`{id, event: "progress", message}` before their final response. Progress is not
completion. Protocol errors use `INVALID_REQUEST`, file errors `FILE_ERROR` and
unexpected failures `BACKEND_ERROR`; diagnostics go to stderr, not JSON stdout.
Input lines are limited to 2,000,000 characters and request IDs to 100 characters.

Session methods (`session.open/list/activate/close`) are routed by `Runtime`.
Project/analysis/library methods are routed by `Service.call`, with project
operations forwarded to `ProjectEditor.call`. `shutdown` closes the runtime.
There is no second public desktop RPC implementation or frontend calculation API.

## Revisions and write boundaries

Desktop edits require the latest revision where checked by the service/editor.
Read-only state and preview operations have their own routing and must stay
read-only. Do not bypass revision checks to make stale UI edits appear to work.
MCP's optional `if_revision` is a separate public contract; its adapters inject
current desktop revisions when they invoke application methods.

| State being changed | Boundary | Acceptance/history |
| --- | --- | --- |
| Analysis draft model/resources | Service draft mutation/history | Apply writes it to the working project; draft undo is separate from project undo |
| Working project rows | `ProjectEditor.mutate` | SQL transaction plus snapshot; bounded project history |
| Related multi-step project/MCP edits | `ProjectEditor.compound` | One outer transaction and project undo entry; preview restores transient state too |
| Open measurement records/properties/links | `MeasurementDraft.mutate` | Draft model and record IDs; Apply accepts as one project operation |
| Source project file | Service save plus persistence helpers | Conflict checks, staged file and backup; no live database write-through |

Compound rollback restores more than SQL: analysis state, revision, dirty flags,
clipboard, measurement IDs, draft state and histories matter. Keep nested
operations inside their existing owner boundary. Use existing preview helpers
or `compound(..., preview=True)` rather than editing and manually undoing.

Dirty analysis/record drafts protect navigation and conflicting mutations.
`discard` intent and MCP `discard_draft` are explicit actions; a stale/failed
write must retain the user's typed value and recoverable work. Save/recovery can
include pending drafts while preserving their live edit histories until success.
Read [database persistence](database-format.md#working-copies-save-and-recovery)
before modifying any save path.

## Calculation authority

[`ScheduleItemModel.evaluate_results`](../../estimator/data/schedule.py) remains
the analysis authority. Row order matters:

- A group rounds its adjusted resource rates, each quantity-times-rate amount
  and the group result through existing Currency rules, adds to the cumulative
  total and sets the weight base.
- Subtotal captures the cumulative total as the next weight base.
- Weight adds a rounded fraction of that base without changing the base.
- Multiply replaces total and base; Round changes the total while preserving
  the prior weight base.
- `get_ana_rate` uses the last calculated result. A stored schedule rate may
  deliberately differ until an explicit recalculation, including Modify & Add.

`Currency` uses Decimal HALF_UP and supports the existing fractional-place
rounding convention. Do not replace it with ordinary `round`, JavaScript money
arithmetic or SQL floating-point totals. Rate dependency changes belong in
`rates.py` and reuse the engine's sub-analysis semantics. Batch related reads and
writes; source databases and the SUB ANALYSIS dependencies are not editable UI
copies to be changed opportunistically.

## Numeric evaluation

[`NumericExpression`](../../estimator/arithmetic.py) owns the shared bounded AST
syntax. [`numbers.decimal`](../../modern/backend/numbers.py) evaluates under a
40-digit Decimal context, keeps literal precision (at most 12 decimal places),
and rounds computed entries to six places. `evaluate_number` retains legacy
integer/float arithmetic for measurement templates and worksheet helpers.
Trigonometric approximations are converted back to Decimal in modern entry;
ordinary Decimal arithmetic and native Decimal math remain Decimal.
The row clipboard decodes stored financial and analysis numbers with the same
expression bounds and enough literal precision for SQLite values, including
DSR 2023 carriage factors.

Supported functions, constants, positional arguments, angle units and limits
are maintained once in the [numeric-expression guide](../manual/README.md#numeric-expressions).
Do not add `eval`, Python namespaces, object attributes or a parallel frontend
parser. Distinguish named `round()` entry math from Currency/rate rounding.
[`loose_number`](../../modern/backend/importing.py) handles worksheet grouping
and currency marks while preserving commas that separate function arguments.

## Measurements and templates

The shared engine's [`Measurement`](../../estimator/data/measurement.py) and
trusted installed [`meas_templates`](../../estimator/meas_templates) own template
calculations. [`template_loader`](../../estimator/data/template_loader.py)
validates names/paths and caches by content; each measurement still receives
independent mutable template state. Do not load a project-supplied Python path.
Presentation metadata lives in
[`measurement_templates.py`](../../modern/backend/measurement_templates.py).

Preserve declared columns, read-only computed cells, dimensions, labels and raw
expression strings. NLBH ignores zero factors; electrical point counts truncate
toward zero; duct/steel templates have their own retained rounding. These are
compatibility contracts, not opportunities to standardize all templates during
an unrelated refactor. Serialization and link cleanup are described in the
[database format](database-format.md#project-settings-and-measurements).

## Extending a backend workflow

1. Identify the domain handler and choose draft/project/compound ownership.
2. Validate field types, bounds, selection and revision at the existing boundary.
   Keep request-specific limits with their schema/validator, not a generic limit
   copied from another command.
3. Apply changes with the engine and existing handlers. Keep external libraries
   read-only; do not introduce a new ORM connection/thread for convenience.
4. Return authoritative decimal strings, row IDs and warnings. Let the frontend
   render them; let MCP reuse the same operation.
5. Test success and the relevant failure invariants: no partial writes, stable
   IDs, stale rejection, preview rollback, draft conflicts, undo/redo and save/reopen.

Start with [calculation baselines](../../tests/test_calculations.py),
[analysis parity](../../tests/test_analysis_parity.py),
[math expressions](../../tests/test_math_expressions.py),
[project editors](../../tests/test_project_editors.py),
[records drafts](../../tests/test_records_draft.py),
[batch additions](../../tests/test_batch_additions.py) and
[document sessions](../../tests/test_document_sessions.py), choosing tests for
the changed concern. The [testing guide](../testing.md) defines the full checks
and evidence to record.
