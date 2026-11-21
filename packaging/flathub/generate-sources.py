#!/usr/bin/env python3
"""Generate the offline Flatpak sources for building GEstimator from source.

Flathub builds without network access, so every dependency is listed with its
URL and checksum. Run this after changing modern/src-tauri/Cargo.lock,
modern/package-lock.json or requirements.txt:

    python3 packaging/flathub/generate-sources.py

It writes cargo-sources.json, node-sources.json and python-sources.json next
to this script.
"""

import base64
import json
import re
import tomllib
import urllib.request
from pathlib import Path

here = Path(__file__).resolve().parent
root = here.parents[1]


def write(name, sources):
    (here / name).write_text(json.dumps(sources, indent=4) + "\n")
    print(f"{name}: {len(sources)} sources")


def cargo_sources():
    """crates.io packages from Cargo.lock, vendored for `cargo --offline`."""
    lock = tomllib.loads((root / "modern/src-tauri/Cargo.lock").read_text())
    sources = []
    for package in lock["package"]:
        source = package.get("source", "")
        if not source:
            continue  # The application crate itself.
        if source != "registry+https://github.com/rust-lang/crates.io-index":
            raise SystemExit(f"Unsupported Cargo source for {package['name']}: {source}")
        name, version, checksum = package["name"], package["version"], package["checksum"]
        dest = f"cargo/vendor/{name}-{version}"
        sources.append({
            "type": "archive",
            "archive-type": "tar-gzip",
            "url": f"https://static.crates.io/crates/{name}/{name}-{version}.crate",
            "sha256": checksum,
            "dest": dest,
        })
        sources.append({
            "type": "inline",
            "contents": json.dumps({"package": checksum, "files": {}}),
            "dest": dest,
            "dest-filename": ".cargo-checksum.json",
        })
    sources.append({
        "type": "inline",
        "contents": '[source.vendored-sources]\ndirectory = "cargo/vendor"\n\n'
                    '[source.crates-io]\nreplace-with = "vendored-sources"\n',
        "dest": "cargo",
        "dest-filename": "config.toml",
    })
    return sources


def node_sources():
    """npm tarballs from package-lock.json, added to an npm cache for `npm ci --offline`."""
    lock = json.loads((root / "modern/package-lock.json").read_text())
    sources = []
    seen = set()
    for path, package in lock["packages"].items():
        if not path or package.get("link"):
            continue
        url, integrity = package["resolved"], package["integrity"]
        if url in seen:
            continue
        seen.add(url)
        algorithm, digest = integrity.split("-", 1)
        if algorithm not in ("sha512", "sha256", "sha1"):
            raise SystemExit(f"Unsupported integrity for {path}: {algorithm}")
        sources.append({
            "type": "file",
            "url": url,
            algorithm: base64.b64decode(digest).hex(),
            "dest": "npm-tarballs",
            "dest-filename": re.sub(r"[^A-Za-z0-9._-]", "_", url.rsplit("/-/", 1)[0].split("registry.npmjs.org/", 1)[-1]) + "-" + url.rsplit("/", 1)[-1],
        })
    return sources


def python_sources():
    """Pinned wheels (or source archives) from requirements.txt, from PyPI."""
    sources = []
    for line in (root / "requirements.txt").read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        name, version = (part.strip() for part in line.split("=="))
        with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/{version}/json") as response:
            files = json.load(response)["urls"]
        wheel = next((f for f in files if f["filename"].endswith("-py3-none-any.whl")
                      or f["filename"].endswith("-py2.py3-none-any.whl")), None)
        chosen = wheel or next(f for f in files if f["packagetype"] == "sdist")
        sources.append({
            "type": "file",
            "url": chosen["url"],
            "sha256": chosen["digests"]["sha256"],
            "dest": "python-packages",
        })
    return sources


if __name__ == "__main__":
    write("cargo-sources.json", cargo_sources())
    write("node-sources.json", node_sources())
    write("python-sources.json", python_sources())
