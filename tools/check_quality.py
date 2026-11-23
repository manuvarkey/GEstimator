"""Check formatting of changed source files without rewriting the legacy tree."""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "modern"
WEB_SUFFIXES = {".ts", ".js", ".mjs", ".vue", ".html", ".css", ".json"}


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=ROOT).decode("utf-8").split("\0")


def changed_files(base=None):
    """Include staged, unstaged and new files, plus branch changes when requested."""
    names = git("diff", "--name-only", "--diff-filter=ACMR", "-z", "HEAD")
    names += git("ls-files", "--others", "--exclude-standard", "-z")
    if base:
        ancestor = git("merge-base", base, "HEAD")[0].strip()
        names += git("diff", "--name-only", "--diff-filter=ACMR", "-z", ancestor, "HEAD")
    return sorted({ROOT / name for name in names if name and (ROOT / name).is_file()})


def run(command, cwd=ROOT):
    print("Running: " + " ".join(map(str, command)), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="Also check changes since the merge base with this Git ref")
    parser.add_argument("--fix", action="store_true", help="Apply import fixes and formatting")
    args = parser.parse_args()
    paths = changed_files(args.base)

    # Step 1: lint imports/spacing, then use the matching Python formatter.
    python = [str(path) for path in paths if path.suffix == ".py"]
    if python:
        run([sys.executable, "-m", "ruff", "check", *(["--fix"] if args.fix else []), *python])
        run([sys.executable, "-m", "ruff", "format", *([] if args.fix else ["--check"]), *python])

    # Step 2: check web source using the pinned local tool and shared config.
    web = [
        str(path)
        for path in paths
        if path.is_relative_to(FRONTEND) and path.suffix in WEB_SUFFIXES and path.name != "package-lock.json"
    ]
    if web:
        node = shutil.which("node")
        prettier = FRONTEND / "node_modules/prettier/bin/prettier.cjs"
        if not node or not prettier.is_file():
            raise SystemExit("Install Node and run npm ci --prefix modern before checking web formatting")
        run([node, str(prettier), "--write" if args.fix else "--check", *web], cwd=FRONTEND)

    # Rustfmt checks the small native crate together so child modules stay consistent.
    if any(path.suffix == ".rs" or path.name == "rustfmt.toml" for path in paths):
        run(
            [
                "cargo",
                "fmt",
                "--manifest-path",
                str(FRONTEND / "src-tauri/Cargo.toml"),
                *([] if args.fix else ["--", "--check"]),
            ]
        )
    print("Changed-file quality checks passed.")


if __name__ == "__main__":
    main()
