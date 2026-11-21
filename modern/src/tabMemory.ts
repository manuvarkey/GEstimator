import { activeDocument } from "./documents";

/** View state of inactive project tabs. Switching tabs remounts the workspace,
 * so components save their view state (tab, search, filters, selection,
 * scroll) here when their tab is switched away and read it back when the tab
 * is shown again. Entries are keyed by document and component. */
const memory = new Map<string, Map<string, unknown>>();

/** Saved state of `key` in the active document, if any. */
export function recallTabState<T>(key: string): T | undefined {
  return memory.get(activeDocument.value)?.get(key) as T | undefined;
}
/** Save state of `key` for `documentId` when that tab is switched away. A
 * component unmounted while its own tab stays active (a project opened in the
 * tab, the view reset) forgets its state instead. */
export function rememberTabState(documentId: string, key: string, value: unknown) {
  if (activeDocument.value === documentId) { memory.get(documentId)?.delete(key); return; }
  let entries = memory.get(documentId);
  if (!entries) memory.set(documentId, entries = new Map());
  entries.set(key, value);
}
/** Forget all saved state of a document: its project changed or it closed. */
export function forgetTabState(documentId: string) {
  memory.delete(documentId);
}
