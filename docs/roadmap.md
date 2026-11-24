# Roadmap and verification gates

Reviewed against repository evidence on 2026-11-23.
Navigation: [documentation index](README.md) · [architecture](architecture/README.md)
· [quality debt](code-quality-audit.md) · [validation history](migration/validation.md).

This page distinguishes unfinished work from implemented baselines. It is not
authorization to perform unrelated changes. Local source/build evidence does not
establish a published store version or successful installation on another machine.

## Remaining product and structural work

| Area | Next work | Acceptance evidence |
| --- | --- | --- |
| Formatted estimate reports | Follow the [report module proposal](report-module-plan.md); phase 1 is an isolated WeasyPrint/Jinja2 experiment | Real-project parity, customizable sections, Excel/HTML/PDF workflow and packaged renderer verification |
| Large shell/view/router modules | Follow the audit's bounded priorities for `App.vue`, `ProjectViews.vue`, `project.py` and `service.py` | Preserve drafts, identity, focus and undo. Follow the [Flatpak acceptance checks](code-quality-audit.md#flatpak-behavior-to-preserve) for affected file workflows. |
| Shared CSS | Continue consolidating feature-local overrides as surfaces change | Relevant dark/light/narrow UI verification |
| Frontend bundle size | Profile the installed WebView before splitting the core editors | A measured improvement with preserved startup and interaction behavior |
| Shared engine maintenance | Narrow remaining legacy error handling as each owning operation changes | Fixed calculation baselines, real-data/save/export comparisons and documented compatibility decisions |
| Search enhancements | Embeddings/bulk AI enrichment remain proposals pending measured benefit and review | Compare against existing search evaluation; preserve exact definitions and optional-metadata fallback |
| Future quantity inputs | IFC-derived quantities remain deferred | A separate accepted design that reuses measurement records rather than creating a second quantity model |

Detailed structural findings are maintained once in the
[quality audit](code-quality-audit.md#remaining-work-in-order).

## Release and distribution gates needing external verification

- Observe the relevant hosted quality/release workflow run and install each
  produced package on a clean target: Windows NSIS, Ubuntu `.deb`, AppImage,
  Flatpak and Snap. Exercise file association/opening, native dialogs/clipboard,
  MCP, save/recovery and shutdown. See [testing](testing.md).
- Consider Windows code signing and record the decision independently of a
  successful unsigned build.
- Verify Snap Store build/publishing configuration, credentials, channel promotion
  and architecture availability. Historical notes describe constraints around
  single-instance D-Bus registration and MIME integration; verify current store
  behavior before marking these resolved.
- Verify the external Flathub repository/manifest against the selected release
  tag and regenerated source lists, including aarch64 evidence. The local manifest
  and [packaging instructions](../packaging/flathub/README.md) are inputs, not proof
  that an external repository has merged/published them.
- Complete the [installed Flatpak desktop review](../packaging/flathub/README.md#linux-desktop-review)
  before Flathub resubmission.
- Keep offline package source lists synchronized with lock/runtime requirements;
  validate the resulting offline build after dependency changes. The current
  offline Node inputs include the locked Prettier tarball.
- Verify the published website/manual and downloadable older databases against
  the intended release. Follow the [release guide](releasing.md#publish-and-check-distribution)
  for the GitHub Pages publishing source and deployment checks.

These items deliberately remain verification gates: no live store, website or
hosted-run status was checked during documentation cleanup.

## Implemented baselines

- The Vue/Tauri application is the desktop implementation on `master`; the GTK
  interface is preserved on `archive/gtk`.
- Bundled databases are DSR 2023, DSR (E&M) 2025 and DSR 2025 Horticulture under
  [`estimator/database/`](../estimator/database). Older databases remain under
  [`Other databases/`](<../Other databases>).
- Database notes, category note sections and read-only notes previews are
  implemented. Notes accompany new database builds; older reference databases
  need not be rewritten just to add notes.
- Project tabs, draft acceptance, bulk analysis rules, the public 19-tool MCP
  surface and skill resources are implemented. Current contracts are in the
  [architecture](architecture/README.md), [analysis-rule reference](features/analysis-rules.md)
  and [manual](manual/README.md).
- Workspace navigation/history, MCP refresh and guarded project file workflows
  have separate composables. File dialogs, recent paths, recovery and queued
  opens reuse the shell's draft guard and existing document-tab routing.
  Library attachment/import handling has separate backend modules while project
  transactions, snapshot lifetime and undo remain with the editor. Further
  shell/router extraction is still tracked in the quality audit.
- Measurement record-page/detail loading and properties/link-picker state have
  separate composables. Typed measurement responses and a small column adapter
  preserve backend authority, the shared command boundary and document memory.
  Schedule and resource editing dialogs, item and category forms, and deletion
  confirmation have dedicated components. Project and analysis exports share
  the workbook chooser. Project workbook import dialogs have a dedicated
  coordinator. Project table rows and callbacks share explicit contracts.
- The manual and README use modern screenshots. The earlier GTK-screenshot and
  DSR 2023 build checklist items are completed repository work, not open tasks.
- Native desktop checks reported by the user on 2026-11-20 are historical
  evidence, not blanket verification of every later build or package.

For completed milestones and deliberate compatibility boundaries, use the
[migration archive](migration/README.md) and [parity ledger](migration/parity.md).
Update an item's status only with linked source/test/deployment evidence.
