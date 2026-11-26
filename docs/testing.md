# Verification and development checks

Current workflow, checked against repository scripts on 2026-11-23.
Navigation: [index](README.md) · [development workflow](development-guidelines.md)
· [build setup](../modern/README.md) · [validation history](migration/validation.md).

## Choose checks from the change

| Change | Focused evidence in addition to the app checks below |
| --- | --- |
| Documentation only | Local links/anchors, navigation reachability and `git diff --check`; check any executable examples against their source |
| Backend behavior | Success/failure regression, revision and rollback invariants; relevant draft/history tests |
| Calculations, numeric parser or templates | Fixed expected values, Decimal/rounding behavior, supported/unsafe inputs, real-data and save/reopen/export comparisons |
| Schema, persistence or saves | Old-version copy migration, original-file preservation, SQLite integrity/foreign keys, conflicts/backups/recovery and round trips |
| Imports or clipboard | Representative malformed/user data, bounded batches, warnings, preserved source data and one undo step |
| Frontend workflow | Real Python browser bridge; keyboard/pointer, busy/error states, focus/selection, tab restoration and stale-edit preservation |
| Styles or layout | Affected browser workflows plus visual inspection in both themes/narrow layouts; installed WebView when platform rendering is affected |
| MCP | Public schemas/envelopes and discovery budgets, read-only denial, previews/rollback, draft conflicts, active-session routing, HTTP lifecycle and affected resources/SQL/search |
| Rust/native integration | Rust formatting, tests and Clippy; installed native app for OS events, dialogs, clipboard, startup/exit and recovery |
| Packaging/dependencies | Rebuild sidecar and affected package/source lists; run outside checkout; clean-machine installation for a release |

Use existing regression coverage for mechanical extraction; add tests for changed
behavior and real invariants, not assertions that copy implementation details.
Local prose-only work does not need an app build; the existing CI job may still
run its standard app checks. Formatting is incremental:
untouched legacy files are not a passing whole-tree baseline.

## Standard app checks

Prepare the environment using the [developer README](../modern/README.md).
Run from the repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe tools/check_quality.py
.\.venv\Scripts\python.exe -m unittest discover -s tests
npm.cmd run --prefix modern build
```

For source formatting fixes, run `tools/check_quality.py --fix` and then check
again without `--fix`. Add `--base <ref>` to cover a branch's changes since its
merge base. The script includes staged, unstaged and untracked source files.
Ruff, Prettier and rustfmt configuration is owned by [AGENTS.md](../AGENTS.md)
and the checked-in configuration files; do not add a conflicting local preset.
The strict local quality checker returns nonzero when formatting differences exist,
allowing developers to catch and format changes before committing.

The production build includes `vue-tsc --noEmit`, so no separate duplicate type
check is needed when it succeeds. Do not silence build warnings without fixing
their cause; record material retained warnings with validation evidence.

On POSIX use `.venv/bin/python` and `npm`/`npx` in place of the Windows commands.

## Browser integration suite

From `modern/`, with the repository virtual environment prepared:

```powershell
npx.cmd playwright install chromium
npm.cmd run test:e2e
```

`playwright.config.ts` starts Vite automatically. A preinstalled browser can be
selected with `PLAYWRIGHT_CHROMIUM_EXECUTABLE`. To exercise a focused workflow,
pass `-- --grep 'part of the test title'` to `npm run test:e2e`. Do not anchor a
grep to an assumed bare title; Playwright may include file/project context.

Set `PLAYWRIGHT_PORT` to an unused local port to keep browser tests separate from
a running desktop development server. For example, on POSIX:
`PLAYWRIGHT_PORT=1421 npm run test:e2e`. The main runner and extra browser contexts
use that configured base URL. Run suites sequentially when sharing the default
`test-results` directory and confirm test-owned servers exit after verification.

The suite substitutes only the Tauri transport and native interaction surface;
commands use a real persistent Python subprocess and disposable project copies.
The shared [workspace harness](../modern/e2e/workspaceHarness.ts) starts that
bridge for both the [project file workflows](../modern/e2e/projectFiles.spec.ts)
and the [editor workflows](../modern/e2e/workspace.spec.ts).
It verifies integration behavior, not real OS dialogs, native clipboard access,
window-manager events or every platform WebView. Native evidence must identify
the platform/build and actual interaction performed.

Wait for observable command completion, such as the post-start Stop control,
before asserting an endpoint or saved result. Do not hide timing errors with
fixed sleeps or blanket retries. When a failure is corrected, rerun the affected
scenario and distinguish targeted reruns from a clean full-suite result.

## Native and packaged backend checks

Rebuild after Python changes before validating a packaged binary:

```powershell
npm.cmd run --prefix modern bundle:backend
cargo fmt --manifest-path modern/src-tauri/Cargo.toml -- --check
cargo test --locked --manifest-path modern/src-tauri/Cargo.toml
cargo clippy --locked --manifest-path modern/src-tauri/Cargo.toml --all-targets -- -D warnings
```

A frozen-backend smoke test should run outside the repository with isolated
temporary data. Check the changed commands, installed template/data discovery,
save/export where relevant and clean shutdown. A binary build alone does not
prove a new dynamically loaded module/data file ships correctly.

Follow [Flathub packaging](../packaging/flathub/README.md) when lock files or
runtime requirements change. Native installation/release gates are tracked in
the [roadmap](roadmap.md), separately from unit/browser test results.

## Documentation checks

Run `python tools/check_docs.py` with the repository virtual environment. It
checks local Markdown/HTML link targets and Markdown section anchors in the
maintained documentation set without fetching remote URLs. It also checks that
current architecture/feature pages are reachable from the documentation index.
Historical documents retain context banners and old entry points forward to the
current references. The checker is a link check, not proof that prose matches code.

## CI and recording evidence

[Code quality](../.github/workflows/quality.yml) runs four independent jobs on
pull requests and master pushes. On Ubuntu, the advisory `formatting` job reports
changed-file diagnostics for Ruff, Prettier and rustfmt. On Windows, `backend`
checks Python syntax and correctness, runs the Python suite and checks
documentation links. The `browser` job builds the frontend, runs Chromium
workflows and uploads reports and traces on failure. The `native` job bundles
the Python sidecar and runs Rust tests and Clippy. Resolve formatting
diagnostics locally with `tools/check_quality.py --fix` when practical.
[Release](../.github/workflows/release.yml) builds tagged or manually dispatched packages.
A locally passing command is not evidence of a successful hosted workflow or
clean-machine installation.

Record date, change, exact scope, commands/results, skips, warnings and remaining
platform limits in [validation.md](migration/validation.md). Avoid fixed test
counts in current architecture pages. A targeted rerun, an older baseline and a
full suite are different evidence; label them accurately.
