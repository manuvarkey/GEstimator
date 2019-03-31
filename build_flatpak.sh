#!/bin/sh

# Build into local repository
flatpak-builder --repo=repo build-dir org.kavil.gestimator.json --force-clean
# Build bundle
flatpak build-bundle repo gestimator.flatpak org.kavil.gestimator
