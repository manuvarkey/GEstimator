# Migration archive and validation evidence

Navigation: [current documentation index](../README.md) ·
[current architecture](../architecture/README.md) · [roadmap](../roadmap.md).

These records explain how the GTK-to-Vue/Tauri migration evolved. Old branches,
tool counts, pending work and test totals describe their date, not the current
checkout. Read current contracts before using historical implementation details.
The validation log remains append-only evidence for new changes as well.

## Current references that moved

- [MCP architecture and public contract](../architecture/mcp.md)
- [Project analysis rules](../features/analysis-rules.md)
- [Database format](../architecture/database-format.md)
- [Backend](../architecture/backend.md) and [frontend](../architecture/frontend.md)

The old MCP/rule paths retain forwarding pages and section anchors.

## Evidence and design records

| Record | How to use it |
| --- | --- |
| [Validation log](validation.md) | Dated changes, commands, results and limitations; later evidence can supersede earlier limitations |
| [Feature parity ledger](parity.md) | Migration comparisons, deliberate compatibility boundaries and tracked PARITY issues; not a current feature backlog |
| [November 18 source review](parity-review-2026-11-18.md) | Evidence behind that period's parity findings |
| [Original architecture](architecture.md) | Migration design and layer evolution; current architecture is maintained separately |
| [Handoff notes](handoff.md) | Chronological continuation notes, including old plans and resolved issues |
| [Editor review](editor-review.md) | Retained template behavior and editor corrections; verify current behavior against the backend contract/tests |
| [Database selection design](database-selection-workflow.md) | Implemented workflow at its date and subsequent rule/preset proposal; not blanket authorization to implement proposals |
| [MCP efficiency design](mcp-efficiency.md) | Rationale for consolidating tools and optional search/enrichment; original migration instructions are historical |
| [Search evaluation](mcp-search-report.json) | Recorded dataset results; rerun the evaluation when changing ranking |
| [Workbench refinement](workbench-refinement.md) | Earlier UI decisions; current interaction rules live in UI guidelines |
| [Workbench feedback](workbench-feedback.md) | Dated feedback and responses, not an independent current specification |

## Adding evidence

Append dated validation instead of rewriting old counts or claiming a previously
unverified platform now passes without observation. Put current contracts and
new implementation guidance outside this archive, link them from the
[index](../README.md), and link evidence back to the affected contract.

Use the [testing guide](../testing.md) for command scope and result reporting.
The [roadmap](../roadmap.md) owns unfinished work; a historical checkbox alone
does not establish current release/deployment state.
