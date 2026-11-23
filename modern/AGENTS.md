# Modern workspace UI

Follow the repository-wide [development rules](../AGENTS.md), including comment,
formatting, modularity and validation requirements. Measurement handlers live in
`backend/measurements.py` and `backend/measurement_records.py`; project transactions
and undo remain in `ProjectEditor`.

Read and follow [the development guidelines](../docs/development-guidelines.md) for all changes and [the UI guidelines](../docs/ui-guidelines.md) for UI changes. Planned work is in [the roadmap](../docs/roadmap.md). Shared design tokens belong in `src/theme.css`, shared styles in `src/style.css`, and reusable behavior in shared components/helpers. Use the shared themed dropdown listbox for value selection, headerbars for draft Apply/Discard that return to the parent list, shared checkbox alignment, and the existing formatting and table navigation helpers.
