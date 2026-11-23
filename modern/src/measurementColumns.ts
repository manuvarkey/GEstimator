import type { CellComponent, ColumnDefinition } from "tabulator-tables";
import type { MeasurementDetail, MeasurementRecord } from "./projectViewTypes";

// Tabulator 6.3 accepts editor:false and HTMLElement tooltips, which its published
// types omit. Keep that compatibility cast here, alongside the table callbacks.
type RecordColumn = Omit<ColumnDefinition, "editor" | "headerTooltip"> & {
  editor?: ColumnDefinition["editor"] | false;
  headerTooltip?: ColumnDefinition["headerTooltip"] | (() => HTMLElement);
};

/** Present raw editable inputs separately from backend-calculated display values.
 * DOM text nodes keep template/author titles and tooltips out of HTML parsing.
 */
export function measurementRecordColumns(columns: MeasurementDetail["columns"]): ColumnDefinition[] {
  const definitions: RecordColumn[] = [
    { title: "Sl. No.", field: "_serial", width: 72, minWidth: 60, hozAlign: "right", editor: false },
    ...columns.map(
      (c): RecordColumn => ({
        title: c.title,
        titleFormatter: () => {
          const label = document.createElement("span");
          label.className = "measurement-column-title";
          label.textContent = c.title;
          return label;
        },
        field: c.field,
        minWidth: c.width || 80,
        width: c.expand ? undefined : c.width || 80,
        widthGrow: c.expand ? 1 : 0,
        hozAlign: c.numeric ? "right" : "left",
        cssClass: c.editable ? "" : "measurement-derived",
        headerTooltip: () => {
          const label = document.createElement("span");
          label.textContent = c.editable
            ? `${c.title}: editable measurement input; arithmetic expressions are retained`
            : `${c.title}: calculated by the measurement template; read-only`;
          return label;
        },
        editor: c.editable ? "textarea" : undefined,
        editable: !!c.editable,
        formatter: (cell: CellComponent) => {
          const row = cell.getData() as MeasurementRecord;
          const element = document.createElement("span");
          element.className = "measurement-cell-value";
          element.textContent = String(row._display?.[cell.getField()] ?? cell.getValue() ?? "");
          return element;
        },
        variableHeight: true,
      }),
    ),
  ];
  return definitions as ColumnDefinition[];
}
