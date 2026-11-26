# GEstimator documentation

Start here for application development. Current contracts were checked against
the source on 2026-11-23. This index separates development rules, implemented
behavior, future work and historical evidence.

## Reading order for coding agents

1. Read [root AGENTS.md](../AGENTS.md), plus [modern/AGENTS.md](../modern/AGENTS.md)
   for changes under `modern/`. These define required development rules.
2. Read the [development workflow](development-guidelines.md) and
   [architecture overview](architecture/README.md).
3. Use the task map below to find the relevant contract, source and regression
   tests. Follow the source links in that contract before changing behavior.
4. Check [known quality debt](code-quality-audit.md) and the
   [roadmap](roadmap.md). Neither is authorization to implement unrelated work.
5. Run the [appropriate checks](testing.md), update the affected current
   contract, and record actual results in the [validation log](migration/validation.md).

## Find guidance by task

| Task | Read next |
| --- | --- |
| Understand layers, request flow or choose a module | [Architecture overview](architecture/README.md) |
| Change `.eproj` storage, schema, measurement serialization or saves | [Database format](architecture/database-format.md), [backend](architecture/backend.md) |
| Change commands, calculations, validation, imports, drafts or undo | [Backend architecture](architecture/backend.md) |
| Change components, navigation, tables, document tabs or refresh | [Frontend architecture](architecture/frontend.md), [UI guidelines](ui-guidelines.md) |
| Change native process lifecycle, file opening or packaging | [Native shell](architecture/README.md#native-shell), [build setup](../modern/README.md) |
| Change MCP tools, permissions, resources, SQL or synchronization | [MCP architecture and contract](architecture/mcp.md) |
| Package or install estimation skill libraries | [Library manifests and folders](architecture/mcp.md#library-folders-and-manifest), [user workflow](manual/README.md#add-an-office-skill-library) |
| Change bulk analysis rules or their presets | [Analysis rules](features/analysis-rules.md), [backend](architecture/backend.md) |
| Change expressions, numeric precision or measurement templates | [Numeric evaluation](architecture/backend.md#numeric-evaluation), [expression syntax](manual/README.md#numeric-expressions) |
| Prepare verification or investigate a failure | [Testing guide](testing.md), [validation evidence](migration/validation.md) |
| Assemble accepted project report data | [Read-only report documents](features/report-documents.md) |
| Plan formatted estimate reports or run the rendering experiment | [Report module proposal](report-module-plan.md) |
| Prepare a release or update the website and distribution packages | [Release guide](releasing.md), [3.1 release notes](releases/3.1.0.md) |
| Assess a large module or plan a refactor | [Development guidelines](development-guidelines.md), [quality audit](code-quality-audit.md) |
| Explain how a user completes a workflow | [User manual](manual/README.md) |
| Understand a past decision or compatibility difference | [Migration archive index](migration/README.md) |

## Authority and document ownership

| Kind | Purpose | Update when |
| --- | --- | --- |
| `AGENTS.md` files | Required rules and routing | The user authorizes a rule change |
| `architecture/` | Current boundaries, formats and implemented contracts | Behavior or ownership changes |
| Development, UI and testing guides | How to extend and verify the app | The development workflow changes |
| `features/` and `manual/` | Current feature and user workflows | The corresponding workflow changes |
| `roadmap.md` | Remaining work and unverified release gates | Scope or evidence changes its status |
| `code-quality-audit.md` | Dated findings, remaining structural debt and limits | A tracked finding is resolved or new evidence changes it |
| `migration/` | Historical designs, compatibility ledger and dated validation | New evidence is appended; old claims keep their historical context |

An implementation brief or unchecked roadmap item is not a current API contract.
Test counts and past platform observations belong in dated validation entries,
not in architecture pages as promises about the latest checkout. When code and
a current contract disagree, investigate the code and tests, report the mismatch,
and update the contract with the behavior change; do not silently invent a new rule.

Keep one canonical description of each contract. Link to it instead of copying
tool lists, numeric syntax, schema details or test commands into several pages.
Use repository-relative Markdown links so navigation works in local checkouts
and on GitHub.
When moving a referenced page, retain a forwarding page at its old path and
preserve referenced section anchors. Keep every current page reachable from this
index, and give it links back to the index and related contracts.
