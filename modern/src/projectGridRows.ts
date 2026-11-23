/** Build the project grid's display trees from the backend's row data. */
import type {
  GridRow,
  MeasurementGridCategory,
  MeasurementListRow,
  ProjectTableRow,
  RateDiscrepancies,
} from "./projectViewTypes";

export function groupMeasurementRows(rows: MeasurementListRow[]): MeasurementGridCategory[] {
  const categories: MeasurementGridCategory[] = [];
  let current: MeasurementGridCategory | undefined;
  for (const row of rows) {
    if (row.type === "Heading") {
      current = { ...row, rowtype: "Category", type: "", _children: [] };
      categories.push(current);
    } else {
      if (!current) {
        current = {
          id: "measurement:uncategorised",
          rowtype: "Category",
          type: "",
          description: "Uncategorised",
          _children: [],
        };
        categories.push(current);
      }
      current._children.push(row);
    }
  }
  return categories;
}

export function highlightScheduleRates(rows: ProjectTableRow[], discrepancies: RateDiscrepancies): ProjectTableRow[] {
  const marks = new Map(discrepancies.rows.map((row) => [row.id, row.colour]));
  function decorate(row: ProjectTableRow): ProjectTableRow {
    if (row.rowtype === "Resource") return { ...row };
    const children = row._children.map(decorate);
    if (row.rowtype === "Category") return { ...row, _children: children };
    const mark = marks.get(row.id);
    return { ...row, colour: mark === undefined ? row.colour : mark, _children: children };
  }
  return rows.map(decorate);
}

export function flattenGridRows(rows: GridRow[]): GridRow[] {
  return rows.flatMap((row) => [row, ...flattenGridRows(row._children ?? [])]);
}
