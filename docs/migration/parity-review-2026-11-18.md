# GTK parity review — 2026-11-18

> Historical migration/design record. Start with the [documentation index](../README.md)
> and [current architecture](../architecture/README.md) for development. Old plans,
> branches, API/tool names and validation counts below describe their date; do not
> treat them as current implementation instructions. See the [archive index](README.md).

Reference: the GTK implementation in this checkout (`estimator/gtk_app.py`, `estimator/view/`, `estimator/data/`). This is a source/workflow audit backed by the Python regression suite and browser tests using the real Python service. It is not a claim that every native GTK/WebView interaction has been tested side by side.

## Corrections in this change

| Finding | Correction and evidence |
|---|---|
| Returning from Analysis could leave the cached Schedule virtual viewport blank until scrolling. | Rebuild rows after the table becomes visible and layout settles, restoring its scroll position. Ordinary cell saves retain their normal redraw to protect Tab/Enter editing. Browser checks cover repeated returns at 1280, 1366, 1600 and 1920 px, plus the existing scrolled-table regression. |
| Analysis could display a horizontal scrollbar on desktop layouts. | Fit the columns and suppress horizontal scrolling when the analysis pane is at least 500 CSS px wide. Preserve scrolling below that usable minimum. Check that the last amount remains inside the visible pane, rather than checking scrollbar CSS alone. |
| Library selection had one outer project snapshot but invoked the legacy individual insert wrappers inside its loop. | Stage new schedule/resource models and call `insert_item_multiple_atomic` / `insert_resource_multiple_atomic`, with `preserve_structure=True`. Retain destination placement, category/parent relationships, prefixes, collision policies and rate handling. Updates to existing items remain updates. The outer project mutation supplies the single undo operation. Dependency models are also inserted in a batch. Tests prohibit individual add wrappers, count batch calls, undo/redo imports, inject a failure midway and verify source files remain identical. |
| Analysis library resource selection dispatched individual resource insertions internally. | Validate the selection and insert the complete block into its group in one draft operation. Preserve visual order, insertion position and reuse of project/draft resource definitions. GTK's `AnalysisView.add_res_library` likewise builds one model and calls `modify_model` once. |
| Measurement record edits immediately changed the project, unlike GTK's accepted/cancelled `ScheduleDialog`. | An explicit records draft holds records, links, description and template properties. Apply records (Ctrl+Enter) accepts it as one project undo step; Discard records (Ctrl+Escape) and navigation use the unsaved-change guard. Draft undo/redo is separate from project undo. Save and recovery include pending records. Failed edits/applies/saves retain the draft. All eight templates are exercised. |
| UI formatting was inconsistent across table cells, summaries and dialogs. | Regional locale, currency code and symbol visibility live in Program Settings. One Intl formatter covers rate/amount columns, database pickers, analysis/explorer/inspector displays, overall estimate total, usage and preview dialogs. Numeric editing retains exact raw values/expressions. Preserve the backend's displayed decimal precision; quantities, factors, tax percentages and measurement dimensions remain non-currency values. Workbook numeric data/calculations are unchanged. |
| Windows did not expose its control font to the modern shell; table defaults followed custom interface typography. | Read Windows message/control typography using `SystemParametersInfoForDpi` at 96 DPI, retain GTK's native font on Linux, and use CSS platform menu typography where needed. Both interface and tables independently follow OS defaults when blank, with a 13 px fallback. Saved custom fonts remain effective. Local Windows detection returned Segoe UI / 13 px. |

MCP reads continue to expose committed working-project measurements, with stable original record IDs even when the human draft deletes records. State reports `records_dirty`; conflicting agent writes return `draft_conflict`. Recovery snapshots include the draft without applying it to the working project.

## Concrete gaps found in the original audit

These six gaps were subsequently implemented. See the [follow-up ledger](parity.md#follow-up-implementation--2026-11-18) for current status; native platform gates remain open.

| Original command | Modern coverage / gap | Reference |
|---|---|---|
| Mark stored rates differing from analysis rates, using discrepancy bands and missing-analysis counts | The MCP summary reports rate differences; there is no equivalent Schedule UI action or discrepancy-band highlighting. Ordinary saved row colours are a separate feature. | `MainWindow.on_sch_mark_clicked`; `ScheduleView.update_store(mark=True)` |
| Renumber resources with selectable library-prefix exclusions | Resource code editing exists, but the resource renumber command and prefix selection are absent. Modern renumber currently supports schedules only. | `MainWindow.on_res_renumber_clicked`; `ScheduleDatabase.assign_auto_item_numbers_res` |
| Explicitly synchronize selected resource rates from same-code schedule items | Modern edits/apply recalculate dependent rates automatically. The standalone repair action for pre-existing mismatched schedule/resource rates is absent from the Resources ribbon. | `MainWindow.on_res_sync_rates_clicked`; `ResourceView.update_resource_from_schedule` |
| Import several analyses from one workbook and match them to existing schedule codes, with comment-position and rounding parser options | Modern range import previews/replaces one loaded analysis; it does not provide this multi-item matching workflow or expose those parser options. | `MainWindow.on_import_ana_clicked`; `view.analysissettings.get_analysis_settings`; modern `importing.import_analysis` |
| Open a project supplied by OS file association / command line, or drop a project into the window | Modern Open/recent/recovery commands exist. There is no file-association declaration, launch-path forwarding or file-drop handler in the Tauri shell. | GTK `do_open`, `do_command_line`, `drag_data_received`; modern `main.rs`, `tauri.conf.json`, `App.vue` |
| Original application help/about commands | Modern shortcut help exists. A full application manual/About dialog is absent. | GTK `Application.on_help`, `on_about` |

Mapped workbook import with Update duplicates covers GTK's selected-column resource rate/tax/discount/reference and schedule rate/quantity update workflows. Modern resource moves replace GTK's instance-local cut/paste protocol. Modern read-only library attachments and validated JSON clipboard are intentional alternatives, as documented in the parity ledger.

The previous ledger claimed existing GTK PDF workflows. No PDF export or print command is present in the inspected GTK application entry points. The original exporter creates five-sheet XLSX workbooks with print settings; direct PDF/report generation is a future feature, not an established GTK parity failure in this checkout.

## Validation limits

Native OS dialogs, actual system clipboard, installed package startup, Windows/macOS scaling and input methods, Excel/LibreOffice rendering, large real estimates, and custom template corpora still need their platform checks. Browser tests replace the Tauri transport only and use real Python calculation/persistence. This audit did not launch GTK or compare native screenshots side by side.


Final automated results: **138 Python tests**, the **63-test full browser suite**, the final **16-scenario affected browser recheck**, and the **new lifecycle regression** passed; **64 distinct browser scenarios** passed across runs. The frontend production build and `git diff --check` passed. See the [validation record](validation.md) for commands, test scopes and native-platform limits.
