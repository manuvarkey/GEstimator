# GEstimator

[Website](https://manuvarkey.github.io/GEstimator) • 
[Forum](https://github.com/manuvarkey/GEstimator/discussions/) •
[Bug tracker](https://github.com/manuvarkey/GEstimator/issues) •
[Git repository](https://github.com/manuvarkey/GEstimator)

[![Release](https://img.shields.io/github/release/manuvarkey/GEstimator.svg)](https://github.com/manuvarkey/GEstimator/releases/latest)
![License](https://img.shields.io/github/license/manuvarkey/GEstimator)


<a href="https://github.com/manuvarkey/GEstimator/releases/latest"><img height="51" alt="Download for Windows" src="docs/badges/windows.svg"/> </a>
<a href="https://flathub.org/apps/com.kavilgroup.gestimator"><img height="51" alt="Download on Flathub" src="docs/badges/flathub.svg"/> </a>
<a href="https://snapcraft.io/gestimator"><img height="51" alt="Download on Snap Store" src="docs/badges/snap-store.svg"/> </a> 

GEstimator prepares cost and quantity estimates of civil and electrical works with detailed rate analysis. It comes bundled with **DSR 2023 (Civil)**, **DSR (E&M) 2025** and **DSR 2025 Horticulture**, and works with any number of your own databases.

![Schedule of an estimate](docs/manual/images/schedule.png)

## Features

- **Schedule** of estimate items, added from a database, entered directly or imported from a `.xlsx` workbook. Items keep their rate analysis, so every rate stays traceable.
- **Rate analysis** editor with resource groups, subtotals, weighted additions (CP&OH, GST, cess), multipliers and rounding. Changing a resource rate updates every dependent item. Bulk edit rules change many analyses at once with a preview.
- **Resources** (materials, labour, plant) shared by all analyses, with usage reports and rate refresh from a newer database.
- **Measurements** recorded against schedule items with templates (NLBH, steel reinforcement, electrical points, ducting), expressions in cells and automatic quantity update.
- **Databases** attached read-only, with notes on how each is organised and what its rates include.
- **Export** of the whole estimate to a `.xlsx` workbook: schedule of rates, schedule of resources, details of measurements, resource usage and analysis of rates.
- **Several projects in tabs**, undo/redo, light and dark themes, and recovery of unsaved work after a crash.
- **AI assistants** (optional): a local [MCP](https://modelcontextprotocol.io) server lets Claude or any MCP client read and prepare estimates in the open project, using bundled estimation guides or your own office skill library.

See [What's new in 3.1](docs/releases/3.1.0.md) for changes and upgrade instructions.

## User manual

The [user manual](docs/manual/README.md) walks through the whole workflow with screenshots, using a sample estimate priced from DSR 2023.

| | |
|---|---|
| ![Rate analysis](docs/manual/images/analysis.png) | ![Add items from a database](docs/manual/images/add-from-database.png) |
| ![Measurement records](docs/manual/images/measurement-records.png) | ![Dark theme](docs/manual/images/schedule-dark.png) |

## Databases

DSR 2023 (Civil), DSR (E&M) 2025 and DSR 2025 Horticulture are bundled. Older schedules and other databases (DSR 2016–2021, DSR (E&M) 2016–2022, market rate databases) can be downloaded from [Other databases](https://github.com/manuvarkey/GEstimator/tree/master/Other%20databases). Any GEstimator project (`.eproj`) can be attached as a database.

## Installation

Installers for Windows (`.exe`) and Linux (`.deb`, `.AppImage`, Flatpak and Snap) are published under [Releases](https://github.com/manuvarkey/GEstimator/releases/latest). Check the version on Flathub and the Snap Store before installing.

On Windows, uninstall any 2.x version of GEstimator (Settings → Apps) before installing 3.x. The new installer does not remove it.

Version 2.7, the last release of the earlier GTK application, remains available under [Releases](https://github.com/manuvarkey/GEstimator/releases/tag/v2.7); its source is on the [`archive/gtk`](https://github.com/manuvarkey/GEstimator/tree/archive/gtk) branch.

## Building from source

The application is a [Tauri](https://tauri.app) desktop program (`modern/`) with a Vue interface and a Python backend (`modern/backend`, using the calculation engine in `estimator/`). Start with the [documentation index](docs/README.md) for development, architecture and code-quality guidance. [modern/README.md](modern/README.md) owns prerequisites and platform build commands.

The [release workflow guide](docs/releasing.md) covers versioning, packaging, the website and store checks.

For contributions, follow [AGENTS.md](AGENTS.md), the
[documentation reading order](docs/README.md#reading-order-for-coding-agents),
[development workflow](docs/development-guidelines.md) and
[repository quality audit](docs/code-quality-audit.md). Current
[database, backend, frontend and MCP contracts](docs/architecture/README.md)
link to their source and regression tests. The
[Code quality workflow](.github/workflows/quality.yml) checks changed-file
formatting, documentation links, backend tests, frontend builds, browser workflows
and native Rust code.
