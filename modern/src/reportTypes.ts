/** Report inputs and authoritative snapshot values at the Python IPC boundary. */
export type ReportSectionKind =
  | "abstract"
  | "schedule"
  | "signoff"
  | "analyses"
  | "resources"
  | "resource_usage"
  | "measurements"
  | "narrative";
export interface ReportSection {
  id: string;
  kind: ReportSectionKind;
  title: string;
  enabled: boolean;
  body?: string;
}
export interface ReportSpecification {
  schema_version: 1;
  sections: ReportSection[];
  item_ids?: string[] | null;
  category_ids?: string[] | null;
  title: string;
  organization: string;
  reference: string;
  issue_date: string;
}
export interface ReportDocument {
  schema_version: 1;
  revision: number;
  project: string;
  specification: ReportSpecification;
  schedule: {
    id: string;
    category_id: string;
    category: string;
    parent_id: string | null;
    code: string;
    description: string;
    unit: string;
    quantity: string;
    rate: string;
    amount: string | null;
    remarks: string;
  }[];
  abstract: { category_id: string; category: string; amount: string }[];
  total: string;
  analyses: {
    code: string;
    description: string;
    unit: string;
    remarks: string;
    stored_rate: string;
    calculated_rate: string;
    rows: {
      kind: string;
      code: string;
      description: string;
      unit: string;
      quantity: string;
      rate: string;
      amount: string;
      remarks: string;
    }[];
  }[];
  resources: {
    code: string;
    description: string;
    unit: string;
    category: string;
    rate: string;
    tax: string;
    discount: string;
    reference: string;
  }[];
  measurements: {
    number: number;
    category: string;
    description: string;
    template: string;
    columns: string[];
    records: string[][];
    properties: [string, string][];
    outputs: { label: string; code: string; description: string; unit: string; quantity: string; remarks: string }[];
  }[];
  resource_usage: {
    code: string;
    description: string;
    unit: string;
    category: string;
    quantity: string;
    rate: string;
    amount: string;
  }[];
}
export interface ReportPreview {
  document: ReportDocument;
  html: string;
  pdf_available: boolean;
}
export type ReportFormat = "html" | "xlsx" | "pdf";
export interface ReportExportResult {
  saved: string;
  revision: number;
  warnings: string[];
}
