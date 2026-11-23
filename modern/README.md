# GEstimator desktop development and builds

Start with [AGENTS.md](../AGENTS.md) and the [documentation index](../docs/README.md).
Current [architecture](../docs/architecture/README.md),
[development workflow](../docs/development-guidelines.md) and
[testing guide](../docs/testing.md) replace migration notes as development entry points.
The [user manual](../docs/manual/README.md) owns feature/interaction instructions.

## Prerequisites

The app uses Python 3.14, Node.js 22.12 or later with npm, stable Rust and the
[Tauri platform prerequisites](https://v2.tauri.app/start/prerequisites/).
Windows builds use the MSVC toolchain, Visual Studio C++ desktop build tools,
a Windows SDK and WebView2. Linux needs the Tauri WebKit/GTK development packages.
Runtime requirements and lock files, not prose version lists, own dependencies.

The GTK interface is preserved on `archive/gtk`; `estimator/` in this checkout
is the shared headless engine used by the modern backend.

## Windows development and builds

Run from the repository root in PowerShell:

```powershell
py -3.14 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt pyinstaller==6.22.3
npm.cmd ci --prefix modern
npm.cmd run --prefix modern bundle:backend
npm.cmd run --prefix modern tauri -- dev
```

Development uses `.venv/Scripts/python.exe`; PyInstaller builds the external
binary Tauri expects. Rebuild the sidecar after Python/data changes before
packaged validation. Production users do not need a separate Python installation.

After the [required verification](../docs/testing.md), build an x64 NSIS installer:

```powershell
npm.cmd run --prefix modern bundle:backend
npm.cmd run --prefix modern tauri -- build --bundles nsis -- --locked
```

Output is under `modern/src-tauri/target/release/bundle/nsis/`. Building is not
installation verification; use the release gates in the [roadmap](../docs/roadmap.md).

## POSIX development

From the repository root with platform prerequisites installed:

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt pyinstaller==6.22.3
npm ci --prefix modern
npm run --prefix modern bundle:backend
npm run --prefix modern tauri -- dev
```

`npm run dev` from `modern/` serves the frontend alone, without a mock backend.
Use Tauri for normal desktop development. Browser tests install their own bridge
to the real Python process; it is not shipped in the app.

## Linux packages

Build the sidecar on the target OS/architecture; PyInstaller does not cross-compile.
From `modern/`, `npm run tauri -- build --bundles deb,appimage` writes bundles
under `src-tauri/target/release/bundle/`. The release workflow uses Ubuntu 22.04
for `.deb`/AppImage compatibility and the core22 Snap base.

[Flathub packaging](../packaging/flathub/README.md) builds from source offline,
using the runtime's Python rather than a PyInstaller sidecar. Regenerate its
source lists when runtime dependency/lock files change. `snapcraft.yaml`
repackages the release `.deb`. The [Release workflow](../.github/workflows/release.yml)
defines actual runner/package behavior; clean-machine validation is separate.

## Backend protocol

Run `.venv/Scripts/python.exe -m modern.backend` on Windows or
`.venv/bin/python -m modern.backend` on POSIX. Requests are UTF-8 JSON Lines;
start with `{"id":"1","method":"state","params":{},"session":"main"}`.
See the [backend protocol](../docs/architecture/backend.md#desktop-json-lines-protocol)
for sessions, response/progress envelopes, revision guards and shutdown.

## Browser integration tests

Commands, focused runs, real-backend scope and native limits are maintained in
[testing.md](../docs/testing.md#browser-integration-suite). The
[Code quality workflow](../.github/workflows/quality.yml) checks PR/master
changes; tagged/manual [Release](../.github/workflows/release.yml) builds packages.
A hosted workflow result must be observed separately from local checks.

## Workspace

Read [frontend architecture](../docs/architecture/frontend.md) for document/view
lifetimes, navigation and refresh ownership, and [UI guidelines](../docs/ui-guidelines.md)
for interaction rules. Use the [manual](../docs/manual/README.md) to learn the UI.

## Schedule, resources and measurements

Read [backend architecture](../docs/architecture/backend.md),
[database format](../docs/architecture/database-format.md),
[analysis rules](../docs/features/analysis-rules.md) and the
[MCP public contract](../docs/architecture/mcp.md) before extending these workflows.
Do not treat historical tool counts or editor notes as current contracts.

## November 18 editor corrections

Historical correction/compatibility evidence is indexed under
[the migration archive](../docs/migration/README.md). Current contracts are
linked from the [documentation index](../docs/README.md).
