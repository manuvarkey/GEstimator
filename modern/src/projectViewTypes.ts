/** Shared project-view contracts. Numeric measurement inputs remain raw strings;
 * calculated display strings, totals and template metadata come from Python.
 */
export type View = "schedule" | "resources" | "measurement";
export type ProjectItemMode = "add" | "edit" | "duplicate";
export type ViewCommand = (operation: string, params?: Record<string, unknown>) => Promise<boolean>;

/** Project selection and revision captured when a database picker opens. */
export interface ProjectDatabaseSelection {
  kind: Exclude<View, "measurement">;
  mode: "add" | "rates";
  revision: number;
  targetIds: string[];
}

/** Existing main-table row adapter. Its dynamic columns remain audit debt;
 * measurement detail below has a separate, explicit backend response contract.
 */
export interface GridRow {
  id: string;
  [key: string]: any;
}

export interface MeasurementTemplate {
  code: string;
  name: string;
  label: string;
  group: string;
  summary: string;
  note: string;
  inputs: string[];
  outputs: number;
  properties: boolean;
}

export interface MeasurementRecord {
  id: string;
  _display?: Record<string, string>;
  [column: `c${number}`]: string | undefined;
}

export interface MeasurementDetail {
  id: string;
  description: string;
  template: string;
  info: MeasurementTemplate;
  offset: number;
  total_records: number;
  property_groups: {
    label: string;
    fields: { index: number; caption: string; numeric: boolean; label: string }[];
  }[];
  columns: {
    title: string;
    field: string;
    editable: boolean;
    width: number;
    expand: boolean;
    numeric: boolean;
  }[];
  rows: MeasurementRecord[];
  links: { code: string; description: string; unit: string | null; label: string; missing: boolean; remark: string }[];
  user_data: { caption: string; value: string; numeric: boolean }[];
  totals: string[];
}

export interface GridState {
  measurement_draft?: { id: string; dirty: boolean; undo: boolean; redo: boolean } | null;
  view_seq?: number;
  delta?: boolean;
  updates?: GridRow[];
  rows: GridRow[];
  total?: number;
  grand_total?: string;
  offset?: number;
  undo: boolean;
  redo: boolean;
  revision: number;
  caption?: string;
  detail?: MeasurementDetail | null;
  categories?: string[];
  enrichment?: { ai_generated: boolean; summary: string } | null;
}

export type TableView = { ids: string[]; position: { top: number; left: number } };
export type RecordViewMemory = { entryId: string; page: number; table: TableView };
export type ViewMemory = {
  query: string;
  categoryFilters: string[];
  page: number;
  table: TableView;
  records?: RecordViewMemory;
};
