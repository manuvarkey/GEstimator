# Vue/Tauri migration handoff

## Editor corrections and recorded parity issues — 2026-11-18

Schedule activation now rebuilds its visible virtual viewport while retaining scroll position. Analysis fits desktop panes and permits horizontal scrolling below a 500 CSS px pane width. Library schedule/resource additions use the original batch helpers as one project operation. Measurement records have explicit Apply/Discard drafts, separate undo/redo, navigation protection, save/recovery inclusion, and a clean-draft lifecycle that preserves main-list Properties and committed MCP edits.

Program Settings now controls regional rate/amount formatting and optional currency symbols across views. Blank interface/table typography independently follows OS control fonts, with a 13 px fallback; saved overrides remain effective.

The [open parity backlog](parity.md#open-parity-issues) records **PARITY-001 through PARITY-006** with status and acceptance criteria: mismatch highlighting, resource renumbering, resource-rate synchronization, multi-item analysis import, OS file opening, and manual/About commands. The [source audit](parity-review-2026-11-18.md) contains the evidence and compatibility distinctions.

Validation: 138 Python tests passed; the full 63-test browser suite passed, followed by 16 affected browser scenarios and one new lifecycle regression after the final correction (64 distinct browser scenarios across runs). The production frontend build passed. The native installer was not rebuilt; see the [validation record](validation.md).

## Database dialog bold rendering resolved — 2026-11-18

User screenshots exposed the missing condition: ordinary dialog text became
visually bold when scrolling activated, while title/input/button text stayed
regular. Native WebKit page snapshots and computed weight (400) had masked the
problem. Capturing the displayed X11 GTK window reproduced it after attaching
the second database at 1280×900.

The database dialog's scroll content now sets
`-webkit-font-smoothing: antialiased`, inherited by its nested Saved libraries
scroll area. Native display captures confirm that toggling it to `auto`
reproduces the bold effect and restoring antialiasing removes it, without
changing CSS font weights or heading emphasis. Both light and dark native
display captures were verified. The earlier regular-weight guard
alone was insufficient. Four focused browser workflows and the production build
pass; see the [native rendering validation](validation.md#native-scroll-layer-font-smoothing--2026-11-18).

## Repeated attachments and toolbar hover — 2026-11-18

The user confirmed the Schedule bold issue is resolved. Attach Database's body
now explicitly uses regular weight (400), preventing inheritance from a bold
system/application font. Headings and saved-library names remain emphasized.
The original native all-bold transition has not been reproduced; six native
WebKit attempts (four distinct catalog databases, then repeats of the two bundled
databases) kept all sampled body fields at 400. Browser coverage also verifies
regular dialog text under a deliberately bold parent font and repeated bundled
attachment through the themed dropdown, with deduplication/source preservation.

Copy/Paste now use filled rectangular SVG outlines with crisp edge rendering.
Toolbar hover/pressed states use square inset borders without size changes,
inspired by OpenCADStudio's outlined hover treatment. Four focused browser
workflows and the production frontend build pass; screenshots were reviewed.
See the latest [validation entry](validation.md#repeated-database-attachments-and-sharp-toolbar-states--2026-11-18).

## Long-description and caret review — 2026-11-18

The startup reveal increment is committed as `ac14230`. The next continuation
keeps 7 px tree connectors from shrinking beside long descriptions and measures
canceled/unchanged edits after their tree prefix is restored. Arrows now move
the caret while editing; Tab/Shift+Tab and Enter retain cell acceptance, while
arrows outside editing retain grid navigation. Shortcut help reflects this.
Toolbar icons remain custom inline SVG, now sharper and black/white by theme
as requested (destructive actions retain their red semantic color). The production
build, five focused editor checks and eight repeated navigation checks passed;
see the [validation record](validation.md#long-first-level-text-caret-arrows-and-monochrome-svgs--2026-11-18).

**Font review status:** the user subsequently confirmed Schedule's bold effect
is resolved. The database dialog has a regular-weight scope and repeated
attachment coverage as described above. Escaping checks found no tag leakage.
The supplied project was inspected through disposable working copies and
read-only access; its source was preserved.

## Hidden-window startup — 2026-11-17

The Schedule total/shortcut increment is committed as `2caa018`. The next change
starts the native main window hidden. Startup finishes desktop typography,
settings/backend/MCP/recovery initialization, font loading and explicit table
and ribbon layout before showing it. Explicit preparation avoids waiting on
animation frames that a hidden WebView can throttle. Startup failures still
show the window with the error visible. Restart the native app to exercise the
new window configuration. Five focused browser workflows, the production
frontend build and locked offline native check passed. See the
[validation record](validation.md#hidden-main-window-until-startup-is-ready--2026-11-17).

## Schedule total and shortcut groups — 2026-11-17

The preceding keyboard/record work is committed as `218aa52`, including the
current default typography settings. The next increment adds a highlighted
**Overall estimate total** summary row below Schedule and groups shortcut help
into Project and search, Rows and clipboard, Cell editing and selection, Editor
actions and Ribbon navigation. The total uses every billable schedule item,
independent of search, category filters and pagination, and refreshes on edit,
undo and incremental updates. Sub-analyses are excluded as in the agent summary.
A delayed table visibility redraw also preserves its saved scroll position.
Validation: 124 Python tests, eight focused browser workflows and the production
frontend build passed. See the [validation record](validation.md#overall-schedule-total-and-categorized-shortcuts--2026-11-17).

## Keyboard and record follow-up — 2026-11-17

The previous review fixes are committed as `20a2b3a`. The next increment retains
cell focus after Escape, refreshes schedule explorer results when loading an
analysis, adds generated serial numbers to all measurement record grids, and
replaces Ctrl/⌘+K with Ctrl/⌘+F for existing search bars in views and selection
dialogs. Measurements and records do not gain new search bars, per user direction.
See [interaction notes](workbench-feedback.md#keyboard-and-record-navigation-follow-up--2026-11-17).
All 50 browser workflows were verified across the full run and focused rerun;
the production frontend build passed. See the [validation record](validation.md#cell-focus-explorer-and-measurement-serials--2026-11-17).

## Review fixes — 2026-11-17

Both immediate pending review items are implemented:

1. **Multiline table text padding.** Compact Analysis rows applied padding to
   both the editing cell and its editor shell. The final editing CSS rule now
   leaves padding to the shell, keeping text coordinates and row height stable
   when Enter accepts the edit. Schedule/resource tree and measurement multiline
   acceptance/reopening are covered by browser checks.
2. **Font family dropdown theme.** Appearance uses a themed, searchable font
   autocomplete instead of a native datalist. Installed fonts, typed names and
   independent interface/table preferences remain supported. Enter chooses a
   suggestion and Escape dismisses its popup while keeping settings open.

See the [workbench review notes](workbench-feedback.md#review-fixes--2026-11-17).
The broader native-platform, save/recovery and release gates under
**Next milestones** remain open.

## Workbench review follow-up — 2026-11-17

Schedule and measurement text editors retain hierarchy markers and indentation
during, after accepting, and after canceling an edit. Edit description opens the
measurement record heading for editing in place. The heading and linked schedule
description show up to five lines, with a middle ellipsis when needed. The
heading editor scrolls through longer text.

Program Settings → Appearance lists installed font families and saves independent
interface and table typography. The default palette and type sizes are in
`modern/src/theme.css`. Common controls and table classes are in
`modern/src/style.css`. The analysis grid fits its columns when shown, and the
schedule library importer keeps preset management and match details expandable.

## Measurement editing checkpoint — 2026-11-17

Current checkout: `/home/manu/Documents/Projects/GEstimator`, branch
`migration/vue-tauri-desktop`. The user runs the modern app with
`npm run tauri dev`.

This checkpoint includes measurement category editing, main-page Properties
and Edit Records, blank-row/editor sizing, inset focus outlines and field spacing,
and four-place Tax precision. Existing `vat` storage/API keys remain compatible;
legacy project round-trip, undo and spreadsheet import/export were checked.
Prior checkpoints: `cca316f` (MCP), `2245ced` (workbench), `cc09d25` (controls/focus).

Validation before this review: 46 browser tests passed in a full run; the Python
suite passed 122 tests plus the subsequently added tax import/export check;
production frontend, standalone backend and offline native development builds
passed. The subsequent review changes are described in
[workbench-feedback.md](workbench-feedback.md).

## Earlier checkpoint history

Resume on `migration/vue-tauri-desktop`. The ribbon/MCP checkpoint is `fe9cd45`, following `c28a449` (database selectors), `c813c2c` (editor efficiency), `c649ec6` (clipboard/insertion) and `8f6c35c` (Program Settings); the compact workbench/read-write agent continuation is described below. The current Linux checkout is `/home/manu/Documents/GitHub/GEstimator`; the earlier Windows checkout is `C:\Users\HP\Documents\GitHub\GEstimator`. Use the [parity ledger](parity.md) for feature status, the [architecture notes](architecture.md) for implementation context, and the [validation record](validation.md) for test evidence.

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
| `fe9cd45` | Ribbon-only application tabs, aligned full-action icons and initial local MCP controls/read tools |

The GTK application is kept on the `archive/gtk` branch (launch `gestimator.py` there). Keep the legacy calculation engine and workbook exporters as the comparison reference.

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

## Workbench and agent editing continuation — 2026-11-15

The current continuation adds higher contrast, compact content-focused spacing, two-row minor ribbon actions and client-side window decorations. Trees remain expanded without controls; schedule category/parent and resource category columns are hidden, bold category rows remain, and SQL category filters run before paging. A shared cell-navigation controller commits through the backend, then restores focus and continues editing with Tab/Shift+Tab/arrows. Enter/F2 starts editing; calculated cells remain read-only; invalid/stale inputs reopen for correction. See [workbench behavior](workbench-refinement.md).

MCP now has read/read-write access modes, 110 typed application operations and seven legacy read aliases. Agent edits share existing transactions/undo and require current revisions. It supports preparing estimates end to end, full database metadata/definition reads, measurement evaluation, save/export and source preservation. Lightweight change-sequence polling updates the desktop while deferring active cell/dialog edits. See the [agent workflow](mcp-server.md). All 87 Python tests and 28 browser workflows pass, as do the native Linux build and three complete read/write HTTP contracts against the frozen executable. Target-platform window/input behavior, third-party clients and the broader release/corpus gates remain.

## Editor continuation — 2026-11-14

The portable-clipboard/shortcut increment is committed as `c649ec6`. The following editor continuation implements selection-aware insertion and GTK numbering, row reveal, F2/context/tree interactions, resource definition editing and identity-preserving category moves. Measurement templates have descriptive previews, atomic Properties, searchable links, paired steel labels/constants, mapped column captions, bulk/multi-record operations and record pages. Paste now reads/writes the measurement model once per batch; template modules are reused with file-change invalidation and fresh mutable defaults. See [editor review](editor-review.md) for measured evidence, unusual formula conventions and modern shortcut choices. Python calculations and the project schema are retained.

## Database and entry continuation — 2026-11-14

The editor increment is committed as `c813c2c`. Its continuation replaces the working-table database-source switch with separate item-selection dialogs, moves management to the Databases tab and keeps attachment dialogs open after attaching. Selected-rate dialogs preview and apply matching source rates with undo. Modify & Add preferences share one settings tab. Single-select popups use the main-menu theme; Enter accepts text and Shift/Ctrl+Enter inserts newlines. Measurement templates are grouped General/Civil/E&M, and original Python callbacks provide evaluated display and Breakup while retaining raw expressions for editing. NLBH optional blank factors are preserved. The [workflow review](database-selection-workflow.md) explains exact rate policies and proposes a future named-rule modification regime. The continuation passes 76 Python tests and 23 browser workflows; native-platform, real-project and report validation remain open in the ledger.

## Linux continuation — 2026-11-14

The working tree includes the reviewed ribbon changes, persisted library manager, custom analysis templates, bulk analysis editing, keyboard table interaction, measurement template layout metadata and additional save/recovery failure checks. Computation and database ownership remain in the existing Python implementation. The small new Python batch adapter reuses existing row edits, validation and calculations; it does not replace the engine or alter the project schema.

Save/recovery tests now inject failed snapshot writes, backup writes, replacement publication and checkpoint publication, and exercise modern save locking and stale second-window saves. These checks preserve source bytes, dirty drafts and complete checkpoints. They supplement, rather than replace, hard process-interruption and real Windows file-lock/GTK-concurrency checks.

The reviewed workspace/editor increment is committed as `dd90598`. The following Program Settings increment is separate: app-level export/Modify & Add/default-row preferences, validation and cancellation, a shared row editor, GTK-compatible Modify & Add imports, blank-analysis defaults, and bundled/custom database discovery. Bundled `.eproj` databases are included in the sidecar and referenced by stable `bundled:` identifiers. Source aliases are deduplicated by their resolved backend paths. Project schema and legacy computation/database implementations remain unchanged.

Program Settings is now committed as `8f6c35c`. The next increment adds the Tauri clipboard-manager text permissions and validated Python row serialization. Required schedule resources/sub-analyses transfer with selected rows; category selections include off-page contents. Destination resource codes reuse existing definitions; schedule stored rates remain as copied. Measurement links use schedule codes, and record paste checks the installed template. All mutations use existing draft/project undo. Creation, duplication and paste now preserve explicit schedule parents and inherit the parent's category; adding while a category is selected no longer enters category-edit dispatch. Native OS clipboard operation and Windows/macOS builds remain validation gates.
