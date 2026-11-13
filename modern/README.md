# GEstimator desktop migration workspace

See [architecture and audit](../docs/migration/architecture.md), [feature parity ledger](../docs/migration/parity.md), and [validation record](../docs/migration/validation.md). GTK remains available via `gestimator.py`.

From the repository root:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt pyinstaller
npm ci --prefix modern
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python modern/bundle_backend.py
cd modern
npm run tauri dev
```

Requires Node 22+, Rust and [Tauri platform build prerequisites](https://v2.tauri.app/start/prerequisites/). To build an installer, build the native backend first and then run `npm run tauri build` from `modern`. Cross-compiling Python sidecars is not supported. The frontend alone (`npm run dev`) has no mock backend; use Tauri for IPC.

## Windows development and builds

Install Node.js 24 LTS with npm, Python 3.14 x64, Rust's stable MSVC toolchain, and the Visual Studio C++ desktop build tools with a Windows SDK. Windows also needs the Edge WebView2 Runtime. [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/#windows)

Run these commands in PowerShell from the repository root. With uv, use `uv venv --python 3.14 --seed .venv` for the first command.

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller==6.22.3
npm.cmd ci --prefix modern
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe modern/bundle_backend.py
npm.cmd run --prefix modern tauri -- dev
```

To produce a Windows x64 NSIS installer, run `npm.cmd run --prefix modern tauri -- build --bundles nsis -- --locked` from the repository root after building the backend. The installer is written to `modern/src-tauri/target/release/bundle/nsis/`. Rebuild the sidecar after editing Python code before packaging a release. The `bundle:backend` npm command also builds the sidecar using the repository's `.venv`.

Use the **New project** icon beside the logo to create a working project, or the **Open project** icon and Browse to choose a v1/v2 `.eproj` (or enter its absolute path). Search/load an item in the explorer, select rows to edit them in the inspector or double click table cells, then use **Save copy** to choose a **new** path. Saving never overwrites an existing file. Numeric entries support bounded arithmetic, evaluated in Python. Rates, VAT and discounts use the existing currency rounding; final calculated values always come from the backend. Ctrl+C/V operates on session rows; text editing uses ordinary text clipboard. Ctrl+Z/Y, Delete and explicit Move up/down act on the analysis. Use **Analysis → Apply analysis** to retain edits while moving between items. Applied changes to multiple items are included in Save copy. Switching items/projects prompts to apply/save/discard a dirty draft; the backend also rejects unconfirmed switches. Closing the desktop window prompts for dirty drafts. Process crashes or forced termination still lose unsaved drafts. Treat saved copies as review artifacts until parity tests are complete.

Backend protocol can also run independently: `.venv/bin/python -m modern.backend`, one JSON object per line, e.g. `{"id":"1","method":"state","params":{}}`. Responses contain `id` plus `result` or `error:{code,message}`; long operations can emit `event:"progress"` first. Edits require the latest `revision` from state.


## Workspace

The ribbon tabs select Schedule, Analysis, Resources and Measurements and show the active view's tools. The logo opens the application menu; file commands and context-sensitive undo/redo are icon-only controls beside it. Explorer tabs provide paged schedule/resource search. The inspector shows resource definitions, effective rates and the selected row's calculated amount. The final rate stays visible below the table. Use the application menu to hide panes, collapse analysis groups or select compact analysis row spacing. Dark/light themes persist locally. Ctrl/⌘+O opens, Ctrl/⌘+S saves a copy, Ctrl/⌘+K focuses search, and the help button lists editing shortcuts.

The visual direction follows [CivilKit Calcs](https://github.com/civilkit/civilkit-calcs)' docked engineering workspace and ribbon organization; the GEstimator implementation and calculation model remain separate.

## Browser integration tests

From `modern`, with the repository Python environment prepared:

```sh
npx playwright install chromium
npm run test:e2e
```

On Windows use `npx.cmd` and `npm.cmd` in PowerShell.

The tests replace only the Tauri invocation transport with a bridge to a real persistent Python subprocess. Calculation responses and project saves are real, with test outputs confined to temporary copies. Native OS dialogs and window-close events still require a desktop interaction check. The test runner starts Vite automatically and saves dark/light/narrow-layout screenshots in `test-results/`. A preinstalled browser can be selected with `PLAYWRIGHT_CHROMIUM_EXECUTABLE`.

Workspace previews: [dark](../docs/migration/screenshots/workspace-dark.png) · [light](../docs/migration/screenshots/workspace-light.png).


## Schedule, resources and measurements

Use the ribbon tabs to open the project editors. Schedule/resources support hierarchical categories, multiline editing, arithmetic numeric entry, duplication, copy/paste, search/paging and project undo/redo. Select categories or items and use the ribbon arrows to reorder them. Delete previews include hidden category contents and descendants. For used resources, choose **Delete unused** or **Delete including used**; the latter removes their analysis entries and recalculates rates. Project undo restores the entire operation. Select an item and use **Edit analysis** to enter its analysis. Paste plain tab-separated cells into a selected table cell; the backend applies the batch transactionally.

**Attach library…** opens a snapshot of an external .eproj for browsing. Choose that data source, select items or whole categories and use **Import selected into project**. Imported resources retain library prefixes when defined. Attached libraries also appear as a source in the analysis resource dialog. Libraries are never edited in place.

Measurements use the existing eight Python templates. Add a heading or a custom item, select it to edit its records, schedule links, item remarks and user data, then use **Update schedule quantities** with the desired legacy rounding scheme. Use the record toolbar arrows to reorder records; stable identifiers and project undo retain their values. Template-calculated columns are read-only. Deleting linked schedule items retains measurement records/remarks and clears their associations; undo restores the links.

**Import workbook** previews a schedule/resource worksheet with field mapping and duplicate policies. **Export workbook** calls the existing five-sheet exporter. Apply an analysis draft before exporting the whole project; analysis-only export includes the draft without changing the project.

**Application menu → Project settings…** edits the existing project name/code metadata. Linux typography reads the actual GTK control font family and size and follows font changes; other platforms use native CSS menu typography until platform validation is complete. No external font is downloaded.

The modern workspace is not yet a complete GTK replacement. Consult the parity ledger before relying on a workflow that has not been exercised. Original project/library files are preserved; save outputs remain new copies.

Editor previews: [Schedule](../docs/migration/screenshots/schedule-desktop.png) · [Resources](../docs/migration/screenshots/resources-desktop.png) · [Measurements](../docs/migration/screenshots/measurements-desktop.png).
