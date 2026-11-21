# Roadmap

Planned work that is designed but not yet done. Completed work is recorded in `docs/migration/validation.md`.

## Database notes (metadata)

The project settings now hold **Database notes** (`project_metadata`, Markdown), edited in Project settings with a preview and returned to MCP clients by `describe_source` (`metadata`) and `get_state` (an excerpt per attached source).

Notes are written for AI agents choosing items for an estimate or analysis: basic metadata (issuer, edition, corrections, specifications, rate basis, codes, units) and, per category, what the items cover, how they are arranged and how to pick the right one. A level-2 heading `## Category: <name>` starts the notes of that category; `describe_source` returns the general part in its overview and each category's notes with `section=category:<name>`, and `get_state` and `search_items` point agents to them.

- [x] DSR E&M 2025 (`spreadsheets/DSREM2025/database_notes.md`, loaded by the build).
- [x] DSR 2023 (`spreadsheets/DSR2023/database_notes.md`).
- Older databases (DSR 2021, DSR E&M 2022, DSR 2016, DSR E&M 2016, DSR BLDC 2019) are kept for reference only and get no notes. New databases get notes when built.
- [x] Decide the heading structure for notes (general part, then `## Category:` sections).
- [x] Show notes in the database picker and the attach dialog (read-only, rendered Markdown, expanded on demand).

## Desktop verification

- [x] Exercise project tabs, tab and window close prompts, OS file opening into tabs, resource cut/paste and the import screens in an installed `tauri dev` / release build (confirmed by the user, 2026-11-20).

## Release 3.0.0

The desktop application replaces the GTK application on `master`; GTK is kept on the `archive/gtk` branch. Packages: Windows NSIS, Linux `.deb`/`.AppImage`, Flatpak (`packaging/flathub`, from source) and Snap (`snapcraft.yaml`), built by `.github/workflows/release.yml` on a `v*` tag.

- [x] Windows: the old 2.x installer (`%USERPROFILE%\GEstimator`, uninstall key `KavilGroup GEstimator`) is not removed by the 3.0.0 installer; users are told to uninstall 2.x first (README, website, release notes).
- [ ] Consider code signing for Windows (unsigned installers show a SmartScreen warning).
- [ ] Run the Release workflow once (manual dispatch) and install each package on a clean machine: Windows installer, `.deb` on Ubuntu 22.04, AppImage, Flatpak, Snap (file association, file dialogs, MCP server, recovery folder).
- [ ] Replace the GTK screenshots in `screenshots/` (README, metainfo) with screenshots of the new interface.
- [ ] Snap Store: disconnect the snapcraft.io GitHub build (it built `latest/edge` from master; the new `snapcraft.yaml` needs the release `.deb` and fails there), add the `SNAPCRAFT_STORE_CREDENTIALS` secret (added 2026-11-22), let the tagged Release workflow publish to `edge`, test, then promote to `stable`. Users on arm64 keep 2.7.0: only amd64 is built now.
- [ ] Flathub: update `flathub/com.kavilgroup.gestimator` from `packaging/flathub` (from-source manifest with the `v3.0.0` tag commit and the three source lists; remove the Python module files) and merge after the test build passes (x86_64 and aarch64; aarch64 not yet built locally).
- [ ] Decide whether `Other databases/` and the GitHub Pages site need updates for 3.0.0.

## Databases

- [ ] Build DSR 2023 (civil) as the bundled civil database, with notes (to be taken up by the user later).

- [x] Resolve the DSR E&M 2025 book inconsistencies (duplicate codes, analyses numbered differently, resource rate/code mismatches, chapter 16 layout, book arithmetic): every analysis now reproduces its published rate within ₹1; changes are listed in `spreadsheets/DSREM2025/corrections.csv`.
- [x] Apply DSR E&M 2025 Correction Slip No. 1 (27-11-2025) to schedule, Appendix II and analyses.
- [x] Take the DSR E&M 2025 schedule text, numbering and rates from the printed book (rates checked against the analyses).
- [x] Decide the DSR E&M 2025 items whose printed schedule rate disagrees with the printed analysis (the analysis rate is kept) and the printed Appendix I/II (the workbook's is kept).
- [x] Finish DSR E&M 2025: analyses under the wrong heading attached, orphan analyses removed, chapter 19 category, Appendix II sub-headings and section heading, 1020/1021, whole-rupee rates, two-level headings 30.7/30.11 (remaining gaps in `spreadsheets/DSREM2025/README.md`).
- [x] Make DSR E&M 2025 the bundled E&M database (`estimator/database/DSREM2025.eproj`); DSR E&M 2022 moved to `Other databases/`, where the tests that need its fixed figures read it.
- [x] Make DSR 2023 the bundled civil database (`estimator/database/DSR2023.eproj`); DSR 2021 moved to `Other databases/`.
