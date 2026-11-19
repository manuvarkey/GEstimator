# Roadmap

Planned work that is designed but not yet done. Completed work is recorded in `docs/migration/validation.md`.

## Database notes (metadata)

The project settings now hold **Database notes** (`project_metadata`, Markdown), edited in Project settings with a preview and returned to MCP clients by `describe_source` (`metadata`) and `get_state` (an excerpt per attached source).

- [ ] Write notes for each bundled and reference database (DSR 2021, DSR E&M 2022, DSR E&M 2025 — include the book inconsistencies listed in `spreadsheets/DSREM2025/README.md`, DSR 2016, DSR E&M 2016, DSR BLDC 2019): issuing authority and edition, effective date, rate basis (taxes, cess, overheads and profit included or not), cartage and wastage conventions, code systems (ICD / material codes, item numbering), units, known corrections and errata, and links to the published volumes.
- [ ] Decide a short heading structure for notes (Scope, Rate basis, Codes, Conventions, Errata) so MCP clients can rely on it.
- [ ] Optionally show notes in the database picker and the Databases tab (read-only, rendered Markdown).

## Desktop verification

- [ ] Exercise project tabs, tab and window close prompts, OS file opening into tabs, resource cut/paste and the import screens in an installed `tauri dev` / release build on each supported platform.

## Databases

- [ ] Bring DSR E&M 2025 to full shape: apply the latest amendments/correction slips, resolve the book inconsistencies listed in `spreadsheets/DSREM2025/README.md` (duplicate codes, analyses without schedule items, resource rate/code mismatches, chapter 16 totals) and write its database notes.
- [ ] Then make DSR E&M 2025 the bundled E&M database: move `Other databases/DSREM2025.eproj` to `estimator/database/`, move `estimator/database/DSREM2022.eproj` to `Other databases/`, and update bundled-source references (MCP tests use `bundled:DSREM2022.eproj`, packaging, documentation).
