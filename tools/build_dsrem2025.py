"""Build the DSR (E&M) 2025 database from the prepared workbooks.

Runs the same backend operations as the desktop import screens, in order:
schedule (code hierarchy), resources, then analyses from all chapter sheets.
Resource lines are then reconciled with the book's line amounts
(tools/dsrem2025_reconcile.py, listed in spreadsheets/DSREM2025/corrections.csv).
Published schedule rates are restored afterwards, because the analysis import
recalculates rates and the book keeps unrounded intermediate amounts.

Usage: python tools/build_dsrem2025.py [output.eproj]
Run tools/prepare_dsrem2025.py first.
"""

import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

from modern.backend.service import Service  # noqa: E402
from tools.dsrem2025_reconcile import published_rates, reconcile  # noqa: E402

FOLDER = ROOT / "spreadsheets" / "DSREM2025"
OUTPUT = ROOT / "Other databases" / "DSREM2025.eproj"
MAPPING = dict(code=0, description=1, unit=2, rate=3, category=4)
SCHEDULE_MAPPING = dict(MAPPING, remarks=5)


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else OUTPUT
    if output.exists():
        raise SystemExit(f"{output} exists; remove it first")
    service = Service()
    call = lambda method, **params: service.call(method, dict(revision=service.revision, **params))
    report = {}
    try:
        call("project.new")
        call("project.settings.edit", settings=dict(
            project_name="DSR E&M 2025", project_item_code="DSREM25", project_resource_code="DE25"))
        schedule = dict(kind="schedule", path=str(FOLDER / "schedule.xlsx"), header_row=1, mapping=SCHEDULE_MAPPING, hierarchy=True)
        report["schedule"] = call("project.import_apply", duplicates="skip", **schedule)
        report["resources"] = call("project.import_apply", kind="resources", path=str(FOLDER / "resources.xlsx"),
                                   header_row=1, mapping=MAPPING, duplicates="skip")
        analyses = dict(path=str(FOLDER / "analysis.xlsx"), first_row=1, first_column=1)
        report["analysis_preview"] = call("project.import_analysis_preview", **analyses)
        report["analysis"] = call("project.import_analysis_apply", **analyses)
        report["reconciled"] = reconcile(call, service.db, FOLDER / "analysis.xlsx",
                                       published_rates(FOLDER / "schedule.xlsx"), FOLDER / "corrections.csv")
        # Keep the published rates; analyses stay attached to the items.
        report["published_rates"] = call("project.import_apply", duplicates="update", **schedule)
        call("project.save_copy", path=str(output))
    finally:
        service.close()
    for step, result in report.items():
        summary = {key: value for key, value in result.items() if key not in ("warnings", "analyses", "matched", "unmatched")}
        if "matched" in result:
            summary.update(matched=len(result["matched"]), unmatched=len(result["unmatched"]))
        print(step, summary)
        for warning in result.get("warnings", [])[:8]:
            print("   ", warning)
    print("saved", output)


if __name__ == "__main__":
    main()
