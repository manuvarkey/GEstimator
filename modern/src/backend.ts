import { debugAction } from "./uiActions";
import { invoke } from "@tauri-apps/api/core";
export type RowKind =
  | "Group"
  | "Resource"
  | "Subtotal"
  | "Weight"
  | "Multiply"
  | "Round"
  | "GroupTotal"; // display-only "TOTAL of <group>" line after a group's resources
export interface AnalysisRow {
  id: string;
  kind: RowKind;
  description: string;
  value: string;
  amount: string;
  code?: string;
  unit?: string;
  rate?: string;
  vat?: string;
  discount?: string;
  effective_rate?: string;
  remarks?: string;
  reference?: string;
  category?: string;
  _children?: AnalysisRow[];
  /** Display-only row (not part of the analysis; never selected or edited). */
  _displayOnly?: boolean;
}
export interface AnalysisState {
  measurement_draft?: { id: string; dirty: boolean; undo: boolean; redo: boolean } | null;
  code: string;
  description: string;
  unit: string;
  rows: AnalysisRow[];
  rate: string;
  revision: number;
  undo: boolean;
  redo: boolean;
  project: boolean;
  project_open: boolean;
  source_path: string | null;
  dirty: boolean;
  workspace_dirty: boolean;
  project_name: string;
  ana_remarks: string;
  libraries: { id: string; name: string }[];
}
export interface LibraryItem {
  code: string;
  description: string;
  unit: string;
  rate: string;
}
interface Response<T> {
  result?: T;
  error?: { code: string; message: string };
}
// Each open document tab is a backend session; requests go to the active tab.
let backendSession = "main";
export function setBackendSession(session: string) { backendSession = session; }
export function currentBackendSession() { return backendSession; }
export async function request<T>(
  method: string,
  params: Record<string, unknown> = {},
  session = backendSession,
): Promise<T> {
  const started = performance.now();
  debugAction("request.start", { method, fields: Object.keys(params) });
  let response: Response<T>;
  try {
    response = await invoke<Response<T>>("backend_request", {
      request: { id: crypto.randomUUID(), method, params, session },
    });
  } catch (error) {
    debugAction("request.failed", { method, ms: Math.round(performance.now() - started), code: "transport" });
    throw error;
  }
  debugAction(response.error ? "request.failed" : "request.done", { method, ms: Math.round(performance.now() - started), code: response.error?.code });
  if (response.error) throw new Error(response.error.message);
  return response.result as T;
}
