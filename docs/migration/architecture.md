# GTK → Vue/Tauri migration: first vertical slice

## Scope and acceptance

Phases 1–4 foundation: open a version 2 project into an isolated workspace, load a schedule analysis, edit all five row types and resource quantities/definitions, calculate using the original Python model, undo/redo, save a new compatible project copy. Preserve GTK startup and every original calculation method. This is a prototype, not feature parity or a replacement release.

## Source audit

* `estimator/__init__.py` originally housed MainWindow/MainApp, project lifecycle, imports/exports, settings, worker threads and GTK orchestration. Its implementation now lives unchanged in `gtk_app.py`; lazy public entry points preserve `from estimator import MainApp`. `gestimator.py` remains the GTK executable.
* `view/schedule.py` is a GTK TreeStore schedule/category/child editor, with resource-selection dialogs, hierarchical search, multi-selection, copy/paste, quantity/rate updates, colouring and Tab traversal. `view/analysis.py` edits deep copies of `ScheduleItemModel`; calls into the database for existing resource definitions and owns a temporary undo stack. It supports group/resource insertion, resource duplication under a new code, subtotal/weight/times/round, resource remarks, analysis remarks, spreadsheet analysis import and pickle/base64 clipboard payloads. Ctrl+C/V, Tab/Shift+Tab and Escape are explicit view handlers. Main-window actions supply other shortcuts. The modern input accepts bounded arithmetic rather than arbitrary Python expression evaluation.
* `view/measurement.py` orchestrates headings/custom measurement dialogs, properties, copy/paste and selection. `data/measurement.py` stores serializable headings and custom items, string cell records, schedule references, remarks and user data. Custom templates in `meas_templates` dynamically provide dimensions, column types and calculation callbacks. RecordCustom currently evaluates numeric expressions and uses template arithmetic; it is not a Decimal-only measurement engine. An unused GTK import was removed; no calculation was changed.
* `data/schedule.py` owns Peewee schemas, CRUD, transactions, analysis parsing and evaluation, dependencies, libraries and openpyxl export. `misc.py` combined constants, path helpers, spreadsheet formatting, command execution and GTK widgets. Widgets/dialogs were extracted to lazy `gtk_misc.py`; Spreadsheet remains headless. Calculation methods remain unchanged. The legacy v1 migration target/connection cleanup was corrected after a failing regression fixture.
* Dependencies: requirements pin appdirs, openpyxl, peewee and prettytable; GTK packaging additionally uses PyGObject/Cairo. Legacy installers include Flatpak, Snap, NSIS and a Windows-specific PyInstaller spec. No pre-existing automated test suite was found. Real library fixtures live in `estimator/database` and `Other databases`; spreadsheet source examples are in `spreadsheets`, and an early design schema is in `design documentation`.

## Persistence and calculation authority

`.eproj` is SQLite, not an archive. `get_orm_model` defines ProjectTable (key/value metadata, JSON measurement), ordered schedule/resource categories, ScheduleTable (unique code, parent/category FKs, Decimal rate/quantity, order/suborder, colour and remarks), ResourceTable (unique code, unit, Decimal base rate/VAT/discount, category/order), SequenceTable (schedule FK, unique schedule/sequence position, itemtype/value/code/description) and ResourceItemTable (schedule/sequence/resource FKs, quantity, remarks). Existing library switching dynamically rebinds Peewee models. Foreign keys and transactions remain owned by Python.

The file marker is `GESTIMATOR_FILE_REFERENCE_VER_2`. Legacy validation may migrate v1 by adding colour; that path requires separate tests (the migrator's literal table name is suspicious). Modern opens v1/v2 read-only and copies via SQLite backup before using the existing database class. The existing v1 migration runs only on that copy. No schema changes occur. Original files are never overwritten; save-copy exclusively creates a new destination. Save commits the current analysis and calls existing dependent-rate propagation with explicit schedule codes: its default None path fails in `get_sub_ana_items`. Original two-pass subanalysis depth is retained. The prototype deliberately avoids original-file migration and concurrent GTK/modern writes to the same file.

Analysis evaluation is sequential. A group rounds each VAT/discount-adjusted resource rate to cents, then each quantity × rate to cents; group totals add to cumulative total and reset the weight base. SUM captures cumulative total as the weight base. WEIGHT adds a rounded fraction of that base without changing it. TIMES replaces total and base. ROUND changes total, retaining the prior base. `get_ana_rate` returns the last result (or final group subtotal), not necessarily cumulative total. `Currency` uses Decimal HALF_UP, including legacy fractional-place rounding. Decimal strings cross IPC; no JavaScript financial arithmetic is used.

## New architecture and lifecycle

`modern/src` uses Vue Composition API, TypeScript, PrimeVue/Aura accessible dialogs, native workspace controls and Tabulator 6. Calculation columns are read-only. Tree rows have stable session UUIDs (resource IDs kept beside legacy lists); positions are resolved only in the service. Column sorting is disabled to preserve visible calculation order. Text is rendered using Tabulator text formatters, never untrusted HTML.

`modern/src-tauri` starts one persistent Python sidecar. Rust exposes a single asynchronous invoke command, queues requests under a mutex on a blocking worker, writes JSON Lines, correlates UUID request IDs and emits progress events. Python serializes commands and SQLite access in its own process. Errors are structured. A failed/timeout connection kills the process; the next request restarts it and the UI reports draft loss. There is no edit replay or crash recovery of unsaved drafts yet. Shutdown/EOF closes the service; desktop exit terminates and reaps the child. Production users do not need Python: `bundle_backend.py` builds a PyInstaller one-file executable and names it with Tauri's host target suffix. Build separately on each platform. Development uses the repo `.venv`.

The service validates types, decimal ranges, row IDs, revision and supported fields; mutations evaluate before entering undo history and restore a deep snapshot on failure. One bounded draft undo stack covers resource definitions and analysis rows; Tabulator history is not enabled. SQLite operations use the original model methods and transactions. Metadata IDs are ignored by the existing persistence writer. GTK and modern clipboard formats are intentionally separate: modern row copying is session-local structured Python data, never deserialized pickle.

## Reports

Existing Spreadsheet/openpyxl helpers and all export methods remain authoritative. Regression tests exercise analysis Excel formulas after project round-trip. Full worksheet/formula/style/merge/print-setting equivalence is not established. Modern mapped schedule/resource imports use openpyxl; analysis/measurement spreadsheet imports still require GTK. No PDF implementation was found in the current orchestration. A future shared report DTO from Python can feed Jinja2/WeasyPrint, independently of Tabulator, but no replacement report path is introduced here.

## Limitations and next gates

The current editor coverage and unfinished parity work are maintained in [the feature parity ledger](parity.md). Schedule, resource and measurement editors, project settings, external-library snapshots, v1 migration and workbook import/export are now implemented. Native interaction, complete clipboard/settings/category workflows, save/recovery and full report equivalence still require further work.

Next: finish the parity ledger's remaining editor operations and save/recovery lifecycle; validate native interactions on target systems; compare larger real estimates and report outputs with GTK; benchmark populated trees and package supported platforms. Keep GTK until parity gates pass. Rollback is to launch `gestimator.py`; no original database or GTK view was removed.

References: [Tauri sidecars](https://v2.tauri.app/develop/sidecar/), [Tabulator tree data](https://www.tabulator.info/docs/6.x/tree/), [Tabulator editing](https://www.tabulator.info/docs/6.x/edit/).


## Workspace refinement — CivilKit reference

The next increment adapts the reference's ribbon, docked panels and dark/light design approach to the existing estimation workflows. It does not reuse CivilKit's calculation engine or worksheet language. No external CSS/font requests are required. `AppIcon.vue` supplies local SVG controls, `AnalysisTable.vue` owns Tabulator lifecycle/rendering/selection, and `useWorkspace.ts` owns request orchestration and authoritative state. The initial shell provided Home/Analysis/View tabs; the unified context ribbon described below now provides searchable/paged schedule and resource navigation, an editable selection inspector, persistent theme selection, table density, group expansion and an always-visible final rate. The amount column stays pinned when a narrow editor requires horizontal scrolling. Resource definitions and all amounts still come from Python.

The Tauri dialog plugin supplies native open/save pickers. Paths can also be entered in the accessible project dialogs. Capabilities grant dialog open/save and window destruction for an explicitly confirmed close. User-facing file I/O failures now have structured FILE_ERROR responses. Existing-file protection remains in Python.

The service adds dirty-state metadata and guards project/item replacement. The clean checkpoint is an independent copy of the analysis/resource definitions, so undoing back to the checkpoint clears dirty state and a failed save does not mark it clean. Save-copy resets the checkpoint only after the database backup succeeds. Both UI dialogs and direct API clients must supply explicit discard intent to replace an unsaved draft. No automatic migration, original-file write, or recovery journal is added.

Browser tests use the actual Python service and fixtures with a test-only replacement for Tauri transport; no test bridge is shipped in the application. Native picker/close interactions, WebKit differences and cross-platform behavior remain separate validation gates.


## Project editors and native typography

`ProjectViews.vue` provides the schedule/resource/measurement workspaces; `DataTable.vue` owns their Tabulator interaction, including typed cell edits and clipboard matrices. `backend/project.py` wraps the existing database CRUD and measurement model/template methods. It uses SQLite backup snapshots for transaction-wide undo/redo, rather than reimplementing persistence or relying on table history. Analysis Apply writes to the working database; database mutation is blocked while an uncommitted analysis draft would be overwritten. The parent window blocks conflicting actions/close while a project operation is running.

Resource price changes update the dependency closure using existing `update_rates`, retaining its sub-analysis calculation semantics. Applied analysis state is reloaded from the database while preserving row identities. This keeps displayed rates/quantities in agreement with the actual persisted decimal precision.

`backend/importing.py` provides previewed, mapped openpyxl imports with a single transaction/snapshot and an explicit duplicate policy. All five legacy workbook export methods remain the output authority. A separate scratch database supports analysis-only export of an uncommitted draft without changing the working project.

Tauri supplies native dialogs; the application popup menu lives in Vue. On Linux it reads GTK's `gtk-font-name` through Pango and sends its family/point size to Vue; changes are observed live. This GTK dependency is confined to the native Rust shell. The Python service remains importable without GI. All UI controls inherit the native base font size; font/theme assets are local.


## Unified application menu and context ribbon

Development now takes place on `migration/vue-tauri-desktop`, with a preserved baseline commit and separate commits for tested milestones. The native menu bar is removed. `ApplicationMenu.vue` provides the logo-area popup using PrimeVue's accessible menu behavior. File commands and active-editor undo/redo share an icon-only quick-access toolbar.

The ribbon tabs are the only view switcher. Analysis tools are rendered by the shell; project editor tools are teleported into the same ribbon host by the editor that owns their handlers/state. This moves controls without duplicating command logic. The previous document-tab strip and separate Home/View tool tabs are removed. History availability is reported by the active editor to the quick-access toolbar; text fields retain their normal undo/redo shortcuts. Dirty-analysis navigation guards remain authoritative when a ribbon tab requests a view change.


## Category, deletion and measurement ordering milestone

Schedule/resource selection expands stable database IDs to complete categories and schedule subtrees on the backend. Display filters and page boundaries never define deletion/import scope. Overlapping selections are deduplicated. Empty categories remain visible/editable. Category ordering swaps only existing category order values inside a project transaction. No schema or calculation-model changes are introduced.

Deletion previews report total items/categories, used resources and linked measurement slots. Used resources require an explicit policy: preserve them while deleting unused resources, or remove their analysis references and recalculate the affected dependency closure with the original engine. Atomic legacy deletion methods run under the existing project-wide transaction/snapshot, so undo restores definitions, analyses, rates and measurement associations together. Schedule deletion clears links to deleted IDs but retains all records and remarks, preventing SQLite primary-key reuse from silently retargeting measurements. Pre-existing dangling links are exposed to the UI. This deliberate behavior difference is recorded in the parity ledger.

Whole-category library imports expand beyond the current page, visit parents before children, retain resource prefixes and map imported parents to disambiguated destination codes. Imports emit progress and return imported/skipped counts. The source remains an isolated read-only snapshot. Measurement record arrows use the existing record-move service operation; records and their session IDs move together with undo/redo.

## In-place save and recovery

The source remains isolated during editing. Explicit Save fingerprints the original database and SQLite journals, stages a complete snapshot, preserves a numbered sibling backup and replaces the original file. An advisory lock serializes modern saves. GTK does not participate in that lock, so concurrent GTK save and clean-machine recovery remain validation gates. The engine checkpoints a dirty workspace and its pending analysis in local app data. Reopening a checkpoint restores a new unsaved project, and successful saves clear its checkpoint.
