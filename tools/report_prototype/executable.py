"""Managed WeasyPrint CLI experiment, compatible with the Windows onedir build."""

import math
import subprocess
import tempfile
from pathlib import Path


def render_pdf(html: str, executable: Path, timeout: float = 60) -> tuple[bytes, str]:
    """Render in a fresh scratch directory and return PDF bytes and diagnostics.

    The caller selects a trusted executable, not a project-supplied command.
    Data-only URL fetching prevents HTTP/file reads. Custom templates remain
    trusted: this process boundary is not an OS sandbox or a memory limit.
    subprocess.run kills and reaps the renderer when its deadline expires.
    """
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Renderer timeout must be positive and finite")
    executable = Path(executable).resolve(strict=True)
    if not executable.is_file():
        raise ValueError("Select the WeasyPrint executable")
    source = html.encode("utf-8")
    if len(source) > 10_000_000:
        raise ValueError("Report HTML exceeds the prototype's 10 MB limit")
    # Step 1: keep partial output and diagnostics away from the chosen destination.
    with tempfile.TemporaryDirectory(prefix="gestimator-report-") as directory:
        output = Path(directory, "report.pdf")
        with Path(directory, "renderer.log").open("w+b") as diagnostics:
            try:
                result = subprocess.run(
                    [
                        str(executable),
                        "--encoding",
                        "utf-8",
                        "--allowed-protocols",
                        "data",
                        "--no-http-redirects",
                        "--fail-on-http-errors",
                        "-",
                        str(output),
                    ],
                    input=source,
                    stdout=subprocess.DEVNULL,
                    stderr=diagnostics,
                    cwd=directory,
                    timeout=timeout,
                    check=False,
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
                )
            except subprocess.TimeoutExpired as error:
                raise RuntimeError(f"Report renderer exceeded {timeout:g} seconds") from error
            diagnostics.seek(0)
            message = diagnostics.read(16_384).decode("utf-8", errors="replace").strip()
        if result.returncode:
            raise RuntimeError(f"Report renderer failed ({result.returncode}): {message}")
        # Step 2: reject missing, oversized or non-PDF output before publication.
        if not output.is_file() or output.stat().st_size > 50_000_000:
            raise RuntimeError("Renderer produced no PDF or exceeded the prototype's 50 MB output limit")
        pdf = output.read_bytes()
        if not pdf.startswith(b"%PDF-"):
            raise RuntimeError("Renderer did not produce a PDF")
        return pdf, message
