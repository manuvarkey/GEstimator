# Repository code quality audit — 2026-11-23

Navigation: [documentation index](README.md) · [current architecture](architecture/README.md)
· [development workflow](development-guidelines.md) · [verification](testing.md).
This is a dated audit/debt record; current contracts are maintained separately.

## Scope and conclusion

Reviewed the repository structure, development/release tooling, Python service
and engine boundaries, measurement loading and editing, Vue orchestration and
table helpers, native Rust bridge, stylesheet organization and regression suite.
This is a structural and targeted source audit, not a claim that every branch,
platform or external input has been exhaustively verified.

The domain/UI separation is sound: Python remains authoritative, desktop and MCP
share operations, and project copies, revisions, drafts and undo have useful
regression coverage. The main maintainability problems are oversized orchestration
modules, weak types in parts of the frontend, accumulated CSS overrides and an
absence of checks on ordinary pull requests. Project-loaded measurement text also
crossed an unsafe execution boundary; that warranted an immediate fix.

## Findings and changes

| Priority | Finding and evidence | Result |
| --- | --- | --- |
| P1 | `RecordCustom`, six measurement templates and `Spreadsheet.read_rows` evaluated numeric text with Python `eval`. Loading saved records bypasses the modern request validator. | Replaced these calls with `estimator/arithmetic.py`. It accepts bounded numeric AST operations and preserves legacy integer/float types and rounding. Regression tests assert that record callbacks and worksheet input never call the file-opening payload. |
| P1 | `template_loader.load_template` constructed a Python filename directly from a project-supplied plugin name. | Validate identifier names before reading source; reject symlinks and paths outside the installed template directory. Content-keyed caching and independent template instances are retained. Installed Python templates remain trusted executable code. |
| P2 | `ProjectEditor` combined transaction/history ownership with measurement presentation, item editing and record editing. `project.py` was 2,287 lines. | Extracted views/item operations into `measurements.py` and record operations into `measurement_records.py`. Small forwarding methods retain callers' existing API. Transaction and draft history ownership stays in `ProjectEditor`/`MeasurementDraft`. That phase left 1,869 lines; the later library extraction below leaves 1,527. |
| P2 | `App.vue` owned navigation/history/tab memory and MCP polling alongside shell rendering and the unsaved-work guard. | Extracted `useWorkspaceNavigation.ts` and `useWorkspaceMCP.ts`, with explicit workspace/guard/load/focus callbacks and document-local lifecycle state. The shell retains the single draft guard. Shared selection, history, ribbon context and status contracts are unchanged. |
| P2 | Project file dialogs, recovery, recent paths and OS-open completion/handoff also lived in `App.vue`. | Extracted `useProjectFiles.ts` with explicit guard, tab-action and post-save callbacks. Reused the guarded open handler for file-dialog submission. Native listener installation/cleanup and the single pending-action guard remain in the shell. `App.vue` decreased from 2,052 to 1,903 lines without template changes. |
| P2 | `ProjectViews.vue` combined main-table coordination with record-page/detail loading, description editing, measurement properties and link-picker state. | Extracted `useMeasurementRecords.ts` and `useMeasurementProperties.ts`, retaining the common command/error boundary and parent-owned memory snapshot. `projectViewTypes.ts` types nullable measurement detail, metadata, records, links and properties. `measurementColumns.ts` isolates the existing Tabulator typing gaps and text-safe column presentation. |
| P2 | `ProjectEditor` also owned attachment snapshots, catalog/notes presentation and a large library import pipeline. | Extracted `libraries.py` and `library_import.py`; factored the dependency stage and source ordering into helpers. Editor methods remain forwards, and the editor retains attachment lifetime and transaction/undo ownership. The factoring reconstructs the original import AST; focused and full backend regressions cover its behavior. |
| P2 | No root agent rules, no formatter configuration, inconsistent imports/spacing, and failing `cargo fmt --check`. | Added root rules and compatible Ruff, Prettier, rustfmt, EditorConfig and Git newline settings. Applied formatting to the changed Python files and the small Rust crate. Existing license headers are retained. |
| P2 | The only workflow was the tagged/manual release build. | Added a separate pull-request/master quality workflow with changed-source formatting, Python tests, frontend type/build checks, browser workflows and Rust tests/Clippy. Its hosted execution remains to be observed after pushing. |

Arithmetic remains bounded. Both numeric modes now share `NumericExpression`,
which allows `+ - * / // % **`, `pi`, `e` and the math functions documented in
the [manual](manual/README.md#numeric-expressions). Direct function calls are
explicitly listed; attribute access, containers, booleans, arbitrary names and
Python execution remain blocked. Input is limited to 200 characters and 64 AST
nodes, with finite real intermediate values of magnitude at most `1e12`.
Power exponents lie between -12 and 12, including fractional exponents for real
results; `round` digits are integers in the same range. Invalid loaded numeric
cells retain their raw text and use the engine's zero/blank fallback. Financial
entry uses Decimal arithmetic and six-place computed-entry rounding; template
evaluation retains integer/float semantics. Trigonometric functions necessarily
use standard math approximations. Custom installed templates should use
`evaluate_number` for their inputs.

## Remaining work, in order

| Priority | Area | Next bounded change and acceptance check |
| --- | --- | --- |
| P2 | `modern/src/App.vue` — 1,903 formatted lines | Navigation/history, MCP refresh and project file workflows are extracted. Next separate bounded analysis/resource dialog state while retaining one draft guard. Verify navigation, project tabs, agent refresh and close guards with existing browser workflows. |
| P2 | `modern/src/components/ProjectViews.vue` — 2,205 formatted lines | Record-page state and measurement properties are extracted. Next separate schedule/resource-specific dialog state. Required formatting expanded previously compressed markup; the formatted baseline would be 2,437 lines. Preserve focus, selection, paging and tab memory; do not duplicate `DataTable` behavior. |
| P2 | `modern/backend/project.py` — 1,527 lines; `service.py` — 1,023 | Library snapshot/import handling is extracted. Next separate schedule/resource edit families or analysis draft operations. Keep `call`, revision checks, transaction scopes and undo ownership easy to find. Current measurement dispatchers retain related operation variants; split by operation family when extended. |
| P2 | `library_import.import_items` — 255 lines; navigation, project-file and measurement composable setup | The import coordinator retains coupled conflict, batch numbering and final rate policies so it does not publish per row; split policy families when next extended. Composable setup keeps one closure for related state/lifetimes and smaller nested operations. File workflows share dialog/open completion state; measurement owners share record/detail lifetimes or staged form/picker state. These owners exceed the function-size review trigger for an explicit ownership reason, not because the trigger was disabled. |
| P2 | `modern/src/style.css` — 2,375 lines | Consolidate repeated selectors by feature while preserving cascade order. Separate table, ribbon, dialog and document-rail rules only with dark/light/narrow visual verification. Do not move rules merely to reduce line counts. |
| P2 | Main-table `GridRow` and generic table callbacks in `ProjectViews.vue`/`DataTable.vue` | Measurement detail and records now have explicit types in `projectViewTypes.ts`. Next discriminate schedule/resource/measurement-list DTOs and type the generic table callbacks. Keep Tabulator compatibility at its adapter, keep `vue-tsc` strict and do not add broad casts to hide disagreements with the backend. |
| P2 | `estimator/data/schedule.py` — 3,466 lines; broad legacy exception handlers | Extract persistence/export concerns only with engine result and workbook round-trip comparisons. Narrow exception handling incrementally so malformed input does not hide programming errors. Shared engine reorganization has higher compatibility cost than adapter extraction. |
| P3 | Production frontend entry — about 1.26 MB, 324 KB gzip | Measure startup before splitting optional dialogs/help into async components. Retain Vite's size warning until an actual bundle change addresses it. |
| P3 | `tools/` database builders and large test modules | Split by build phase or workflow when next edited. Preserve generated database results; avoid unrelated rewrites of occasional maintenance tools. |

The remaining items are explicit follow-up debt, not completed refactors. A
single broad rewrite of all large files would make behavior changes harder to
review and validate. The root rules require extracting new concerns before
growing these hotspots further.

## Enforcement

- `AGENTS.md` defines ownership, safe input handling, meaningful regression
  coverage, comments in simple English and logical-step comments for complex
  functions. 600-line modules and 80-line functions trigger review, not automatic
  rejection; line count alone does not establish code quality.
- `pyproject.toml` uses the requested FreeCAD-HVAC settings: 120 columns,
  `skip-magic-trailing-comma`, `E302/E303/I` and
  `split-on-trailing-comma = false`, with preview enabled for spacing checks.
- `tools/check_quality.py` checks staged, unstaged and untracked source. With
  `--base <ref>`, it also checks changes since the merge base. It runs Ruff,
  local pinned Prettier and Rust formatting as applicable. It does not claim to
  replace tests, architectural review or a full semantic linter.
- Formatting adoption is incremental. Untouched legacy Python/Vue/CSS files are
  not a passing whole-tree formatting baseline. The current changed files pass;
  later edits must bring their changed files into the checked-in style.
- Current development contracts now have a [documentation index](README.md),
  separate [architecture references](architecture/README.md), source/test maps,
  [verification guide](testing.md) and explicitly labeled migration history.
  `tools/check_docs.py` checks local targets/anchors and current-page discovery
  in CI. Documentation links are checked automatically; semantic accuracy still
  requires comparing the owning source and tests when behavior changes.

Actual commands, results and platform limits are recorded in the
[validation log](migration/validation.md).
