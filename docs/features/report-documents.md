# Read-only report documents

Current core workspace and export workflow, 2026-11-26. Navigation: [index](../README.md) ·
[backend](../architecture/backend.md) · [report proposal](../report-module-plan.md).

The Reports workspace composes abstract, schedule, analyses, resources, resource
usage and signoff sections from immutable accepted-project snapshots. It previews and exports
standalone HTML, Excel and PDF when a suitable renderer is installed. Measurements/narrative sections, persisted specifications and packaged PDF
distribution remain future work.

## Request and response

`Service.call("report.document", params)` requires an open project and the current
integer `revision`. `specification` is optional and defaults to an empty object.
A stale/missing revision or a dirty analysis/measurement draft fails without
changing state. A `discard` flag does not bypass this read's draft protection.
Accepted but unsaved project edits are included; no save or recalculation occurs.
This is an internal desktop operation, not an additional public MCP tool.

The version-one specification accepts only:

| Field | Meaning |
| --- | --- |
| `schema_version` | Integer `1`; omitted means version one |
| `sections` | Ordered list of up to 20 section objects; omitted means abstract, schedule, signoff |
| `item_ids`, `category_ids` | Lists of up to 10,000 unique positive decimal-string database IDs; omitted/null means all; empty means none |
| `title`, `organization`, `reference`, `issue_date` | Plain text, using the backend text length limit; issue date is a display label |

Each section has a unique `id` matching `[A-Za-z][A-Za-z0-9_-]{0,63}`, a supported
`kind` (`abstract`, `schedule`, `analyses`, `resources`, `resource_usage`, `signoff`), optional plain-text `title`, and optional
boolean `enabled` (default true). Instances retain their IDs, order and enabled
state, including repeated kinds with distinct IDs. No arbitrary HTML, template
source, columns or layout fields are accepted. Unsupported fields/versions,
malformed selections and IDs absent from the current project fail explicitly.
Item and category filters intersect; they never reorder the project rows.
IDs are local to the current project, so callers must not reuse them across files.

The response contains `schema_version`, `revision`, `project`, the normalized
`specification`, `schedule`, `abstract`, `total`, `analyses`, `resources` and
`resource_usage`. Disabled optional datasets are empty lists. Financial values are decimal
strings. Schedule rows include stable item/category IDs, parent ID, category,
code, description, unit, quantity, stored rate, amount and remarks. Heading
amounts are null. Abstract rows contain category ID/name and amount.

Rows use project category and parent/child order. SUB ANALYSIS dependencies are
excluded from both sections, even if their stored quantity is nonzero. A heading
is included only when selected; selecting a child does not implicitly select its
parent. Headings have no amount. Each payable amount uses the engine's
`Currency(rate * quantity)` rounding, then category and grand totals sum those
amounts. Stored schedule rates remain authoritative even if analysis results
differ. Categories with no selected payable rows have no abstract row.
Section visibility/order never changes the shared selected dataset or totals.

## Ownership and preservation

[`reporting/specification.py`](../../modern/backend/reporting/specification.py)
validates and freezes the definition.
[`reporting/document.py`](../../modern/backend/reporting/document.py) batch-reads
categories, schedule rows and project settings in one database transaction and
builds frozen dataclasses containing only immutable values. `to_dict()` returns
independent JSON containers. Later edits cannot alter an existing snapshot.
The runtime owner thread serializes this read with project operations.

No ORM models escape into the document. Generation never updates stored analyses, accepts drafts, changes quantities or
rates, creates identities, advances revisions, changes clipboard contents or adds
undo entries. The service retains its existing
draft/revision boundaries. Report settings are not written into project files.

## Analyses, catalog and usage

The optional `analyses`, `resources` and `resource_usage` sections start disabled
in the desktop, preserving the original default report. Enable them through the
same section controls. The API's omitted `sections` default remains the original
abstract/schedule/signoff list. Only enabled optional datasets are assembled.

[`datasets.py`](../../modern/backend/reporting/datasets.py) batches accepted
sequence/resource-entry/catalog reads and reconstructs detached engine models.
`ScheduleItemModel.evaluate_results` owns every analysis calculation. The report
preserves row order and group totals, Weight/Multiply factors, rounding, resource
adjustments/references, entry remarks and analysis notes. Each analysis includes
both `stored_rate` and `calculated_rate`; displaying a calculated rate never
updates its stored counterpart. Items without an analysis are omitted, as in
the existing analysis workbook. Headings and dependency-only schedule items do
not create analyses in this report.

Without item/category filters the resource section lists the complete stored
catalog in category/order sequence, including unused resources, matching the
existing resource workbook. With filters it lists resources directly referenced
by the selected payable analyses. Rows include basic rate, tax, discount,
reference and category. It does not replace basic rates with adjusted rates.

Resource usage always applies the selected payable schedule codes and excludes
SUB ANALYSIS quantities. It uses the engine's optional `get_res_usage(codes=...)`
selection, preserving the existing last-Multiply factor, rounding each entry's
quantity to four places before summing, and direct-resource semantics. It does
not recursively expand dependency resources or apply Weight rows to quantities.
Adjusted rates/amounts match the existing usage view. Usage amounts are not
promised to equal the estimate total, which can include analysis weights and
stored schedule rate overrides. No unrelated quantities are added together.

All values, including nested analysis rows, are frozen within the snapshot;
JSON output uses detached lists. The complete assembly runs inside one read
transaction on the runtime owner thread. Existing `get_res_usage()` callers keep
their whole-project behavior; an explicit empty code list returns no usage.

## Preview and export operations

`report.preview` accepts the same revision/specification inputs and returns
`document`, escaped standalone `html`, and boolean `pdf_available`. A fixed
Python layout uses standard HTML escaping at output; project strings never become
HTML, CSS or template source. No arbitrary templates/assets are accepted. The
complete generated HTML is limited to 10 MB. The desktop displays it in an iframe
with an empty sandbox and a restrictive document CSP. Preview is continuous;
PDF provides final page numbers and contents targets.

`report.export` accepts those inputs plus `format` (`html`, `xlsx`, `pdf`), a
native-selected `path` with matching extension, and the existing
`replace_selected` chooser flag. It captures a fresh snapshot and rejects stale
revisions/dirty drafts again after the chooser. It returns `saved`, `revision`
and a list of renderer diagnostic `warnings`. There is no cached-preview export
that could silently publish data from a different revision.

HTML/PDF consume the same fixed layout. Excel consumes the same frozen row and
total values, uses literal text cells for author strings (including leading
`=`), numeric cells for amounts, a contents sheet with internal worksheet links,
repeated headings and print settings. Generated sheet names avoid collisions
and unsupported worksheet title characters. It does not add editable formulas.
The existing full-project workbook export remains unchanged.

Exports use the existing
[export publication boundary](../architecture/database-format.md#working-copies-save-and-recovery).
Rendering failures remove partial new files and preserve chooser-confirmed
portal replacements. Ordinary existing paths retain the existing exclusive-create
policy. A selected project `.eproj` file cannot be an output destination because
its extension does not match any report format.

PDF discovers a trusted `report-renderer/weasyprint[.exe]` beside the interpreter
or packaged backend, then the interpreter's sibling CLI, then the system PATH.
It requires `--version` to report WeasyPrint 70 or newer. Requests/project files
cannot provide an executable path. Missing/older renderers disable PDF while
HTML and Excel remain available. No native WeasyPrint imports or new runtime
Python dependencies are introduced.

The shared managed CLI adapter receives UTF-8 HTML on stdin, permits only data
URLs, rejects redirects/failed assets, hides its Windows console and kills/reaps
the direct child after a 60-second timeout. It validates the completed PDF and
limits output to 50 MB and returned diagnostics to 16 KB. These are post-render
checks, not hard memory/disk quotas. Full cancellation/process-tree control and
installed renderer packaging still need release hardening.

## Desktop workspace lifetime

[`ReportWorkspace.vue`](../../modern/src/components/ReportWorkspace.vue) owns
composition, generation/export busy states and inline errors. Report requests
have explicit shapes in [`reportTypes.ts`](../../modern/src/reportTypes.ts).
The shell forwards Reports navigation through the existing draft guard and
retains native destination selection in the desktop adapter.

Users edit facing fields, enable/rename/reorder the six sections and
manually generate a preview. The fixed cover and contents are always included. Analyses add per-item nested
contents links. Resource/usage tables use named landscape PDF pages; cover,
schedule, analyses and signoff use portrait pages. Running section headers,
repeated headings and caption break controls keep multi-page reports readable.
Changing the definition or project revision visibly marks the preview stale and
disables export until regenerated. Section order controls both output order and
contents links. Python retains selection, rounding and validation authority.

KeepAlive retains settings/preview across view changes; document-local memory
retains them across project-tab switches. Replacing/closing a project clears
them. Settings are intentionally not saved in project files yet, and the view
states that limitation. Busy generation/export disables conflicting inputs and
navigation through the existing shell busy state. Cancellation of the native
save chooser leaves the composition intact and sends no export request.

## Real-project rendering experiment

The optional [prototype](../report-module-plan.md#try-the-prototype) can consume
this snapshot using `--project /path/to/project.eproj`, optionally with
`--organization "Office name"`. It opens an isolated working copy through Service,
uses snapshot amounts directly, closes it, then renders the existing HTML/PDF
layout. Source files remain untouched. The CLI section chooser uses the initial
three section kinds; it does not yet expose the full specification editor.
The cover identifies accepted project data instead of demonstration quantities.

Rendering remains a development experiment: optional Jinja2/WeasyPrint packages
are not app dependencies, and publication requires a fresh output directory.
The application workflow now has safe export/portal publication for its fixed
layout. Cancellation, custom template validation and installed Windows renderer
verification remain gates in the proposal.

Regression coverage:
[`test_report_documents.py`](../../tests/test_report_documents.py) and
[`test_render.py`](../../tools/report_prototype/test_render.py),
[`test_report_exports.py`](../../tests/test_report_exports.py),
[`test_report_datasets.py`](../../tests/test_report_datasets.py) and
[`reports.spec.ts`](../../modern/e2e/reports.spec.ts).
