import type { TableView } from "./dataTableTypes";

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

export const scheduleItemFields = [
  "code",
  "description",
  "unit",
  "rate",
  "qty",
  "remarks",
  "category",
  "parent",
] as const;
export const resourceItemFields = [
  "code",
  "description",
  "unit",
  "rate",
  "vat",
  "discount",
  "reference",
  "category",
] as const;
export type ProjectItemField = (typeof scheduleItemFields)[number] | (typeof resourceItemFields)[number];

interface ProjectRowBase extends Partial<Record<ProjectItemField, string>> {
  id: string;
  description: string;
  type?: string;
}

interface PricedRow extends ProjectRowBase {
  code: string;
  unit: string;
  rate: string;
  category: string;
  remarks: string;
}

export interface ScheduleRow extends PricedRow {
  rowtype: "Schedule";
  qty: string;
  amount: string;
  parent: string;
  colour: string | null;
  has_children: boolean;
  _children: ProjectTableRow[];
}

export interface ResourceRow extends PricedRow {
  rowtype: "Resource";
  vat: string;
  discount: string;
  reference: string;
  _children?: never;
}

interface ProjectTableCategory extends ProjectRowBase {
  rowtype: "Category";
  code: "";
  _children: ProjectTableRow[];
}

export type ProjectTableRow = ProjectTableCategory | ScheduleRow | ResourceRow;

/** Python sends the measurement list flat, with headings identified by type. */
export interface MeasurementListRow extends ProjectRowBase {
  rowtype?: never;
  type: string;
  totals: string;
  count: number;
  _children?: never;
}

/** The view projects measurement headings onto Tabulator's category tree. */
export interface MeasurementGridCategory extends ProjectRowBase {
  rowtype: "Category";
  type: "";
  totals?: string;
  count?: number;
  _children: MeasurementListRow[];
}

export type GridRow = ProjectTableRow | MeasurementListRow | MeasurementGridCategory;

export interface RateDiscrepancies {
  revision: number;
  counts: Record<"items" | "mismatch" | "small" | "medium" | "large" | "missing", number>;
  rows: { id: string; code: string; stored: string; calculated: string | null; colour: string | null }[];
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

interface GridHistory {
  undo: boolean;
  redo: boolean;
  revision: number;
}

interface ProjectTableStatus extends GridHistory {
  view_seq: number;
  grand_total?: string;
  enrichment: { ai_generated: boolean; summary: string } | null;
}

export interface ProjectTablePage extends ProjectTableStatus {
  delta?: never;
  rows: ProjectTableRow[];
  categories: string[];
  total: number;
  offset: number;
  found_id?: string | null;
}

/** Incremental updates carry values for existing rows and leave their children in place. */
export interface ProjectTableDelta extends ProjectTableStatus {
  delta: true;
  updates: (Omit<ScheduleRow, "_children"> | ResourceRow)[];
}

export interface MeasurementDetailState extends GridHistory {
  caption: string;
  detail: MeasurementDetail | null;
  measurement_draft: { id: string; dirty: boolean; undo: boolean; redo: boolean } | null;
}

export interface MeasurementListState extends MeasurementDetailState {
  rows: MeasurementListRow[];
}

/** Local state holds the current page and merges detail or delta status into it. */
export type GridState = GridHistory &
  Partial<Omit<ProjectTablePage, "rows" | "delta"> & MeasurementDetailState> & {
    rows: (ProjectTableRow | MeasurementListRow)[];
  };

export type RecordViewMemory = { entryId: string; page: number; table: TableView };
export type ViewMemory = {
  query: string;
  categoryFilters: string[];
  page: number;
  table: TableView;
  records?: RecordViewMemory;
};
