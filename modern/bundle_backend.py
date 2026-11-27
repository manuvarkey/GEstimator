"""Build a native standalone Python sidecar; run on each target OS/architecture."""

import shutil
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
modern = root / "modern"
triple = next(
    line.split(": ", 1)[1]
    for line in subprocess.check_output(["rustc", "-vV"], text=True).splitlines()
    if line.startswith("host:")
)
subprocess.run(
    [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--name",
        "gestimator-backend",
        "--paths",
        str(root),
        "--exclude-module",
        "gi",
        "--distpath",
        str(modern / ".bundle/dist"),
        "--workpath",
        str(modern / ".bundle/work"),
        "--specpath",
        str(modern / ".bundle"),
        *[
            argument
            for template in (root / "estimator/meas_templates").glob("*.py")
            for argument in ("--add-data", str(template) + ":estimator/meas_templates")
        ],
        *[
            argument
            for database in (root / "estimator/database").glob("*.eproj")
            for argument in ("--add-data", str(database) + ":estimator/database")
        ],
        "--add-data",
        str(root / "estimator/fonts") + ":estimator/fonts",
        # Search dictionaries and estimation skills (served as MCP resources).
        "--add-data",
        str(modern / "backend/data") + ":modern/backend/data",
        str(modern / "backend/entry.py"),
    ],
    cwd=root,
    check=True,
)
ext = ".exe" if sys.platform == "win32" else ""
target = modern / "src-tauri/binaries" / f"gestimator-backend-{triple}{ext}"
target.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(modern / ".bundle/dist" / f"gestimator-backend{ext}", target)
print(target)
