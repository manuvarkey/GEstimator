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
