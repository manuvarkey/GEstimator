#!/bin/sh
# Test the Flathub manifest with the working tree instead of the release tag.
# --manifest-only writes local.json without building (used by CI).
set -eu
here=$(cd "$(dirname "$0")" && pwd)
cd "$here"
python3 - <<'PY'
import json
manifest = json.load(open("com.kavilgroup.gestimator.json"))
module = manifest["modules"][-1]
module["sources"][0] = {
    "type": "dir",
    "path": "../..",
    "skip": [".git", ".venv", "pvenv", "modern/node_modules", "modern/dist",
             "modern/src-tauri/target", "modern/src-tauri/binaries", "modern/.bundle",
             "modern/test-results", "packaging/flathub/build-dir",
             "packaging/flathub/repo", "packaging/flathub/.flatpak-builder",
             "build-dir", "repo", ".flatpak-builder", "Other databases", "spreadsheets",
             "sources", "screenshots", "artifacts", "design documentation"],
}
json.dump(manifest, open("local.json", "w"), indent=4)
PY
[ "${1:-}" = "--manifest-only" ] && exit 0
flatpak-builder --user --install-deps-from=flathub --force-clean \
  --repo=repo build-dir local.json
flatpak build-bundle repo gestimator.flatpak com.kavilgroup.gestimator
echo "$here/gestimator.flatpak"
