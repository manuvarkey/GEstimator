# Prepare and verify a release

Navigation to the [documentation index](README.md), [testing guide](testing.md)
and [validation log](migration/validation.md).

## Prepare the candidate

1. Start a task branch from the intended source. Compare it with the latest
   published version and with the default branch. Check the hosted quality
   results and record any commits that still need to reach the release branch.
2. Use the same `X.Y.Z` in [npm package metadata](../modern/package.json) and
   both root entries of [package-lock.json](../modern/package-lock.json), the
   application crate in [Cargo.toml](../modern/src-tauri/Cargo.toml) and
   [Cargo.lock](../modern/src-tauri/Cargo.lock), the
   [Tauri config](../modern/src-tauri/tauri.conf.json) and the version and
   input `.deb` filename in [snapcraft.yaml](../snapcraft.yaml). Add the
   [AppStream release entry](../packaging/linux/metainfo/com.kavilgroup.gestimator.metainfo.xml)
   and confirm its date before tagging. Use `vX.Y.Z` for the Git tag.
3. Write user-facing release notes under `docs/releases/`, link them from the
   README and manual, and update affected workflows in the manual. For new
   screenshots, use the [manual Playwright config](../modern/playwright.manual.config.ts)
   with the sample project.
4. Create a separate website task branch from `gh-pages`. Update its
   `index.html` and regenerate the HTML manual and images from the app
   checkout using `python3 tools/build_site.py /path/to/website-worktree`.
   Check links, anchors and images, and keep download URLs pointed at the
   published release or store.
5. Follow the [Flatpak packaging instructions](../packaging/flathub/README.md)
   to validate the local build and prepare the external manifest and source
   lists. Run the [app and packaging checks](testing.md), validate AppStream
   and desktop metadata, and record results and platform limits. Run the
   documentation checker before building Flatpak, or from a clean source
   checkout, so it skips the generated source tree.

## Publish and check distribution

1. After publication is authorized, tag the reviewed commit. The
   [Release workflow](../.github/workflows/release.yml) builds Windows NSIS,
   Linux `.deb` and AppImage, Snap and Flatpak. It attaches the artifacts to
   a draft GitHub release and publishes the tagged Snap to edge. A manual
   workflow run can build candidate packages before tagging.
2. Install and smoke-test the artifacts on the target platforms using the
   [testing guide](testing.md). Add the release notes to the draft and publish
   it after reviewing the version, assets and upgrade instructions.
3. Resolve the Flathub source commit from the published tag and submit the
   prepared update. Verify each architecture and the final permissions.
   Inspect the Snap edge build and verify the stable channel after promotion.
4. Merge the reviewed website changes into `gh-pages` and check the GitHub
   Pages source in repository settings. For branch-based publishing, the
   static site lives at the root of `gh-pages`. Once the deployment succeeds,
   open the published home page and manual and check the release and store
   links.
