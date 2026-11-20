#!/bin/sh
# Build the GEstimator Flatpak bundle from the Tauri .deb.
# Build the .deb first: npm run --prefix modern bundle:backend
#   && npm run --prefix modern tauri -- build --bundles deb
set -eu
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../.." && pwd)
deb=$(ls "$root"/modern/src-tauri/target/release/bundle/deb/GEstimator_*_amd64.deb | tail -n 1)
cp "$deb" "$here/gestimator.deb"
cd "$here"
flatpak-builder --user --install-deps-from=flathub --force-clean \
  --repo=repo build-dir com.kavilgroup.gestimator.yml
flatpak build-bundle repo gestimator.flatpak com.kavilgroup.gestimator
echo "$here/gestimator.flatpak"
