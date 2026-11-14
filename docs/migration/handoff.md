# Vue/Tauri migration handoff

Resume on `migration/vue-tauri-desktop`. The database-selector checkpoint is `c28a449`, following `c813c2c` (editor efficiency), `c649ec6` (clipboard/insertion) and `8f6c35c` (Program Settings); the ribbon/MCP continuation is described below. The current Linux checkout is `/home/manu/Documents/GitHub/GEstimator`; the earlier Windows checkout is `C:\Users\HP\Documents\GitHub\GEstimator`. Use the [parity ledger](parity.md) for feature status, the [architecture notes](architecture.md) for implementation context, and the [validation record](validation.md) for test evidence.

## Completed through the checkpoint

| Commit | Milestone |
|---|---|
| `4bcc2c2` | Windows x64 development, PyInstaller sidecar and NSIS packaging |
| `e32b1d8`, `8b7324f`, `2e8cdd2` | Selected library price refresh with undo, resource usage totals, and direct and indirect analysis references |
| `bff125b`, `24d143c` | Schedule colours, selected measurement quantities, hierarchy moves, renumbering and import of referenced library sub-analyses |
| `87d1d25` | In-place Save with conflict checks and numbered backups, local recovery checkpoints and recent projects |
| `ccd28fd` | Excel analysis and measurement record imports and whole-item measurement multi-selection |
| `6cd7f7d` | Insert the shipped GTK analysis rows and refresh rates for selected schedule items |
| `dd90598` | Reviewed ribbons, bulk editing, saved libraries, keyboard table selection and measurement layout |
| `8f6c35c` | Program Settings, configured default rows, GTK Modify & Add preferences, bundled/custom database discovery |
| `c649ec6` | Portable row clipboard and GTK insertion shortcuts |
| `c813c2c` | Selection-aware insertion, resource editing and efficient measurement templates |
| `c28a449` | Database item/rate dialogs, themed menus and original measurement expression/Breakup display |

GTK remains available through `gestimator.py`. Keep the legacy calculation engine and workbook exporters as the comparison reference.

## Start and verify on Windows

From the repository root, with the dependencies already installed:

```powershell
npm.cmd run --prefix modern tauri -- dev
```

For setup on another checkout, see [Windows development and builds](../../modern/README.md#windows-development-and-builds). To verify or rebuild from the repository root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm.cmd run --prefix modern build
cargo check --locked --manifest-path modern/src-tauri/Cargo.toml
npm.cmd run --prefix modern test:e2e
npm.cmd run --prefix modern bundle:backend
npm.cmd run --prefix modern tauri -- build --bundles nsis -- --locked
```

The browser suite needs Playwright Chromium or `PLAYWRIGHT_CHROMIUM_EXECUTABLE` set to an installed Chrome executable. The NSIS installer is a local build output under `modern/src-tauri/target/release/bundle/nsis/`. The last implementation pass recorded 43 Python tests, 11 Playwright scenarios, a Vue production build, an x64 installer build, and recovery across two frozen sidecar processes. Native Windows validation covered startup, engine connection and opening the Windows file picker.

## Next milestones

1. **Validate Save and recovery under failure.** Use disposable projects to test external GTK edits, a concurrent modern save, a Windows file held open, and interruption during save and checkpoint creation. Verify source contents, numbered backups, recovery and the dirty state after each failure. The modern advisory lock coordinates modern instances. GTK does not acquire it.
2. **Validate settings and library workflows on target platforms.** The Databases tab owns attachment management; Schedule/Resources use modal item selectors and selected-rate preview/apply dialogs. Saved application library paths restore through the existing read-only snapshot API, with retry/forget and duplicate prevention across browser reloads. Configurable analysis row templates persist in application preferences and insert with a Python preview and atomic undo. Linux browser tests cover repeated attachment without closing, themed source menus, fresh backend processes, moved/missing libraries and source preservation. Broaden prefix/code-collision and Windows/macOS path fixtures.
3. **Finish editor interactions.** Batch preview/atomic editing, keyboard selection and template widths are implemented. The current continuation adds validated JSON system clipboards for analysis, schedule, resources, measurement items and records, plus Ctrl+I/Ctrl+Shift+I insertion, Ctrl+E analysis and Ctrl+M row colour. Test native clipboard read/write on each target platform. Selection-aware placement, GTK numbering suggestions, automatic row reveal, resource editing/relocation, F2/context actions and modern shortcut mappings are implemented. Measurement template previews, atomic Properties, searchable links, bulk/multi-record operations and record paging are implemented. Compare native input methods and larger real/custom-template projects next; see the editor review for unusual legacy behavior and efficiency evidence.
4. **Complete release validation.** Compare the five exported worksheets against GTK on real projects, including formulas, styles, merges and print settings in Excel and LibreOffice. Validate native menus, file dialogs, dirty-window close, typography and accessibility on target platforms. Exercise a clean Windows install and supported Linux/macOS builds. Check larger and cyclic sub-analysis graphs and populated measurement fixtures. Track PDF reporting as a later phase.

Record evidence in the validation log and update the ledger as each milestone lands. Keep GTK available until the editor, file safety, report and native-platform gates are exercised.

## Ribbon and MCP continuation — 2026-11-14

Databases now changes only the ribbon; its separate page and embedded manager were removed. The attachment dialog retains its non-closing workflow. MCP is also a ribbon-only tab. The active editor, selection, draft, inspector and undo context remain in place while either application tab is selected. Full ribbon actions reserve equal caption height so one/two-line labels align their icons.

The MCP ribbon controls a local authenticated, read-only HTTP server: Start/Stop, port, optional automatic startup, token rotation, client configuration copy/reveal, tool inspection and activity. A bounded queue serializes HTTP reads with desktop requests on one service/SQLite owner thread. Computation and database implementations are retained. Shutdown closes the listener; start conflicts and invalid saved settings remain visible outside the MCP tab. See [server setup, tools and protocol boundaries](mcp-server.md). Validate third-party client setup and native Windows/macOS behavior next.

## Editor continuation — 2026-11-14

The portable-clipboard/shortcut increment is committed as `c649ec6`. The following editor continuation implements selection-aware insertion and GTK numbering, row reveal, F2/context/tree interactions, resource definition editing and identity-preserving category moves. Measurement templates have descriptive previews, atomic Properties, searchable links, paired steel labels/constants, mapped column captions, bulk/multi-record operations and record pages. Paste now reads/writes the measurement model once per batch; template modules are reused with file-change invalidation and fresh mutable defaults. See [editor review](editor-review.md) for measured evidence, unusual formula conventions and modern shortcut choices. Python calculations and the project schema are retained.

## Database and entry continuation — 2026-11-14

The editor increment is committed as `c813c2c`. Its continuation replaces the working-table database-source switch with separate item-selection dialogs, moves management to the Databases tab and keeps attachment dialogs open after attaching. Selected-rate dialogs preview and apply matching source rates with undo. Modify & Add preferences share one settings tab. Single-select popups use the main-menu theme; Enter accepts text and Shift/Ctrl+Enter inserts newlines. Measurement templates are grouped General/Civil/E&M, and original Python callbacks provide evaluated display and Breakup while retaining raw expressions for editing. NLBH optional blank factors are preserved. The [workflow review](database-selection-workflow.md) explains exact rate policies and proposes a future named-rule modification regime. The continuation passes 76 Python tests and 23 browser workflows; native-platform, real-project and report validation remain open in the ledger.

## Linux continuation — 2026-11-14

The working tree includes the reviewed ribbon changes, persisted library manager, custom analysis templates, bulk analysis editing, keyboard table interaction, measurement template layout metadata and additional save/recovery failure checks. Computation and database ownership remain in the existing Python implementation. The small new Python batch adapter reuses existing row edits, validation and calculations; it does not replace the engine or alter the project schema.

Save/recovery tests now inject failed snapshot writes, backup writes, replacement publication and checkpoint publication, and exercise modern save locking and stale second-window saves. These checks preserve source bytes, dirty drafts and complete checkpoints. They supplement, rather than replace, hard process-interruption and real Windows file-lock/GTK-concurrency checks.

The reviewed workspace/editor increment is committed as `dd90598`. The following Program Settings increment is separate: app-level export/Modify & Add/default-row preferences, validation and cancellation, a shared row editor, GTK-compatible Modify & Add imports, blank-analysis defaults, and bundled/custom database discovery. Bundled `.eproj` databases are included in the sidecar and referenced by stable `bundled:` identifiers. Source aliases are deduplicated by their resolved backend paths. Project schema and legacy computation/database implementations remain unchanged.

Program Settings is now committed as `8f6c35c`. The next increment adds the Tauri clipboard-manager text permissions and validated Python row serialization. Required schedule resources/sub-analyses transfer with selected rows; category selections include off-page contents. Destination resource codes reuse existing definitions; schedule stored rates remain as copied. Measurement links use schedule codes, and record paste checks the installed template. All mutations use existing draft/project undo. Creation, duplication and paste now preserve explicit schedule parents and inherit the parent's category; adding while a category is selected no longer enters category-edit dispatch. Native OS clipboard operation and Windows/macOS builds remain validation gates.
