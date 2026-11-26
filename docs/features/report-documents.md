# Read-only report documents

Current foundation, 2026-11-26. Navigation: [index](../README.md) ·
[backend](../architecture/backend.md) · [report proposal](../report-module-plan.md).

The backend can assemble accepted working-project data into an immutable report
snapshot. The Report workspace, production export service, Excel renderer,
persisted specifications and packaged PDF renderer are still future work.

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
`kind` (`abstract`, `schedule`, `signoff`), optional plain-text `title`, and optional
boolean `enabled` (default true). Instances retain their IDs, order and enabled
state, including repeated kinds with distinct IDs. No arbitrary HTML, template
source, columns or layout fields are accepted. Unsupported fields/versions,
malformed selections and IDs absent from the current project fail explicitly.
Item and category filters intersect; they never reorder the project rows.
IDs are local to the current project, so callers must not reuse them across files.

The response contains `schema_version`, `revision`, `project`, the normalized
`specification`, `schedule`, `abstract` and `total`. Financial values are decimal
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

No ORM models escape into the document. Generation does not evaluate analyses,
accept drafts, alter quantities/rates, create identities, advance revisions,
change clipboard contents or add undo entries. The service retains its existing
draft/revision boundaries. Report settings are not written into project files.

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
Production safe export/portal publication, cancellation, template validation and
Windows installation remain gates in the proposal.

Regression coverage:
[`test_report_documents.py`](../../tests/test_report_documents.py) and
[`test_render.py`](../../tools/report_prototype/test_render.py).
