# Workbench refinement — 2026-11-15

Light-theme content uses darker text (`#111827`), secondary text (`#344155`) and hints (`#45566b`). Dark-theme secondary/hint colours are brighter for contrast. System typography and 24 px full-action icons are retained. Ribbon captions use `.85rem`; full-button widths are measured from their captions, allowing two lines. Smaller actions use 20 px icons with side captions in three fixed-height rows. One- and two-button stacks align to the top and leave unused space below. Full buttons span all three rows; Schedule Add subitem and Duplicate (also Resources, Measurements and Analysis Duplicate) use this form. Measured overflow reduces individual buttons from right to left to icons in the same grid, retaining captions where space permits. This follows the fixed-height stacks and per-button fitting approach inspected in [Open Planner Studio's ribbon](https://github.com/OpenAEC-Foundation/open-planner-studio/blob/main/src/components/layout/Ribbon/Ribbon.css), implemented using the existing Vue component. Tighter buttons, form gaps, table padding and chrome expose more content. Redundant breadcrumbs, instructional headings, counts/legends and calculation notes are hidden; the active description, remarks, rate and editable data remain visible.

Tauri disables native decorations and uses the existing compact header for client-side drag regions and minimize/maximize/close controls. Close still travels through the existing dirty-project guard. Native scaling, resize edges and platform window-manager behavior require target-platform checks; browser tests exercise the controls through the transport substitute, and native compilation validates configuration/capabilities.

On Linux, [Tauri's shadow API is unsupported](https://v2.tauri.app/reference/javascript/api/namespacewindow/#setshadow), so enabling `shadow` is not a fix for the current fully undecorated window. A native route to investigate is GTK-managed client-side decorations, using [a custom GTK titlebar](https://docs.gtk.org/gtk3/method.Window.set_titlebar.html) before showing the window. That integration needs compositor/theme and resizing tests while retaining the application header. No native shadow change is included in the picker update.

Schedule omits category/parent columns; Resources omits category. Definitions, parent/category relationships and editing dialogs/API fields are retained. Category rows are bold. Trees stay expanded and have no expand/collapse control or collapse action. Multi-category filters run in SQL before paging/counting, preserve matching ancestors, include selected empty categories and compose with text search. Clearing the filter restores all categories. Imports/inserts reveal their new rows; deleted/renamed filter names are dropped on refresh.

| Key | Cell behavior |
|---|---|
| Enter/F2 while focused | Start editing the focused editable cell. Enter leaves calculated cells read-only. |
| Tab / Shift+Tab while editing | Accept, wait for backend validation/refresh, then edit the next/previous editable cell. Skip calculated fields and wrap rows. At a table boundary, Tab leaves the table. |
| Plain arrows while editing | Accept and continue in the adjacent editable cell. Up/down retain the column and skip rows where it is not editable. |
| Enter while editing | Accept and continue down the same editable column; at its end, accept and retain focus. |
| Modified Enter in multiline text | Shift/Ctrl/Meta+Enter inserts a newline. Composition input is preserved. |
| Escape while editing | Cancel through the installed table editor. Outside editing, clear row selection. |
| Ctrl/⌘+E | Open the selected schedule analysis or resource/measurement Properties. |

Plain arrows outside editing move cell focus; Home/End, Shift row ranges and Ctrl/⌘+A retain row-selection behavior. Pointer and keyboard focus survive authoritative row replacement using row IDs and field names. Off-screen columns scroll into view before editing, accounting for the fixed Amount column; its opaque header prevents overlapping labels in narrow windows. A rejected edit restores backend data, reopens its input with the typed value and retains focus for correction. Shared navigation is used by Schedule, Resources, Measurements and Analysis; original Python measurement display, raw expression and Breakup behavior is retained.

The [MCP server](mcp-server.md) now supports typed read/write operations for preparing/editing estimates, plus database metadata/definition reads. Its revision checks, existing transactions and UI synchronization prevent silent overwrites between human and agent edits.

## Fine-tuning ribbon buttons

These controls are source settings, not Program Settings. Adjust the final workbench rules near the end of `modern/src/style.css`; earlier base rules are overridden there.

| Control | Current source/value |
|---|---|
| Caption text size | `.ribbon-label` and `.ribbon-icon .ribbon-label`: `.85rem`. Change both together. |
| Full / smaller icons | `.ribbon-action svg`: `24px`; `.ribbon-icon svg`: `20px`. CSS controls the final size. |
| Button padding and spacing | `.ribbon-action`: `2px 4px` padding and `3px` gap; `.ribbon-actions`: `1px 3px` row/column gaps. |
| Group spacing | `.ribbon-group`: `0 5px` padding. |
| Full-button width | `sizeCaptions()` in `modern/src/components/RibbonToolbar.vue` measures the current font and finds the narrowest two-line split. Minimum width is `52px` (also in CSS), caption cap is `80px`, and CSS outer maximum is `88px`. Keep these bounds consistent if changing them. |
| Side-caption width | `.ribbon-action.ribbon-icon`: maximum `140px`, with a single-line caption. |
| Row height and top alignment | `.ribbon-actions`: three rows of `calc((32px + 2.1rem) / 3)` with `align-content: start`. One or two smaller buttons use the first rows without stretching. Full buttons span all three. |
| Overflow fitting | `fit()` in `RibbonToolbar.vue` measures visible groups, then adds `data-ribbon-mini` to individual buttons from the right until they fit. CSS renders these as 30 px icon-only actions. Tooltips and accessible names remain available. |
| Shared ribbon depth | `.ribbon`: `calc(56px + 2.1rem)` height and min-height. Adjust both together if needed for a larger font/icon. |
| Individual button content | `modern/src/components/ProjectViews.vue` for project editors and `modern/src/App.vue` for Analysis/application tabs: `AppIcon` name, `.ribbon-label`, `title` tooltip and group placement. `.ribbon-action` puts the icon above the caption; adding `.ribbon-icon` uses a smaller side-caption action. |

For a tighter ribbon, first shorten captions or reduce horizontal padding/group gaps. Reducing the font alone does not reduce icon sizes or the shared ribbon depth. Widths are remeasured on resize, caption changes and desktop font changes. Check each tab at the intended window width and confirm that two-line captions fit, full icons align, and compact-mode tooltips remain useful.

Analysis has a visible **Schedule** back button and **Alt+Left** shortcut. Both use the existing Apply / Discard / Cancel guard for dirty drafts. The draft-local field batch remains available as **Edit rows**, with a visible caption. **Bulk edit analysis** now opens [project analysis rules](analysis-rules.md) from either the Schedule or Analysis ribbon.
