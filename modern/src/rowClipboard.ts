import { invoke } from "@tauri-apps/api/core";
import { request } from "./backend";

export type ClipboardKind = "analysis" | "schedule" | "resources" | "measurement" | "records";
let fallback: { kind: ClipboardKind; data: string } | undefined;
const writeText = (text: string) => invoke<void>("write_clipboard_text", { text });
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
/** Read the same text for toolbar and keyboard paste, with a window-only fallback. */
export async function readClipboardText(kind: ClipboardKind) {
  try {
    return await invoke<string>("read_clipboard_text");
  } catch {
    if (fallback?.kind !== kind)
      throw new Error("Unable to read text from the system clipboard. Copy GEstimator rows and try again.");
    return fallback.data;
  }
}
export async function pasteRows(kind: ClipboardKind, params: Record<string, unknown>) {
  const { clipboardData, ...requestParams } = params;
  const data = typeof clipboardData === "string" ? clipboardData : await readClipboardText(kind);
  // A readable clipboard always wins. Never silently paste stale local rows over text.
  return request<{
    ok: boolean;
    moved?: boolean;
    unlinked?: number;
    selected?: string[];
    selected_records?: string[];
    record_offset?: number;
  }>("clipboard.paste", { ...requestParams, kind, data });
}
export function isRowClipboard(data: string) {
  try {
    return JSON.parse(data)?.format === "org.gestimator.rows";
  } catch {
    return false;
  }
}
/** A cut reference is used once (GTK clears it after the move). */
export async function clearRowClipboard() {
  fallback = undefined;
  try {
    await writeText("");
  } catch {
    /* Clipboard unavailable: nothing to clear. */
  }
}
