# Database selection and measurement entry — 2026-11-14

The starting tree was already clean at `c813c2c`; no duplicate checkpoint commit was needed before this continuation.

## Implemented workflow

* **Databases ribbon tab:** exposes the attachment dialog and custom database folder without switching the active editor. The dialog attaches external `.eproj` files, discovers bundled/custom databases, shows active attachments and manages remembered paths. It stays open after each attach and immediately adds or reuses its row. Close is a separate action; there is no separate database page.
* **Schedule → Add item from database:** open a separate selector with an attached-database menu, paged/searchable hierarchy and multiple row/category selection. The project table and insertion target remain in place. Add performs the usual import; Modify & Add uses the consolidated application settings. Category selection includes off-page contents through the existing backend selection API. Imports retain code-collision handling, required resources/sub-analyses, atomic undo and source-file preservation.
* **Resources → Add resources from database:** the same selection workflow imports resource/rate definitions. Existing matching definitions follow the existing import policy; use the refresh action to update their prices.
* **Refresh selected rates from database:** choose a database, preview matching codes, then apply one undoable update. Schedule refresh copies the stored rate without replacing descriptions, quantities or analysis rows. Resource refresh copies rate/VAT/discount/reference and recalculates dependent analyses through the existing Python engine. Changed/current/unmatched counts are visible before applying. Reopening an analysis or recalculating project analysis rates can produce a different rate from an explicitly loaded stored schedule rate, just as with the existing Modify & Add stored-rate policy.
* **Library Modify & Add settings:** the rate multiplier, trailing-row count and replacement rows are together in one tab. General contains export options; the default analysis template has its own tab. Database attachment/folder management belongs to the Databases tab.

The old working-table data-source switch and attachment tools are removed from the Schedule/Resources ribbon. Ctrl+L opens the item selector. Dropdown popups throughout the application share the main menu's theme, focus/hover styling and grouped-item presentation, while native select values, labels and form events are preserved.

## Text entry and measurement display

Enter accepts a text value or submits its dialog. Shift+Enter or Ctrl+Enter inserts a line break in multiline fields. The table editors use their installed textarea editor's submit/newline support; other text dialogs use the same keyboard convention. Composition input is left to the input method.

Measurement templates are grouped as **General**, **Civil** and **E&M**. The original Python template renderer supplies accepted cell values and derived fields, including Breakup. Editors keep the original expression: `2*3` displays as `6` after acceptance and reopens as `2*3`. Numeric expression validation, calculations and custom render callbacks remain in Python; no frontend evaluation is added. Description cells remain text, as in GTK. Existing integer/length formatting conventions are retained.

NLBH keeps the original optional-factor behavior. Filling only No measures numbers; only L measures length; L/B measures area; L/B/H measures volume. No can multiply any of those. Blank factors do not force the result to zero. Explicit zero-factor handling is also retained from GTK, and an entirely empty record totals zero. Regression cases produce 5, 6, 6, 120 and 0 for representative count/length/area/volume/empty records. Breakup preserves the expression and the blank positions, e.g. `[,2*3,,]`.

## Suggested next step: named modification presets

The current count-based replacement remains compatible with existing settings. A more flexible successor would use **named presets containing ordered rules**, with a preview before import:

| Preset part | Example |
|---|---|
| Scope | Apply to selected source schedule items, with an explicit choice about referenced sub-analyses. |
| Match | Match calculation rows by kind, group code or description, rather than assuming that the last two rows always have the same meaning. |
| Action | Keep, remove, replace, append, or insert before/after a matched row. Numeric values use the existing Python expression evaluator. |
| Rate policy | Explicitly choose either “source stored rate × factor” or “recalculate the modified analysis”. Show both values in the preview. |
| Review | Show row changes, unmatched rules and before/after rates; apply the complete import as one undo step. |

For example, a preset could preserve all resource groups, remove only matching overhead/profit/rounding rows, append configured overhead/profit/rounding rows, and recalculate the result. A second preset could change only the stored schedule-rate multiplier and leave the analysis untouched. This avoids brittle trailing-row counts and makes the current distinction between stored rate and calculated analysis rate explicit.

This is a proposal, not a hidden change to calculation or import semantics. It can reuse the existing Python batch-preview and import transaction seams without introducing a second calculation engine or modifying the project schema.
