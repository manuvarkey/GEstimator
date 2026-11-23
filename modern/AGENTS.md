# Modern application development

Follow the repository-wide [rules](../AGENTS.md). Start with the
[documentation index](../docs/README.md) and [development workflow](../docs/development-guidelines.md).

- Backend/domain changes: read [backend architecture](../docs/architecture/backend.md)
  and [database format](../docs/architecture/database-format.md). Measurement
  handlers leave project transactions and undo in `ProjectEditor`.
- Vue/UI changes: read [frontend architecture](../docs/architecture/frontend.md)
  and [UI guidelines](../docs/ui-guidelines.md). Shared tokens belong in
  `src/theme.css`, shared styles in `src/style.css`, and reusable behavior in
  shared components/helpers. Reuse themed dropdowns, draft headerbars, checkbox
  alignment, formatting and table navigation helpers.
- MCP changes: read the [public contract](../docs/architecture/mcp.md), including
  permission/revision boundaries and schema budgets; reuse application operations.
- Native changes: read the [native shell overview](../docs/architecture/README.md#native-shell)
  and [build setup](README.md). Preserve process cleanup and guarded file opening.

Use the [testing guide](../docs/testing.md) for checks, the
[quality audit](../docs/code-quality-audit.md) for structural debt and the
[roadmap](../docs/roadmap.md) for unfinished work.
