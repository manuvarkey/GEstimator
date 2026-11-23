# Development guidelines

These rules keep the modern desktop application (`modern/`) maintainable as features are added. UI rules are in [ui-guidelines.md](ui-guidelines.md); planned work is in [roadmap.md](roadmap.md).

Repository-wide comment, formatting and quality-check rules are in
[AGENTS.md](../AGENTS.md). The [repository audit](code-quality-audit.md) records
current structural debt and the order for further extraction. Install
`requirements-dev.txt` and the locked frontend dependencies, then use
`python tools/check_quality.py --fix` and `python tools/check_quality.py` with the
repository virtual environment. Add `--base <ref>` to check a whole branch.

## Layering

- **Python backend owns the domain.** Calculations, parsing (spreadsheets, clipboard, analyses), validation, numbering, placement, rate updates and persistence live in `modern/backend` or the shared engine (`estimator/`). The frontend never re-implements them; it sends requests and renders results.
- **Vue renders and collects input.** Components display backend data, hold view state (selection, open dialogs, scroll) and send commands. Shared behaviour goes into composables (`useWorkspace`, `useDocumentTabs`) or helpers (`rowClipboard.ts`, `numberFormatting.ts`, `markdown.ts`), not into `App.vue` or a single view.
- **One protocol.** Every desktop and MCP operation goes through `Service.call` / `ProjectEditor.call`. MCP tools call the same methods as the desktop (`mcp_writes.py` uses `self.app(...)`), so behaviour and validation stay identical.
- **Read-only requests stay read-only.** Previews (`*_preview`, `dry_run`) either run outside `mutate` or inside `compound(..., preview=True)` so nothing is committed. Keep them before the revision check only when they cannot change data.

## Modules

- Keep a module to one concern and name it for that concern: `importing.py` (worksheet helpers and mapped schedule/resource import), `analysis_import.py` (analysis parsing and analysis import operations), `rates.py` (rate recalculation), `clipboard.py` (row transfer format), `insertion.py` (placement), `search.py` (indexes).
- `measurements.py` builds measurement views and handles item operations;
  `measurement_records.py` handles record edits. Both use `ProjectEditor` for
  draft-aware data access and leave transactions and history with the caller.
- When a module grows a second concern, split it before adding more. Prefer new files to larger `App.vue`, `ProjectViews.vue`, `project.py` or `service.py`.
- Delete code that becomes unused in the same change; do not leave parallel implementations.
- Use lazy imports inside handlers only to avoid import cycles or slow start-up; otherwise import at the top.

## Data and behaviour

- **Exact numbers.** Use `Decimal`/`Currency`; never floats for money or quantities. Parse user and worksheet numbers with `numbers.decimal` or `importing.loose_number`.
- **Measurement compatibility.** Existing measurement templates retain their
  integer/float arithmetic and rounding. Their expressions use
  `estimator.arithmetic.evaluate_number`, which bounds syntax, powers and
  intermediate values without executing Python text. This exception does not
  apply to financial arithmetic. Project-file loading must enforce the same
  safety boundary as interactive editing.
- **Shared math syntax.** Both numeric modes use `NumericExpression` in
  `estimator/arithmetic.py`. Extend its explicit function/constant list rather
  than adding another parser. Decimal entry keeps exact decimal arithmetic and
  native Decimal roots/logarithms where available; trigonometric functions use
  standard math approximations converted back to Decimal before entry rounding.
- **Undo.** Every mutation runs through `ProjectEditor.mutate` (or `compound` for multi-step operations) so it is one undo step and rolls back completely on error.
- **Shared engine changes.** `estimator/` is the calculation engine of the GTK application (kept on the `archive/gtk` branch). Behaviour changes there must keep its results identical unless the change is a deliberate fix; performance changes must be verified to produce identical output (see the `get_item` and rate-engine checks in `docs/migration/validation.md`).
- **Bulk over per-row.** Load related rows with one query (joins, `IN` chunks of ≤ 500, raw SQL for integer graphs) instead of a query per row; batch writes with `insert_many`/`executemany`. Profile with real databases (DSR 2021, DSR E&M 2022) before and after.
- **Resilient imports.** Worksheets are user data: accept common variations, report what could not be used as row-numbered warnings, and never fail the whole import for one bad row unless the result would be wrong.
- **Limits.** Validate request sizes and types at the backend boundary (lists ≤ 1000 rows, text lengths, ranges); keep MCP tool discovery within its size budget (tests enforce it).

## User-facing text

- Describe GEstimator behaviour only. Never mention the GTK application, earlier versions or implementation references in labels, tooltips, help or messages; keep such notes in code comments and developer docs.
- Name actions by outcome ("Import 12 records", "Resources moved") and put counts in buttons and status notices.

## Tests and verification

- Add a Python unit test for every backend behaviour change and a browser test (`modern/e2e/workspace.spec.ts`) for every user-visible workflow change. Test behaviour, not CSS.
- Run before committing: `.venv/bin/python -m unittest discover -s tests`, `npx vue-tsc --noEmit -p tsconfig.json`, `npm run build` and the browser suite (`npx playwright test`).
- For parser or engine changes, compare against real data (export/re-import round trips of the bundled databases, source spreadsheets in `spreadsheets/`).
- Record notable changes and their validation in `docs/migration/validation.md`.
