# Workbench refinement — 2026-11-15

Light-theme content uses darker text (`#111827`), secondary text (`#344155`) and hints (`#45566b`). Dark-theme secondary/hint colours are brighter for contrast. System typography and 24 px full-action icons are retained. Smaller actions use two rows with 20 px icons and captions; measured overflow switches to the existing two-row icon layout. Tighter buttons, form gaps, table padding and chrome expose more content. Redundant breadcrumbs, instructional headings, counts/legends and calculation notes are hidden; the active description, remarks, rate and editable data remain visible.

Tauri disables native decorations and uses the existing compact header for client-side drag regions and minimize/maximize/close controls. Close still travels through the existing dirty-project guard. Native scaling, resize edges and platform window-manager behavior require target-platform checks; browser tests exercise the controls through the transport substitute, and native compilation validates configuration/capabilities.

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
