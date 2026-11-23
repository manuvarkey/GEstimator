<script setup lang="ts">
import { computed, nextTick, onMounted, onBeforeUnmount, ref, shallowReactive, watch } from "vue";
import Dialog from "primevue/dialog";
import { afterDialogsClose, focusSearch } from "./uiActions";
import { invoke, isTauri } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import { getCurrentWindow } from "@tauri-apps/api/window";
import ApplicationMenu from "./components/ApplicationMenu.vue";
import ApplicationHelp from "./components/ApplicationHelp.vue";
import ThemedDropdowns from "./components/ThemedDropdowns.vue";
import LibraryManager from "./components/LibraryManager.vue";
import AnalysisDialogs from "./components/AnalysisDialogs.vue";
import AnalysisInspector from "./components/AnalysisInspector.vue";
import ProjectDatabasePickers from "./components/ProjectDatabasePickers.vue";
import ProgramSettings from "./components/ProgramSettings.vue";
import ProjectSettings from "./components/ProjectSettings.vue";
import MCPSettings from "./components/MCPSettings.vue";
import {
  mcpStatus,
  mcpBusy,
  mcpError,
  mcpMessage,
  initializeMCP,
  refreshMCP,
  startMCP,
  stopMCP,
  copyMCPConfig,
} from "./mcp";
import { savedLibraries } from "./libraryPreferences";
import { programSettings, programSettingsWarning } from "./programSettings";
import { activeTheme as theme, setPlatformFont, toggleTheme } from "./appearance";
import RibbonToolbar from "./components/RibbonToolbar.vue";
import AppIcon from "./components/AppIcon.vue";
import ProjectLanding from "./components/ProjectLanding.vue";
import ProjectFileDialog from "./components/ProjectFileDialog.vue";
import DocumentRail from "./components/DocumentRail.vue";
import {
  activeDocument,
  activeTab as currentDocument,
  closeConfirmed,
  documents,
  pendingPaths,
  startup,
  takeDocumentAction,
} from "./documents";
import { useDocumentTabs } from "./useDocumentTabs";
import { useProjectFiles } from "./useProjectFiles";
import { useWorkspaceNavigation, type ProjectView } from "./useWorkspaceNavigation";
import { useWorkspaceMCP } from "./useWorkspaceMCP";
import { notify, statusNotice } from "./statusNotice";
import ProjectViews from "./components/ProjectViews.vue";
import AnalysisTable from "./components/AnalysisTable.vue";
import { useWorkspace } from "./useWorkspace";
import { installProjectOpening } from "./projectOpening";
import { request, type AnalysisRow, type RowKind } from "./backend";
import { formatMoney } from "./numberFormatting";
const w = useWorkspace();
const analysisTable = ref<InstanceType<typeof AnalysisTable>>();
const analysisDialogs = ref<InstanceType<typeof AnalysisDialogs>>();
const projectDatabasePickers = ref<InstanceType<typeof ProjectDatabasePickers>>();
const ribbonToolbar = ref<InstanceType<typeof RibbonToolbar>>();
const emptyAnalysisRows: AnalysisRow[] = [];
const {
  state,
  busy,
  error,
  status,
  connected,
  selected,
  schedule,
  resources,
  scheduleQuery,
  resourceQuery,
  resourceSource,
  schedulePage,
  resourcePage,
  projectName,
  resourceCount,
  groups,
  selection,
  projectSession,
} = w;
const libraryManagerOpen = ref(false);
const programSettingsOpen = ref(false);
function showAnalysisRules(ids: string[] = []) {
  const code = activeView.value === "analysis" && state.value?.project ? state.value.code : "";
  analysisDialogs.value?.showRules(ids, code);
}
async function applyAnalysisRules(params: Record<string, unknown>) {
  const ok = await w.run(async () => {
    await request("schedule.editor.analysis_rules.apply", params);
    await w.refresh();
    await projectView.value?.reload();
  }, "Updating project analyses…");
  if (ok) {
    activeView.value = "schedule";
    activeTab.value = "schedule";
  }
  return ok;
}
const unavailableLibraries = computed(() => savedLibraries.value.filter((library) => library.error));
async function librariesChanged() {
  await w.run(async () => {
    await w.refresh();
    await projectView.value?.reload();
  }, "Refreshing libraries…");
}
const projectBusy = ref(false);
const discardOpen = ref(false);
const uiBusy = computed(() => busy.value || projectBusy.value);
const documentId = activeDocument.value;
const projectViews = shallowReactive<Partial<Record<ProjectView, InstanceType<typeof ProjectViews>>>>({});
const projectView = computed(() => (activeView.value === "analysis" ? undefined : projectViews[activeView.value]));

const libraryManager = ref<InstanceType<typeof LibraryManager>>();
const mcpSettingsOpen = ref(false);
const projectHistory = ref({ undo: false, redo: false });
const allViews = [
  { key: "schedule", label: "Schedule" },
  { key: "analysis", label: "Analysis" },
  { key: "resources", label: "Resources" },
  { key: "measurement", label: "Measurements" },
  { key: "databases", label: "Databases" },
  { key: "mcp", label: "MCP" },
] as const;
// The MCP tab appears only after the user enables the server in Program Settings.
const views = computed(() => allViews.filter((view) => view.key !== "mcp" || !!programSettings.value?.mcp_enabled));
const settingsOpen = ref(false);
// Navigation keeps document-local view state; this shell remains the draft-guard owner.
const {
  activeView,
  activeTab,
  measurementEntry,
  inspector,
  visitedViews,
  navigation,
  navigationIndex,
  travelNavigation,
  returnToSchedule,
  switchView,
  loadAnalysis,
  changeMeasurementEntry,
} = useWorkspaceNavigation({
  documentId,
  initialView: currentDocument.value.view,
  state,
  projectSession,
  uiBusy,
  mcpEnabled: () => !!programSettings.value?.mcp_enabled,
  guard: (action) => navigate(action),
  load: w.load,
  focusSchedule: async (code) => {
    if (code) await projectView.value?.revealCode(code);
    await projectView.value?.focus();
  },
});
// Project views show the landing page (and no ribbon tools) until a project is open.
const landingVisible = computed(() => connected.value && !state.value?.project_open && activeView.value !== "analysis");
const recordsDirty = computed(() => !!state.value?.measurement_draft?.dirty);
let cancelAnalysisFocus: (() => void) | undefined;
watch(
  activeView,
  async (view) => {
    cancelAnalysisFocus?.();
    if (view === "analysis") {
      await nextTick();
      cancelAnalysisFocus = afterDialogsClose(async () => {
        if (activeView.value === "analysis") await analysisTable.value?.focus();
      });
    }
  },
  { flush: "post" },
);
onBeforeUnmount(() => cancelAnalysisFocus?.());
function bindProjectView(view: ProjectView, instance: unknown) {
  projectViews[view] = instance as InstanceType<typeof ProjectViews> | undefined;
}
const mcpRefresh = useWorkspaceMCP({
  workspace: w,
  uiBusy,
  activeTab,
  reloadProjectView: async () => projectView.value?.reload(),
});
const { inNewDocument, switchProjectTab, addProjectTab, closeProjectTab, cycleProjectTab, continueWindowClose } =
  useDocumentTabs({
    documentId,
    state,
    projectName,
    recordsDirty,
    uiBusy,
    error,
    navigate: (action, project) => navigate(action, project),
  });

// File workflows reuse the shell's guard and document-tab/session routing.
const {
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
} = useProjectFiles({
  workspace: w,
  documentId,
  uiBusy,
  discardOpen,
  navigate,
  inNewDocument,
  closeProjectTab,
  continueAfterSave,
  showSchedule: () => {
    activeView.value = "schedule";
    activeTab.value = "schedule";
  },
});

let pendingProject = false;
const explorer = ref("schedule");
const sidebar = ref(true);
const helpOpen = ref(false);
const manualOpen = ref(false);
const aboutOpen = ref(false);
const shortcutGroups = [
  {
    title: "Project and search",
    items: [
      ["Open project", "Ctrl / ⌘ + O"],
      ["Save project", "Ctrl / ⌘ + S"],
      ["Save project copy", "Ctrl / ⌘ + Shift + S"],
      ["Focus search in current view or selection dialog", "Ctrl / ⌘ + F"],
      ["New project tab / Close project tab", "Ctrl / ⌘ + T / W"],
      ["Next / previous project tab", "Ctrl / ⌘ + Tab / Shift + Tab"],
    ],
  },
  {
    title: "Rows and clipboard",
    items: [
      ["Undo / Redo", "Ctrl / ⌘ + Z / Y"],
      ["Copy / Paste rows", "Ctrl / ⌘ + C / V"],
      ["Cut resources (Paste moves them)", "Ctrl / ⌘ + X"],
      ["Repair stored item order", "Ctrl / ⌘ + Shift + R"],
      ["Add item / measurement record / analysis resource", "Ctrl / ⌘ + I"],
      ["Add schedule subitem / custom analysis resource", "Ctrl / ⌘ + Shift + I"],
      ["Duplicate selected rows", "Ctrl / ⌘ + D"],
      ["Delete selected rows", "Delete"],
      ["Move project item or measurement record", "Alt + Up / Down"],
    ],
  },
  {
    title: "Cell editing and selection",
    items: [
      ["Edit focused cell", "Enter / F2"],
      ["Cancel cell edit and retain focus", "Escape"],
      ["Accept and edit next / previous cell", "Tab / Shift + Tab"],
      ["Move caret / select text while editing", "Arrow keys / Shift + arrows"],
      ["Navigate cells outside editing", "Arrow keys"],
      ["New line while editing text", "Shift / Ctrl + Enter"],
      ["Navigate editable cells", "Tab / Shift + Tab"],
      ["Select table rows", "Up / Down / Home / End"],
      ["Extend table selection", "Shift + Up / Down / Home / End"],
      ["Select current table page / Clear selection", "Ctrl / ⌘ + A / Escape"],
    ],
  },
  {
    title: "Editor actions",
    items: [
      ["Open selected schedule analysis", "Ctrl / ⌘ + E"],
      ["Colour selected schedule items", "Ctrl / ⌘ + M"],
      ["Edit resource / Measurement properties", "Ctrl / ⌘ + E"],
      ["Browse attached schedule / resource library", "Ctrl / ⌘ + L"],
      ["Apply analysis or records / Confirm draft discard", "Ctrl / ⌘ + Enter / Escape"],
    ],
  },
  {
    title: "Ribbon navigation",
    items: [
      ["Focus ribbon tabs", "Left / Right / Home / End"],
      ["Activate focused ribbon tab", "Enter / Space"],
    ],
  },
];
let pending: ((discard: boolean) => Promise<unknown>) | undefined;
let unsubscribers: UnlistenFn[] = [];
const rowKinds: {
  kind: RowKind;
  icon: string;
  label: string;
  hint: string;
  value: string;
}[] = [
  {
    kind: "Group",
    icon: "group",
    label: "Resource group",
    hint: "Insert a resource group for materials, labour or equipment at the current selection.",
    value: "",
  },
  {
    kind: "Subtotal",
    icon: "sum",
    label: "Subtotal",
    hint: "Insert a subtotal that captures the cumulative total as the base for later weighted additions.",
    value: "",
  },
  {
    kind: "Weight",
    icon: "percent",
    label: "Weighted addition",
    hint: "Insert a weighted addition calculated as a fraction of the latest group or subtotal base.",
    value: "0.01",
  },
  {
    kind: "Multiply",
    icon: "multiply",
    label: "Multiplier",
    hint: "Insert a multiplier that replaces the total with the last base multiplied by a factor.",
    value: "1",
  },
  {
    kind: "Round",
    icon: "round",
    label: "Round off",
    hint: "Insert a rounding step for the cumulative analysis total using the existing currency rules.",
    value: "2",
  },
];
const canEdit = computed(
  () => connected.value && !busy.value && !projectBusy.value && !!state.value?.code && activeView.value === "analysis",
);
async function navigate(action: (discard: boolean) => Promise<unknown>, project = false) {
  if (projectBusy.value) return;
  pendingProject = project;
  if (state.value?.dirty || recordsDirty.value || (project && state.value?.workspace_dirty)) {
    pending = action;
    discardOpen.value = true;
  } else await action(false);
}
async function discard() {
  if (recordsDirty.value) {
    if (
      !(await w.run(async () => {
        await request("measurement.draft.discard", { revision: state.value?.revision });
        await w.refresh();
        await projectViews.measurement?.reload();
      }, "Discarding records…"))
    )
      return;
  }
  const action = pending;
  pending = undefined;
  discardOpen.value = false;
  await action?.(true);
}
function cancelDiscard() {
  closeConfirmed.clear();
  pending = undefined;
  discardOpen.value = false;
  cancelPendingOpen();
}
async function continueAfterSave() {
  if (measurementEntry.value) await projectViews.measurement?.reload();
  if (pending) {
    const action = pending;
    pending = undefined;
    discardOpen.value = false;
    await action(false);
  }
}
async function edit(row: AnalysisRow, field: string, value: string) {
  return w.command("edit", { id: row.id, field, value });
}
function beforeUnload(event: BeforeUnloadEvent) {
  if (state.value?.dirty || recordsDirty.value || state.value?.workspace_dirty || projectBusy.value) {
    event.preventDefault();
    event.returnValue = "";
  }
}
function keyboard(event: KeyboardEvent) {
  if (!event.defaultPrevented && (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "f") {
    event.preventDefault();
    if (!document.querySelector('[role="dialog"]') && activeView.value === "analysis") sidebar.value = true;
    void nextTick(focusSearch);
    return;
  }
  if (event.defaultPrevented || document.querySelector('[role="dialog"]')) return;
  if (analysisDialogs.value?.customResourceOpen || fileMode.value || discardOpen.value || helpOpen.value) return;
  const key = event.key.toLowerCase();
  const mod = event.ctrlKey || event.metaKey;
  if (event.altKey && ["ArrowLeft", "ArrowRight"].includes(event.key)) {
    event.preventDefault();
    void travelNavigation(event.key === "ArrowLeft" ? -1 : 1);
    return;
  }
  if (mod && event.shiftKey && key === "r") {
    event.preventDefault();
    if (uiBusy.value || !state.value?.project_open) return;
    void w.run(async () => {
      await request("project.reorder", { revision: state.value?.revision });
      await w.refresh();
      await projectView.value?.reload();
      notify("Item order repaired.");
    }, "Repairing item order…");
    return;
  }
  if (mod && (key === "t" || key === "w" || event.key === "Tab")) {
    event.preventDefault();
    if (uiBusy.value) return;
    if (key === "t") void addProjectTab();
    else if (key === "w") void closeProjectTab(documentId);
    else void cycleProjectTab(event.shiftKey ? -1 : 1);
    return;
  }
  if (mod && ["o", "s"].includes(key)) {
    event.preventDefault();
    if (busy.value || projectBusy.value) return;
    if (key === "o") showFile("open");
    if (key === "s" && state.value?.project_open) {
      if (event.shiftKey) showFile("save");
      else void saveProject();
    }
    return;
  }
  if (
    (event.ctrlKey || event.metaKey) &&
    ["z", "y"].includes(key) &&
    !(event.target as HTMLElement).closest("input,textarea,select,[contenteditable=true]")
  ) {
    event.preventDefault();
    void historyAction(key === "y" || event.shiftKey ? "redo" : "undo");
    return;
  }
  if (activeView.value !== "analysis") {
    projectView.value?.handleKeyboard(event);
    return;
  }
  if ((event.target as HTMLElement).closest("input,textarea,select,[contenteditable=true]")) return;
  if (mod && key === "i") {
    event.preventDefault();
    if (canEdit.value && groups.value.length) {
      analysisDialogs.value?.showResource(event.shiftKey ? "custom" : "library");
    }
    return;
  }
  if (mod && event.key === "Enter") {
    event.preventDefault();
    if (canEdit.value && state.value?.project) void applyAnalysis();
    return;
  }
  if (mod && event.key === "Escape" && state.value?.project && state.value.dirty) {
    event.preventDefault();
    void discardAnalysis();
    return;
  }
  if (mod && ["z", "y", "c", "v", "d"].includes(key)) {
    event.preventDefault();
    if (!canEdit.value) return;
    void w.command(
      key === "z"
        ? event.shiftKey
          ? "redo"
          : "undo"
        : key === "y"
          ? "redo"
          : key === "c"
            ? "copy"
            : key === "d"
              ? "duplicate"
              : "paste",
    );
  } else if (event.key === "Delete" && selected.value.length) {
    event.preventDefault();
    void w.command("delete");
  } else if (event.key === "Escape") analysisTable.value?.clearSelection();
}
async function showSettings() {
  if (state.value?.project_open) settingsOpen.value = true;
}
function navigateTabs(event: KeyboardEvent, index: number) {
  const last = views.value.length - 1;
  const next =
    event.key === "ArrowRight"
      ? (index + 1) % views.value.length
      : event.key === "ArrowLeft"
        ? (index + last) % views.value.length
        : event.key === "Home"
          ? 0
          : event.key === "End"
            ? last
            : -1;
  if (next < 0) return;
  event.preventDefault();
  // Move focus without switching away from a draft; Enter/Space activates the tab.
  document.getElementById("view-" + views.value[next]!.key)?.focus();
}
async function applyAndContinue() {
  if (await (recordsDirty.value ? applyRecords() : w.command("analysis.apply"))) {
    const action = pending;
    pending = undefined;
    discardOpen.value = false;
    await action?.(false);
  }
}
async function applyRecords(returnToList = false) {
  const result = (await projectViews.measurement?.applyRecords(returnToList)) ?? false;
  await w.refresh();
  if (result && returnToList) measurementEntry.value = undefined;
  return result;
}
async function discardRecords() {
  if (uiBusy.value) return;
  const ok = (await projectViews.measurement?.discardRecords()) ?? false;
  await w.refresh();
  if (ok) measurementEntry.value = undefined;
}
async function applyAnalysis() {
  if (await w.command("analysis.apply")) await returnToSchedule();
}
async function discardAnalysis() {
  if (!state.value?.project || uiBusy.value) return;
  if (await w.load(state.value.code, true)) await returnToSchedule();
}
async function historyAction(method: "undo" | "redo") {
  if (uiBusy.value) return;
  if (activeView.value === "analysis") await w.command(method);
  else await projectView.value?.historyAction(method);
}
async function applicationAction(action: string) {
  switch (action) {
    case "new":
      await newProject();
      break;
    case "open":
      showFile("open");
      break;
    case "save":
      await saveProject();
      break;
    case "save-copy":
      showFile("save");
      break;
    case "close-project":
      await closeProject();
      break;
    case "export":
      if (activeView.value === "analysis") await analysisDialogs.value?.exportWorkbook();
      else projectView.value?.exportWorkbook();
      break;
    case "settings":
      await showSettings();
      break;
    case "libraries":
      libraryManagerOpen.value = true;
      break;
    case "program-settings":
      programSettingsOpen.value = true;
      break;
    case "reconnect":
      await w.reconnect();
      await initializeMCP();
      await refreshRecovery();
      if (recoveryProjects.value.length && !state.value?.project_open) showFile("open");
      break;
    case "manual":
      manualOpen.value = true;
      break;
    case "about":
      aboutOpen.value = true;
      break;
    case "help":
      helpOpen.value = true;
      break;
    case "close":
      if (isTauri()) await getCurrentWindow().close();
      break;
  }
}
onMounted(async () => {
  window.addEventListener("keydown", keyboard);
  window.addEventListener("beforeunload", beforeUnload);
  try {
    if (isTauri()) {
      let font = await invoke<{ family?: string; size?: string }>("desktop_font");
      if (!font.family || !font.size) {
        const native = await request<{ family?: string; size?: string }>("program.desktop_font").catch(() => ({}));
        font = { ...font, ...native };
      }
      setPlatformFont(font);
      unsubscribers.push(
        await listen<{ family?: string; size?: string }>("desktop-font", (event) => setPlatformFont(event.payload)),
      );
      unsubscribers.push(
        await listen<{ message: string }>("backend-progress", (e) => (status.value = e.payload.message)),
      );
      unsubscribers.push(
        await getCurrentWindow().onCloseRequested(async (event) => {
          if (busy.value || projectBusy.value) {
            event.preventDefault();
            return;
          }
          const dirty = state.value?.dirty || recordsDirty.value || state.value?.workspace_dirty;
          if (dirty && !closeConfirmed.has(documentId)) {
            event.preventDefault();
            await navigate(async (discard) => {
              if (discard) await request("recovery.discard");
              closeConfirmed.add(documentId);
              await continueWindowClose();
            }, true);
          } else if (documents.value.some((tab) => tab.id !== documentId && tab.dirty && !closeConfirmed.has(tab.id))) {
            event.preventDefault();
            await continueWindowClose();
          }
        }),
      );
    }
    await w.reconnect();
    unsubscribers.push(
      await installProjectOpening(openOsProject, (message) => {
        error.value = message;
      }),
    );
    await mcpRefresh.start();
    const action = takeDocumentAction();
    if (!startup.done) {
      startup.done = true;
      await refreshRecovery();
      if (recoveryProjects.value.length && !state.value?.project_open) await showFile("open");
    } else if (action) void runDocumentAction(action);
    else if (pendingPaths.length) void openOsProject(pendingPaths.shift()!);
  } catch (reason) {
    error.value = String(reason);
  }
  await nextTick();
  try {
    // Hidden native windows may throttle animation frames. Finish initial
    // layout explicitly instead of waiting for a frame before showing them.
    document.documentElement.getBoundingClientRect();
    await document.fonts.ready;
    await analysisTable.value?.prepare();
    ribbonToolbar.value?.prepare();
  } catch (reason) {
    error.value = String(reason);
    await nextTick();
  }
  if (isTauri()) await getCurrentWindow().show();
});
onBeforeUnmount(() => {
  window.removeEventListener("keydown", keyboard);
  window.removeEventListener("beforeunload", beforeUnload);
  unsubscribers.forEach((fn) => fn());
});
</script>
<template>
  <div class="app-shell">
    <header class="titlebar" data-tauri-drag-region>
      <ApplicationMenu
        :busy="uiBusy"
        :project-open="!!state?.project_open"
        :can-export="activeView === 'analysis' ? !!state?.project : !!state?.project_open"
        :analysis="activeView === 'analysis'"
        @action="applicationAction"
      />
      <div class="quick-actions" role="toolbar" aria-label="Common actions">
        <button
          class="icon-button"
          aria-label="Go back"
          title="Back (Alt+Left)"
          :disabled="uiBusy || navigationIndex <= 0"
          @click="travelNavigation(-1)"
        >
          <AppIcon name="back" />
        </button>
        <button
          class="icon-button"
          aria-label="Go forward"
          title="Forward (Alt+Right)"
          :disabled="uiBusy || navigationIndex + 1 >= navigation.length"
          @click="travelNavigation(1)"
        >
          <AppIcon name="forward" />
        </button>
        <span class="quick-actions-separator" />

        <button
          class="icon-button"
          aria-label="New project"
          title="Create a blank estimate. Unsaved changes prompt you to save or discard before switching projects."
          :disabled="uiBusy"
          @click="newProject"
        >
          <AppIcon name="file" />
        </button>
        <button
          class="icon-button"
          aria-label="Open project"
          title="Open an existing estimate or recover a checkpoint. The project is edited in an isolated working copy (Ctrl+O)."
          :disabled="uiBusy"
          @click="showFile('open')"
        >
          <AppIcon name="folder" />
        </button>
        <button
          class="icon-button"
          aria-label="Save copy"
          title="Save the working project to a new file without replacing the opened source (Ctrl+Shift+S)."
          :disabled="uiBusy || !state?.project_open"
          @click="showFile('save')"
        >
          <AppIcon name="save" />
        </button>
        <span class="quick-actions-separator" />
        <button
          class="icon-button"
          aria-label="Undo"
          title="Undo the last analysis or records draft edit, or the last project operation in other views (Ctrl+Z)."
          :disabled="uiBusy || !(activeView === 'analysis' ? state?.undo : projectHistory.undo)"
          @click="historyAction('undo')"
        >
          <AppIcon name="undo" />
        </button>
        <button
          class="icon-button"
          aria-label="Redo"
          title="Restore the last undone change in the active editing context (Ctrl+Y)."
          :disabled="uiBusy || !(activeView === 'analysis' ? state?.redo : projectHistory.redo)"
          @click="historyAction('redo')"
        >
          <AppIcon name="redo" />
        </button>
        <span class="quick-actions-separator" />
      </div>
      <div class="titlebar-project" data-tauri-drag-region>
        <AppIcon name="folder" :size="15" /><span>{{ projectName }}</span
        ><span
          v-if="state?.dirty || recordsDirty || state?.workspace_dirty"
          class="unsaved-dot"
          title="Unsaved changes"
        />
      </div>
      <div class="titlebar-actions">
        <span class="version-tag">DESKTOP PREVIEW</span
        ><button
          class="icon-button"
          :title="theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'"
          :aria-label="theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'"
          @click="toggleTheme"
        >
          <AppIcon :name="theme === 'dark' ? 'sun' : 'moon'" /></button
        ><button
          class="icon-button"
          title="Keyboard shortcuts"
          aria-label="Keyboard shortcuts"
          @click="helpOpen = true"
        >
          <AppIcon name="help" />
        </button>
      </div>
      <div v-if="isTauri()" class="window-controls" role="toolbar" aria-label="Window controls">
        <button
          class="icon-button"
          aria-label="Minimize window"
          title="Minimize"
          @click="getCurrentWindow().minimize()"
        >
          <AppIcon name="minimize" />
        </button>
        <button
          class="icon-button"
          aria-label="Maximize or restore window"
          title="Maximize or restore"
          @click="getCurrentWindow().toggleMaximize()"
        >
          <AppIcon name="maximize" :size="15" />
        </button>
        <button
          class="icon-button window-close"
          aria-label="Close window"
          title="Close"
          :disabled="uiBusy"
          @click="getCurrentWindow().close()"
        >
          <AppIcon name="close" />
        </button>
      </div>
    </header>
    <div class="ribbon-tabs" role="tablist" aria-label="Workspace views">
      <button
        v-for="(view, index) in views"
        :key="view.key"
        role="tab"
        :id="'view-' + view.key"
        :aria-selected="activeTab === view.key"
        :tabindex="activeTab === view.key ? 0 : -1"
        :disabled="uiBusy"
        :aria-controls="'tools-' + view.key"
        :class="{ active: activeTab === view.key, 'record-context': view.key === 'measurement' && !!measurementEntry }"
        :title="view.key === 'measurement' && measurementEntry ? 'Measurement records mode' : undefined"
        :aria-description="view.key === 'measurement' && measurementEntry ? 'Measurement records mode' : undefined"
        @click="switchView(view.key)"
        @keydown="navigateTabs($event, index)"
      >
        {{ view.label }}
      </button>
      <span class="spacer" /><span class="engine-status" :class="{ online: connected }"
        ><i />{{ connected ? "Calculation engine connected" : "Engine disconnected" }}</span
      >
    </div>
    <RibbonToolbar
      v-show="!(landingVisible && ['schedule', 'resources', 'measurement'].includes(activeTab))"
      ref="ribbonToolbar"
      class="ribbon"
      :id="'tools-' + activeTab"
      role="tabpanel"
      :aria-labelledby="'view-' + activeTab"
      :aria-label="(views.find((view) => view.key === activeTab)?.label || '') + ' tools'"
    >
      <template v-if="activeTab === 'analysis'">
        <div class="ribbon-group">
          <div class="ribbon-actions">
            <button
              class="ribbon-action"
              aria-label="Add resources from database"
              :disabled="!canEdit || !groups.length"
              @click="analysisDialogs?.showResource('library')"
            >
              <AppIcon name="database" /><span class="ribbon-label">From database</span>
            </button>
            <button
              class="ribbon-action"
              aria-label="Add custom resource"
              :disabled="!canEdit || !groups.length"
              @click="analysisDialogs?.showResource('custom')"
            >
              <AppIcon name="resource" /><span class="ribbon-label">Custom resource</span>
            </button>
            <button
              class="ribbon-action"
              aria-label="Duplicate"
              :disabled="!canEdit || !selected.length"
              @click="w.command('duplicate')"
            >
              <AppIcon name="duplicate" /><span class="ribbon-label">Duplicate</span>
            </button>
          </div>
          <small>RESOURCES</small>
        </div>
        <div class="ribbon-group">
          <div class="ribbon-actions ribbon-actions-wide">
            <button
              v-for="row in rowKinds"
              :key="row.kind"
              class="ribbon-action"
              :aria-label="row.label"
              :title="row.hint"
              :disabled="!canEdit"
              @click="w.command('add', { kind: row.kind, value: row.value })"
            >
              <AppIcon :name="row.icon" /><span class="ribbon-label">{{ row.label }}</span>
            </button>
            <button
              class="ribbon-action"
              aria-label="Default analysis rows"
              title="Insert the default calculation rows configured in Program Settings into this draft. Undo restores the previous draft."
              :disabled="!canEdit"
              @click="w.command('analysis.insert_template')"
            >
              <AppIcon name="file" /><span class="ribbon-label">Default rows</span>
            </button>
            <button
              class="ribbon-action"
              aria-label="Custom analysis template…"
              title="Configure, save and preview reusable calculation rows before inserting them as one undoable batch."
              :disabled="!canEdit"
              @click="analysisDialogs?.showTemplate()"
            >
              <AppIcon name="settings" /><span class="ribbon-label">Custom template</span>
            </button>
          </div>
          <small>INSERT</small>
        </div>
        <div class="ribbon-group">
          <div class="ribbon-actions ribbon-pairs">
            <button
              class="ribbon-action ribbon-icon"
              aria-label="Copy rows"
              title="Copy selected analysis rows and resource definitions to the system clipboard for use in another GEstimator window (Ctrl+C)."
              :disabled="!canEdit || !selected.length"
              @click="w.command('copy')"
            >
              <AppIcon name="copy" /><span class="ribbon-label">Copy rows</span>
            </button>
            <button
              class="ribbon-action ribbon-icon"
              aria-label="Paste rows"
              title="Insert analysis rows copied from this or another GEstimator window at the current selection. Existing project resource definitions are reused by code (Ctrl+V)."
              :disabled="!canEdit"
              @click="w.command('paste')"
            >
              <AppIcon name="paste" /><span class="ribbon-label">Paste rows</span>
            </button>

            <button
              class="ribbon-action ribbon-icon danger"
              aria-label="Delete"
              title="Remove the selected rows from this analysis draft. Use Undo to restore them."
              :disabled="!canEdit || !selected.length"
              @click="w.command('delete')"
            >
              <AppIcon name="trash" /><span class="ribbon-label">Delete</span>
            </button>
          </div>
          <small>EDIT</small>
        </div>
        <div class="ribbon-group">
          <div class="ribbon-actions">
            <button
              class="ribbon-action ribbon-icon"
              aria-label="Move up"
              title="Move the selected analysis row one position earlier in the calculation sequence."
              :disabled="!canEdit || selected.length !== 1"
              @click="w.command('move', { delta: -1 })"
            >
              <AppIcon name="up" /><span class="ribbon-label">Move up</span></button
            ><button
              class="ribbon-action ribbon-icon"
              aria-label="Move down"
              title="Move the selected analysis row one position later in the calculation sequence."
              :disabled="!canEdit || selected.length !== 1"
              @click="w.command('move', { delta: 1 })"
            >
              <AppIcon name="down" /><span class="ribbon-label">Move down</span>
            </button>
          </div>
          <small>SEQUENCE</small>
        </div>
        <div class="ribbon-group">
          <div class="ribbon-actions">
            <button
              class="ribbon-action"
              :aria-label="sidebar ? 'Hide explorer' : 'Show explorer'"
              @click="sidebar = !sidebar"
            >
              <AppIcon name="panel-left" /><span class="ribbon-label">{{
                sidebar ? "Hide explorer" : "Show explorer"
              }}</span>
            </button>
            <button
              class="ribbon-action"
              :aria-label="inspector ? 'Hide analysis inspector' : 'Show analysis inspector'"
              :title="
                inspector
                  ? 'Hide the selected-row inspector to give the analysis table more room.'
                  : 'Show the inspector to edit the selected analysis row and resource definition.'
              "
              :class="{ pressed: !inspector }"
              :aria-pressed="!inspector"
              @click="inspector = !inspector"
            >
              <AppIcon name="panel" />
              <span class="ribbon-label">{{ inspector ? "Hide inspector" : "Show inspector" }}</span>
            </button>
          </div>
          <small>VIEW</small>
        </div>
        <div class="ribbon-group">
          <div class="ribbon-actions">
            <button
              class="ribbon-action"
              aria-label="Export analysis"
              title="Export this analysis, including unapplied draft edits, to an Excel workbook."
              :disabled="!canEdit || !state?.project"
              @click="analysisDialogs?.exportWorkbook()"
            >
              <AppIcon name="export" /><span class="ribbon-label">Export analysis</span>
            </button>
            <button
              class="ribbon-action"
              aria-label="Import analysis"
              title="Preview an Excel worksheet range and insert its calculation rows into this draft. The import can be undone."
              :disabled="!canEdit || !state?.project"
              @click="analysisDialogs?.showImport()"
            >
              <AppIcon name="import" /><span class="ribbon-label">Import analysis</span>
            </button>
          </div>
          <small>PROJECT</small>
        </div>
      </template>
      <template v-else-if="activeTab === 'databases'">
        <div class="ribbon-group">
          <div class="ribbon-actions">
            <button
              class="ribbon-action"
              aria-label="Attach database…"
              title="Bundled and folder databases attach automatically. Open the database manager to attach other databases, retry saved paths or forget entries. The editor stays in place."
              @click="libraryManagerOpen = true"
            >
              <AppIcon name="attach" /><span class="ribbon-label">Attach database…</span></button
            ><button
              class="ribbon-action"
              aria-label="Open database folder"
              title="Open the custom database folder in your file manager. Open the database manager to rescan after adding files."
              @click="libraryManager?.openDirectory()"
            >
              <AppIcon name="folder" /><span class="ribbon-label">Database folder</span>
            </button>
          </div>
          <small>DATABASES</small>
        </div>
      </template>
      <template v-else-if="activeTab === 'mcp'">
        <div class="ribbon-group">
          <div class="ribbon-actions">
            <button
              class="ribbon-action"
              aria-label="Start MCP server"
              title="Start the authenticated local MCP server using the access mode selected in Configure server."
              :disabled="mcpBusy || !mcpStatus || mcpStatus.running"
              @click="startMCP"
            >
              <AppIcon name="play" /><span class="ribbon-label">Start server</span></button
            ><button
              class="ribbon-action"
              aria-label="Stop MCP server"
              title="Stop listening and prevent further MCP requests. The current project and editor stay open."
              :disabled="mcpBusy || !mcpStatus?.running"
              @click="stopMCP"
            >
              <AppIcon name="stop" /><span class="ribbon-label">Stop server</span>
            </button>
          </div>
          <small>SERVER</small>
        </div>
        <div class="ribbon-group">
          <div class="ribbon-actions">
            <button
              class="ribbon-action"
              aria-label="Configure MCP server"
              title="Configure the local port, automatic startup and connection token; inspect available tools and client configuration."
              :disabled="mcpBusy"
              @click="mcpSettingsOpen = true"
            >
              <AppIcon name="settings" /><span class="ribbon-label">Configure server</span></button
            ><button
              class="ribbon-action"
              aria-label="Copy MCP client configuration"
              title="Copy the server URL and authorization header as JSON for a Streamable HTTP MCP client."
              :disabled="mcpBusy || !mcpStatus"
              @click="copyMCPConfig"
            >
              <AppIcon name="copy" /><span class="ribbon-label">Client config</span></button
            ><button
              class="ribbon-action"
              aria-label="Refresh MCP status"
              title="Refresh server status and client activity without changing the project."
              :disabled="mcpBusy"
              @click="refreshMCP"
            >
              <AppIcon name="refresh" /><span class="ribbon-label">Refresh status</span>
            </button>
          </div>
          <small>CONNECTION</small>
        </div>
        <span class="ribbon-note" role="status"
          >{{ mcpStatus?.running ? "Running" : "Stopped" }} ·
          {{ mcpStatus?.access === "read-write" ? "Read and write" : "Read only" }}<br />{{
            mcpStatus?.url || "Connecting…"
          }}</span
        >
      </template>
      <div
        id="project-ribbon-tools"
        class="ribbon-tools-host"
        v-show="activeTab !== 'analysis' && activeTab !== 'databases' && activeTab !== 'mcp'"
      />
    </RibbonToolbar>
    <div v-if="error" class="error-banner" role="alert">
      <AppIcon name="help" /><span>{{ error }}</span
      ><button class="icon-button" aria-label="Dismiss error" @click="error = ''">
        <AppIcon name="close" :size="16" />
      </button>
    </div>
    <div v-if="programSettingsWarning" class="library-warning program-settings-warning" role="status">
      <span>{{ programSettingsWarning }}</span>
      <button class="text-button" :disabled="uiBusy" @click="programSettingsOpen = true">
        Review program settings
      </button>
    </div>
    <div v-if="mcpError && !mcpSettingsOpen" class="error-banner mcp-error" role="alert">
      <span>{{ mcpError }}</span
      ><button class="text-button" :disabled="mcpBusy" @click="mcpSettingsOpen = true">Review MCP settings</button
      ><button class="icon-button" aria-label="Dismiss MCP error" @click="mcpError = ''">
        <AppIcon name="close" :size="16" />
      </button>
    </div>
    <div v-if="state?.project_open && unavailableLibraries.length" class="library-warning" role="status">
      <span
        >{{ unavailableLibraries.length }} saved
        {{ unavailableLibraries.length === 1 ? "library is" : "libraries are" }} unavailable. The project is open and
        available libraries are attached.</span
      >
      <button class="text-button" :disabled="uiBusy" @click="libraryManagerOpen = true">Manage libraries</button>
    </div>
    <div class="workspace">
      <DocumentRail :busy="uiBusy" @switch="switchProjectTab" @close="closeProjectTab" @add="addProjectTab" />
      <aside v-show="sidebar && activeView === 'analysis'" class="explorer">
        <div class="panel-heading"><span>PROJECT EXPLORER</span></div>
        <div class="explorer-project">
          <span class="project-icon"><AppIcon name="folder" :size="20" /></span>
          <div>
            <strong>{{ projectName }}</strong
            ><small>{{ state?.project_open ? "Project working copy" : "No project open" }}</small>
          </div>
        </div>
        <div class="explorer-tabs" role="tablist" aria-label="Explorer">
          <button
            role="tab"
            :aria-selected="explorer === 'schedule'"
            :class="{ active: explorer === 'schedule' }"
            @click="explorer = 'schedule'"
          >
            <AppIcon name="grid" :size="15" />Schedule</button
          ><button
            role="tab"
            :aria-selected="explorer === 'resources'"
            :class="{ active: explorer === 'resources' }"
            @click="
              explorer = 'resources';
              if (state?.project_open) w.searchResources();
            "
          >
            <AppIcon name="library" :size="15" />Resources
          </button>
        </div>
        <form class="search-field" @submit.prevent="explorer === 'schedule' ? w.searchSchedule() : w.searchResources()">
          <AppIcon name="search" :size="15" /><input
            v-if="explorer === 'schedule'"
            id="navigator-search"
            v-model="scheduleQuery"
            placeholder="Find schedule items…"
            aria-label="Find schedule items"
            :disabled="!state?.project_open"
          /><input
            v-else
            id="navigator-search"
            v-model="resourceQuery"
            placeholder="Find resources…"
            aria-label="Find resources"
            :disabled="!state?.project_open"
          /><button
            type="submit"
            class="icon-button"
            aria-label="Search explorer"
            :disabled="uiBusy || !state?.project_open"
          >
            <AppIcon name="chevron" :size="14" />
          </button>
        </form>
        <div class="explorer-caption">
          <span>{{ explorer === "schedule" ? "SCHEDULE ITEMS" : "RESOURCE LIBRARY" }}</span
          ><span>{{ (explorer === "schedule" ? schedule : resources).length }} shown</span>
        </div>
        <nav class="item-list" :aria-label="explorer === 'schedule' ? 'Schedule items' : 'Resource library'">
          <template v-if="explorer === 'schedule'"
            ><button
              v-for="item in schedule"
              :key="item.code"
              class="item-card"
              :class="{ active: state?.code === item.code }"
              :disabled="uiBusy"
              @click="loadAnalysis(item.code)"
            >
              <span class="item-code"
                ><AppIcon name="file" :size="14" />{{ item.code
                }}<span v-if="state?.code === item.code" class="item-active-dot" /></span
              ><span class="item-description">{{ item.description }}</span
              ><span class="item-unit">{{ item.unit || "Heading" }}</span>
            </button></template
          >
          <template v-else
            ><button
              v-for="item in resources"
              :key="item.code"
              class="item-card"
              :disabled="uiBusy || !canEdit || !groups.length"
              @click="analysisDialogs?.insertExplorerResource(item.code)"
            >
              <span class="item-code"><AppIcon name="resource" :size="14" />{{ item.code }}</span
              ><span class="item-description">{{ item.description }}</span
              ><span class="item-unit">{{ formatMoney(item.rate) }} / {{ item.unit }}</span>
            </button></template
          >
          <div v-if="!(explorer === 'schedule' ? schedule : resources).length" class="empty-explorer">
            <AppIcon :name="state?.project_open ? 'search' : 'folder'" :size="30" /><strong>{{
              state?.project_open ? "No items to show" : "Your project starts here"
            }}</strong>
            <p>
              {{
                state?.project_open
                  ? "Search by code or description."
                  : "Open a GEstimator project to explore its schedule and resources."
              }}
            </p>
            <button v-if="!state?.project_open" class="button secondary" :disabled="uiBusy" @click="showFile('open')">
              Open project
            </button>
          </div>
        </nav>
        <div v-if="state?.project_open" class="pagination">
          <button
            class="icon-button"
            aria-label="Previous page"
            :disabled="busy || (explorer === 'schedule' ? schedulePage : resourcePage) === 0"
            @click="explorer === 'schedule' ? w.searchSchedule(schedulePage - 1) : w.searchResources(resourcePage - 1)"
          >
            <AppIcon name="up" :size="15" /></button
          ><span>Page {{ (explorer === "schedule" ? schedulePage : resourcePage) + 1 }}</span
          ><button
            class="icon-button"
            aria-label="Next page"
            :disabled="busy || (explorer === 'schedule' ? schedule : resources).length < 100"
            @click="explorer === 'schedule' ? w.searchSchedule(schedulePage + 1) : w.searchResources(resourcePage + 1)"
          >
            <AppIcon name="down" :size="15" />
          </button>
        </div>
        <div class="explorer-foot"><AppIcon name="check" :size="14" /><span>Isolated working copy</span></div>
      </aside>
      <main class="editor-pane">
        <ProjectLanding
          v-if="landingVisible"
          :busy="uiBusy"
          :recent="recentProjects"
          :recovery="recoveryProjects"
          @new="newProject"
          @open="browseProject"
          @open-recent="openProjectPath"
          @recover="recoverProject"
          @clear-recent="setRecentProjects([])"
        />
        <ProjectViews
          v-for="view in visitedViews"
          :key="projectSession + ':' + view"
          :ref="(instance) => bindProjectView(view, instance)"
          v-show="activeView === view && !!state?.project_open"
          :active="activeView === view"
          :entry-id="view === 'measurement' ? measurementEntry : undefined"
          :view="view"
          :project-open="!!state?.project_open"
          @changed="w.refresh()"
          @history="activeView === view && (projectHistory = $event)"
          @busy="projectBusy = $event"
          @analysis="loadAnalysis"
          @entry="changeMeasurementEntry"
          @apply-records="applyRecords(true)"
          @discard-records="discardRecords"
          @libraries="libraryManagerOpen = true"
          @database="projectDatabasePickers?.show($event)"
          @analysis-rules="showAnalysisRules"
        />
        <div v-show="activeView === 'analysis'" class="analysis-content">
          <div class="draft-headerbar" role="region" aria-label="Analysis draft">
            <strong
              >Rate analysis <span v-if="state?.code" class="code-tag">{{ state.code }}</span></strong
            >
            <span class="spacer" />
            <button
              class="button small danger"
              aria-label="Discard analysis"
              title="Discard this draft and return to Schedule."
              :disabled="uiBusy || !state?.project"
              @click="discardAnalysis"
            >
              <AppIcon name="close" :size="16" />Discard analysis
            </button>
            <button
              class="button small primary"
              aria-label="Save analysis without leaving"
              title="Save this analysis to the working project and update dependent rates without leaving the editor. Save the project to retain changes on disk."
              :disabled="uiBusy || !canEdit || !state?.project"
              @click="w.command('analysis.apply')"
            >
              <AppIcon name="save" :size="16" />Save analysis
            </button>
            <button
              class="button small apply"
              aria-label="Apply analysis"
              title="Apply this draft to the project working copy and update dependent rates (Ctrl+Enter). Return to Schedule after applying. Save the project to retain changes on disk."
              :disabled="uiBusy || !canEdit || !state?.project"
              @click="applyAnalysis"
            >
              <AppIcon name="check" :size="16" />Apply analysis
            </button>
          </div>
          <div class="analysis-intro">
            <div class="breadcrumbs">
              Workspace<AppIcon name="chevron" :size="12" />{{ projectName }}<AppIcon name="chevron" :size="12" /><span
                >Rate analysis</span
              >
            </div>
            <div class="analysis-heading">
              <div>
                <div class="eyebrow">RATE ANALYSIS</div>
                <h1>{{ state?.description || "Select a schedule item" }}</h1>
                <p>
                  {{
                    state?.code
                      ? "Build up the rate with resources and calculation rows."
                      : "Choose a schedule item from the explorer to begin editing."
                  }}
                </p>
              </div>
              <span class="draft-badge" :class="{ dirty: state?.dirty }"
                ><i />{{ state?.dirty ? "Unsaved changes" : "Up to date" }}</span
              >
            </div>
            <div class="analysis-metadata">
              <span><AppIcon name="resource" :size="14" />{{ resourceCount }} resources</span
              ><span><AppIcon name="group" :size="14" />{{ groups.length }} groups</span
              ><span v-if="state?.unit"
                >Unit <b>{{ state.unit }}</b></span
              ><span class="metadata-last"><AppIcon name="check" :size="14" />Calculated in project order</span>
            </div>
          </div>
          <label class="analysis-remarks"
            >Analysis remarks<input
              :value="state?.ana_remarks"
              :disabled="uiBusy || !canEdit"
              placeholder="Notes printed with this rate analysis"
              @change="
                w.command('analysis.edit', {
                  field: 'ana_remarks',
                  value: ($event.target as HTMLInputElement).value,
                })
              "
          /></label>
          <section class="table-panel" aria-label="Analysis editor">
            <div class="table-toolbar">
              <div>
                <strong>Analysis breakdown</strong
                ><span>{{ selected.length ? selected.length + " selected" : "Double-click a cell to edit" }}</span>
              </div>
              <button
                class="button small secondary"
                :disabled="!canEdit || !groups.length"
                @click="analysisDialogs?.showResource('custom')"
              >
                <AppIcon name="plus" :size="15" />Add resource
              </button>
            </div>
            <AnalysisTable
              ref="analysisTable"
              :active="activeView === 'analysis'"
              :rows="state?.rows || emptyAnalysisRows"
              :busy="busy || !connected"
              :save-cell="edit"
              @selection="selected = $event"
              @action="w.command($event)"
            />
            <div class="table-caption">
              <span><i class="legend-dot group" />Group</span><span><i class="legend-dot subtotal" />Subtotal</span
              ><span><i class="legend-dot adjustment" />Adjustment</span><span class="spacer" /><span
                >{{ state?.rows.length || 0 }} calculation rows</span
              >
            </div>
          </section>
          <div class="rate-summary">
            <div class="summary-icon"><AppIcon name="sum" :size="22" /></div>
            <div><strong>Calculated unit rate</strong><small>Final result of the analysis sequence</small></div>
            <span class="spacer" />
            <div class="summary-value">
              <strong>{{ formatMoney(state?.rate || "0.00") }}</strong
              ><span v-if="state?.unit">/ {{ state.unit }}</span>
            </div>
          </div>
        </div>
      </main>
      <AnalysisInspector
        :visible="inspector && activeView === 'analysis'"
        :selection="selection"
        :multiple-selected="selected.length > 1"
        :busy="uiBusy"
        @edit="edit"
        @move="w.command('move', { delta: $event })"
        @delete="w.command('delete')"
        @hide="inspector = false"
        @shortcuts="helpOpen = true"
      />
    </div>
    <footer class="statusbar" role="status">
      <span class="status-indicator" :class="{ working: busy, offline: !connected }" /><span
        :class="{ 'status-notice': statusNotice }"
        >{{ statusNotice || status }}</span
      ><span v-if="state?.dirty || recordsDirty || state?.workspace_dirty" class="status-unsaved">Unsaved draft</span
      ><span class="spacer" /><span>Tab to navigate</span><span class="status-divider" /><span
        >Ctrl / ⌘ + F to find</span
      ><span class="status-divider" /><span>{{ state?.unit || "GEstimator" }}</span>
    </footer>
  </div>
  <ProjectFileDialog
    v-model:mode="fileMode"
    v-model:path="filePath"
    :error="error"
    :busy="busy"
    :ui-busy="uiBusy"
    :recent-projects="recentProjects"
    :recovery-projects="recoveryProjects"
    @browse="browse"
    @submit="submitFile"
    @clear-recent="setRecentProjects([])"
    @recover="recoverProject"
  />
  <AnalysisDialogs
    ref="analysisDialogs"
    :workspace="w"
    :busy="uiBusy"
    :apply-rules="applyAnalysisRules"
    @manage-libraries="libraryManagerOpen = true"
  />
  <Dialog
    :visible="discardOpen"
    modal
    :header="recordsDirty ? 'Keep your measurement records?' : 'Keep your analysis changes?'"
    class="workspace-dialog file-dialog"
    @update:visible="cancelDiscard"
    ><p class="dialog-intro">
      This workspace has unsaved changes. Save them before continuing, or discard the pending changes.
    </p>
    <div v-if="error" class="dialog-error" role="alert">{{ error }}</div>
    <div class="dialog-footer">
      <button class="button secondary" :disabled="uiBusy" @click="cancelDiscard">Keep editing</button
      ><button class="button danger" :disabled="uiBusy" @click="discard">Discard changes</button
      ><button
        v-if="!pendingProject && (state?.project || recordsDirty)"
        class="button secondary"
        :disabled="uiBusy"
        @click="applyAndContinue"
      >
        Apply and continue</button
      ><button v-if="state?.source_path" class="button secondary" :disabled="uiBusy" @click="saveProject">
        Save project</button
      ><button class="button primary" :disabled="uiBusy || !state?.project_open" @click="showFile('save')">
        Save copy…
      </button>
    </div></Dialog
  >
  <Dialog v-model:visible="helpOpen" modal header="Keyboard shortcuts" class="workspace-dialog shortcuts-dialog"
    ><div class="shortcut-groups">
      <section v-for="group in shortcutGroups" :key="group.title" class="shortcut-group" :aria-label="group.title">
        <h3>{{ group.title }}</h3>
        <div class="shortcut-list">
          <div v-for="[label, key] in group.items" :key="label">
            <span>{{ label }}</span
            ><kbd>{{ key }}</kbd>
          </div>
        </div>
      </section>
    </div>
    <p class="field-hint">
      Text fields keep their normal editing shortcuts. Copied rows can be pasted in the same editor in another
      GEstimator window. Measurement records require the same template; whole-item schedule links match codes in the
      destination. Analysis resource paste uses the selected resource group. In project tables, Ctrl+D duplicates and
      Delete removes selected items; these shortcuts apply to records when the measurement record table has focus.
      Spreadsheet cell paste keeps its normal Ctrl+V behavior.
    </p></Dialog
  >

  <ProjectSettings
    v-if="settingsOpen"
    v-model="settingsOpen"
    :revision="state?.revision"
    :busy="uiBusy"
    @saved="w.refresh()"
  />
  <LibraryManager
    ref="libraryManager"
    v-model="libraryManagerOpen"
    :project-open="!!state?.project_open"
    @changed="librariesChanged"
  />
  <MCPSettings v-model="mcpSettingsOpen" />
  <div v-if="activeTab === 'mcp' && !mcpSettingsOpen && mcpMessage" class="mcp-feedback" role="status">
    {{ mcpMessage }}
  </div>
  <ThemedDropdowns />
  <ApplicationHelp v-model:manual="manualOpen" v-model:about="aboutOpen" />
  <ProgramSettings v-if="programSettingsOpen" v-model="programSettingsOpen" />
  <ProjectDatabasePickers
    ref="projectDatabasePickers"
    :project-session="projectSession"
    :project-view="projectView"
    @manage="libraryManagerOpen = true"
  />
</template>
