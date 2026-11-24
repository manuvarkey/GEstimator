# Project development rules

These rules apply to the whole repository. Start with the
[documentation index](docs/README.md), then read the
[development workflow](docs/development-guidelines.md) and
[current architecture](docs/architecture/README.md) before structural changes.
The index routes database, backend, frontend, MCP, feature and testing work to
their current contracts. Migration notes are historical context, not API rules.
Changes under `modern/` also follow its [AGENTS.md](modern/AGENTS.md).

## Branches and pull requests

- Always work on a task branch and keep the task's commits on that branch.
- Open a pull request only on request. Describe the modifications in plain
  English and include the verification performed.
- Leave merging to the repository owner.

For release preparation, follow [the release guide](docs/releasing.md) for
version metadata, release notes, manual and website updates, Flathub source
pins and package verification. Record which checks were local and which
packages or stores were verified after publication.

## Responsibilities and modularity

- Python owns calculations, validation, imports, persistence and numbering.
  Vue collects input and renders authoritative results. Rust owns native
  integration and the sidecar transport. Keep domain decisions out of Vue/Rust.
- Desktop and MCP commands use the same service/editor operations. Keep revision
  checks, draft guards and write permissions at their existing boundaries.
- `ProjectEditor` owns project transactions and undo; `MeasurementDraft` owns
  record draft history. Domain handlers must not create competing histories,
  commit independently or bypass rollback. Previews must leave data, identities,
  revision, clipboard and history unchanged.
- Extract a new concern into a named helper, component or composable before
  extending `App.vue`, `ProjectViews.vue`, `project.py` or `service.py`. Do not
  split files into arbitrary numbered parts or introduce mixins that hide state.
  Small forwarding methods may preserve an existing service API.
- Treat 600 source lines per module and 80 per function as review triggers,
  not targets or automatic errors. Explain larger units in the change/audit;
  do not enlarge existing oversized units with unrelated responsibilities.
- Keep dependencies flowing from adapters to domain code. The shared engine
  must not import `modern`, Vue, Tauri or UI-only dependencies. Prefer top-level
  imports; document lazy imports needed for cycles or startup cost.
- Remove superseded code in the same change. Reuse existing table navigation,
  number formatting, input and styling helpers. Add explicit types at new IPC
  boundaries; keep `any` confined to documented third-party adapters.

## Data safety and behavior

- Use Decimal/Currency for financial calculations and modern numeric entry.
  Existing measurement templates intentionally retain Python integer/float
  arithmetic and rounding; do not convert them to Decimal as a style change.
- Never evaluate project, clipboard, worksheet or request text with `eval` or
  `exec`. Use the bounded numeric parsers. The template loader may compile
  trusted installed modules, selected by validated names inside its directory.
- Validate loaded project data as well as interactive requests. Restrict file
  selection to the intended directory and reject traversal/symlink escapes.
- Preserve atomic writes, rollback, recovery, stable row IDs and read-only
  library snapshots. Keep native child cleanup and response-ID checks intact.
- Do not render user text as HTML. Use text formatters or the shared escaped
  Markdown renderer, and do not add a second sanitization implementation.
- Keep queries and updates batched. Calculation/engine changes need parity
  checks against bundled data and explicit documentation of intentional changes.

## Code comments

This repository follows the more explanatory comment style of FreeCAD-HVAC.

- Use plain, simple English that a colleague can follow on a first reading.
  A comment is normally one or two lines.
- Add a module description and useful function/class docstrings (or Rust/TS
  documentation) for public contracts, ownership and side effects.
- Mark the logical steps of non-trivial, multi-step functions with short
  comments, such as `Step 1: validate the selection`. Explain constraints,
  invariants and workarounds as well as the process flow.
- Avoid narrating obvious assignments. When substantially editing a module,
  clarify dense or stale comments alongside the code. Preserve existing license
  and attribution headers; do not copy another project's license.

## Formatting

Format files changed by the task; do not reformat unrelated files. Use UTF-8,
spaces, LF newlines and a final newline, as set in `.editorconfig`.

### Python

Use the checked-in `pyproject.toml`, matching FreeCAD-HVAC:

```toml
line-length = 120

[format]
skip-magic-trailing-comma = true

[lint]
select = ["E302", "E303", "I"]

[lint.isort]
split-on-trailing-comma = false
```

Run Ruff's selected lint fixes and formatter on changed Python files, then check
both. Preview is enabled for E302/E303. Use four-space indentation and keep
imports grouped; do not compress compound statements onto one line. New or
substantially rewritten error handlers catch expected exceptions; broad catches
are reserved for rollback/cleanup or protocol boundaries and must re-raise or
report the error. Never add bare `except:` handlers.

### Rust

Use stable `rustfmt` with `modern/src-tauri/rustfmt.toml`: 120-column target,
four spaces, edition 2021. Use normal blocks rather than compressed statements.
Propagate recoverable errors with `Result`; avoid new `unwrap`/`expect` in request
handling. Run `cargo fmt`, tests and Clippy for native changes. Document ownership,
platform-specific workarounds and process/thread cleanup with short comments.

### TypeScript, Vue, HTML, CSS and JSON

Use the pinned Prettier and `modern/.prettierrc.json`: 120-column target, two
spaces, double quotes, semicolons and trailing commas where supported. Use the
Vue/HTML parser's whitespace rules; do not manually wrap meaningful inline text.
Keep template markup readable, semantic and accessible. Use logical CSS
properties and existing tokens; shared tokens belong in `theme.css`, shared
styles in `style.css`, and isolated component styles may be scoped. Avoid
appending duplicate selectors to override an earlier rule when that rule can
be edited directly. Keep cascade order intact during CSS refactors.

## Checks and audit follow-through

- Install `requirements-dev.txt` into `.venv` and run `npm ci --prefix modern`.
- Run `.venv/Scripts/python tools/check_quality.py --fix`, then the same command
  without `--fix`. On POSIX use `.venv/bin/python`. The script includes staged,
  unstaged and untracked source files; use `--base <ref>` for a whole branch.
  Formatting is incremental because untouched legacy files predate these rules.
- Run the full Python suite, frontend type/build check and browser suite for
  app changes, as specified in the development guidelines. Add focused tests
  for changed backend behavior; use existing regression coverage for mechanical
  extractions. Add browser coverage for new user-visible workflows.
- Native changes also require `cargo test --locked` and
  `cargo clippy --locked --all-targets -- -D warnings` in `modern/src-tauri`.
  Build the Python sidecar first if Tauri needs its external binary.
- Report failures and unavailable checks accurately. Do not suppress warnings,
  weaken checks or update expected results merely to make the suite pass.
- Record notable changes and actual validation in
  [validation.md](docs/migration/validation.md). Keep remaining structural debt
  and audit limits in [the repository audit](docs/code-quality-audit.md).

## Documentation maintenance

- Keep the relevant current contract in `docs/architecture/` or `docs/features/`
  synchronized with behavior and link it from [the index](docs/README.md).
  Link to canonical contracts instead of copying schemas, tool lists or commands.
- Keep future proposals in the roadmap and historical evidence in `docs/migration/`.
  Do not present old tool counts, branches, test totals or completed plans as
  current instructions. Preserve old entry points and referenced section anchors
  when moving a document.
- For documentation-only changes, run `tools/check_docs.py` and
  `git diff --check`; app tests are needed only when behavior/code changes.
  Use the [testing guide](docs/testing.md) for the complete verification matrix.

Do not change these rules without explicit user instruction. An uncovered case
is a reason to flag it, not to silently expand the rules.
