# Development workflow and maintainability

Current workflow. Navigation: [index](README.md) · [architecture](architecture/README.md)
· [UI rules](ui-guidelines.md) · [verification](testing.md).
Root [AGENTS.md](../AGENTS.md) owns mandatory code/comment/formatting rules.

## Before changing code

1. Use the [task map](README.md#find-guidance-by-task) and read the relevant
   current contract and source links. Check existing tests for retained behavior.
2. Identify the owner: domain calculation, service orchestration, transaction,
   view state, native integration or public MCP adaptation. Read neighboring
   helpers before creating another abstraction.
3. Check the [quality audit](code-quality-audit.md) and [roadmap](roadmap.md).
   Separate requested work from future proposals and historical migration notes.
4. State the behavior/invariant being changed and choose focused regression
   evidence from the [testing matrix](testing.md#choose-checks-from-the-change).

## Keep changes in their layer

- Python owns calculations, validation, imports, numbering and persistence. Vue
  renders authoritative results and collects input; Rust owns native integration
  and transport. The [architecture overview](architecture/README.md) maps owners.
- Desktop and MCP reuse `Service.call` / `ProjectEditor.call`; public MCP
  contracts are defined in [MCP architecture](architecture/mcp.md), not by exposing
  arbitrary internal methods.
- Preserve [draft/project transaction boundaries](architecture/backend.md#revisions-and-write-boundaries).
  Helpers do not commit or create parallel undo histories. Previews restore data
  and transient state; do not implement a preview by applying and manually undoing.
- Use top-level imports unless a documented cycle/startup constraint needs lazy
  loading. Keep the shared engine independent of `modern` and UI packages.

## Modularity review

Choose a named module for one concern and explicit inputs/outputs. Existing
owners are listed in the [backend](architecture/backend.md#ownership-and-module-map)
and [frontend](architecture/frontend.md#ownership-and-module-map) maps.

Before extending an oversized shell/router, extract the new concern into a
handler, composable or component. Small forwarding methods are acceptable when
preserving an existing API. Do not replace a large file with hidden state mixins,
numbered file fragments or layers that only forward every argument unchanged.

The root rules use 600-line modules and 80-line functions as review triggers.
For a larger unit, explain why its responsibilities belong together and how it
will be verified. Do not create many trivial helpers merely to pass a line count.
Delete superseded implementations and update the owning contract in the same change.

## Preserve data and compatibility

- Keep financial arithmetic Decimal/Currency and preserve numeric strings across
  IPC. Measurement templates retain integer/float semantics. The shared bounded
  [numeric evaluator](architecture/backend.md#numeric-evaluation) owns expression
  syntax; do not add a frontend parser or execute data as Python.
- [Project files](architecture/database-format.md) and attached libraries are
  isolated before editing/migration. Preserve stable identities, foreign keys,
  measurement links, source fingerprints, recovery and atomic undo.
- Reuse engine calculations and workbook output. For engine changes compare fixed
  baselines and real-data round trips; record any intentional behavior change.
- Load related rows in batches and write in batches rather than querying per row.
  Profile relevant bundled databases before/after a performance change and compare
  outputs, not just timings.
- Treat worksheets/clipboard as user data. Accept supported variations, return
  row-specific warnings where appropriate, and reject invalid batches atomically
  where a partial result would be wrong. Request limits belong to their actual
  schema/validator; do not copy one tool's limits into a global rule.

## Frontend and user-facing behavior

Follow [UI guidelines](ui-guidelines.md) for shared controls, tokens, accessibility,
keyboard behavior, draft actions, status/error presentation and both themes.
Keep new IPC shapes explicit; isolate third-party `any` in an adapter rather than
adding casts throughout a view. Preserve human inputs during stale/agent refresh.

User-facing text describes GEstimator behavior. Internal migration/GTK references
belong in code comments or historical developer records. Name actions by their
outcome and include counts when they help the user understand scope.

## Finish a change

1. Apply/check the configured formatting on changed source files. Keep unrelated
   files out of formatting-only churn. The [testing guide](testing.md) owns commands.
2. Run relevant focused checks and the required app/native suites for executable
   changes. Documentation-only work uses local link/anchor checks and diff checks.
3. Review error paths, previews, undo and cleanup as well as the happy path.
   Do not weaken checks, increase schema budgets or replace expected values just
   to make a test pass.
4. Update the owning current document and its cross-references. Keep one canonical
   description of each contract, using the [documentation ownership rules](README.md#authority-and-document-ownership).
5. Append actual commands/results, warnings, skips and remaining platform limits
   to the [validation log](migration/validation.md). Label targeted reruns and
   historical evidence accurately. Update roadmap/audit status only with evidence.
