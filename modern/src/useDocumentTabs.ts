import { watch, type ComputedRef, type Ref } from "vue";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { request, type AnalysisState } from "./backend";
import { closeConfirmed, closeDocument, createDocument, documentForPath, documents, switchDocument, updateDocument, type DocumentAction } from "./documents";

/** Project-tab commands for one mounted workspace: keeps the tab card in sync
 * with the workspace state and routes new/open/close through the tab store.
 * The workspace supplies its unsaved-work guard (`navigate`). */
export function useDocumentTabs(context: {
  documentId: string;
  state: Ref<AnalysisState | undefined>;
  projectName: ComputedRef<string>;
  recordsDirty: ComputedRef<boolean>;
  uiBusy: ComputedRef<boolean>;
  error: Ref<string>;
  navigate: (action: (discard: boolean) => Promise<unknown>, project?: boolean) => Promise<void>;
}) {
  const { documentId, state, projectName, recordsDirty, uiBusy, error, navigate } = context;
  watch(() => [state.value?.project_open, projectName.value, state.value?.source_path, state.value?.dirty || recordsDirty.value || state.value?.workspace_dirty] as const,
    ([open, title, path, dirty]) => { if (state.value) updateDocument(documentId, { open: !!open, title, path: path || null, dirty: !!dirty }); });
  /** New and opened projects use a new tab when this tab already holds a project. */
  async function inNewDocument(action: DocumentAction) {
    if (action.type === "open") {
      const existing = documentForPath(action.path);
      if (existing) { if (existing.id !== documentId) await switchDocument(existing.id); return true; }
    }
    if (!state.value?.project_open) return false;
    try { await createDocument(action); }
    catch (reason) { error.value = String(reason); }
    return true;
  }
  async function switchProjectTab(id: string) {
    if (uiBusy.value || id === documentId) return;
    try { await switchDocument(id); } catch (reason) { error.value = String(reason); }
  }
  async function addProjectTab() {
    if (uiBusy.value) return;
    try { await createDocument(); } catch (reason) { error.value = String(reason); }
  }
  /** Close a tab; unsaved work in the tab is offered for Save/Discard first. */
  async function closeProjectTab(id: string) {
    if (uiBusy.value) return;
    const tab = documents.value.find(item => item.id === id);
    if (!tab) return;
    try {
      if (id !== documentId) {
        if (tab.dirty) await switchDocument(id, { type: "close-tab" });
        else await closeDocument(id);
        return;
      }
      await navigate(async discard => {
        if (discard) await request("recovery.discard");
        await closeDocument(id);
      }, true);
    } catch (reason) { error.value = String(reason); }
  }
  async function cycleProjectTab(delta: number) {
    const index = documents.value.findIndex(tab => tab.id === documentId);
    const next = documents.value[(index + delta + documents.value.length) % documents.value.length];
    if (next) await switchProjectTab(next.id);
  }
  /** Window close: every tab with unsaved work is offered for Save/Discard in turn. */
  async function continueWindowClose() {
    const other = documents.value.find(tab => tab.id !== documentId && tab.dirty && !closeConfirmed.has(tab.id));
    if (other) await switchDocument(other.id, { type: "close-window" });
    else await getCurrentWindow().destroy();
  }
  return { inNewDocument, switchProjectTab, addProjectTab, closeProjectTab, cycleProjectTab, continueWindowClose };
}
