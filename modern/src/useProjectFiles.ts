import { nextTick, ref, type Ref } from "vue";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { open, save } from "@tauri-apps/plugin-dialog";
import { request } from "./backend";
import { activeDocument, documentForPath, documents, pendingPaths, type DocumentAction } from "./documents";
import { restoreLibraries } from "./libraryPreferences";
import type { useDocumentTabs } from "./useDocumentTabs";
import type { useWorkspace } from "./useWorkspace";

interface ProjectFilesContext {
  workspace: ReturnType<typeof useWorkspace>;
  documentId: string;
  uiBusy: Readonly<Ref<boolean>>;
  discardOpen: Readonly<Ref<boolean>>;
  navigate: (action: (discard: boolean) => Promise<unknown>, project?: boolean) => Promise<void>;
  inNewDocument: ReturnType<typeof useDocumentTabs>["inNewDocument"];
  closeProjectTab: ReturnType<typeof useDocumentTabs>["closeProjectTab"];
  continueAfterSave: () => Promise<void>;
  showSchedule: () => void;
}

/** Project file dialogs, recovery and queued opens for one mounted workspace.
 * The shell owns pending draft actions and native listener cleanup; document
 * tabs own session switching. All replacement/close paths reuse their guard.
 */
export function useProjectFiles(context: ProjectFilesContext) {
  const { documentId, uiBusy, discardOpen, navigate, inNewDocument, closeProjectTab, continueAfterSave } = context;
  const w = context.workspace;
  const {
    state,
    error,
    projectSession,
    schedule,
    resources,
    scheduleQuery,
    resourceQuery,
    resourceSource,
    schedulePage,
    resourcePage,
    selected,
  } = w;
  let finishOsOpen: (() => void) | undefined;
  let switchingAway = false;

  const fileMode = ref<"open" | "save" | null>(null);
  const recoveryProjects = ref<{ id: string; updated: number }[]>([]);
  const recentProjects = ref<string[]>([]);
  try {
    const stored = JSON.parse(localStorage.getItem("gestimator.recent-projects") || "[]");
    if (Array.isArray(stored))
      recentProjects.value = stored.filter((path): path is string => typeof path === "string").slice(0, 10);
  } catch {
    // A missing or invalid preference can be rebuilt by opening a project.
  }
  function setRecentProjects(paths: string[]) {
    recentProjects.value = paths;
    try {
      localStorage.setItem("gestimator.recent-projects", JSON.stringify(recentProjects.value));
    } catch {
      // The in-memory list still works when storage is unavailable.
    }
  }
  function rememberProject(path: string) {
    setRecentProjects([path, ...recentProjects.value.filter((item) => item !== path)].slice(0, 10));
  }
  const filePath = ref("");

  async function openOsProject(path: string) {
    // Step 1: wait for the active input/guard before consuming the next OS request.
    while (uiBusy.value || discardOpen.value || fileMode.value !== null) {
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
    if (switchingAway) {
      pendingPaths.push(path);
      return;
    }
    const existing = documentForPath(path);
    if (existing?.id === documentId) return;
    if (existing || state.value?.project_open) {
      // Step 2: hand queued requests to the workspace mounted by document-tab routing.
      switchingAway = true;
      await inNewDocument({ type: "open", path });
      if (activeDocument.value === documentId) switchingAway = false;
      return;
    }
    // Step 3: keep the native queue waiting until Save, Discard or Cancel has settled.
    await new Promise<void>((resolve, reject) => {
      finishOsOpen = resolve;
      void navigate(async (discard) => {
        try {
          if (await w.openProject(path, discard)) rememberProject(state.value?.source_path || path);
        } finally {
          finishOsOpen = undefined;
          resolve();
        }
      }, true).catch((reason) => {
        finishOsOpen = undefined;
        reject(reason);
      });
    });
  }

  async function showFile(mode: "open" | "save") {
    // Step 1: offer recent files and recovery before opening the native picker.
    filePath.value =
      mode === "save" ? state.value?.source_path?.replace(/\.eproj$/i, "-edited.eproj") || "estimate.eproj" : "";
    if (mode === "open") {
      await refreshRecovery();
      if (recentProjects.value.length || recoveryProjects.value.length) {
        fileMode.value = mode;
        return;
      }
    }
    // Step 2: reuse the guarded open path or resume the pending action after saving.
    try {
      const filters = [{ name: "GEstimator project", extensions: ["eproj"] }];
      const path =
        mode === "open"
          ? await open({ multiple: false, filters })
          : await save({ filters, defaultPath: filePath.value });
      if (typeof path !== "string") return;
      if (mode === "open") await openProjectPath(path);
      else if (await w.saveCopy(path)) {
        rememberProject(path);
        await continueAfterSave();
      }
    } catch (reason) {
      error.value = String(reason);
    }
  }

  async function openProjectPath(path: string) {
    if (await inNewDocument({ type: "open", path })) return;
    await navigate(async (discard) => {
      if (await w.openProject(path, discard)) rememberProject(state.value?.source_path || path);
    }, true);
  }

  /** Landing page: go straight to the system picker; recent projects are already listed there. */
  async function browseProject() {
    try {
      const path = await open({ multiple: false, filters: [{ name: "GEstimator project", extensions: ["eproj"] }] });
      if (typeof path === "string") await openProjectPath(path);
    } catch (reason) {
      error.value = String(reason);
    }
  }

  async function refreshRecovery() {
    recoveryProjects.value = await request<typeof recoveryProjects.value>("recovery.list").catch(() => []);
  }

  async function recoverProject(id: string) {
    fileMode.value = null;
    if (await inNewDocument({ type: "recover", id })) return;
    await navigate((discard) => w.openProject(id, discard, true), true);
  }

  async function browse() {
    try {
      const filters = [{ name: "GEstimator project", extensions: ["eproj"] }];
      const path =
        fileMode.value === "open"
          ? await open({ multiple: false, filters })
          : await save({ filters, defaultPath: filePath.value || undefined });
      if (typeof path === "string") filePath.value = path;
    } catch (e) {
      error.value = String(e);
    }
  }

  async function submitFile() {
    const path = filePath.value.trim();
    if (!path) return;
    if (fileMode.value === "open") {
      fileMode.value = null;
      await openProjectPath(path);
    } else if (await w.saveCopy(path)) {
      rememberProject(path);
      fileMode.value = null;
      await continueAfterSave();
    }
  }

  async function saveProject() {
    if (!state.value?.source_path) {
      await showFile("save");
      return;
    }
    let directory: string | undefined;
    const dirty = state.value.workspace_dirty || state.value.dirty || state.value.measurement_draft?.dirty;
    if (state.value.source_requires_folder && dirty) {
      try {
        const selected = await open({
          title: "Choose the project folder to save and keep backups",
          directory: true,
          multiple: false,
        });
        if (typeof selected !== "string") return;
        directory = selected;
      } catch (reason) {
        error.value = String(reason);
        return;
      }
    }
    if (await w.saveProject(directory)) await continueAfterSave();
  }

  async function newProject() {
    // Step 1: route to a new document when the current tab already holds a project.
    if (await inNewDocument({ type: "new" })) return;
    await navigate(async (discard) => {
      await w.run(async () => {
        await request("project.new", { discard });
        await restoreLibraries();
        await w.refresh();
        // Step 2: invalidate old view state only after the replacement succeeds.
        projectSession.value++;
        schedule.value = [];
        resources.value = [];
        scheduleQuery.value = resourceQuery.value = resourceSource.value = "";
        schedulePage.value = resourcePage.value = 0;
        selected.value = [];
        context.showSchedule();
      });
    }, true);
  }

  /** Close the project (Save/Discard first). With other tabs open, the tab closes too. */
  async function closeProject() {
    if (!state.value?.project_open || uiBusy.value) return;
    if (documents.value.length > 1) {
      await closeProjectTab(documentId);
      return;
    }
    await navigate(async (discard) => {
      await w.run(async () => {
        await request("project.close", { discard });
        await w.refresh();
        projectSession.value++;
        schedule.value = [];
        resources.value = [];
        selected.value = [];
        context.showSchedule();
      }, "Closing project…");
    }, true);
  }

  /** Work handed over by the tab that created or activated this one. */
  async function runDocumentAction(action: DocumentAction) {
    await nextTick();
    if (action.type === "new") await newProject();
    else if (action.type === "open") await openProjectPath(action.path);
    else if (action.type === "recover") await recoverProject(action.id);
    else if (action.type === "close-tab") await closeProjectTab(documentId);
    else if (action.type === "close-window") await getCurrentWindow().close();
    while (pendingPaths.length && !switchingAway) await openOsProject(pendingPaths.shift()!);
  }

  /** Settle the native open queue when the shell's unsaved-work dialog is cancelled. */
  function cancelPendingOpen() {
    finishOsOpen?.();
    finishOsOpen = undefined;
  }

  return {
    fileMode,
    filePath,
    recoveryProjects,
    recentProjects,
    setRecentProjects,
    openOsProject,
    showFile,
    openProjectPath,
    browseProject,
    refreshRecovery,
    recoverProject,
    browse,
    submitFile,
    saveProject,
    newProject,
    closeProject,
    runDocumentAction,
    cancelPendingOpen,
  };
}
