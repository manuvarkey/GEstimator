# Validation record — 2026-11-13

Environment: Ubuntu 26.04 x86_64, Python 3.14.4, Node 24.21.0, Rust 1.98.1, GTK 3.24.52 and WebKitGTK 2.52.6. Python dependencies are the existing requirements; PyInstaller 6.22.3 was added only to the development environment. npm/Cargo dependency locks are included.

Passed:

* `python -m unittest discover -s tests -v`: six tests. Golden original-source calculations cover every analysis item type, VAT/discount, order-sensitive weights, rounding and final-rate selection. Service tests cover multiline edits, quantity/rate edits, copying/pasting, stable identities through moves, delete, undo/redo, stale revision, invalid decimals, subprocess protocol recovery and absence of GTK imports. Real DSREM2022 database tests cover isolated opening, paging, transaction rollback, edited analysis/resource persistence, saved calculated rate, project metadata preservation, source hash preservation, overwrite refusal and analysis Excel formula output.
* `npm run --prefix modern build`: TypeScript checking and production Vue build. One expected bundle-size warning: approximately 800 kB uncompressed JS with full Tabulator and component theme.
* `cargo check --manifest-path modern/src-tauri/Cargo.toml --offline`: Rust/Tauri compile check.
* `python modern/bundle_backend.py`: native Linux one-file sidecar build, GTK excluded. Frozen executable smoke test: state request, 100 sequential requests and shutdown exit 0.
* Legacy GTK compatibility import using system Python with the installed pure-Python dependencies: MainApp and CellRendererMultilineText import successfully. The moved GTK application is byte-identical to HEAD's original package initializer; all extracted misc function/class ASTs match their originals. No source edits to the calculation/database implementation.
* `git diff --check` passes.

Performance smoke measurements (single local run, not a release budget): frozen sidecar startup/state about 204 ms, mean warm state IPC 0.033 ms for an empty demo; 10,000 resource entries with multiline descriptions, median Python state construction/evaluation 27.33 ms over ten iterations; Python maximum RSS about 59,184 KiB. These exclude Rust/WebView rendering and JSON transport of the large table. Reproduce engine benchmark with `python -m modern.benchmark`.

Not validated: interactive desktop flows, table navigation/clipboard behavior in WebKit, UI responsiveness at scale, full application memory/startup, crash replay, v1 migration, all external library variants, estimates containing custom measurement plugins, full Excel workbook/style/print equivalence, Windows/macOS installers and PDF output. A compile/build success is not feature parity. No original project file was migrated or replaced.


## Workspace refinement validation

* Seven Python regression tests pass, including dirty-state transitions, undo back to a clean checkpoint, explicit discard, metadata, and save-copy clearing the checkpoint.
* Two Chromium/Playwright integration scenarios pass against the real Python process: custom resource entry with multiline text/VAT/discount, inspector quantity editing, calculated rates, undo, calculation-row insertion, Tabulator header alignment through state updates, light/dark themes, panel toggling, compact/narrow layout; and real project loading, search/navigation, unsaved-draft guard/cancel, save-copy and clean-state feedback.
* TypeScript + Vite production build and native `tauri build --debug --no-bundle` pass. The native dialog plugin and close-event capabilities compile. The approximately 841 kB JS bundle still produces a size warning.
* The Python sidecar was rebuilt with PyInstaller. GTK entry points and calculation implementation remain unchanged by this refinement.

These browser tests substitute the Tauri transport, not the engine. They do not validate real OS dialogs, native close interception, platform WebView differences, installers, or crash recovery. Screenshots are generated from real backend responses; the project screenshot uses DSREM2022. The computer-use browser host was unavailable, so native interaction remains a manual gate.

Reviewed rendered dark/light layouts and the populated DSREM2022 analysis; preview images are in `screenshots/`. A final frozen-backend smoke check passed state retrieval, structured missing-file error and clean shutdown. Native OS interaction remains unverified.

## Schedule/resource/measurement implementation and system typography

Final checks for this increment:

* **24 Python regression tests pass.** Coverage now includes selection-based analysis insertion, entry/group/analysis metadata, safe arithmetic, independent resource duplication, copy/paste preserving destination resource definitions, apply across several items, persisted currency precision, transactional project undo/redo, schedule/resource CRUD and dependency updates, row/cell paste, mapped Excel import rollback, external-library snapshots/prefixes/source hashes, new-project settings, and version 1 migration on a copy.
* Each of the **eight shipped measurement templates** was populated through the service, compared with direct use of its existing Python callbacks, and included in a workbook export. NLBH schedule links, quantities, record duplication/undo and persisted measurement models also pass.
* **Four browser integration scenarios pass** against the persistent real Python backend: analysis editing/undo/themes, real-project draft guard/save-copy, native-sized typography plus schedule/resource/measurement editing and cell paste, and new-project/settings/mapped import. Browser tests replace only the native IPC/OS-event transport. Typography uses the current desktop setting (`Iosevka 11`) in the test transport; the actual native Rust bridge reads GTK/Pango settings, observes changes and compiles successfully.
* `npm run tauri -- build --debug --no-bundle` passes, including TypeScript, Vite and native Rust linking. The production JS bundle is approximately 874 kB uncompressed and still emits a size warning.
* The PyInstaller sidecar includes all measurement template source assets. Its frozen-process check passes new project creation, template discovery (8), custom measurement insertion, record calculation and clean shutdown.
* Legacy GTK MainApp and multiline renderer imports pass. Calculation methods were not changed. The v1 migration's table target/connection lifetime were corrected under regression tests.
* Source whitespace verification uses `git -c core.whitespace=cr-at-eol diff --check` because the legacy schedule source retains its original CRLF line endings.

Rendered schedule, resource and measurement examples are in `screenshots/*-desktop.png`. These are browser renderings of the desktop workspace, not evidence of native OS menu/dialog interaction. Native menus, OS dialogs, close events, live typography changes, Windows/macOS, cross-instance clipboard, save/recovery and the remaining entries in [the parity ledger](parity.md) remain explicit gates. This increment does **not** declare full replacement parity.


## Application menu / context ribbon milestone

Before shell edits, 24 Python tests and the production frontend build passed. After the change, five browser scenarios pass, including the four existing editing/export/import flows and a new logo-menu/ribbon/header-history scenario. Menu Escape/focus restoration, disabled file commands, icon-only accessible buttons, removal of duplicate tabs, active-view tool changes and project undo/redo through the header are covered. TypeScript/Vite and Rust checks pass. The Python protocol and calculation engine were unchanged in this milestone. Native OS interaction remains a manual platform gate.

## Category and measurement ordering milestone

* **30 Python regression tests pass** (`.venv/bin/python -m unittest discover -s tests -v`). Added coverage includes empty category visibility/rename/order/undo, category deletion with measurement records/remarks retained and links restored on undo, preventing association reuse after inserting another schedule item, used-resource protection/unused/all deletion and rate restoration, complete-category selection beyond a 100-row page, overlapping selection deduplication and invalid-ID rollback, prefixed library imports with parent code collisions/source hash preservation, and measurement record ordering with stable IDs/values/totals/undo/redo.
* **Six Playwright integration scenarios pass** against the persistent Python service. The new scenario exercises category add/move/delete/cancel/undo, whole-category library import, and both used-resource deletion policies. The measurement scenario now exercises record duplication/reordering/deletion and header undo. Testing exposed and resolved a source-switch/import race; the source selector is disabled during requests and selection resets on source changes.
* TypeScript/Vite production compilation, `cargo check --offline`, and `npm run --prefix modern tauri -- build --debug --no-bundle` pass. The approximately 895 kB uncompressed JS bundle retains its existing size warning.
* Rebuilt the Linux PyInstaller sidecar and exercised new-project creation, empty-category creation, delete preview/delete/undo, discovery of all eight measurement templates and clean process shutdown in the frozen executable.
* Reviewed the rendered category-deletion dialog with all three policy buttons and inherited system typography. Refreshed editor screenshots and added [the deletion preview](screenshots/category-deletion.png). `git diff --check` passes.

The original GTK views and calculation methods are unchanged by these two milestones. No database schema change is introduced. Full parity is still gated by the remaining workflows in [parity.md](parity.md), especially save/recovery, advanced editor operations, spreadsheet equivalence and native/cross-platform interaction. Chromium tests substitute native IPC/dialog transport; they do not verify real WebKit/OS behavior.

## Windows x64 development and packaging

Validated on Windows 11 x64 (build 26200) with Visual Studio Build Tools 2022, Windows SDK 10.0.26100.0, Edge WebView2 157.0.4341.46, Rust 1.99.0 (MSVC), Node.js 24.20.0, npm 11.19.0, CPython 3.14.8 and PyInstaller 6.22.3.

* Dependency installation, all 30 baseline Python tests, six baseline Playwright scenarios using Chrome, the production Vue build, and the locked Cargo check passed.
* The frozen Windows sidecar returned UTF-8 JSON, created a project, discovered all eight measurement templates and shut down cleanly.
* `npm.cmd run --prefix modern tauri -- dev` started the app in WebView2 and connected to the Python engine. The open-project dialog launched the native Windows file picker.
* `npm.cmd run --prefix modern tauri -- build --bundles nsis -- --locked` produced an x64 installer. Archive inspection confirmed it contains the app and sidecar executables. A clean-machine installation and the full native interaction matrix remain to be exercised.

## Resource price updates from attached libraries

All 31 Python regression tests and seven Windows Chrome/Playwright scenarios pass. The price update tests cover selected categories, exact resource-code matching with library prefixes, unmatched resources, dependent rate recalculation, undo and redo, and preservation of the attached source. The Windows x64 NSIS installer was rebuilt, and its release sidecar passed a preview, apply, dependent rate and shutdown smoke test.

## Resource usage and analysis references

The Windows suite passed 32 Python tests and eight Chrome/Playwright scenarios. Resource usage tests exercise the original aggregate quantity method, analysis multipliers, VAT, discount, search, paging, direct-reference lookup and navigation into the analysis editor. The dependency browser lists directly referencing analyses. Resource totals reflect the current project working database.

## Schedule colours and selected measurement quantities

The Schedule ribbon now exposes row colouring, selected-item quantity refresh from linked measurements, and the project Resource usage dialog. Colour and quantity updates reuse the legacy database methods and apply to explicitly selected items. Category rows and unselected descendants are excluded. Custom colours persist in project copies, and the table chooses black or white text against each saved colour.

Windows validation passed 34 Python regression tests, nine Chrome/Playwright scenarios, the locked Cargo check and the production Vue build. Coverage includes saved colour round-trips, multi-row selection, colour contrast, clearing and undo/redo, and applying legacy measurement rounding to selected items. The frozen sidecar passed a colour, undo and shutdown smoke test.

## Schedule hierarchy, numbering and library sub-analyses

Windows validation passed 36 Python tests, nine Playwright scenarios and the Vue production build. Tests cover moving whole branches across categories, cycle rejection, hierarchical codes, preserved measurement IDs and active analysis across undo/redo, prefixed library sub-analysis insertion, dependent rates and source-file preservation.

## Save, backup and recovery milestone

Windows validation passed the 38 persistence-inclusive Python tests, ten Playwright scenarios, the locked Cargo check and Vue production build. Fixtures cover backup contents, external edits, preservation of a rejected draft, recovery of an unapplied analysis, and saving a recovered project as a new file. Browser coverage exercises Ctrl+S and reopening via the recent-project selector.

## Indirect resource dependencies

The resource usage browser follows references through nested sub-analyses, deduplicates results and marks indirect references. The 39-test Python suite passed, including a three-level dependency fixture. Aggregate resource totals still use the GTK calculation.

## Workbook ranges and whole-item measurement selection

The Analysis ribbon previews and imports six-column analysis ranges through the GTK parser. The Measurement record toolbar imports editable template columns from a worksheet range, with original callbacks calculating the derived columns and totals. Formula cells rely on saved workbook values. Whole-item measurement selections support ordered copy, paste, duplication, movement and deletion. Changes are undoable.

The Windows checks passed 42 Python tests, the ten existing Playwright scenarios and the new Excel import scenario. Tests cover worksheet preview, draft undo, measurement calculations, rollback on an invalid record, and measurement selection order.

## Default analysis rows and selected rate refresh

The Analysis ribbon inserts the shipped GTK default rows into a draft. The Schedule ribbon recalculates the selected analyses and their dependents. Both operations are undoable. All 43 Python tests passed, including these operations.

## Handoff checkpoint

Implementation commit `6cd7f7d` passed 43 Python tests, 11 Playwright scenarios on Windows Chrome and the Vue production build. The locked Windows release build produced the x64 NSIS installer. Archive inspection verified the desktop and sidecar executables. A separate frozen-sidecar smoke test restored an unapplied analysis across two processes, saved it to a new file and verified the recovery entry was cleared.

The browser suite uses the real Python engine with a test transport. Native Windows coverage to date includes startup, engine connection and opening the OS file picker. Clean-machine installation, concurrent GTK saves, native dirty-window close, and the wider platform and workbook comparison matrix remain open. See the [handoff plan](handoff.md#next-milestones).

## Ribbon UI parity pass

The application menu now contains application/file commands only. Explorer visibility is an icon-only quick action immediately after undo/redo, while compact rows, group expansion and inspector visibility are owned by an Analysis ribbon View group. Schedule, Analysis, Resources and Measurements use the same fixed ribbon depth and categorized action groups. Review restored the earlier Analysis scale (24 px icons and normal-size toolbar text) and made a single row standard, with a two-row Analysis clipboard group. Familiar edit, ordering and view operations use icons with accessible names. A shared ribbon measures the actual action widths after tab changes, resizing and font loading, switching to a two-row icon layout when necessary rather than clipping at a fixed breakpoint. Tooltips explain the action, selection scope and save/undo implications.

Browser coverage includes control placement, Explorer hide/show, equal ribbon depth, all four ribbons fitting at 700/800/1100/1280/1366/1600 px, descriptive tooltip content, and manual-activation keyboard tab navigation. Arrow keys/Home/End focus tabs; Enter/Space activates through the existing draft guard. Project tables add Ctrl+D, Delete and Alt+Up/Down, including focused measurement records, while text editors retain native shortcuts and modal dialogs suppress background editor shortcuts. The measurement regression exercises record duplication by keyboard. Python computation, database and protocol implementations are unchanged. Native WebView scaling and accessibility settings remain platform validation gates; this pass does not claim the remaining data, file-safety, reporting or cross-platform parity gates are complete.

Review validation: all 43 Python tests and 11 Chromium/Playwright scenarios passed, along with the Vue/TypeScript production build, locked offline Cargo check and whitespace check. The existing production bundle-size warning remains. Reviewed the restored Analysis and Schedule toolbar scale in rendered screenshots.

## Broader parity continuation — 2026-11-14

Implemented persisted library paths and a shared attach/retry/forget manager. Browser evidence uses actual file snapshots and fresh backend processes: repeated attachment, browser reload, process restart, moved/missing sources, forgetting stale paths and byte-for-byte library source preservation. An editor session key resets visible project tables on open/new rather than retaining rows from the previous working copy.

Bulk analysis editing and configurable row templates use a bounded Python batch adapter that calls the existing row-edit, numeric-validation and calculation methods. Preview evaluates an isolated draft copy, preserves revision/history and restores the original even when an operation fails. Apply uses the existing transaction around draft edits, producing one undo step. Regression tests cover currency rounding, preview/apply agreement, partial-batch rollback, stale revisions, unsupported operations, template ordering and undo. The template is stored as versioned application preferences; saving it first validates through preview. No frontend arithmetic or database schema migration is introduced.

Measurement state now exposes the eight templates' existing column widths, expansion flags and numeric-input metadata. Python tests compare these against each original template while retaining the calculation/export checks. Browser checks exercise the 16-column steel template, user data, arithmetic strings, narrow layout and read-only calculated cells. Shared keyboard table handling covers Home/End, arrow navigation, Shift range selection, Ctrl/⌘+A, Escape and Enter-to-analysis.

Repeated transition testing exposed a loading-state render loop: a fresh empty-array prop caused table replacement, empty-selection emission and another render while the first measurement response was pending. Stable empty-row props and ignoring redundant empty selections resolve the loop; the transition passed five consecutive browser runs. Its regression now deliberately delays the measurement response to exercise the loading state. Temporary debugger instrumentation was removed.

Save/recovery fault tests cover partial snapshot writes, backup failures, failed destination replacement, failed checkpoint publication, modern save locking and stale second-window saves. They verify source/checkpoint bytes, dirty draft state and staging cleanup; replacement failure is injected and is not a claim of a real Windows file-held-open test. GTK concurrent writes, hard process interruption, clean installers, cross-instance clipboard and the full Excel/LibreOffice/platform matrix remain explicit parity gates.

Final checks: **48 Python tests** and **14 Chromium/Playwright workflows** pass. The TypeScript/Vue production build and locked offline Linux native debug build (`tauri build --debug --no-bundle -- --locked --offline`) pass. Rebuilt the PyInstaller sidecar; a frozen-process smoke check verified template discovery, non-mutating batch preview, apply/undo and measurement layout metadata. Reviewed the custom-template dialog and narrow steel-table layout screenshots. The existing JavaScript bundle-size warning remains.

The all-template export regression now compares the modern workbook with a workbook produced by directly invoking the existing GTK data-layer writers: all five worksheets match on cell values/formulas/types/styles/number formats, merges, row/column dimensions and page/print settings. With LibreOffice installed, the same test additionally uses an isolated profile to round-trip the workbook through headless LibreOffice and checks that all five sheets remain and no cached formula-error cells appear. This passed locally with all eight templates populated. It does not establish visual print equivalence or the full real-project/Microsoft Excel corpus.
