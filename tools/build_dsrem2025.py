"""Build the DSR (E&M) 2025 database from the prepared workbooks.

Runs the same backend operations as the desktop import screens, in order:
schedule (code hierarchy), resources, then analyses from all chapter sheets.
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

FOLDER = ROOT / "spreadsheets" / "DSREM2025"
OUTPUT = ROOT / "Other databases" / "DSREM2025.eproj"
MAPPING = dict(code=0, description=1, unit=2, rate=3, category=4)
SCHEDULE_MAPPING = dict(MAPPING, remarks=5)


LABOUR = {"1001", "1002", "1003", "1004", "1005", "1006", "1007", "1008", "1010", "1012", "1017", "1019", "1021", "1087"}


def back_calculate(service):
    """Set the rate of the main material of each item in BACKCALC_ITEMS so that its analysis gives the published
    rate (see dsrem2025_nomenclature); the changes are listed in backcalculated_materials.csv."""
    import csv
    from modern.backend import rates
    sys.path.insert(0, str(ROOT / "tools"))
    import dsrem2025_nomenclature as nomenclature
    db = service.db
    R, Sch, RI = db.ResourceTable, db.ScheduleTable, db.ResourceItemTable
    from openpyxl import load_workbook
    book = {}
    for row in load_workbook(FOLDER / "schedule.xlsx", read_only=True).active.iter_rows(min_row=2, values_only=True):
        if row[0]:
            book.setdefault(str(row[0]), row[3])
    rows = []
    for code in nomenclature.BACKCALC_ITEMS:
        item = Sch.get(Sch.code == code)
        published = float(book[code])
        lines = [(line.id_res, float(line.qty)) for line in RI.select().where(RI.id_sch == item.id)]
        candidates = [(qty * float(res.rate), res) for res, qty in lines if res.code not in LABOUR]
        if not candidates:
            continue
        res = max(candidates, key=lambda c: c[0])[1]
        old = float(res.rate)

        def rate_at(value):
            R.update(rate=value).where(R.id == res.id).execute()
            rates.recalculate_rates(db, [code])
            return float(Sch.get(Sch.code == code).rate)
        base, step = rate_at(old), rate_at(old + 100)
        slope = (step - base) / 100
        value = round(old + (published - base) / slope, 2)
        result = rate_at(value)
        rows.append([code, res.code, res.description.split("\n")[0][:60], old, value, published, result])
    path = ROOT / "spreadsheets" / "DSREM2025" / "backcalculated_materials.csv"
    with open(path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["item", "resource", "description", "book_rate", "adjusted_rate", "published_rate", "analysis_rate"])
        writer.writerows(rows)
    return dict(items=len(rows), file=path.name)


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
        report["backcalc"] = back_calculate(service)
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
