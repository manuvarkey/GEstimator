# Workspace UI design guidelines

These rules apply to the modern desktop workspace. Keep design decisions in shared components and tokens so every new editor follows the same UI.

## Ownership

- `modern/src/theme.css` owns semantic colours, typography, spacing-related tokens, focus treatment and theme variants. Use tokens instead of literal colours in components.
- `modern/src/style.css` owns shared control, dialog, headerbar, ribbon, table and summary classes. Change the shared rule before adding a local override.
- Reuse `RibbonToolbar`, `AppIcon`, `DataTable`, `PersistentDialog` and the standard dialog/button classes. Add a shared component when multiple callers need the same behavior; do not duplicate editor-specific copies.
- Interface and table fonts independently follow platform defaults unless explicitly overridden. Keep light and dark themes equally usable.

## Dropdowns and menus

Use themed dropdowns for every single-value choice. Declare values with HTML `select`, `option` and `optgroup`; the shared `ThemedDropdowns` component presents an anchored, field-width listbox using workspace theme tokens. Preserve pointer selection, option groups, disabled options, arrows, Home/End, type-to-select, Enter, Escape and Tab. Do not use popup command menus for value selection. Multiple selections and list boxes retain their native semantics. Use a labelled themed autocomplete when free text and suggestions are required, such as category entry. Fonts and regional formats are selection-only controls; use the shared themed dropdown, never an editable autocomplete for them. Retain saved unavailable font/locale values as labelled options without allowing arbitrary new text. Use `ThemedAutocomplete` for these editable suggestions; do not use browser-native datalists.

Reserve popup command menus for commands such as the application menu and table context actions. A command menu must not impersonate a dropdown field.

## Action placement and colour

Put draft acceptance actions in a visible headerbar belonging to the active editor, above its content. Use `.draft-headerbar`; show explicit Apply analysis / Discard analysis or Apply records / Discard records labels. Keep these actions out of ribbons. In Measurements, put the template type on the left of the first headerbar row and Discard then Apply on the right, matching Analysis. Put the editable description and its status on a separate row below; do not repeat the template in another row. Apply and Discard finish the editor and return to Schedule or the Measurements list after success. Analysis places a matching green Save analysis button between Discard and Apply. Save applies to the working project while keeping the editor open; its tooltip distinguishes this from saving the project file. Keep Discard/Apply as the finish-and-return actions. Do not add separate back-to-list buttons in these editors. Failed operations retain the editor and draft. Apply uses the shared green treatment (`button apply`, or the headerbar's `button primary`); Discard uses `button danger`. Keep textual labels and icons so meaning does not depend on colour.

Ribbons group editing, insertion, arrangement, import/export and view commands. Use short captions, shared icons, explanatory tooltips and the existing measured overflow. Disable unavailable actions and retain keyboard equivalents. Draft Apply accepts into the working project; Save writes the project to disk. Communicate that distinction consistently.

## Tables, totals and numbers

Reuse the table editor and navigation helpers. Display derived fields as read-only. Preserve raw numeric values and arithmetic for editing. Format money through `numberFormatting.ts`; never apply currency formatting to quantities, dimensions, factors or percentages. Currency code is a display symbol choice, never exchange-rate conversion.

Show an explicit highlighted total beneath the records grid, following analysis summary styling. Totals cover the complete dataset, including off-page records and rows hidden by filters. Multiple measurement outputs retain their labels and units; do not add unlike quantities together.

## Checkboxes and database toggles

Checkboxes and radio buttons use the shared 16 px dimensions, zero padding and aligned label grid in `style.css`. They must never inherit text-input height, padding or full-width rules. Align the control with the first line of wrapping label text; use semantic labels and retain keyboard focus. Do not add per-dialog checkbox positioning fixes.

List each database on its own row in resource renumbering, with a labelled Enable/Exclude switch. Enabled means its resources participate in renumbering. Keep project resources included and explain the default exclusions.

## Dialogs, accessibility and validation

Use dialogs for bounded tasks that require input or review. Use inline status and error messages for routine feedback. Every field needs a label, every icon-only action an accessible name, and every interactive control a visible focus state. Long lists and dialogs must scroll within the viewport. Preserve focus and cell selection after edits and navigation.

Before completing a UI change, build the frontend and exercise affected workflows in browser tests. Verify keyboard operation, disabled/busy states, narrow layouts and both themes when affected. Add regression tests for behavior, not mirrored CSS implementation. Document native WebView/platform checks that still need an installed build.

## Surfaces and icon accents

The visual reference is [Open Planner Studio](https://github.com/OpenAEC-Foundation/open-planner-studio), specifically its [OpenAEC 0.4 tokens](https://github.com/OpenAEC-Foundation/open-planner-studio/blob/main/src/styles/openaec-tokens.css) and [two-tone icon treatment](https://github.com/OpenAEC-Foundation/open-planner-studio/blob/main/src/components/icons/Icon.tsx). Map charcoal frame/panel/field/workspace layers and neutral light surfaces through `theme.css`; use warm amber for accents and selection. Preserve GEstimator's system typography and semantic green Apply/red Discard treatments.

All icons go through `AppIcon`. Use a neutral silhouette with a restrained accent detail, rather than colouring the whole icon orange. Keep semantic/destructive, disabled and filled-button icons monochrome for contrast. Reuse local semantic icon names and shapes; do not introduce unrelated icon sets or per-button colour overrides.

Planner's B2 assets are generated by [`scripts/style-icons.py`](https://github.com/OpenAEC-Foundation/open-planner-studio/blob/main/scripts/style-icons.py): it reads Blueprint's `design/icon-set-b2/manifest.json`, converts construction geometry to compact paths (or uses lossless SVG exports where required), and writes separate 16/24 px definitions in `icons.generated.ts`. Its lock file records the source commit, B2 revision and manifest hash. This is reference documentation; GEstimator's current SVG paths remain locally maintained, with similar accents rather than a copied B2 asset library.
