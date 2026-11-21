import { computed, ref } from "vue";
import { request, setBackendSession } from "./backend";
import { forgetTabState } from "./tabMemory";

/** One open project tab. Each tab owns a backend session (an independent
 * project, undo history, drafts and recovery copy). Only the active tab's
 * workspace is mounted; the others keep their state in the backend. */
export interface DocumentTab {
  id: string;
  title: string;
  path: string | null;
  open: boolean;
  dirty: boolean;
  view: "analysis" | "schedule" | "resources" | "measurement";
}
export type DocumentAction =
  | { type: "new" }
  | { type: "open"; path: string }
  | { type: "recover"; id: string }
  | { type: "close-tab" }
  | { type: "close-window" };

const blank = (id: string): DocumentTab => ({ id, title: "", path: null, open: false, dirty: false, view: "schedule" });
export const documents = ref<DocumentTab[]>([blank("main")]);
export const activeDocument = ref("main");
export const activeTab = computed(() => documents.value.find(tab => tab.id === activeDocument.value)!);
/** Startup-only work (recovery prompt) runs for the first workspace only. */
export const startup = { done: false };
/** Documents whose unsaved changes were confirmed for discard during window close. */
export const closeConfirmed = new Set<string>();
/** OS open requests still waiting for a tab. */
export const pendingPaths: string[] = [];
let pending: DocumentAction | undefined;
let switching = false;

export function takeDocumentAction() {
  const action = pending;
  pending = undefined;
  return action;
}
export function updateDocument(id: string, values: Partial<DocumentTab>) {
  const tab = documents.value.find(item => item.id === id);
  if (tab) Object.assign(tab, values);
}
export function documentForPath(path: string) {
  const normalized = path.replace(/\\/g, "/");
  return documents.value.find(tab => tab.path && tab.path.replace(/\\/g, "/") === normalized);
}
export async function switchDocument(id: string, action?: DocumentAction) {
  if (switching || (id === activeDocument.value && !action)) return;
  switching = true;
  try {
    await request("session.activate", { session: id }, id);
    pending = action;
    setBackendSession(id);
    activeDocument.value = id;
  } finally { switching = false; }
}
export async function createDocument(action?: DocumentAction) {
  const id = "doc-" + crypto.randomUUID().replace(/-/g, "").slice(0, 12);
  await request("session.open", { session: id }, id);
  documents.value.push(blank(id));
  await switchDocument(id, action);
  return id;
}
/** Close a tab after its unsaved work was saved or discarded. */
export async function closeDocument(id: string) {
  const index = documents.value.findIndex(tab => tab.id === id);
  if (index < 0) return;
  if (documents.value.length === 1) await createDocument();
  else if (id === activeDocument.value) {
    const next = documents.value[index + 1] ?? documents.value[index - 1]!;
    await switchDocument(next.id);
  }
  await request("session.close", { session: id }, id);
  documents.value = documents.value.filter(tab => tab.id !== id);
  closeConfirmed.delete(id);
  forgetTabState(id);
}
const palette = ["#d97706", "#2563eb", "#16a34a", "#7c3aed", "#db2777", "#0891b2", "#ca8a04", "#0d9488"];
export function documentColour(seed: string) {
  let hash = 0;
  for (let index = 0; index < seed.length; index++) hash = (hash * 31 + seed.charCodeAt(index)) >>> 0;
  return palette[hash % palette.length]!;
}
export function documentCode(title: string) {
  const words = title.replace(/\.eproj$/i, "").trim().split(/[\s\-_.]+/).filter(Boolean);
  if (!words.length) return "–";
  if (words.length === 1) return words[0]!.slice(0, 2).toUpperCase();
  return (words[0]![0]! + words[1]![0]!).toUpperCase();
}
