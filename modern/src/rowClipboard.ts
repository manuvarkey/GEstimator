import { readText, writeText } from "@tauri-apps/plugin-clipboard-manager";
import { request } from "./backend";

export type ClipboardKind = "analysis" | "schedule" | "resources" | "measurement" | "records";
let fallback: { kind: ClipboardKind; data: string } | undefined;
export async function copyRows(kind: ClipboardKind, params: Record<string, unknown>) {
  const data = await request<string>("clipboard.export", { ...params, kind });
  try {
    await writeText(data);
    fallback = undefined;
    return "Rows copied to the system clipboard.";
  } catch {
    fallback = { kind, data };
    return "System clipboard unavailable. Rows copied within this window only.";
  }
}
export async function pasteRows(kind: ClipboardKind, params: Record<string, unknown>) {
  const { clipboardData, ...requestParams } = params;
  let data: string;
  try { data = typeof clipboardData === "string" ? clipboardData : await readText(); }
  catch {
    if (fallback?.kind !== kind)
      throw new Error("Unable to read text from the system clipboard. Copy GEstimator rows and try again.");
    data = fallback.data;
  }
  // A readable clipboard always wins. Never silently paste stale local rows over text.
  return request<{ ok: boolean; unlinked?: number }>("clipboard.paste", { ...requestParams, kind, data });
}
export function isRowClipboard(data: string) {
  try { return JSON.parse(data)?.format === "org.gestimator.rows"; }
  catch { return false; }
}
