# Workbench feedback implementation

## Review fixes — 2026-11-17

- Compact Analysis cells no longer apply padding twice while editing. A later
  compact-table rule had overridden the editing cell's zero padding, adding
  7 px horizontally and 3 px vertically around an already padded editor shell.
  The final editing override keeps the shell responsible for padding. Browser
  checks compare text coordinates and row height before editing and after Enter,
  including multiline schedule/resource tree cells and measurement records.
- Appearance font suggestions use PrimeVue AutoComplete with the application's
  dropdown palette, border, shadow and focus colors. The installed list is
  filtered without restricting typed font names. Popup Enter and Escape retain
  selection/dismissal behavior without saving or closing the settings dialog.

Four focused browser workflows and the production frontend build passed.
Popup and Analysis edit/accept screenshots were reviewed; see the
[validation record](validation.md#pending-workbench-review-fixes--2026-11-17).

## Initial window reveal — 2026-11-17

The native main window starts hidden, preventing a visible transition through
unstyled/default typography and partially initialized controls. The frontend
shows it after startup preferences, desktop font, backend state, MCP/recovery,
font loading, table construction/data replacement and explicit ribbon/table
layout. Initialization errors are displayed when the window is revealed.
Normal resize and typography updates retain their scheduled layout behavior.

## Schedule total and shortcut categories — 2026-11-17

- Schedule has a highlighted, read-only **Overall estimate total** row below
  its grid. The backend sums individually currency-rounded rate × quantity
  values for every item with a unit, excluding the sub-analysis category.
  Search, category filters and pages do not restrict this overall amount.
  Both full and incremental state responses carry the total, including when
  the changed item is off the visible page. Edit, undo and returning to Schedule
  refresh the displayed value.
- Shortcut help groups commands under Project and search, Rows and clipboard,
  Cell editing and selection, Editor actions and Ribbon navigation. Each group
  has a semantic heading. Escape's retained-cell-focus behavior is listed.
- The summary row exposed a delayed Tabulator visibility redraw that shifted a
  restored virtual table by 7 px. A follow-up visibility observer restores the
  saved scroll position after Tabulator's own redraw, preserving navigation.

## Keyboard and record navigation follow-up — 2026-11-17

- Escape cancels a table cell edit and focuses that cell, preserving its keyboard
  navigation position. Enter/F2 can reopen it; arrows and Tab continue navigation
  in Schedule, Resources, Analysis and measurement records.
- Loading an analysis refreshes the explorer's schedule results using its current
  search and page. Newly added schedule items appear without submitting a search.
- Every measurement template's record grid prepends a generated, read-only
  **Sl. No.** column. Numbers follow record order across pages and are recomputed
  after insertion, deletion and undo; template data and project files are unchanged.
- Ctrl/⌘+F focuses and selects the existing search input in the frontmost dialog,
  otherwise in the active editor. Analysis reveals its explorer when needed.
  Views without a search bar retain their existing layout. Ctrl/⌘+K is removed,
  and the shortcuts overlay lists the replacement.

## Measurement editing review follow-up

1. Schedule and measurement text editors keep the table's tree decorations in
   the first line of the editor, retaining the indentation and connector lines.
2. Edit description turns the measurement record heading into a multiline editor.
   Enter or focus loss saves the change. Escape discards it.
3. The heading fits up to five lines and uses a middle ellipsis when needed.
   The full text is available in the heading tooltip and when editing.
The user explicitly requested marking and committing the current work, then
continuing in a separate thread. No further redesign was attempted here.

The MCP efficiency work is checkpointed separately in `cca316f`
(`feat(mcp)!: streamline estimate workflows`). The changes described here follow
that checkpoint. The first workbench feedback implementation is committed as
`2245ced` (`feat(workbench): streamline editing and navigation`).

## Follow-up interaction refinements

- Search fields and category buttons share their height and baseline. Full ribbon
  buttons reserve the same caption height and align their icons, including
  single-line captions such as Duplicate. Explorer uses a left-pane icon;
  Inspector uses a normal full ribbon button. Delete actions use red text/icons.
- Resource Edit and Move actions are grouped under EDIT.
- Opening measurement records replaces the list ribbon with record creation,
  duplication, copy/paste/delete, move, import and properties actions. The
  Measurements caption uses a green contextual accent and an accessible mode
  description. This follows the color-coded contextual-tab convention in the
  [Windows Ribbon documentation](https://learn.microsoft.com/en-us/windows/desktop/windowsribbon/windowsribbon-element-ribbon-contextualtabs).
  The duplicate body toolbar is removed; totals remain beside the record table.
- Measurement descriptions are the first column. Category names are bold parent
  rows, with indented measurement items; the category's Type cell is blank.
- Dragging near or beyond either vertical table edge scrolls the viewport and
  extends selection while the pointer is held. The same implementation serves
  editors and database pickers, retaining row-only selection in import pickers.
- Main dialog fields use autofocus, including reused dialogs. Editor focus is
  restored after modal close transitions and when entering or leaving Analysis
  and measurement records; the corresponding parent item remains selected.

## Measurement editing and tax precision follow-up

- Measurement template help describes calculations directly, without references
  to GTK or another application version.
- Double-clicking a saved measurement category, or pressing Enter with it
  selected, opens its name editor. The list also provides full Edit Records and
  Properties ribbon buttons. Properties supports both items and categories.
- Description edits on the records page update the list and remain undoable.
- Schedule-link and remark fields in Properties have spacing for their focus
  outlines, including at dialog edges.
- Table text editors preserve the original font, padding and hierarchy prefix.
  Entering edit mode and typing a character no longer changes the row height.
  Blank measurement records use the normal single-line row height; additional
  text lines can increase it. Home/End operate inside the editor.
- Visible VAT labels are renamed **Tax**. Tax percentages are rounded and stored
  to four decimal places; base rates and discount retain their existing precision.
  The resource model, desktop edits, custom analysis resources, spreadsheet import
  and resource-usage export use the four-place tax value.

The existing `vat` column, MCP keys and SQL-view field remain for compatibility.
No destructive schema operation or project-version change is needed: existing
SQLite resource columns accept the higher precision. Tests cover a legacy project
round-trip without schema changes or modification of its source file. Older app
versions that write tax with two-place rounding can reduce precision if the value
is edited there; reverting this implementation does not rewrite stored values.

## Navigation and refresh

- Title-bar Back and Forward traverse editor, ribbon and measurement-entry
  history. Shortcuts are **Alt+Left** and **Alt+Right**. Existing unsaved-draft
  prompts also apply to history navigation.
- Schedule, Resources and Measurements retain their table instances, selection,
  filters, page and scroll when switching views. Analysis's Schedule button
  reveals and selects the matching schedule item, including on another page.
- A connection-local SQLite change journal tracks schedule/resource writes.
  Returning to a table requests changes since its previous sequence and updates
  only changed rows on its current page. Inserts, deletes, reordering, hierarchy
  changes, category changes, filtered-result changes and undo/redo invalidate the
  affected table so its structure can be rebuilt correctly. No project-file
  schema change is required; failed transactions roll back their journal entries.

## General controls

- The project explorer is displayed only in Analysis. Its toggle is in Analysis's
  View ribbon group. **Ctrl/⌘+F** focuses the existing search bar in the active
  view or frontmost selection dialog. In Analysis it reveals explorer search.
  The earlier **Ctrl+K** shortcut is removed.
- Refresh MCP status is a labeled ribbon button.
- Save Copy and workbook/analysis export open the OS save dialog directly. Open
  uses the OS picker directly when there are no recent or recovery files. The
  recent/recovery chooser remains when it adds those options. Spreadsheet import
  retains its preview, range and mapping controls.
- Dialogs focus their main editable field. Persistent pickers retain their
  contents and stack correctly above other dialogs; themed option menus fit the
  viewport and remain above the active dialog.

## Schedule and Analysis

- Selecting a schedule parent in a database picker imports that parent only.
  Selecting its children explicitly imports those children too. Selecting a
  category remains an explicit request for all its contents.
- Schedule, Analysis and measurement records share pointer-drag row and column
  ranges without selecting display text. Schedule/resource database import
  pickers use whole-row selection only, including keyboard navigation; their
  column headers do not select cell ranges. Cell text can be selected while editing. Zero rates and quantities display
  blank. Row colors use a 16-swatch palette and remain undoable.
- Analysis offers separate **From database** and **Custom resource** actions. The
  database picker supports multiple selection, drag selection, category/search
  filters and paging. One insertion batch is one draft undo step.
- Custom resource codes are optional and receive an available `MR.n` code when
  blank. Clicking an explorer resource inserts it directly into the current
  analysis group.
- Analysis rows are compact by default. Duplicate follows the add-resource
  buttons; Delete sits below Copy/Paste. Edit Rows and project bulk rules are
  removed from the Analysis ribbon; project rules remain in Schedule.
- The resource table displays a consolidated rate. Resource quantity is editable
  in the table; code, description, unit, base rate, VAT and discount are edited
  through the Inspector. Calculation descriptions retain their height on entering
  edit mode.
- Resource-usage analysis descriptions wrap to the dialog width.

## Measurements

- The list groups measurement items under categories. Double-click an item to
  open a separate measurement-entry view; Back returns to the list. Entry changes
  update the cached item's description, record count and totals.
- Categories retain the existing heading representation on disk for compatibility
  with original projects. Category creation respects group boundaries; category
  moves, copies, duplication and deletion include their contents. Items before
  the first saved category appear under a virtual Uncategorised group.
- The redundant measurement caption field is removed. Link and remark controls
  have additional padding. The schedule chooser is reused and wraps long
  descriptions. The rounding control and its menu fit within the viewport.
- Editing starts at the existing measurement row height and grows only when the
  edited text needs additional lines.

## Search algorithm

Desktop tables, explorer search, database pickers and MCP `search_items` share
the cached search index:

1. Normalize units and dimensions; expand terms from user, database-enrichment,
   built-in and automatically extracted abbreviation dictionaries.
2. Rank literal and expanded text using SQLite **FTS5 BM25**. A Python BM25
   implementation is used when FTS5 is unavailable.
3. Combine literal and expanded rankings using weighted reciprocal rank fusion:
   `3 / (60 + literal_rank) + 1 / (60 + expanded_rank)`.
4. Put an exact code match first; apply category/limit constraints. Leaf items
   receive a small ranking boost.

Desktop searches additionally prioritize partial code matches (prefixes before
other code fragments) and retain description/category substring matches as a
fallback. This preserves code lookup and incomplete-word searches. Empty search
keeps the usual project ordering. Ranked table pages retain category/parent
context; groups are ordered by their best matching item. Category filters apply
before paging, including searches with more than 100 matches.

There are no embeddings or vector-model downloads in the current implementation.

## Debug traces

Frontend debug messages use `[GEstimator]` in the webview console for button,
menu, tab and shortcut actions and backend requests. Requests record method,
parameter names, elapsed time and failure code, without input values.

The backend's `gestimator.actions` logger writes action start/completion/failure
to stderr. MCP traces include operation name, read/write classification, access
mode, revision changes and duration. HTTP authorization rejections record their
reason. Credentials and request payloads are not logged. Set
`GESTIMATOR_LOG_LEVEL=INFO` to suppress the default debug action traces.

## Validation

Regression coverage includes affected-row updates, empty draft-navigation deltas,
structural/undo invalidation, failed-transaction rollback, generated resource
codes, atomic multi-resource insertion, explicit parent/child imports, category
movement and credential-free MCP action logs. Browser checks cover the changed
workflows alongside the existing editor, clipboard, import/export, settings,
library, recovery and MCP workflows.

Verified on 2026-11-17: 119 Python tests passed; all 39 browser workflows passed
across the full run and a focused rerun of the ranked-result selection assertion.
The production frontend and standalone backend builds passed. The frozen backend
also passed a smoke test for dictionary-based desktop search and incremental
refresh. Native file dialogs are exercised through the mocked Tauri transport in
browser tests.

Follow-up verification: all 42 browser workflows passed across the full run and
the focused alignment/focus/drag rerun; the production build passed. Screenshots
were reviewed for the measurement hierarchy, contextual record ribbon and shared
resource/search alignment. No backend or project-file format changes are part of
this follow-up.

Measurement/tax verification: the full Python run passed 122 tests, and the
additional tax-header spreadsheet import/export test passed in the focused
backend run. All 45 browser workflows were verified across the full run and the
focused rerun, including category rename, record remarks, focus-outline spacing,
blank-row height, editor geometry and tax precision. Production and standalone
backend builds passed; the frozen backend passed tax-storage and template-copy
smoke checks. The cached measurement ribbon now refits when it becomes visible,
including at narrow viewport widths.

Main-page Properties and Edit Records keep their text labels at narrow widths.
Editable controls use inset focus outlines, with additional field and
paired-field spacing.

All 46 browser tests passed in one full run. The added audit checks every editable
schedule/resource column, tree-marker coordinates and focus-ring clipping in the
main forms, inspector, custom-resource dialog, measurement properties and record
page. The production frontend and offline native development build passed. The
native executable is `modern/src-tauri/target/debug/gestimator-modern`.
