# Workbench feedback implementation

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
  View ribbon group. **Ctrl+K** opens Analysis and focuses explorer search.
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
