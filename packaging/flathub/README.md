# Flathub

Development guidance: [documentation index](../../docs/README.md) ·
[build setup](../../modern/README.md) · [verification](../../docs/testing.md).

Files for the Flathub repository [flathub/com.kavilgroup.gestimator](https://github.com/flathub/com.kavilgroup.gestimator). The manifest builds GEstimator from source without network access:

- `cargo-sources.json`, `node-sources.json` and `python-sources.json` list every Rust crate, npm package and Python package with its checksum. Regenerate them with `python3 packaging/flathub/generate-sources.py` after changing `modern/src-tauri/Cargo.lock`, `modern/package-lock.json` or `requirements.txt`.
- The frontend is built with Vite and the Tauri binary with `cargo build --offline`. The backend runs from source on the runtime's Python (`gestimator-backend` wrapper) instead of the PyInstaller executable used by the other packages.
- peewee is installed without its optional C extensions (`NO_SQLITE=1`); they do not build with the SDK's Cython and GEstimator does not use them.
- The Flatpak enables Tauri's XDG FileChooser backend. Keep the source desktop launcher's `Exec=gestimator %F` so Flatpak can add file forwarding when it exports the launcher. The [database format contract](../../docs/architecture/database-format.md#working-copies-save-and-recovery) covers folder grants for in-place saves.

Test the manifest with the working tree: `packaging/flathub/build-local.sh` (writes `local.json`, builds `gestimator.flatpak`). The Release workflow runs the same build.
Install the resulting bundle with
`flatpak install --user --bundle packaging/flathub/gestimator.flatpak`
before doing the desktop review.

## Linux desktop review

Test the installed Flatpak without a filesystem override. Open a project with
the chooser and by double-clicking it in the file manager. Save in place with a
writable file grant and check the app's backup. Repeat from a read-only grant,
select the folder when prompted, and check the sibling backup. Confirm
replacement of a disposable project with Save Copy. Copy and paste schedule
items and resources using both the ribbon and keyboard. Attach and remember an
external library, restart the app, and check that it is attached again. Export a
workbook to a new file and to an existing file after confirmation.

For a release:

1. Tag `vX.Y.Z` and push the tag.
2. In the manifest, set the git source `tag` and `commit` (`git rev-parse vX.Y.Z^{commit}`).
   The tag must include the portal save fix and the source desktop entry
   with `Exec=gestimator %F`.
3. In the Flathub repository, replace `com.kavilgroup.gestimator.json` and add `cargo-sources.json`, `node-sources.json`, `python-sources.json`; delete `python3-requirements.yaml` and `requirements.txt` (used by the GTK application).
4. Update the [Tauri migration pull request](https://github.com/flathub/com.kavilgroup.gestimator/pull/12)
   if it is still open, or open a new one. Explain that FileChooser grants project
   and library access and that network sharing lets host MCP clients reach the
   optional loopback listener. The updated Flathub build and permission review
   must pass before merging.

After 3.0.0, the Flathub external data checker opens update pull requests from `x-checker-data` when a new tag is pushed; regenerate the source lists in that pull request when the lock files changed.
