"""Check formatting and correctness of changed source files without rewriting the legacy tree."""

import argparse
import os
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
        try:
            raw_ancestors = (
                subprocess.check_output(["git", "merge-base", base, "HEAD"], cwd=ROOT, stderr=subprocess.PIPE)
                .decode("utf-8")
                .strip()
            )
            if not raw_ancestors:
                raise ValueError(f"No common ancestor between '{base}' and HEAD")
            ancestor = raw_ancestors.splitlines()[0].strip()
        except (subprocess.CalledProcessError, ValueError) as exc:
            error_msg = (
                exc.stderr.decode("utf-8").strip() if isinstance(exc, subprocess.CalledProcessError) else str(exc)
            )
            raise SystemExit(f"Unable to find merge base for Git reference '{base}': {error_msg}") from exc
        names += git("diff", "--name-only", "--diff-filter=ACMR", "-z", ancestor, "HEAD")
    return sorted({ROOT / name for name in names if name and (ROOT / name).is_file()})


def run(command, cwd=ROOT):
    print("Running: " + " ".join(map(str, command)), flush=True)
    return subprocess.run(command, cwd=cwd).returncode


def report_advisory_summary():
    """Emit GitHub Actions warning annotations and step summary for advisory formatting."""
    print(
        "::warning::Formatting differences detected in changed files. "
        "Run 'python tools/check_quality.py --fix' locally to resolve.",
        flush=True,
    )
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        try:
            with open(summary_path, "a", encoding="utf-8") as summary:
                summary.write(
                    "### ⚠️ Advisory formatting differences detected\n\n"
                    "Formatting differences were found in changed files. "
                    "These checks are advisory and do not block CI, but changes should be formatted before merging.\n\n"
                    "**To fix locally:**\n"
                    "```bash\n"
                    "python tools/check_quality.py --fix\n"
                    "```\n"
                )
        except OSError:
            pass
    print("\nAdvisory: formatting differences detected in changed files.", flush=True)
    print("To fix locally, run:\n    python tools/check_quality.py --fix\n", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="Also check changes since the merge base with this Git ref")
    parser.add_argument("--fix", action="store_true", help="Apply import fixes and formatting")
    parser.add_argument(
        "--mode",
        choices=["all", "formatting", "correctness"],
        default="all",
        help="Check mode: 'all' (default), 'formatting', or 'correctness'",
    )
    parser.add_argument(
        "--advisory",
        action="store_true",
        help="Report formatting warnings without exiting nonzero (for CI advisory checks)",
    )
    args = parser.parse_args()

    if args.mode == "correctness":
        if args.fix:
            parser.error("--fix cannot be used with --mode correctness")
        if args.advisory:
            parser.error("--advisory cannot be used with --mode correctness")

    paths = changed_files(args.base)
    python = [str(path) for path in paths if path.suffix == ".py"]

    # Step 1: high-confidence Python correctness checks (blocking in 'correctness' and 'all' modes).
    if args.mode in ("all", "correctness"):
        if python:
            code = run([sys.executable, "-m", "ruff", "check", "--select", "E9,F63,F7,F82", "--no-fix", *python])
            if code != 0:
                sys.exit(code)
        if args.mode == "correctness":
            print("Changed-file correctness checks passed.")
            return

    # Step 2: formatting checks (Python, web, Rust).
    formatting_failed = False

    if python:
        if args.fix:
            run([sys.executable, "-m", "ruff", "check", "--fix", *python])
            run([sys.executable, "-m", "ruff", "format", *python])
        else:
            if run([sys.executable, "-m", "ruff", "check", *python]) != 0:
                formatting_failed = True
            if run([sys.executable, "-m", "ruff", "format", "--check", *python]) != 0:
                formatting_failed = True

    # Step 3: check web source using the pinned local tool and shared config.
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
        if run([node, str(prettier), "--write" if args.fix else "--check", *web], cwd=FRONTEND) != 0:
            formatting_failed = True

    # Step 4: Rustfmt checks the native crate together so child modules stay consistent.
    if any(path.suffix == ".rs" or path.name == "rustfmt.toml" for path in paths):
        cargo = shutil.which("cargo")
        if not cargo:
            raise SystemExit("Install Rust and cargo before checking Rust formatting")
        if (
            run(
                [
                    "cargo",
                    "fmt",
                    "--manifest-path",
                    str(FRONTEND / "src-tauri/Cargo.toml"),
                    *([] if args.fix else ["--", "--check"]),
                ]
            )
            != 0
        ):
            formatting_failed = True

    if formatting_failed:
        if args.advisory:
            report_advisory_summary()
            sys.exit(0)
        print("\nFormatting violations detected. Run with --fix to format automatically.", file=sys.stderr)
        sys.exit(1)

    print("Changed-file quality checks passed.")


if __name__ == "__main__":
    main()
