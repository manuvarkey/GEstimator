# GEstimator desktop migration workspace

See the [migration handoff](../docs/migration/handoff.md), [architecture and audit](../docs/migration/architecture.md), [feature parity ledger](../docs/migration/parity.md), and [validation record](../docs/migration/validation.md). GTK remains available via `gestimator.py`.

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

Use the **New project** icon beside the logo to create a working project, or the **Open project** icon and Browse to choose a v1/v2 `.eproj` (or enter its absolute path). Search/load an item in the explorer, select rows to edit them in the inspector or double click table cells, then use **Save copy** to choose a **new** path. Use **Save project** to replace the opened project after checking for external changes and writing a numbered backup beside it. Numeric entries support bounded arithmetic, evaluated in Python. Tax percentages use four decimal places; rates and discounts use two-place currency rounding; final calculated values always come from the backend. Ctrl+C/V copies validated row data through the system clipboard between modern GEstimator windows; text editing uses the ordinary text clipboard. Ctrl+Z/Y, Delete and explicit Move up/down act on the analysis. Use **Analysis → Apply analysis** to retain edits while moving between items. Applied changes to multiple items are included in Save copy. Switching items/projects prompts to apply/save/discard a dirty draft; the backend also rejects unconfirmed switches. Closing the desktop window prompts for dirty drafts. The Open Project dialog lists recent projects and recoverable checkpoints. Save a recovered project to a new location.

Backend protocol can also run independently: `.venv/bin/python -m modern.backend`, one JSON object per line, e.g. `{"id":"1","method":"state","params":{}}`. Responses contain `id` plus `result` or `error:{code,message}`; long operations can emit `event:"progress"` first. Edits require the latest `revision` from state.


## Workspace

The ribbon tabs select Schedule, Analysis, Resources and Measurements editors. Databases and MCP change only the ribbon, preserving the active editor, draft and selection. The logo opens the application menu; file commands and context-sensitive undo/redo are icon-only controls beside it. The Explorer visibility icon follows undo/redo. Explorer tabs provide paged schedule/resource search. The inspector shows resource definitions, effective rates and the selected row's calculated amount. The final rate stays visible below the table. Analysis → View controls inspector visibility, group expansion and compact row spacing. Ribbons share one depth with aligned 24 px full-action icons and one/two-line captions. Minor actions use two rows with 20 px icons and text; overflow uses a two-row icon layout. Client-side window controls replace native decorations, and tighter spacing keeps the editable content prominent. The light theme uses darker text and the dark theme uses higher-contrast secondary text. Hover actions for explanations of selection scope, calculations and saving. Dark/light themes persist locally. Ctrl/⌘+O opens, Ctrl/⌘+S saves the current project, Ctrl/⌘+Shift+S saves a copy, Ctrl/⌘+K focuses search, and the help button lists editing shortcuts.

With a ribbon tab focused, Left/Right and Home/End move focus; Enter/Space activates it through the unsaved-draft guard. In a project table, Ctrl/⌘+D duplicates selected items, Delete uses the existing deletion flow, and Alt+Up/Down reorders the selection. These commands act on measurement records when their table has focus. Ctrl/⌘+I opens item creation (or inserts a record when the record table has focus). Ctrl/⌘+Shift+I creates a schedule subitem with its parent prefilled; Ctrl/⌘+E opens the selected schedule analysis and Ctrl/⌘+M opens row colours. In Analysis, Ctrl/⌘+I opens library resources and Ctrl/⌘+Shift+I opens custom resource entry. Text fields retain native editing shortcuts and project cells retain spreadsheet paste.

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

The attachment dialog can remember library paths in application preferences. Remembered libraries reopen with every project, including after restarting the backend. Missing paths produce a non-blocking warning; use **Application menu → Databases…** to retry, attach a moved file or forget its old path. Forget affects future restoration; the current read-only snapshot remains until the project closes. Duplicate attachments in a window are reused. Up to 50 library paths can be remembered.

In Analysis, **Bulk edit analysis…** previews setting one field on the selected rows. Resource definition changes affect other uses of the same resource in the draft. **Custom analysis template…** configures reusable Group, Subtotal, Weight, Multiply and Round rows. Saving the template updates the default analysis template in Program Settings; previewing and applying inserts the rows after the selection as one undo step. Both workflows use the Python engine for validation and final calculated values.

**Application menu → Program settings…** is available without an open project. It controls workbook description splitting, the library schedule-rate multiplier, the number of trailing analysis rows to replace (0–5), and the default and Modify & Add analysis templates. Settings are validated by Python and saved as versioned application preferences, separately from project files. Cancel discards settings edits; Restore shipped defaults changes the dialog draft until Save is pressed. Existing modern custom-template preferences are carried into the unified settings. GTK pickle settings are not read.

**Analysis → Default rows** inserts the configured default template. Opening an analysis with no calculation rows also inserts those defaults as an undoable draft change; apply the analysis and save to retain them. **Schedule → Modify & Add**, available while browsing a library, applies the configured multiplier and eligible trailing-row replacements and records the library item reference. As in GTK, its multiplied stored schedule rate may differ from the resulting analysis rate until explicitly recalculated. Plain import retains its existing behavior. The entire Modify & Add operation is one project undo step.

The library dialog also lists the bundled DSR databases and `.eproj` files in the legacy custom database folder. The Databases ribbon and attachment dialog can open that folder. Refresh available databases after adding a file. Bundled databases are packaged in the sidecar and remembered by stable names rather than temporary extraction paths; attachments remain read-only snapshots.

Measurements are grouped under categories. Double-click a category or press Enter to edit its name. Select an item and choose **Edit records**, or double-click it, to open its records page. **Properties** is available on the main Measurements ribbon and the records ribbon. On the records page, **Edit description** focuses the editable Description / remarks field; the heading shows up to 120 characters, with the full description available in its tooltip. Record actions appear in the contextual ribbon. Use **Update schedule quantities** from the main list with the desired rounding rule. Stable identifiers and project undo retain record values. Template-calculated columns are read-only. Deleting linked schedule items retains measurement records/remarks and clears their associations; undo restores the links.

Measurement columns use the widths and expansion rules declared by their Python templates, including the steel table. Numeric inputs align right, calculated columns are shaded and read-only, and template user data and schedule links wrap into responsive fields. Trees stay expanded. Arrows navigate cells; Home/End and Shift ranges retain row selection, Ctrl/⌘+A selects the current page, and Escape clears selection. Enter/F2 starts the focused cell editor. During editing, Tab/Shift+Tab and plain arrows accept the value, wait for backend validation and continue editing the next editable cell. Read-only calculated fields are skipped. Invalid/stale edits reopen with the typed value for correction; Shift/Ctrl+Enter inserts a newline.

Row copy/paste works between modern instances for Analysis, Schedule, Resources, whole measurement items and template-matched records. Category selections include contents beyond the displayed page; schedule transfers carry required resource and sub-analysis definitions. Schedule/resource collisions receive a copy suffix. Matching destination resource definitions are reused; copied schedule stored rates are retained. Measurement links match schedule codes; missing codes clear the link with visible feedback and preserve records/remarks. Each paste is one undo step. The versioned JSON format is separate from GTK's pickle clipboard; unsupported data is rejected. Limits are 500,000 characters, 1,000 items/dependencies and 1,000 records per copied measurement item. When native clipboard writing fails, the UI explicitly reports a fallback limited to the current window. Actual native clipboard behavior remains a supported-platform check.

Schedule/resource creation suggests codes using the original GTK numbering helpers. A selected category inserts at its start; a selected item supplies the insertion position. New items are selected and revealed on the appropriate page; an active search/category filter is cleared to make the new row visible. Right-click a row for contextual editing actions. Ctrl+E opens schedule analysis or resource/measurement Properties. Category rows are bold; the schedule omits category/parent columns and resources omit category. Use the category filter to choose one or several categories before paging, and use item dialogs/API fields to edit category/parent relationships. **Move resources…** moves selected definitions between categories with their codes and links intact. Ctrl+L opens Add item/resources from database in a separate dialog; the working selection remains the insertion target. Whole-category imports retain their categories.

Measurement templates are grouped by General, Civil and E&M and show descriptive names, inputs and calculation notes before creation. **Properties…** (Ctrl+E) stages description, links and template data until Save; Cancel preserves the item. Steel labels and constants are paired by bar, and numeric constants accept evaluated arithmetic. Search/clear controls manage schedule links; per-item remarks identify mapped quantity columns. Use **Add multiple records** for a single undoable batch of 1–1000 rows. Record tables show 100 rows per page; Ctrl+A selects the current page, and copy/paste/duplicate/delete/move work on ordered record selections. Full totals and quantity updates include every page. Ctrl+Enter applies an analysis; Ctrl+Escape opens draft-discard confirmation. Ctrl+Shift+S remains Save Copy.

The [editor review](../docs/migration/editor-review.md) records corrected inefficiencies and unusual retained template rules, including NLBH's treatment of zero factors and the electrical templates' count/dimension conventions.

Use the **Databases** tab to attach/manage sources. Attach adds a row and keeps the dialog open; Close is separate. Schedule and Resources have **Add from database** and **Database rates** dialogs, with source selection, search, multiple-item/category selection and rate-change preview. Program Settings groups all Library Modify & Add controls in one tab. Dropdown popups follow the main menu theme. Enter accepts text; Shift/Ctrl+Enter inserts a line break. Measurement cells display the original evaluated results and Breakup while retaining expressions for editing. See the [database workflow and modification-preset proposal](../docs/migration/database-selection-workflow.md).

Use **MCP → Configure server** to set the local port and optional automatic startup, inspect tools, rotate the connection token and copy client configuration. **Start server** / **Stop server** control the listener independently of the editor. Choose Read only or Read and write. The server exposes 110 typed application operations plus seven read aliases through the existing Python service, including database metadata/definitions, complete estimate editing, batch operations, measurement evaluation, save/export and undo. Writes require the current revision. Agent updates refresh the UI while active human inputs are preserved for stale-edit correction. See [MCP setup and lifecycle](../docs/migration/mcp-server.md) for supported tools and client requirements.

In Schedule, select item rows and use **Row colour…** to apply or clear their saved colours. Use **Quantities from measurements…** to update the selected items from their linked totals. **Resource usage** opens the project totals from either Schedule or Resources.

**Import workbook** previews a schedule/resource worksheet with field mapping and duplicate policies. **Export workbook** calls the existing five-sheet exporter. Apply an analysis draft before exporting the whole project; analysis-only export includes the draft without changing the project.

**Application menu → Project settings…** edits the existing project name/code metadata. Linux typography reads the actual GTK control font family and size and follows font changes; other platforms use native CSS menu typography until platform validation is complete. No external font is downloaded.

The modern workspace is not yet a complete GTK replacement. Consult the parity ledger before relying on a workflow that has not been exercised. Library snapshots preserve their source files.

Editor previews: [Schedule](../docs/migration/screenshots/schedule-desktop.png) · [Resources](../docs/migration/screenshots/resources-desktop.png) · [Measurements](../docs/migration/screenshots/measurements-desktop.png).

See the [workbench refinement](../docs/migration/workbench-refinement.md) for compact layout, client decorations, filters and cell-navigation behavior.
