# Vue/Tauri migration handoff

Resume on `migration/vue-tauri-desktop`. The Program Settings checkpoint is `8f6c35c`, following `dd90598` (workspace/editor parity); the clipboard/insertion continuation is described below. The current Linux checkout is `/home/manu/Documents/GitHub/GEstimator`; the earlier Windows checkout is `C:\Users\HP\Documents\GitHub\GEstimator`. Use the [parity ledger](parity.md) for feature status, the [architecture notes](architecture.md) for implementation context, and the [validation record](validation.md) for test evidence.

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
2. **Validate settings and library workflows on target platforms.** Saved application library paths now restore through the existing read-only snapshot API, with a retry/forget manager and duplicate prevention across browser reloads. Configurable analysis row templates persist in application preferences and insert with a Python preview and atomic undo. Linux browser tests cover fresh backend processes, moved/missing libraries and source preservation. Broaden prefix/code-collision and Windows/macOS path fixtures.
3. **Finish editor interactions.** Batch preview/atomic editing, keyboard selection and template widths are implemented. The current continuation adds validated JSON system clipboards for analysis, schedule, resources, measurement items and records, plus Ctrl+I/Ctrl+Shift+I insertion, Ctrl+E analysis and Ctrl+M row colour. Test native clipboard read/write on each target platform. GTK insertion position/automatic numbering, remaining shortcuts and template-specific dialogs still need comparison on representative projects.
4. **Complete release validation.** Compare the five exported worksheets against GTK on real projects, including formulas, styles, merges and print settings in Excel and LibreOffice. Validate native menus, file dialogs, dirty-window close, typography and accessibility on target platforms. Exercise a clean Windows install and supported Linux/macOS builds. Check larger and cyclic sub-analysis graphs and populated measurement fixtures. Track PDF reporting as a later phase.

Record evidence in the validation log and update the ledger as each milestone lands. Keep GTK available until the editor, file safety, report and native-platform gates are exercised.

## Linux continuation — 2026-11-14

The working tree includes the reviewed ribbon changes, persisted library manager, custom analysis templates, bulk analysis editing, keyboard table interaction, measurement template layout metadata and additional save/recovery failure checks. Computation and database ownership remain in the existing Python implementation. The small new Python batch adapter reuses existing row edits, validation and calculations; it does not replace the engine or alter the project schema.

Save/recovery tests now inject failed snapshot writes, backup writes, replacement publication and checkpoint publication, and exercise modern save locking and stale second-window saves. These checks preserve source bytes, dirty drafts and complete checkpoints. They supplement, rather than replace, hard process-interruption and real Windows file-lock/GTK-concurrency checks.

The reviewed workspace/editor increment is committed as `dd90598`. The following Program Settings increment is separate: app-level export/Modify & Add/default-row preferences, validation and cancellation, a shared row editor, GTK-compatible Modify & Add imports, blank-analysis defaults, and bundled/custom database discovery. Bundled `.eproj` databases are included in the sidecar and referenced by stable `bundled:` identifiers. Source aliases are deduplicated by their resolved backend paths. Project schema and legacy computation/database implementations remain unchanged.

Program Settings is now committed as `8f6c35c`. The next increment adds the Tauri clipboard-manager text permissions and validated Python row serialization. Required schedule resources/sub-analyses transfer with selected rows; category selections include off-page contents. Destination resource codes reuse existing definitions; schedule stored rates remain as copied. Measurement links use schedule codes, and record paste checks the installed template. All mutations use existing draft/project undo. Creation, duplication and paste now preserve explicit schedule parents and inherit the parent's category; adding while a category is selected no longer enters category-edit dispatch. Native OS clipboard operation and Windows/macOS builds remain validation gates.
