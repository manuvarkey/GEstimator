# Frontend architecture and workspace contracts

Current contract, checked against source on 2026-11-23.
Navigation: [index](../README.md) · [architecture](README.md) · [backend](backend.md)
· [UI rules](../ui-guidelines.md) · [verification](../testing.md).

## Ownership and module map

Vue collects input and renders Python results. It owns view state, not estimates,
rate calculations, numeric expression evaluation or persistence rules. Monetary
formatting is presentation; the currency option does not convert prices.

| Concern | Owner |
| --- | --- |
| App mounting, PrimeVue, styles and shared input installation | [`main.ts`](../../modern/src/main.ts) |
| Active document workspace lifetime | [`Root.vue`](../../modern/src/Root.vue) |
| Document/session store and actions | [`documents.ts`](../../modern/src/documents.ts), [`useDocumentTabs.ts`](../../modern/src/useDocumentTabs.ts) |
| Shell, ribbon/context, guarded navigation and coordination | [`App.vue`](../../modern/src/App.vue) |
| Keyboard shortcut reference and its layout | [`KeyboardShortcutsDialog.vue`](../../modern/src/components/KeyboardShortcutsDialog.vue) |
| Guarded file workflows, recent paths and recovery state | [`useProjectFiles.ts`](../../modern/src/useProjectFiles.ts) |
| File chooser form, recent paths and recovery actions | [`ProjectFileDialog.vue`](../../modern/src/components/ProjectFileDialog.vue) |
| View/history navigation and document-local memory | [`useWorkspaceNavigation.ts`](../../modern/src/useWorkspaceNavigation.ts) |
| MCP change polling and workspace refresh coordination | [`useWorkspaceMCP.ts`](../../modern/src/useWorkspaceMCP.ts) |
| Analysis requests, authoritative state and selection refresh | [`useWorkspace.ts`](../../modern/src/useWorkspace.ts) |
| Analysis resource, workbook, custom template and project analysis rules dialogs | [`AnalysisDialogs.vue`](../../modern/src/components/AnalysisDialogs.vue) |
| Native save chooser for project and analysis workbooks | [`workbookExport.ts`](../../modern/src/workbookExport.ts) |
| Selected analysis row fields, amounts and inspector actions | [`AnalysisInspector.vue`](../../modern/src/components/AnalysisInspector.vue) |
| Analysis ribbon groups and row insertion buttons | [`AnalysisRibbon.vue`](../../modern/src/components/AnalysisRibbon.vue) |
| Analysis Schedule and Resources explorer | [`AnalysisExplorer.vue`](../../modern/src/components/AnalysisExplorer.vue) |
| Schedule and resource database picker coordination | [`ProjectDatabasePickers.vue`](../../modern/src/components/ProjectDatabasePickers.vue) |
| Schedule/resource/measurement workspaces | [`ProjectViews.vue`](../../modern/src/components/ProjectViews.vue) |
| Rate discrepancy query, summary and grid highlighting | [`ScheduleRateDiscrepancies.vue`](../../modern/src/components/ScheduleRateDiscrepancies.vue) |
| Schedule, Resources and Measurements list ribbon groups | [`ProjectListRibbon.vue`](../../modern/src/components/ProjectListRibbon.vue) |
| Project editor shortcut recognition and precedence | [`projectViewShortcuts.ts`](../../modern/src/projectViewShortcuts.ts) |
| Project grid loading, search, paging, delta refresh and table restoration | [`useProjectGrid.ts`](../../modern/src/useProjectGrid.ts) |
| Post-insertion grid focus across editors and dialogs | [`useEditorFocus.ts`](../../modern/src/useEditorFocus.ts) |
| Resource category move and renumbering dialogs | [`ResourceEditingDialogs.vue`](../../modern/src/components/ResourceEditingDialogs.vue) |
| Schedule row colour, quantity update and renumbering dialogs | [`ScheduleEditingDialogs.vue`](../../modern/src/components/ScheduleEditingDialogs.vue) |
| Delete preview and confirmation | [`ProjectDeletionDialog.vue`](../../modern/src/components/ProjectDeletionDialog.vue) |
| Item and category forms | [`ProjectItemDialogs.vue`](../../modern/src/components/ProjectItemDialogs.vue) |
| Schedule/resource workbook, multiple analysis and measurement record import dialogs | [`ProjectImportDialogs.vue`](../../modern/src/components/ProjectImportDialogs.vue) |
| Measurement record page, detail loading, description edit and record memory | [`useMeasurementRecords.ts`](../../modern/src/useMeasurementRecords.ts) |
| Measurement draft header, description field, totals and page controls | [`MeasurementRecordLayout.vue`](../../modern/src/components/MeasurementRecordLayout.vue) |
| Measurement record editor ribbon groups | [`MeasurementRecordRibbon.vue`](../../modern/src/components/MeasurementRecordRibbon.vue) |
| Staged measurement/category properties and schedule-link picker | [`MeasurementPropertiesDialog.vue`](../../modern/src/components/MeasurementPropertiesDialog.vue) |
| Project table pages and deltas, measurement responses and tab memory | [`projectViewTypes.ts`](../../modern/src/projectViewTypes.ts) |
| Measurement category projection, schedule rate highlighting and row traversal | [`projectGridRows.ts`](../../modern/src/projectGridRows.ts) |
| Measurement column presentation and Tabulator type compatibility | [`measurementColumns.ts`](../../modern/src/measurementColumns.ts) |
| JSON request transport and shared analysis types | [`backend.ts`](../../modern/src/backend.ts) |
| Project and analysis grid lifecycle | [`DataTable.vue`](../../modern/src/components/DataTable.vue), [`dataTableTypes.ts`](../../modern/src/dataTableTypes.ts), [`AnalysisTable.vue`](../../modern/src/components/AnalysisTable.vue) |
| Tab memory, row clipboard, cell navigation/editing and selection | [`tabMemory.ts`](../../modern/src/tabMemory.ts), [`rowClipboard.ts`](../../modern/src/rowClipboard.ts), [`cellNavigation.ts`](../../modern/src/cellNavigation.ts), [`tableTextEditor.ts`](../../modern/src/tableTextEditor.ts), [`tableSelection.ts`](../../modern/src/tableSelection.ts) |
| Display formatting and appearance | [`numberFormatting.ts`](../../modern/src/numberFormatting.ts), [`appearance.ts`](../../modern/src/appearance.ts) |
| Program settings and shared helpers | [`programSettings.ts`](../../modern/src/programSettings.ts), [`uiActions.ts`](../../modern/src/uiActions.ts), [`statusNotice.ts`](../../modern/src/statusNotice.ts) |
| MCP control/status and library restoration | [`mcp.ts`](../../modern/src/mcp.ts), [`libraryPreferences.ts`](../../modern/src/libraryPreferences.ts) |
| Native file-open/drop routing | [`projectOpening.ts`](../../modern/src/projectOpening.ts) |

Before adding behavior to a shell/view, check for an existing shared helper.
Extract a separate concern into a composable or component with explicit inputs
and cleanup. The [quality audit](../code-quality-audit.md) tracks the remaining
shell and project view concerns.

## Document and view lifetimes

`documents.ts` maps document tabs to backend sessions and marks the active one.
`Root.vue` keys `App` by the active document, so switching documents unmounts one
workspace and mounts another. Backend projects and drafts remain alive; local
component state does not automatically survive remounting.

`tabMemory.ts` stores document-specific navigation, selection, paging and scroll
state for restoration. `useWorkspaceNavigation` owns editor/ribbon state, history,
record-page identity, inspector visibility and the workspace memory snapshot.
It receives the shell's draft guard and analysis-loading/focus callbacks, keeping
one guard path. A new/replaced project or closed document forgets its old state.
`useDocumentTabs` routes New/Open/Close and window close through that same guard;
do not bypass it from a new button or native callback.
File opens resolve the requested path with the backend before looking for an
already open document. Opening that document activates its existing tab and
preserves its working copy, drafts and history. A closed project clears its
tab path. Resolving aliases at the time of the request lets a moved symlink
select its current target.

`useProjectFiles` owns New/Open/Save/Close orchestration, the file-dialog state,
recent paths, recovery choices and OS-open completion/handoff state. It delegates
session switching to `useDocumentTabs` and persistence to `useWorkspace`/Python.
`ProjectFileDialog` renders the form and binds its mode and path to the same
state that the OS-open queue observes. Browse, submit and recovery actions
delegate to the existing file workflow.
The shell supplies the same draft guard and a post-save continuation, retaining
pending actions and measurement-view refresh in one place. Cancelling that guard
also settles the composable's pending native open; displaying the dialog alone
must not release the OS request queue. `projectOpening.ts` still owns native
event/drop serialization; the shell installs it after reconnect and cleans up
its listeners on unmount. New entry points reuse these paths.

For an in-place Save of a dirty project with `source_requires_folder`,
`useProjectFiles` asks for the project folder and passes the selected path to
Python. Cancelling leaves the pending action and edits available. Python owns
grant verification and reuse under the [save contract](database-format.md#working-copies-save-and-recovery).

Project and analysis workbook exports share a native save chooser. Cancelling
the chooser sends no export request. A returned path carries the chooser's
replacement confirmation to Python, which owns export publication and
replacement rules. Each view keeps its export command and error handling.

Schedule/Analysis/Resources/Measurements select editors. Databases and MCP
select ribbon context while preserving the active editor. Active project views
are retained within a mounted workspace to preserve their state. Keep this
separate from document switching, which changes backend session and remounts it.

`AnalysisRibbon` renders its groups directly in the shared ribbon host.
`App.vue` supplies the edit, selection and panel state, and handles ribbon
events through the existing analysis commands, dialogs and visibility controls.

`AnalysisExplorer` renders the active search tab and its project items.
The workspace loads the Schedule page when the Explorer becomes visible,
including for new and remounted projects. It refreshes the last submitted
query, keeping unsubmitted search text available. Search stays available
during this initial load and a newer request takes priority over its result.
The workspace retains results and paging state and uses the shared Search
as you type setting for both tabs. Up or Down from search moves focus
to a result button. Arrow keys and Home/End navigate results, and Enter
activates the focused result. The shell routes schedule activation through
guarded navigation and resource activation through the existing draft
insertion command.

`ProjectListRibbon` renders the Schedule, Resources and Measurements list
actions, using the current view, selection and busy state to determine which
actions are available. `MeasurementRecordRibbon` renders the record editor's
four groups using record selection and loading state. Both components render
groups as siblings in the shared ribbon host so it can measure overflow.
`ProjectViews` chooses the active ribbon, keeps the Measurements rounding
selection across record entry and exit, and routes ribbon and keyboard actions
through the existing editor commands and dialogs.

Both project keyboard entry points use `projectViewShortcut` to resolve an
action against the current editor, selection, and event target. Draft finish
and history shortcuts are resolved before source and grid guards.
`ProjectViews` consumes recognized events and dispatches them through its
existing command, draft and dialog handlers.

Shared ribbon, table and dialog styles live in `style.css`. The ribbon
measures its available width and applies `data-ribbon-mini` to individual
actions while honoring actions whose labels must stay visible.

The in-app manual and About, Program Settings and Project Settings load from
local build assets when opened. The shell owns their visibility state.
Startup preferences and the initial workspace load continue through the
workspace setup.

## Requests, stale edits and refresh

`backend.ts` wraps Tauri `backend_request` with a unique ID and explicit document
session. Request orchestration sends the current backend revision for writes.
The Python result is the final authority, including numeric strings, totals,
draft flags and history availability.

Refresh should reconcile selections by stable ID and preserve scroll/focus where
valid. Before a refresh replaces a focused grid cell, keyboard focus moves to
the grid so navigation can resume from the reconciled selection after a row
paste. Do not use a visible row index as an item identity. Hidden category
contents and off-page rows are resolved by backend selection expansion; frontend
filtering cannot define deletion, import or total scope.

`useWorkspaceMCP` polls change sequence/project epoch and refreshes the active workspace.
Refresh is deferred around human edits and dialogs. A stale edit is rejected
with its input retained for correction; do not silently overwrite it with an
agent's new value. Poll state is local to the mounted workspace, seeded from
current MCP status after initialization and cleared on unmount. Do not replay
earlier agent writes as project replacements when switching back to a document.
See [MCP synchronization](mcp.md#desktop-synchronization-and-transport)
and [backend revisions](backend.md#revisions-and-write-boundaries).

## Grids and drafts

The analysis dialogs use the mounted workspace's selection, revision, commands
and error state. `AnalysisDialogs` owns the custom resource form, database
resource picker, workbook import and export, custom template, and project
analysis rule dialog. It keeps the insertion group selected when a resource
action starts and uses the selected row as the insertion point when that row
belongs to the same group. The shell still handles keyboard routing, database
manager requests and the schedule reload and navigation after applying rules.

`AnalysisInspector` renders the workspace's selected analysis row and emits
field edits and row actions. The shell routes field edits through the same
callback as the analysis grid. `useWorkspaceNavigation` owns inspector
visibility and restores it when switching back to an open document tab.

Analysis cell edits reconcile the refreshed row by ID and column. Enter
returns focus to the committed cell by default, while the Program Settings
option opens the next editable cell below. Tab retains its existing navigation
order. Analysis layout redraws preserve focus on a surviving cell.

`ProjectDatabasePickers` keeps separate schedule and resource add pickers and a
shared rate refresh picker mounted across editor switches. The project view
supplies the selected IDs and revision when opening a picker and handles its
apply command. The picker displays the view's command error if applying fails.
Up or Down from the search field moves selection and keyboard focus into the
results grid. This handoff also applies to the Schedule and Resources project
tables. Enter in the search field still runs a search.
Enter in the results grid imports all selected item rows, skipping category
headings. Schedule Enter uses Modify & Add. Ctrl+Enter (Command+Enter on macOS)
adds the items unmodified. Double-click applies to the clicked item.
An updated project session recreates the picker instances, and the shell
continues to open the database manager for picker requests.
The database manager handles reselection of unavailable remembered paths.
`libraryPreferences.ts` updates the saved entry after the replacement
attachment succeeds.

Successful insert commands in Schedule, Resources, Analysis and Measurements
focus the receiving grid once its rows are refreshed and the dialog, if any,
has closed. The same handoff covers new items, subitems, categories, database
and workbook insertion, duplication and row paste. Measurement records use
the record grid when their draft is open. Analysis resources inserted from
the Explorer focus the analysis grid. A failed command leaves focus in the
current workflow, and inactive views cancel a pending handoff.

`ResourceEditingDialogs` stages the destination category for resource moves
and the database prefixes to exclude from renumbering. It loads prefixes
through the project view's busy and error handling. Both edits use the view's
shared command, which supplies the current revision and selection and refreshes
the table and undo controls after a successful edit.

`ScheduleEditingDialogs` stages the row colour, the quantity rounding choice
and the renumber confirmation. The ribbon and the row colour keyboard shortcut
open the same dialogs. The view supplies the selected schedule IDs, current
revision and shared busy/error handling. After a successful command the view
refreshes the grid and history, and the dialog closes. The quantity dialog and
the Measurements ribbon share the [rounding choices](../../modern/src/quantityRounding.ts).

`ProjectDeletionDialog` stages schedule and resource deletion using Python's
preview, and also confirms deletion of selected measurement categories.
It submits the original row IDs and revision through the view's shared
command. The view owns selection, keyboard and menu routing, and refresh.
The preview determines when schedule and resource deletion needs a dialog.

`ProjectItemDialogs` stages item creation, editing, duplication and category
creation. It uses Python's selection-aware defaults for schedule and resource
insertion. The view supplies the selection, category options and measurement
templates, routes ribbon and keyboard actions, and runs the shared commands
that handle errors, grid refresh and undo.
Measurement insertion passes the selected row IDs directly. An explicit
destination in the item form supplies the category ID as the selection instead.

`ProjectImportDialogs` opens the mapped schedule/resource workbook dialog and
the range dialogs for multiple analyses and measurement records. The view
supplies the current revision, editable fields and record selection. Mapped
imports apply from their preview dialog, then refresh the view before showing
the import counts. Range imports use the view's shared command and error
handling. Python owns the preview and write rules for both paths.

Tabulator is a rendering/editing adapter. It does not own authoritative undo or
calculation history. Reuse the table input, arrow/Tab navigation, selection,
clipboard, tooltip and virtual-row helpers instead of making view-specific copies.
Confine unavoidable access to third-party internals to a documented adapter.
The Schedule renders its entire paged result, including category headers and
parent rows. Wrapped rows therefore keep their actual heights during rapid
scrolling, and pagination limits the number of items in the table.

Raw editable numeric strings may be expressions. Keep them distinct from
rendered results; send validation to Python. Derived cells remain read-only.
`GroupTotal` analysis rows and generated record serial numbers are display-only,
not new domain rows to select, edit, copy or persist.

Analysis and records have explicit Apply/Discard boundaries. Accepting a draft
changes the working project; Save publishes a project file. A failed acceptance
retains the editor and draft. Dirty drafts must be guarded during navigation,
project replacement and close. Detailed action placement, keyboard semantics,
numeric formatting and accessible states belong in the [UI guidelines](../ui-guidelines.md).

`useMeasurementRecords` owns the record page, selection, table ref,
description draft and draft-aware detail loading. Its request-token,
item-ID and revision checks reject superseded detail responses before replacing
view state. `ProjectViews` still owns the common command, busy/error recovery,
selection, focus and document-memory snapshot. The composable contributes its
matching record-page memory to that snapshot and restores it after detail loads.
It delegates focus, change notifications and commands through explicit callbacks;
it does not create another draft history or navigation guard.

`MeasurementRecordLayout` renders the draft actions, description editor,
whole-measurement totals and page controls around the view's link fields
and record grid. It owns the textarea ref and provides a focus method for
opening or restoring a description edit. The view routes actions through the
existing draft guard and record-page operations.

`useProjectGrid` loads project pages and applies schedule/resource deltas through
the shared table adapter. It coordinates search, type-ahead, paging and
restoration from the view's remembered table state. Measurement refresh keeps
draft activation and summary synchronization on the existing shared path.

`MeasurementPropertiesDialog` stages description, links and template constants
in a form snapshot with the original revision. The component owns both the
properties form and its schedule-link picker. The view opens the same picker
from the active record editor. Search follows the shared Search as you type
setting. Results scroll independently of the search and page controls. A new
search or page clears the previous results and resets scrolling before the
request completes. Up or Down from search focuses a result, including when the
key is pressed during loading and search still has focus when results arrive.
Arrow keys and Home/End navigate the page, and Enter selects the focused item.
Result buttons show a focus outline regardless of how the picker was opened.
The Properties dialog is inert while its child picker is open. Closing the
picker restores focus to its opener after the parent becomes interactive.
Saving properties and changing a record link use the view's common command.
Python owns validation, calculations and undo.

The contracts in `projectViewTypes.ts` distinguish schedule items, resources,
categories and flat measurement list rows. Full project table pages carry
the row tree, while delta responses carry row values that preserve existing
children. Measurement detail requests update records, links, properties and
totals independently of the list. `projectGridRows.ts` projects measurement
headings into display categories and overlays schedule discrepancy colours.
`DataTable` uses its caller's row type for selection, activation, edits and
patches. The adapter casts rows returned by Tabulator, which does not publish
generic row types. `measurementColumns.ts` handles the existing column options
missing from Tabulator's types and preserves text-node rendering for author data.

## Preferences, styles and text

Program/appearance/MCP/library preferences are application settings, separate
from `.eproj` project metadata. Program settings are validated by Python and
stored in versioned frontend preferences. Do not add project-specific state to
a global preference or store derived backend totals as preferences.

Semantic tokens belong in [`theme.css`](../../modern/src/theme.css); shared
styles in [`style.css`](../../modern/src/style.css). Reuse `AppIcon`,
`RibbonToolbar`, `PersistentDialog`, `ThemedDropdowns` and `ThemedAutocomplete`.
Prefer changing the owning shared rule over adding duplicate selectors at the
end of the stylesheet. Preserve cascade order in any CSS extraction.

User data is rendered as text. Only the shared escaped
[`markdown.ts`](../../modern/src/markdown.ts) renderer formats author notes;
do not insert untrusted HTML into Tabulator, Vue or tooltips. User-facing labels
describe GEstimator behavior, not internal migration/GTK implementation history.

## Extending a frontend workflow

1. Identify its backend operation and typed request/result shape. Add missing
   validation in Python, not a competing JavaScript implementation.
2. Put reusable orchestration in a composable/helper and bounded UI in a
   component. Keep pending/busy/error ownership explicit.
3. Preserve keyboard and pointer interaction, focus, row identity and tab memory.
   Clean up listeners, timers and table instances when the owner unmounts.
4. Reuse the existing unsaved-work guard and status/error presentation. Wait for
   command completion before navigating or asserting an asynchronous result.
5. Verify the affected browser behavior through the real Python bridge, and use
   installed native builds for OS dialogs, file associations and WebView-specific
   behavior. Follow the [testing guide](../testing.md).

The main browser suite is
[`workspace.spec.ts`](../../modern/e2e/workspace.spec.ts); fixtures live in
[`modern/e2e/`](../../modern/e2e). Relevant backend coverage includes
[desktop refresh](../../tests/test_desktop_refresh.py),
[document sessions](../../tests/test_document_sessions.py) and
[records drafts](../../tests/test_records_draft.py). Type checking is strict in
[`tsconfig.json`](../../modern/tsconfig.json); do not broaden `any` or casts to
hide a disagreement at an IPC boundary.
