# Validation record — 2026-11-13

Filter-inspired bulk-edit continuation (2026-11-16): **93 Python tests pass**; the two affected analysis browser workflows and the new nested-condition/preset workflow pass, building on the 32-workflow baseline below. New checks exercise nested AND/OR groups, numeric ranges/inequality and empty-value operators, bounded nesting, project-independent typed MCP validation, named preset save/reload/delete across page reload, exclusion of project scope/IDs/revision from presets, and storage-write failures retaining current rules and project data. Production frontend, locked offline Linux native debug and rebuilt Python sidecar builds pass. The final frozen-process contract verifies nested rule validation, range/OR preview/apply, dependency rates, undo and original-source preservation. The reference filter components were inspected through GitHub; an interactive browser connection was unavailable.

Native packaging check (2026-11-16): the locked offline Linux debug build passes and produces `modern/src-tauri/target/debug/gestimator-modern`. The Python sidecar has been rebuilt with the project analysis-rule module.

Project analysis rules and persistent pickers (2026-11-16): **91 Python tests and all 32 Chromium workflows pass**, with browser coverage completed in two batches after the first long run was terminated at 20 successful cases. Focused follow-up checks also pass after the final changes. New regression proof covers ordered type/text/numeric matches, category/child scope deduplication, insert/replace/delete and resource reassignment, dependency rates, atomic validation, dirty/stale guards, no-op history, preview/apply equivalence, project undo/redo, MCP adapters and source preservation. Persistent picker tests verify the same table instance, page, filters, selection and exact scroll without repeating library item queries, including editor switches and the separate rate workflow. Back-to-Schedule and Alt+Left use the dirty-draft prompt. Ribbons fit every tab from 1600 to 700 px, retain equal depth/aligned full icons, support enlarged desktop text and top-align short stacks. TypeScript/Vue production builds pass. The rebuilt frozen Python backend passes rules preview/apply/dependency/undo/source-preservation contracts. The existing bundle-size warning remains; native OS interaction is still a platform test gate.

Latest workbench/agent continuation (2026-11-15): **87 Python tests and 28 Chromium/Playwright workflows pass**, with TypeScript/Vue production and locked offline Linux native debug builds and frozen-backend MCP read/write contracts. See the final section, [workbench refinement](workbench-refinement.md) and [server workflow](mcp-server.md) for scope and protocol boundaries.

Database picker refinement (2026-11-15): the Vue/TypeScript production build and five targeted Chromium workflows pass. Two new workflows cover Schedule/Resource picker category filters composed with search, source-change filter/selection resets, plain drag selection across category headings without selecting text, importing only the double-clicked item, undo and source-file preservation. The existing database/rate workflow, project category/toolbar workflow and cross-editor cell-navigation workflow also pass. Python/native code is unchanged in this increment; the prior full-suite/native results above are the baseline, not a new native platform test.

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

## Program Settings and Modify & Add — 2026-11-14

Checkpoint `dd90598` commits the preceding ribbon/editor increment. Program Settings is implemented separately, following the GTK `default_program_settings`, ProgramSettings dialog and SelectScheduleDialog behavior: workbook description splitting, five-place schedule-rate multiplication, trailing-row replacement count (0–5), default analysis rows, Modify & Add replacement rows and custom database folder access. Settings are available without a project, stored as versioned JSON application preferences, validated using existing Python decimal/currency and analysis routines, and applied only on Save. Cancel and restore-defaults act on an isolated dialog draft. The existing custom template editor shares the default-row setting; old modern custom-template JSON is carried forward. No GTK pickle preferences are deserialized.

The configured default rows are used both by the ribbon and for empty analyses as an undoable dirty draft. Modify & Add is a distinct schedule-library action and one project undo step. It preserves the GTK guard on replacing trailing rows (nonzero count, nonempty replacement, source length greater than count) and the original multiplied stored rate even when the changed analysis calculates a different rate. Tests cover code collisions, source references, invalid-settings rollback, undo/redo and unchanged library source bytes. Plain import is unchanged.

The library dialog discovers bundled and legacy-folder custom databases. The sidecar now includes DSR2021/DSREM2022 assets; stable `bundled:` identifiers avoid persisting PyInstaller extraction paths. Backend canonical-path deduplication reuses a snapshot across path aliases, and the attach result identifies the reused source for the frontend. Directory discovery is non-recursive; choosing a database still attaches an isolated read-only snapshot. Native folder opening is implemented with platform file-manager commands and remains an interactive target-platform check.

**52 Python tests and 16 Chromium/Playwright workflows pass.** Browser evidence includes no-project settings access, invalid arithmetic, Save/Cancel/reset/reload behavior, blocked preference storage preserving active settings, visible fallback warnings for invalid saved settings, real joined/split workbook exports, configured default rows/blank analyses, Modify & Add and source preservation. Reviewed the settings dialog screenshot. The TypeScript/Vue build, locked offline Linux native debug build and whitespace check pass. The rebuilt frozen sidecar passes settings validation, bundled database discovery, read-only attachment and deduplication. The existing bundle-size warning remains; native folder opening and Windows/macOS packaging are not claimed by these checks.

## System row clipboard and GTK insertion interactions — 2026-11-14

Committed the Program Settings checkpoint as `8f6c35c` before proceeding. Added the Tauri clipboard-manager plugin with text read/write permissions and a bounded versioned JSON codec in Python. Analysis, schedule, resource, whole measurement and measurement-record copy/paste now work across modern instances. The codec validates the editor/version, fields, decimal arithmetic, hierarchy and installed measurement templates before mutation. It rejects GTK pickle payloads and arbitrary Python expressions. Paste delegates to existing analysis/project transactions and undo; no calculation engine or database backend is ported.

Regression coverage exercises destination resource reuse, copied schedule stored rates, category/subtree overlap, empty categories, duplicate-code suffixes, required sub-analysis transfer/conflicts, measurement schedule-code remapping, missing-link warnings, template-matched record paste, all eight templates' raw values/user data/totals, malformed/cyclic payload rejection, stale revisions and rollback after an injected second insertion failure. Unnamed legacy resource groups use an empty string in the wire format. Numeric measurement input is validated before calling legacy callbacks. Limits are 500,000 characters, 1,000 items/dependencies and 1,000 records per measurement item.

Browser tests run two isolated browser contexts and two independent persistent Python processes, sharing only a simulated native clipboard transport. They cover keyboard/toolbar copying, toolbar/native-paste-event insertion, rejection of ordinary text by row paste, undo, matching-template records and explicit fallback feedback when clipboard access fails. Existing TSV cell paste and text-field behavior continue to pass. Tabulator's competing built-in clipboard copy is disabled. This proves the UI/protocol integration; actual OS clipboard read/write remains a native-platform gate.

Added explicit schedule Add subitem and the GTK Ctrl+I/Ctrl+Shift+I insertion shortcuts, Ctrl+E analysis and Ctrl+M colour; Analysis selects library/custom resource entry, and a focused measurement record table inserts records. Creation, duplication and paste retain schedule parents and inherit their category, including parents with a unit and nested items. Adding with a category selected uses item creation rather than category-edit dispatch. The focused keyboard browser workflow and backend hierarchy tests pass. GTK automatic numbering/insertion positions and remaining dialog/shortcut details remain in the parity ledger.

**62 Python tests and 19 Chromium/Playwright workflows pass**, along with the TypeScript/Vue production build, locked offline Cargo check, Linux native debug build and whitespace check. Rebuilt the PyInstaller sidecar and exercised all five clipboard kinds across two frozen processes, with arithmetic totals, schedule links, undo, saved-project reopening and source byte preservation. Reviewed the Schedule screenshot with the new subitem action; shared-depth/narrow-ribbon tests pass. The existing JavaScript bundle-size warning remains. Native clipboard operation, Windows/macOS builds and the broader file-safety/report/platform matrix are not established by these checks.

## Insertion, editor interactions and measurement efficiency — 2026-11-14

Implemented the three requested editor areas after `c649ec6`: selection-aware schedule/resource insertion and GTK numbering suggestions, modern keyboard/context interactions and resource editing/relocation, and the remaining measurement-template workflows. The [editor review](editor-review.md) records the detailed behavior, unusual legacy conventions and deliberate modern alternatives.

Insertion tests cover category starts, last selection in visual order, root/child positioning, explicit parent inheritance, generated codes with and without a selection, blank-code subitems, duplicate/paste hierarchy, library destination selection and unchanged source bytes. Queries honor saved child order. SQL rank counts reveal inserted rows on another page without materializing all IDs in Python. Browser evidence covers insertion into a collapsed category, selection/reveal, F2 editing, right-click analysis navigation, whole-resource editing and category moves with undo. Context menus filter actions that do not apply to categories or multiple selections.

Measurement Properties stages and atomically saves descriptions, schedule links/remarks and user data. Steel labels/constants are grouped by bar, and mapped column headings use their corresponding labels/remarks. Browser checks cover Save/Cancel, invalid arithmetic, constant normalization, schedule search/selection, safe text headers, bulk insertion, record pages, ordered multi-record copying/pasting/deletion, undo and authoritative restoration after rejected cell edits. Ctrl+A and TSV paste avoid tree-only calls on flat record tables. Module-cache tests verify reuse, independent mutable defaults and changed-source invalidation, including equal-length edits within one second.

The 200-cell/100-record comparison with the previous committed editor path returned the same NLBH total (2400). Model reads/writes dropped from **600/200 to 1/1**; observed local elapsed time dropped from 0.8032s to 0.0048s. Both paths used the new module cache, isolating batching. Regression assertions cover counts, totals and rollback rather than wall-clock thresholds. Record rendering is paged; the underlying legacy JSON model is still parsed as a whole. Template formulas, currency routines and project schema remain unchanged.

Final checks: **72 Python tests and 21 Chromium/Playwright workflows pass**, including the original all-template calculation/export comparison and optional LibreOffice round trip. TypeScript/Vue production and locked offline Linux native debug builds pass; incremental Cargo output is disabled for the native build to limit disk usage. The rebuilt frozen sidecar passed a two-process smoke check of generated numbering, blank-code children, eight template descriptors, grouped steel properties, arithmetic constants, 105-record paging, cell batches, multi-record clipboard, missing schedule links, undo and saved-project reopening with original source bytes preserved. Reviewed the steel-properties dialog screenshot. The existing JavaScript bundle-size warning remains; OS clipboard, native input methods, Windows/macOS packaging and broader real/custom-template projects remain platform/corpus validation work.

## Database selectors, text entry and original measurement display — 2026-11-14

Starting checkpoint `c813c2c` was clean. Schedule and Resources now open a separate database selector while retaining the working project and insertion target. Attachment management belongs to the fifth, equal-depth Databases ribbon tab. Attaching keeps its dialog open, updates the attached rows immediately and uses a separate Close action. Selected schedule-rate refresh previews and copies matching stored rates without replacing descriptions or analysis rows; resource refresh retains the existing rate/VAT/discount/reference update and dependent calculation behavior. Both apply through existing undo transactions. Program Settings consolidates all Modify & Add options in one tab. See the [workflow review](database-selection-workflow.md), including the proposed named-rule presets.

Native single-select controls now open themed menus matching the application menu. Browser checks click these popups to select databases and grouped General/Civil/E&M templates. Enter accepts dialog/table text; Shift/Ctrl+Enter preserves multiline descriptions. The original Python record renderer supplies accepted numeric values and Breakup, while editors retain raw expressions. All eight templates compare against their existing render callbacks. NLBH fixtures verify numbers, length, area, volume and empty records with optional blank dimensions; no formula or database schema changes are introduced.

**76 Python tests and 23 Chromium/Playwright workflows pass.** New coverage includes repeated attachment without closing, dialog-to-tab attachment refresh, selection-aware schedule/resource imports, schedule-rate preview/apply/undo, unchanged source bytes, themed popup interaction, multiline acceptance, raw-expression editing and original Breakup display. The rebuilt frozen backend passed attachment/import, rate preview/apply/undo, template groups, expression/rendered-value agreement, optional NLBH dimensions and saved-file reopening with source bytes unchanged. Reviewed the database-picker and measurement-expression screenshots. The TypeScript/Vue production build, locked offline Linux native debug build and whitespace check pass. The existing bundle-size warning and native/platform/corpus validation gates remain.

## Application ribbons and local MCP server — 2026-11-14

After `c28a449`, Databases changes only the ribbon and opens the existing attachment dialog; the unnecessary database page is removed. The new MCP tab also preserves the active editor, selection, draft, inspector and header undo context. Full ribbon buttons reserve equal caption height so one/two-line captions align their 24 px icons. Browser assertions compare visible full-button icon positions, exercise all six equal-depth ribbons at the established narrow widths/enlarged font size, and preserve schedule selection and dirty analysis state across application-tab changes.

The local authenticated, read-only MCP listener implements initialization, tool discovery/calls, notifications, ping and JSON HTTP responses using Python's standard library. Its seven bounded tools expose the current project, schedule, resources, active analysis, measurements and attachments through existing service methods. HTTP requests and desktop commands share one service/SQLite owner thread via a bounded queue. Desktop operations retain their existing timeout behavior; MCP reads have a 30-second wait limit. Start/Stop, port validation, automatic-start preferences, token rotation, copied/revealed client configuration and tool/activity inspection are implemented. Bind conflicts and invalid saved settings are visible outside the MCP tab and recover through its configuration dialog. See the [supported protocol, tools and lifecycle](mcp-server.md).

**81 Python tests and 25 Chromium/Playwright workflows pass.** New HTTP tests cover discovery/initialization, notifications, malformed transport messages, authentication, Host/Origin restrictions, concurrent desktop/HTTP reads, live project/measurement results, rejected write/extra-argument attempts, configuration validation, port conflicts, restart, token rotation and shutdown cleanup. Browser tests use the real backend and HTTP listener to verify saved automatic startup across a backend restart, client configuration, old-token rejection, startup-error recovery and unchanged project files. Existing calculation/export, clipboard, insertion and persistence workflows remain green.

A repeated browser run exposed an existing test wait that parsed plain clipboard text before asynchronous copying completed. The wait now tolerates the intermediate value, matching the other clipboard assertions. The corrected clipboard workflow and the new MCP workflow each passed three consecutive runs, with a clean runner exit. The other 24 workflows passed in the full run; no application change was needed for the test timing issue.

The TypeScript/Vue production build, locked offline Linux native debug build and whitespace check pass. Rebuilt the frozen sidecar and verified initialization/discovery, live schedule reads, raw measurement expressions, original evaluated display/Breakup, unchanged state/source bytes, saved-file reopening and listener release on shutdown. A final artifact smoke check repeats authenticated live reads and shutdown cleanup. Reviewed the MCP settings screenshot with masked token and aligned ribbon icons. The existing bundle-size warning remains. Third-party client setup, native Windows/macOS behavior and the broader platform/report/corpus gates remain explicit validation work; no Python computation/database port or project schema change is introduced.

## Compact workbench, cell navigation, category filters and MCP editing — 2026-11-15

Implemented all nine requested workbench/agent areas after `fe9cd45`. Light-theme fonts are darker and secondary dark-theme text has higher contrast. Tighter chrome/forms/table spacing and removal of visible instructional headings/legends expose content. Minor ribbon actions use two rows with captions; full action icons remain aligned. Tauri disables native decorations and enables client-side drag/minimize/maximize/close controls; Close uses the existing dirty-project guard. Browser evidence verifies the transport calls, while native compilation verifies configuration/capabilities. Native platform/window-manager interaction remains a manual gate.

Schedule omits category/parent columns and Resources omits category. Category rows are bold. All trees remain expanded, without tree controls or collapse commands. Category filters run in SQL before paging/counting, compose with search and preserve matching ancestors/selected empty categories. Fixtures cover 105 items across pages, parent/child context, multiple categories, resources and malformed inputs.

Shared cell navigation starts editing with Enter/F2 and commits before Tab/Shift+Tab/arrows continue editing. It skips calculated fields and rows where the target column is not editable, retains raw measurement expressions/Breakup and preserves modified-Enter newlines. Invalid/stale values restore authoritative data and reopen for correction with typed text retained. A regression exposed F2 retaining the previous anchor after insertion; focus now follows explicit row selection, and the insertion/relocation workflow passes. Tests that previously blurred by clicking removed headings now use the table header. Narrow-window review also found transparent frozen headers; the Amount header is now opaque, and navigation scrolls off-screen editors into view without hiding them behind that column. A browser assertion verifies the editor's bounds and header background at 1100 px.

MCP now exposes **110 typed application operations plus seven read aliases**. A saved read/read-write mode controls discovery and execution; existing settings remain read-only. Every write requires the current revision, and existing engine guards/transactions/undo remain authoritative. New operations cover project files/settings/recovery, complete database metadata/definitions, schedule/resources, analyses, measurement items/records/properties/links, portable transfer, imports/exports and batches. Status polling omits schemas and refreshes desktop content only after a change sequence, deferring while a cell/dialog is edited. Browser tests verify the real HTTP write path, visible updates, retained human input and stale-edit retry, returning to an agent-created dirty analysis, and resetting after agent-created projects.

**87 Python tests and all 28 Chromium/Playwright workflows pass.** Python contracts prepare an estimate, calculate/preview/apply analysis, measure/link/update quantities, export, save with backup and reopen; they also verify attached-database metadata/import/source preservation, concurrent revision races, strict argument/access guards, atomic failure and committed-operation recovery warnings. A held-body HTTP regression first reproduced a write arriving through an old listener after Stop; listener generations are now checked on the owner thread, rejecting that request even after a restart with the same token. The rebuilt frozen executable passes three of these complete HTTP contracts: preparation/save/reopen, database reads/import/source preservation, and read-mode/revision/rollback boundaries. TypeScript/Vue production, locked offline Linux native debug build and whitespace checks pass. Reviewed compact light-category and dark-workbench screenshots. The existing bundle-size warning remains; third-party MCP clients, native input/window-manager behavior and Windows/macOS packaging remain platform gates. No computation/database backend port or project schema change is introduced.

## MCP efficiency migration — 2026-11-16

Implemented the coordinated 19-tool MCP migration and metadata/dictionary/FTS5 core.
Old aliases/dotted names are removed only from MCP exposure; desktop service operations
and original calculation engines remain authoritative. Embeddings, bulk AI generation
and changed bundled database files remain deferred.

Validation on Linux:

* `.venv/bin/python -m unittest discover -s tests -v`: **111 tests pass**. Coverage includes atomic compound failure/preview rollback, one-step undo/redo, revision races, dirty drafts, parent imports/placement/cycles, source preservation, rate warnings/stored-rate mode, measurement title mapping, malformed/missing enrichment, FTS5 fallback, and bounded SQL view isolation (including CTE impersonation and non-JSON values).
* Representative house fixture: **15 actual HTTP tool calls**, 11 priced items plus three parents, linked measurements, expected total **58,660.00**, export/save/reopen, and unchanged source hash. This replaces the unavailable historical trial with a committed reproducible fixture.
* Full read/write `tools/list` result: **16,204 bytes** with compact JSON; a JSON-RPC response with integer ID 1 is **16,238 bytes**, below 16 KiB. Exactly 19 unique valid names; eight tools in read-only mode. Measured tool tokens: **3,601 cl100k_base / 3,731 o200k_base**. Server instructions: **217 / 215 tokens**, before the short access-mode suffix. Tokenizer was installed under `/tmp` for measurement only; no runtime dependency was added.
* `.venv/bin/python tools/evaluate_search.py --output docs/migration/mcp-search-report.json`: 30 queries per bundled database. Dictionary-assisted recall@5 is **0.8667 DSREM2022 / 0.9000 DSR2021**. MRR@5 is **0.8167 / 0.6744**; corresponding plain FTS5 MRR is **0.8000 / 0.6761**. This is modest ranking benefit on the electrical set and near-neutral on the civil set, not evidence for adding embeddings yet.
* `npm run build --prefix modern`: production build passes. The existing large-bundle advisory remains.
* `PLAYWRIGHT_CHROMIUM_EXECUTABLE=/home/manu/.cache/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-linux64/chrome-headless-shell npm run test:e2e --prefix modern -- --grep 'MCP|enrichment'`: **four browser tests pass**, including UI synchronization/stale human edits, MCP controls/startup recovery, and enrichment label/clear/undo with source preservation. The executable override uses the installed browser because the current Playwright default revision is absent. Enrichment screenshot was visually checked.
* `npm run bundle:backend --prefix modern`: native sidecar rebuild passes; its JSON-line smoke test finds `1.10.1` in the top five and reads the packaged socket/outlet dictionary entry. Dictionary assets are explicitly included in the package.
* `git diff --check`: passes.

Third-party MCP client interoperability and other native platforms remain separate release checks.


## Pending workbench review fixes — 2026-11-17

The compact Analysis editor padding regression was reproduced by comparing
committed multiline text coordinates against its textarea: the editor moved text
7 px horizontally because the compact cell's CSS padding overrode the editing
rule and duplicated the shell padding. The final editing override passes the
same coordinate assertions, retains row height after Enter, and preserves
existing schedule/resource tree decorations and measurement multiline geometry.

Appearance now uses a themed installed-font autocomplete. Browser coverage
checks the full installed list, filtering, popup colors and stacking above the
settings dialog, pointer and keyboard selection, typed names, Escape dismissal,
and persisted independent interface/table settings. Open-combobox Enter is
excluded from the shared dialog-submit handler.

All **four focused Chromium/Playwright workflows passed** in one run: appearance
settings/library rules, text editor geometry, tree geometry/focus rings and the
new multiline Analysis regression. The **Vue/TypeScript production build passed**
with the existing bundle-size warning. Screenshots of the font suggestion popup,
editing Analysis text and accepted Analysis text were visually reviewed. The
installed Chromium headless shell was selected through
`PLAYWRIGHT_CHROMIUM_EXECUTABLE`; the current Playwright default browser download
was unavailable. Python, frozen-backend and native-platform checks were not rerun
for these frontend-only fixes. Broader release gates remain open.


## Cell focus, explorer and measurement serials — 2026-11-17

The earlier padding/font review fixes were committed as `20a2b3a` before this
increment. Escape is handled by the shared cell-navigation controller: it cancels
the editor, retains its coordinate and focuses the cell. Browser checks exercise
cancel/reopen and adjacent-cell navigation in Schedule, Resources and Analysis,
and cancellation/reopening in measurement records. Canceled text is not stored.

Analysis loading refreshes the schedule explorer using its existing query/page.
A browser fixture adds a schedule item after opening the project and verifies
that it appears in the explorer on Edit analysis without submitting Find.

Measurement records prepend display-only serial numbers across all templates.
Checks cover two template layouts and values 1 and 101 on successive pages,
alongside existing insertion, deletion, clipboard and atomic undo workflows.
The generated field is read-only and is not added to backend template data.
The record grid screenshot was reviewed for the new column and existing ranges.

Ctrl/⌘+F targets existing search bars in Schedule, Resources, both explorer tabs,
database selection and the frontmost linked-schedule picker above Properties.
Analysis reveals a hidden explorer. Ctrl/⌘+K no longer changes views or focus.
The help overlay and status bar show Ctrl/⌘+F. Measurements and records do not
receive new search fields, as requested by the user.

**All 50 browser workflows were verified across the full run and focused rerun.**
The full run passed 49 workflows; the new shortcut workflow used a nonexistent
Close button for a database picker whose footer says Cancel. Correcting that
locator passed the focused rerun, including help/status-bar assertions.
The **Vue/TypeScript production build** and whitespace check passed. The existing
bundle-size warning remains. No backend or project-file changes were made;
Python, frozen-backend and native-platform validation were not rerun.


## Overall Schedule total and categorized shortcuts — 2026-11-17

The prior interaction increment and default typography are committed as
`218aa52`. Schedule now displays a highlighted overall estimate total beneath
the grid. Its exact decimal calculation rounds each billable rate × quantity
with the existing Currency helper, excludes unitless headings and the
sub-analysis category, and includes all pages regardless of search/category
filters. Full and incremental state responses carry the total. Backend checks
cover rounding, child items, excluded sub-analyses, filtering/paging, an off-page
quantity edit with no visible-row updates, and undo.

Shortcut help uses five named sections with headings and includes Escape's cell
focus behavior. Browser checks verify group membership, the 25.00 → 45.00 → 25.00
schedule edit/undo sequence while filtered, hiding the summary in Resources,
and the existing search shortcut help. Screenshots of the total and grouped
help were reviewed.

The summary row exposed a virtual-table scroll regression: switching views
restored 700 px before Tabulator's delayed visibility redraw shifted it to
707 px. An IntersectionObserver registered after table initialization restores
the saved position following Tabulator's visibility callback. Existing picker
retention, insertion/reveal, cached navigation, scroll/save/export and focus-ring
checks pass with this change.

**124 Python tests, eight focused browser workflows and the Vue/TypeScript
production build passed.** The existing bundle-size warning remains. Project
schema, GTK computations and workbook exporters are unchanged; native-platform
and standalone-backend builds were not rerun for this increment.


## Hidden main window until startup is ready — 2026-11-17

The preceding Schedule total/shortcut work is committed as `2caa018`. Tauri's
main window now starts with `visible: false`, and its capability allows the
frontend's explicit show command. App initialization waits for platform fonts,
settings/backend state, MCP and recovery handling, Vue updates, font readiness,
table construction/data replacement and synchronous initial table/ribbon layout
before showing the window. Explicit preparation avoids a dependency on animation
frames in a hidden WebView. Startup errors still reveal a window with the error
message instead of leaving it hidden.

A mocked native startup holds font retrieval and backend state independently,
asserting that neither permits an early show command. At reveal, it verifies
the saved light theme, custom typography, loaded fonts, rendered analysis rows,
fitted ribbon and exactly one show call. Another workflow injects backend startup
failure and verifies the revealed error. Existing appearance persistence, compact
layout and application/ribbon interactions are included in the focused gate.

**Five focused browser workflows, the Vue/TypeScript production build and
`cargo check --locked --offline` passed.** A preceding rerun lost its reused
local development server and reported connection refusals; rerunning with the
available server completed all five checks. The existing bundle-size warning
remains. Native visual startup across supported operating systems remains a
manual validation gate; Python/backend logic is unchanged.


## Long first-level text, caret arrows and monochrome SVGs — 2026-11-18

The preceding startup work is committed as `ac14230`. Inspected the supplied
`/home/manu/Desktop/Rates/test.eproj` through read-only SQLite access and isolated
backend working copies. Item 1.1 is a unitless first-level parent with children;
1.2 is a billable first-level item. Both contain long wrapping descriptions.
The source file retains its original size and modification timestamp.

Two padding/geometry mechanisms were reproduced. A flex tree connector shrank
from its configured 7 px to approximately 3 px next to long display text, while
the editor retained 7 px. Connectors and spacers now have zero flex shrink.
Accepting unchanged text also follows Tabulator's cancel path, where height is
measured before the tree marker is restored. The shared controller now measures
again after restoration. A generated fixture with both parent and leaf shapes
checks identical text left edges and padding, full connector width, stable
height on unchanged Enter, and font-weight preservation through changed edits.

Arrow keys retain native caret movement while a cell editor is open; Shift+arrows
select text. Outside editing they still navigate cells. Tab/Shift+Tab and Enter
retain commit/navigation behavior. Checks exercise caret movement and selection
in Schedule, Resources, Analysis and measurement records. The existing editor
navigation workflow was updated to use the new semantics.

Toolbars use custom inline SVG paths, not an icon library/font. Per user approval,
the existing shapes use 2 px strokes, square caps, miter joins and black/white
colors in light/dark themes. Destructive controls retain red. Browser checks
verify both palettes and stroke geometry; native WebKit light/dark screenshots
were also inspected during the investigation.

**Bold reports remain unconfirmed.** Chromium checks against the supplied project
and native GTK/WebKit probes with Iosevka 11 retained normal text at computed
weight 400 during editing and after library attachment. Dialog headings and
saved-library names intentionally use 700; buttons retain their existing 550.
The tests preserve these distinctions. The user's current saved appearance was
light with no custom font overrides. A restart confirmation was requested; these
two reports have not been marked fixed or given a speculative CSS override.

The full browser run passed **55 of 56 workflows**; the scroll-retention workflow
again exposed an observer-order-dependent 700 → 707 px shift. DataTable now
preserves pixel position around public renderStarted/renderComplete events,
replacing the extra visibility observer. Picker retention, insertion/reveal,
cached navigation and scroll/save/export each passed **two consecutive runs**
(eight repeated workflows). The five focused editor/typography/icon workflows
passed, and the final **Vue/TypeScript production build** and whitespace check
passed. The existing bundle-size warning remains. Backend/Python and native
builds were not rerun for these frontend changes.


### Escaping investigation requested by the user

The user cannot currently retest the bold reports and asked whether unescaped
characters cause them. Both supplied descriptions and all schedule descriptions
in the provided file contain no `<`/`&` characters. The only matches in inspected
resource categories are ordinary ampersands, such as `STEEL & PVC`.

Source inspection confirms that Tabulator's textarea/plaintext formatters escape
HTML before content insertion. Table editors assign `input.value`; library
names, attachment messages and categories use Vue text interpolation. No `v-html`
or direct raw-HTML insertion exists in the frontend source.

An additional browser fixture uses literal `<b>`, `<strong>`, `<style>`, ampersands
and quotes in descriptions, a category and the library's project name. It verifies
literal text before/during/after cell editing and attachment, no injected tag
nodes, unchanged normal cell/body/dialog-intro weights, and unchanged source
bytes. The **three-workflow rerun passed** (markup, long first-level geometry,
and caret/monochrome SVGs). No escaping failure was found, and the two reported
bold effects remain unresolved rather than being labeled fixed.


## Repeated database attachments and sharp toolbar states — 2026-11-18

User confirmed that Schedule's bold issue is resolved; Attach Database remained
reported after repeated built-in database attachments. A native GTK/WebKit probe
now follows the themed Available databases menu, attaches four distinct catalog
entries, then repeats the two bundled entries. This checkout ships DSR2021 and
DSREM2022; the other two entries were custom databases already in the catalog.
All six attempts retained 400 for the dialog root, intro, labels and input. The
attached count increased to four and remained four for duplicate attempts.
Snapshots were inspected. The original all-bold native transition did not occur.

The manager previously inherited its base font weight. A scoped regular-weight
rule now isolates its body typography from a bold native/application font context.
Browser coverage deliberately sets the parent body to 700 during four bundled
attachment attempts and verifies manager/field weights remain 400, with h3 and
saved-name emphasis still 700. It uses the themed menu, checks duplicate
prevention and verifies both bundled source files remain byte-identical. This is
an explicit inheritance guard; the original renderer transition is unconfirmed.

Clipboard icons are now angular, filled SVG outlines with even-odd holes and
crispEdges rendering. Toolbar hover/pressed states have zero-radius inset outlines,
including full ribbon actions, minor actions and title-bar controls. The styling
was informed by OpenCADStudio's flat toolbar hover/outline implementation:
[OpenCADStudio toolbar source](https://github.com/HakanSeven12/OpenCADStudio/blob/main/src/ui/kit/toolbar.rs).
No external implementation code or icon dependency was added.

**Four focused browser workflows passed:** repeated bundled attachment, clipboard
icon/hover geometry, existing multi-source attachment/import/rate refresh and the
caret/monochrome icon workflow. Assertions verify both icon palettes, fill/stroke
mode and unchanged button position/size on hover. Screenshots in light and dark
were visually reviewed. The **Vue/TypeScript production build** and whitespace
check passed. A first test run used a nonexistent Save project toolbar label; its
locator was corrected to the existing Save copy label before the clean rerun.
No backend/schema changes; Python and native builds were not rerun.


## Native scroll-layer font smoothing — 2026-11-18

The user's three screenshots showed regular text after the first attachment,
then heavy ordinary text as the dialog began scrolling after the second. The
title, input values and button labels stayed regular. This narrowed the issue
to the scrollable content's rasterization, not HTML escaping or a CSS font-weight
transition.

Reproduced in GTK/WebKit 2.52.6 at 1280×900 using Iosevka 11 and the light theme.
The decisive difference was capture method: WebKit.get_snapshot rendered the
page with regular text, while Gdk.pixbuf_get_from_window captured the visible
window with the heavy text seen by the user. Computed body/dialog/field weights
remained 400 in both cases. This explains the earlier false-negative native
checks. Native screenshots must capture display output for this regression.

Compared opaque scroll-area backgrounds, transforms, opacity, filters, text
shadow, geometric text rendering, removed overflow and explicit font smoothing.
The confirmed narrow fix is `-webkit-font-smoothing: antialiased` on the database
dialog's `.p-dialog-content`; the saved-library scroll area inherits it. It
preserves actual font weights, geometry, scrolling and heading emphasis.

After attaching four distinct catalog databases, an A/B/A-style native check
verified normal text with the fix, reproduced heavy text by overriding smoothing
to `auto`, then restored normal text by removing the override. Both captures used
the same window and content. Display artifacts are
`/tmp/font-regression-auto-display.png` and
`/tmp/font-regression-fixed-display.png`. A stable intro-text crop had red-channel
ink mass 786387 with auto smoothing and 530350 with antialiasing, consistent with
the visible weight difference despite unchanged CSS weight.

**Four focused browser workflows and the production frontend build passed.**
The repeated-attachment regression now uses 1280×900, asserts that overflow is
actually active after the second database, and checks inherited antialiasing in
both the intro and nested saved-library text, alongside stable weights and
source preservation. Chromium tests verify the CSS/overflow contract; the native
display captures verify the visual fix. No backend or native-source changes.


The same native display-capture toggle was repeated in dark mode after four
attachments. Auto smoothing showed the heavier, color-fringed text; antialiasing
restored consistent neutral regular text and retained bold headings. Artifacts:
`/tmp/dark-font-regression-auto-display.png` and
`/tmp/dark-font-regression-fixed-display.png`. Light and dark captures were
visually reviewed, with the scope limited to the database dialog's content.


## 2026-11-18 — editor corrections and GTK parity review

- `.venv/Scripts/python.exe -m unittest discover -s tests -v`: **138 passed** (47.174 seconds in the final run).
- `npm.cmd run --prefix modern build`: **passed**, including TypeScript checking. Vite reports the existing large-chunk size advisory.
- Full Playwright run against installed Chrome and real Python transport: **63 passed** (6.1 minutes).
- After the final clean-records-draft lifecycle correction, the affected measurement, records, clipboard, cell navigation, regional-formatting and font-default browser scenarios were rechecked: **16 existing scenarios passed**, plus **one new lifecycle scenario passed**. All **64 distinct browser scenarios** passed across these runs.
- Browser regressions check repeated Analysis → Schedule activation without scrolling at 1280/1366/1600/1920 px, retained scroll position, large custom fonts at 1080 px, and accessible horizontal scrolling in a narrow 820 px workspace. Frozen borders allow up to two pixels of extent rounding in the compact-layout assertion; desktop checks also inspect the last amount cell's bounds.
- Regional formatting checks Indian grouping with the symbol enabled, German grouping/decimals with the symbol disabled, exact large decimal-string display and raw numeric cell editing. Program-settings validation covers old preferences and invalid format fields.
- Records tests cover all eight shipped templates, separate draft/project undo, apply/discard, navigation, main-list Properties after closing records, switching measurement items, save/recovery and failed/stale operations. MCP reads remain committed; agent edits cannot replace a dirty human draft.
- Batch tests count use of original schedule/resource batch helpers, prohibit individual add wrappers for library selection, verify ordering/parentage/source preservation, and inject a mid-batch failure to check complete rollback.
- Native Windows font detection returned **Segoe UI / 13 px**. Browser tests verify independent OS defaults for interface and tables, saved overrides and restart persistence.

The [source/workflow parity review](parity-review-2026-11-18.md) records six remaining GTK command gaps and corrects the previous PDF claim. No native installer was rebuilt or installed. Native OS dialogs/clipboard, installed packaging, other platforms and larger real/custom-template corpora remain validation limits.
