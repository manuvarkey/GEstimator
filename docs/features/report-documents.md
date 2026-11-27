# Read-only report documents

Current workspace, saved definitions and export workflow, 2026-11-27. Navigation: [index](../README.md) ·
[backend](../architecture/backend.md) · [report proposal](../report-module-plan.md).

The Reports workspace composes abstract, schedule, analyses, resources, resource
usage, measurements, notes and signoff sections from immutable accepted-project snapshots. It previews and exports
standalone HTML, Excel and PDF when a suitable renderer is installed. Office layout templates and packaged PDF renderer distribution remain future work.

## Request and response

`Service.call("report.document", params)` requires an open project and the current
integer `revision`. `specification` is optional and defaults to an empty object.
A stale/missing revision or a dirty analysis/measurement draft fails without
changing state. A `discard` flag does not bypass this read's draft protection.
Accepted but unsaved project edits are included; no save or recalculation occurs.
This is an internal desktop operation, not an additional public MCP tool.

[`ReportAppearance.vue`](../../modern/src/components/ReportAppearance.vue) owns
the typography inputs. The version-one specification accepts only:

| Field | Meaning |
| --- | --- |
| `schema_version` | Integer `1`; omitted means version one |
| `sections` | Ordered list of up to 20 section objects; omitted means abstract, schedule, signoff |
| `item_ids`, `category_ids` | Lists of up to 10,000 unique positive decimal-string database IDs; omitted/null means all; empty means none |
| `title`, `organization`, `reference`, `issue_date` | Plain text, using the backend text length limit; issue date is a display label |

Each section has a unique `id` matching `[A-Za-z][A-Za-z0-9_-]{0,63}`, a supported
`kind` (`abstract`, `schedule`, `analyses`, `resources`, `resource_usage`, `measurements`, `narrative`, `signoff`), optional plain-text `title`, and optional
boolean `enabled` (default true). Narrative sections also accept a plain-text
`body` of up to 10,000 characters; nonempty bodies on other kinds are rejected. Instances retain their IDs, order and enabled
state, including repeated kinds with distinct IDs. Sections also accept the bounded
column/orientation settings described below. Arbitrary HTML, template source,
CSS and unknown layout fields are rejected. Unsupported fields/versions,
malformed selections and IDs absent from the current project fail explicitly.
Item and category filters intersect; they never reorder the project rows.
IDs are local to the current project, so callers must not reuse them across files.

The response contains `schema_version`, `revision`, `project`, the normalized
`specification`, `schedule`, `abstract`, `total`, `analyses`, `resources`,
`resource_usage` and `measurements`. Disabled optional datasets are empty lists. Financial values are decimal
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
draft/revision boundaries. Document generation never writes report settings;
explicit definition persistence is described below.

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

## Measurements and notes

Measurements are detached from accepted project data using the installed engine
and existing column/output labels. Sheets retain their original project number,
category heading, description, template name, rendered record values, template
constants and independently labelled outputs with schedule code, description,
unit, quantity and link remarks. Quantities retain measurement-template rounding;
outputs with unlike units are never added together or applied to schedule quantities.

Without filters every sheet is included, including unlinked sheets. Item/category
filters include a whole sheet when at least one link targets a selected payable
schedule item. All outputs of that sheet remain visible, including other links,
so multi-output template records remain interpretable. Empty selections include
no sheets. Disabled measurement sections do not load measurement models. Existing
report revision and dirty-draft guards also protect this read.

Each narrative instance owns a bounded Jinja2 plain-text template in its section `body`.
Accepted fields and limits are described below. HTML escapes the resolved text and
retains line breaks; Excel writes literal wrapped text cells. Notes accept no HTML
or external assets. Notes
and measurement settings share the existing open-tab memory and stale-preview
behavior; applying and saving their definition is described below.

## Report presentation

Reports use numbered collapsible settings groups beside the preview, following
[Open Planner Studio's Gantt report studio](https://github.com/OpenAEC-Foundation/open-planner-studio/blob/main/src/components/panels/reportStudio/GanttReportStudio.tsx).
**Report details** contains facing fields; **Page and typography** contains font
selection and scale. Individual section headers summarize inclusion and page
orientation. Expanding another section closes the previous section's settings;
inclusion and ordering controls remain available while collapsed.

[`ReportAppearance.vue`](../../modern/src/components/ReportAppearance.vue) owns
the typography inputs. The version-one specification accepts `font_family` (a plain family name up to
200 characters, default empty) and `font_scale` (a finite number from 0.6 to 2,
default 1). The desktop's **Report font** dropdown reuses `program.fonts`, the
existing system-font inventory. Empty selects bundled Iosevka with a monospace fallback. Saved unavailable families remain selectable and labelled; rendering
uses local fallback fonts when necessary. Fonts are not bundled in project files.
**Font scale (%)** scales body, tables, headings and running text together; it does
not change physical page margins. Values are validated in Python, and family
names are quoted as CSS strings so they cannot introduce markup/styles. Both
settings use the same explicit Apply/Save, Undo/Redo and stale-preview boundaries
as other report settings.

All A4 print pages have **20 mm margins on all four sides**, including landscape
sections. Excel worksheets use the same physical margins and selected family /
scale. HTML/PDF use a page-number tab, horizontal header rule and running section
heading inspired by the
[GElectrical report stylesheet](https://github.com/manuvarkey/GElectrical/blob/master/gelectrical/templates/report.css).
A ruled footer shows the organization (or project name), GEstimator and page
count; the cover suppresses running furniture. Excel uses corresponding text
headers/footers. Screen HTML stays continuous; PDF provides final pagination.

Column proportions follow field meaning across HTML/PDF and Excel: descriptions
receive most space, unit/code fields stay compact, amounts/quantities have room
for numeric values, and remarks/reference/category fields get intermediate
widths. Hiding or reordering columns redistributes their relative space. Variable
measurement tables use known field weights with equal fallback widths for
unrecognized template labels. No values or estimate calculations change.

## Columns and page orientation

Each section accepts `orientation`: `auto` (the default), `portrait` or
`landscape`. Explicit settings control that section's A4 PDF pages and Excel
worksheet orientation. Standalone HTML uses the same print CSS; the continuous
screen preview does not simulate paper dimensions. Cover and contents retain
their fixed layout. Auto preserves existing format defaults: resource, usage and
measurement PDF sections are landscape; other PDF sections are portrait. Excel
uses its existing table-width defaults.

The fixed tables accept `columns`, an ordered, nonempty list of unique keys:

| Section kind | Available keys, in default order |
| --- | --- |
| `abstract` | `category`, `amount` |
| `schedule` | `code`, `description`, `unit`, `quantity`, `rate`, `amount`, `remarks` |
| `resources` | `code`, `description`, `unit`, `rate`, `tax`, `discount`, `reference`, `category` |
| `resource_usage` | `code`, `description`, `unit`, `quantity`, `rate`, `amount`, `category` |

Omitted/null columns preserve existing defaults, including schedule remarks in
Excel and their omission in default HTML/PDF. Explicit selections use exactly
the same chosen order in every format. Other section kinds reject non-null column
settings: analysis and measurement templates retain their complete structures.
Invalid, duplicate, unknown or empty selections fail before rendering.

[`tables.py`](../../modern/backend/reporting/tables.py) owns the validated column
catalog and shared projection of immutable row values. Column settings never
filter data or change totals. Schedule heading quantities/rates/amounts remain
blank. Excel retains numeric amounts and quantity precision after reordering;
a separate estimate summary remains visible even if Amount is omitted or moved
first. Literal text and existing escaping rules also apply to selected columns.

In Reports, expand a section header to configure its columns and page layout.
[`ReportSections.vue`](../../modern/src/components/ReportSections.vue) owns stable
instances, numbered enable buttons, keyboard/drag-handle ordering and adding/removing
sections (up to 20). A section's badge is a toggle button with `aria-pressed`;
there is no separate inclusion checkbox. Drag the handle or focus it and press
Alt+Up/Down. **Add page or section** can repeat any section, including independent
signoff sections. Each instance retains its own title, body, columns, signatures
and pagination. [`ReportSectionLayout.vue`](../../modern/src/components/ReportSectionLayout.vue)
owns bounded column/orientation inputs. Apply and Save explicitly to persist.

## Estimate defaults, signature blocks and notes templates

Program settings has **Estimate defaults** for report title, organization,
reference, issue date, notes pages and one to six signature blocks. Each block
has an editable plain-text `caption` and multiline `body`. The program preference
uses the existing validated local settings envelope. New projects copy it into
an optional `project_estimate_fields` JSON project setting. Project settings shows
these fields with per-field **Use default** controls and the corresponding program
value. Editing them uses the existing ProjectEditor undo/save boundary. Existing
projects without that key can accept program defaults through Project settings;
reading or previewing alone never writes them.

A Reports tab without an accepted report definition loads these project values
(and program fallback values for an older project). A saved report definition
retains its explicit report overrides; **Reload report settings** reloads it or
the project defaults. The initial order is Notes, Abstract, Schedule, Signoff,
Analyses, Resources, Usage, Measurements. Notes is initially included when its
default text is nonempty. Signoff defaults to continuing after Schedule;
`new_page: true` gives it its own page/sheet. Inline Excel signatures preserve the
preceding table's geometry, orientation and repeated rows. Multiple signoff
sections and one to six independent caption/body blocks per section are supported.

`each_item_page` (default false) applies only to analysis/measurement sections.
Their items are grouped by category in first-occurrence order, with nested category
and item contents links in HTML/PDF. Measurement contents now has individual sheet
targets. Item captions use normal body size in bold. Per-item pagination inserts
PDF page breaks and Excel row breaks; a long item may continue beyond its first
page. Category captions stay with their first item. `show_name_of_work` (default
false) adds the project name above the abstract/schedule table.

Notes pages are edited in [`ReportNotesEditor.vue`](../../modern/src/components/ReportNotesEditor.vue).
**Add notes page** creates up to three explicit page areas; form feed separates
pages in the stored `body`. Each starts a new printed page (Excel row break), and
long text can flow farther. Templates resolve once against the immutable captured
estimate. Fields: `project_name`, `name_of_work`, `title`, `organization`,
`reference`, `issue_date`, `estimate_total`, `item_count`, `category_count`.
For example: `Work: {{ name_of_work }} — {{ estimate_total }}`. Jinja2 `if`
conditions and `upper`, `lower`, `title`, `trim`, `default` filters are supported.
The sandbox parser allowlists the AST before compilation; loops, calls, attributes,
imports, includes and arithmetic are rejected. Undefined fields/template errors
fail visibly. Source is bounded to 60,000 characters / three pages and 2,000 AST
nodes per page; resolved output to 100,000 characters per page. Resolved values
are plain text, escaped in HTML and written literally in Excel. Raw template
source stays in the saved definition. Project field values remain primitive text; only the allowlisted notes AST is compiled by Jinja.

Bundled Iosevka Regular/Bold faces and their OFL license live under
[`estimator/fonts/iosevka`](../../estimator/fonts/iosevka/README.md); the frozen
sidecar includes them. Default HTML/PDF embeds the faces as data URLs, allowing
offline font use without system installation. Other selected families use the
system inventory. Excel stores the family name and needs that font installed in
its viewer; XLSX does not embed font binaries. Font assets count toward the
existing 10 MB standalone HTML bound. Jinja2/MarkupSafe are now runtime dependencies.

## Saved report definitions

`report.settings` requires an open project and the current integer `revision`.
It returns `{specification, warning, revision}`. An absent definition returns null
with no warning; invalid, oversized or unsupported optional data returns null
with a warning. Reads do not activate drafts or change data/history. They may
read the definition while a draft is open because no analysis/measurement data
is included. Unreadable definitions remain byte-for-byte unchanged on ordinary
open, unrelated edits, preview, Save and recovery.

`report.settings.apply` requires those same revision checks, a valid complete
`specification`, and no dirty analysis/measurement draft. A `discard` flag never
bypasses this protection. Python normalizes the version-one definition to JSON,
bounded to 1,000,000 UTF-8 bytes, and updates only the optional
`project_report_specification` project setting through `ProjectEditor.mutate`.
This creates one undo entry and marks the working project dirty. Reapplying the
identical normalized definition is a no-op. Failures roll back settings, revision
and history. The response has the same shape as the read. These are internal
desktop operations, not new public MCP tools.

Saved definitions include facing fields, section order/IDs/enabled state, titles,
notes, columns, orientation, font family, font scale, editable signatures and pagination choices. Persisted `item_ids`/`category_ids` must be null
or omitted. Explicit lists, including empty lists, are rejected for persistence
until deletion/ID-reuse invalidation is implemented; transient report snapshots
still support their existing filters. No derived values or external file paths
are stored. Project format version/tables are unchanged.

In Reports, **Apply report settings** updates the working project. **Save
project** (or Save Copy) publishes that accepted definition alongside other
project data through the normal backup/conflict boundary. Closing without saving
can discard it. **Reload report settings** explicitly replaces the tab's local
composition with the working project's accepted definition, or defaults when no
readable definition exists. It can therefore load a project Undo/Redo result
without silently overwriting local inputs during revision refresh. Apply changes
the revision and invalidates an earlier preview. Changing a definition locally
never applies it implicitly when previewing/exporting or saving the project.

Compatibility uses an additive optional key, with no destructive migration.
The archived version-two engine retained unknown project settings in the
pre-implementation save/reopen check. Future/invalid JSON is preserved until
**Apply report settings** explicitly replaces it. See the
[project format](../architecture/database-format.md#project-settings-and-measurements)
and dated [validation evidence](../migration/validation.md) for preservation scope.

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

Users edit facing fields, enable/rename/reorder and repeat section instances and
manually generate a preview. The fixed cover and contents are always included. Analyses add per-item nested
contents links. Resource/usage tables use named landscape PDF pages; cover,
schedule, analyses and signoff use portrait pages. Running section headers,
repeated headings and caption break controls keep multi-page reports readable.
Changing the definition or project revision visibly marks the preview stale and
disables export until regenerated. Section order controls both output order and
contents links. Python retains selection, rounding and validation authority.

KeepAlive retains settings/preview across view changes; document-local memory
retains them across project-tab switches. Replacing/closing a project clears
them. A fresh Reports workspace loads the saved definition from the working
project; an existing tab retains its unapplied composition until Reload report
settings is chosen. Busy generation/export disables conflicting inputs and
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
[`test_report_datasets.py`](../../tests/test_report_datasets.py),
[`test_report_customization.py`](../../tests/test_report_customization.py),
[`test_report_layout.py`](../../tests/test_report_layout.py),
[`test_report_settings.py`](../../tests/test_report_settings.py) and
[`reports.spec.ts`](../../modern/e2e/reports.spec.ts).
