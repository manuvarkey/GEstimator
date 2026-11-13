<script setup lang="ts">
import {
  computed,
  nextTick,
  onMounted,
  onBeforeUnmount,
  ref,
  watch,
} from "vue";
import Dialog from "primevue/dialog";
import { invoke, isTauri } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { open, save } from "@tauri-apps/plugin-dialog";
import ApplicationMenu from "./components/ApplicationMenu.vue";
import AppIcon from "./components/AppIcon.vue";
import ProjectViews from "./components/ProjectViews.vue";
import AnalysisTable from "./components/AnalysisTable.vue";
import { useWorkspace } from "./useWorkspace";
import { request, type AnalysisRow, type RowKind } from "./backend";
const w = useWorkspace();
const analysisTable = ref<InstanceType<typeof AnalysisTable>>();
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
  clipboardReady,
  projectName,
  resourceCount,
  groups,
  selection,
  destinationGroup,
} = w;
const projectView = ref<InstanceType<typeof ProjectViews>>();
const projectHistory = ref({ undo: false, redo: false });
const views = [
  { key: "schedule", label: "Schedule" },
  { key: "analysis", label: "Analysis" },
  { key: "resources", label: "Resources" },
  { key: "measurement", label: "Measurements" },
] as const;
const settingsOpen = ref(false);
const settings = ref<Record<string, string>>({});
const activeView = ref<"analysis" | "schedule" | "resources" | "measurement">(
  "analysis",
);
const projectBusy = ref(false);
const uiBusy = computed(() => busy.value || projectBusy.value);

let pendingProject = false;
const duplicateCode = ref("");
const duplicateOpen = ref(false);
const exportAnalysisOpen = ref(false);
const exportAnalysisPath = ref("");
const explorer = ref("schedule");
const sidebar = ref(true);
const inspector = ref(true);
const compact = ref(false);
const expanded = ref(true);
const helpOpen = ref(false);
const theme = ref(localStorage.getItem("gestimator-theme") || "dark");
watch(
  theme,
  (value) => {
    document.documentElement.dataset.theme = value;
    localStorage.setItem("gestimator-theme", value);
  },
  { immediate: true },
);
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
const resourceOpen = ref(false);
const resourceTab = ref("library");
const form = ref({
  code: "",
  description: "",
  unit: "",
  rate: "0",
  qty: "0",
  vat: "0",
  discount: "0",
  reference: "",
  category: "",
  remarks: "",
});
const groupId = ref("");
const discardOpen = ref(false);
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
    hint: "Materials, labour or equipment",
    value: "",
  },
  {
    kind: "Subtotal",
    icon: "sum",
    label: "Subtotal",
    hint: "Capture the cumulative total",
    value: "",
  },
  {
    kind: "Weight",
    icon: "percent",
    label: "Weighted addition",
    hint: "Add a fraction of the last base",
    value: "0.01",
  },
  {
    kind: "Multiply",
    icon: "multiply",
    label: "Multiplier",
    hint: "Multiply the last base",
    value: "1",
  },
  {
    kind: "Round",
    icon: "round",
    label: "Round off",
    hint: "Round the cumulative total",
    value: "2",
  },
];
const selectedKind = computed(() => selection.value?.kind.toLowerCase());
const canEdit = computed(
  () =>
    connected.value &&
    !busy.value &&
    !projectBusy.value &&
    !!state.value?.code &&
    activeView.value === "analysis",
);
const resourceTarget = computed(() =>
  groups.value.find((g) => g.id === groupId.value),
);
const selectionHint = computed(
  () =>
    ({
      Group: "Organize resources into a calculation group.",
      Resource:
        "Definition changes apply to every use of this resource when saved.",
      Subtotal: "Sets the base for subsequent weighted additions.",
      Weight: "Adds a fraction of the latest group or subtotal base.",
      Multiply:
        "Replaces the total with the last base multiplied by this factor.",
      Round: "Rounds the cumulative total using the existing currency rules.",
    })[selection.value?.kind || "Group"],
);
async function navigate(
  action: (discard: boolean) => Promise<unknown>,
  project = false,
) {
  if (projectBusy.value) return;
  pendingProject = project;
  if (state.value?.dirty || (project && state.value?.workspace_dirty)) {
    pending = action;
    discardOpen.value = true;
  } else await action(false);
}
async function discard() {
  const action = pending;
  pending = undefined;
  discardOpen.value = false;
  await action?.(true);
}
function cancelDiscard() {
  pending = undefined;
  discardOpen.value = false;
}
function showFile(mode: "open" | "save") {
  fileMode.value = mode;
  filePath.value =
    mode === "save"
      ? state.value?.source_path?.replace(/\.eproj$/i, "-edited.eproj") || ""
      : "";
  if (mode === "open") void refreshRecovery();
}
async function refreshRecovery() {
  recoveryProjects.value = await request<typeof recoveryProjects.value>("recovery.list")
    .catch(() => []);
}
async function recoverProject(id: string) {
  fileMode.value = null;
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
    await navigate(async (discard) => {
      if (await w.openProject(path, discard)) rememberProject(state.value?.source_path || path);
    }, true);
  } else if (await w.saveCopy(path)) {
    rememberProject(path);
    fileMode.value = null;
    await continueAfterSave();
  }
}
async function continueAfterSave() {
  if (pending) {
    const action = pending;
    pending = undefined;
    discardOpen.value = false;
    await action(false);
  }
}
async function saveProject() {
  if (!state.value?.source_path) showFile("save");
  else if (await w.saveProject()) await continueAfterSave();
}
function addResource() {
  groupId.value = destinationGroup.value?.id || groups.value[0]?.id || "";
  resourceOpen.value = true;
}
async function insertResource(libraryCode?: string) {
  if (
    await w.command("resource.add", {
      id:
        destinationGroup.value?.id === groupId.value
          ? selected.value[0]?.id || groupId.value
          : groupId.value,
      library: !!libraryCode,
      source: resourceSource.value,
      ...form.value,
      code: libraryCode || form.value.code,
    })
  ) {
    resourceOpen.value = false;
    form.value = {
      code: "",
      description: "",
      unit: "",
      rate: "0",
      qty: "0",
      vat: "0",
      discount: "0",
      reference: "",
      category: "",
      remarks: "",
    };
  }
}
async function edit(row: AnalysisRow, field: string, value: string) {
  await w.command("edit", { id: row.id, field, value });
}
function editField(event: Event, field: string) {
  if (selection.value)
    void edit(selection.value, field, (event.target as HTMLInputElement).value);
}
function beforeUnload(event: BeforeUnloadEvent) {
  if (state.value?.dirty || state.value?.workspace_dirty || projectBusy.value) {
    event.preventDefault();
    event.returnValue = "";
  }
}
function keyboard(event: KeyboardEvent) {
  if (
    resourceOpen.value ||
    fileMode.value ||
    discardOpen.value ||
    helpOpen.value
  )
    return;
  const key = event.key.toLowerCase();
  const mod = event.ctrlKey || event.metaKey;
  if (mod && ["o", "s", "k"].includes(key)) {
    event.preventDefault();
    if (busy.value || projectBusy.value) return;
    if (key === "o") showFile("open");
    if (key === "s" && state.value?.project_open) {
      if (event.shiftKey) showFile("save");
      else void saveProject();
    }
    if (key === "k") {
      sidebar.value = true;
      void nextTick(() => document.getElementById("navigator-search")?.focus());
    }
    return;
  }
  if (
    (event.ctrlKey || event.metaKey) &&
    ["z", "y"].includes(key) &&
    !(event.target as HTMLElement).closest(
      "input,textarea,select,[contenteditable=true]",
    )
  ) {
    event.preventDefault();
    void historyAction(key === "y" || event.shiftKey ? "redo" : "undo");
    return;
  }
  if (activeView.value !== "analysis") return;
  if (
    (event.target as HTMLElement).closest(
      "input,textarea,select,[contenteditable=true]",
    )
  )
    return;
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
async function newProject() {
  await navigate(async (discard) => {
    await w.run(async () => {
      await request("project.new", { discard });
      await w.refresh();
      schedule.value = [];
      resources.value = [];
      selected.value = [];
      activeView.value = "schedule";
    });
  }, true);
}
async function showSettings() {
  if (!state.value?.project_open) return;
  settings.value = await request("project.settings");
  settingsOpen.value = true;
}
async function saveSettings() {
  if (
    await w.run(async () => {
      await request("project.settings.edit", {
        revision: state.value?.revision,
        settings: settings.value,
      });
      await w.refresh();
    })
  )
    settingsOpen.value = false;
}
async function switchView(view: typeof activeView.value) {
  if (view === activeView.value) return;
  await navigate(async (discard) => {
    if (discard && state.value?.project) await w.load(state.value.code, true);
    activeView.value = view;
  });
}
async function loadAnalysis(code: string) {
  await navigate(async (discard) => {
    if (await w.load(code, discard)) activeView.value = "analysis";
  });
}
async function applyAndContinue() {
  if (await w.command("analysis.apply")) {
    const action = pending;
    pending = undefined;
    discardOpen.value = false;
    await action?.(false);
  }
}
async function exportAnalysis() {
  if (
    await w.run(async () => {
      await request("analysis.export_xlsx", { path: exportAnalysisPath.value });
    }, "Exporting analysis…")
  )
    exportAnalysisOpen.value = false;
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
    case "export":
      if (activeView.value === "analysis") exportAnalysisOpen.value = true;
      else projectView.value?.exportWorkbook();
      break;
    case "settings":
      await showSettings();
      break;
    case "explorer":
      sidebar.value = !sidebar.value;
      break;
    case "inspector":
      inspector.value = !inspector.value;
      break;
    case "compact":
      compact.value = !compact.value;
      break;
    case "groups":
      expanded.value = !expanded.value;
      break;
    case "reconnect":
      await w.reconnect();
      await refreshRecovery();
      if (recoveryProjects.value.length && !state.value?.project_open) showFile("open");
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
  if (isTauri()) {
    const applyFont = (font: { family?: string; size?: string }) => {
      if (font.family)
        document.documentElement.style.fontFamily =
          JSON.stringify(font.family) + ", system-ui";
      if (font.size) document.documentElement.style.fontSize = font.size;
    };
    applyFont(await invoke("desktop_font"));
    unsubscribers.push(
      await listen<{ family?: string; size?: string }>(
        "desktop-font",
        (event) => applyFont(event.payload),
      ),
    );
    unsubscribers.push(
      await listen<{ message: string }>(
        "backend-progress",
        (e) => (status.value = e.payload.message),
      ),
    );
    unsubscribers.push(
      await getCurrentWindow().onCloseRequested(async (event) => {
        if (busy.value || projectBusy.value) {
          event.preventDefault();
          return;
        }
        if (state.value?.dirty || state.value?.workspace_dirty) {
          event.preventDefault();
          await navigate(async (discard) => {
            if (discard) await request("recovery.discard");
            await getCurrentWindow().destroy();
          }, true);
        }
      }),
    );
  }
  await w.reconnect();
  await refreshRecovery();
  if (recoveryProjects.value.length && !state.value?.project_open) showFile("open");
});
onBeforeUnmount(() => {
  window.removeEventListener("keydown", keyboard);
  window.removeEventListener("beforeunload", beforeUnload);
  unsubscribers.forEach((fn) => fn());
});
</script>
<template>
  <div class="app-shell">
    <header class="titlebar">
      <ApplicationMenu
        :busy="uiBusy"
        :project-open="!!state?.project_open"
        :can-export="
          activeView === 'analysis' ? !!state?.project : !!state?.project_open
        "
        :analysis="activeView === 'analysis'"
        :explorer="sidebar"
        :inspector="inspector"
        :compact="compact"
        :expanded="expanded"
        @action="applicationAction"
      />
      <div class="quick-actions" role="toolbar" aria-label="Common actions">
        <button
          class="icon-button"
          aria-label="New project"
          title="New project"
          :disabled="uiBusy"
          @click="newProject"
        >
          <AppIcon name="file" />
        </button>
        <button
          class="icon-button"
          aria-label="Open project"
          title="Open project (Ctrl+O)"
          :disabled="uiBusy"
          @click="showFile('open')"
        >
          <AppIcon name="folder" />
        </button>
        <button
          class="icon-button"
          aria-label="Save copy"
          title="Save project copy (Ctrl+Shift+S)"
          :disabled="uiBusy || !state?.project_open"
          @click="showFile('save')"
        >
          <AppIcon name="save" />
        </button>
        <span class="quick-actions-separator" />
        <button
          class="icon-button"
          aria-label="Undo"
          title="Undo (Ctrl+Z)"
          :disabled="
            uiBusy ||
            !(activeView === 'analysis' ? state?.undo : projectHistory.undo)
          "
          @click="historyAction('undo')"
        >
          <AppIcon name="undo" />
        </button>
        <button
          class="icon-button"
          aria-label="Redo"
          title="Redo (Ctrl+Y)"
          :disabled="
            uiBusy ||
            !(activeView === 'analysis' ? state?.redo : projectHistory.redo)
          "
          @click="historyAction('redo')"
        >
          <AppIcon name="redo" />
        </button>
      </div>
      <div class="titlebar-project">
        <AppIcon name="folder" :size="15" /><span>{{ projectName }}</span
        ><span
          v-if="state?.dirty || state?.workspace_dirty"
          class="unsaved-dot"
          title="Unsaved changes"
        />
      </div>
      <div class="titlebar-actions">
        <span class="version-tag">DESKTOP PREVIEW</span
        ><button
          class="icon-button"
          :title="
            theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'
          "
          :aria-label="
            theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'
          "
          @click="theme = theme === 'dark' ? 'light' : 'dark'"
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
    </header>
    <div class="ribbon-tabs" role="tablist" aria-label="Workspace views">
      <button
        v-for="view in views"
        :key="view.key"
        role="tab"
        :id="'view-' + view.key"
        :aria-selected="activeView === view.key"
        :aria-controls="'tools-' + view.key"
        :class="{ active: activeView === view.key }"
        @click="switchView(view.key)"
      >
        {{ view.label }}
      </button>
      <span class="spacer" /><span
        class="engine-status"
        :class="{ online: connected }"
        ><i />{{
          connected ? "Calculation engine connected" : "Engine disconnected"
        }}</span
      >
    </div>
    <section
      class="ribbon"
      :id="'tools-' + activeView"
      role="tabpanel"
      :aria-labelledby="'view-' + activeView"
      :aria-label="
        (views.find((view) => view.key === activeView)?.label || '') + ' tools'
      "
    >
      <template v-if="activeView === 'analysis'">
        <div class="ribbon-group">
          <div class="ribbon-tools">
            <button
              class="ribbon-large"
              :disabled="!canEdit || !groups.length"
              @click="addResource"
            >
              <AppIcon name="resource" :size="24" /><span>Add resource</span>
            </button>
          </div>
          <small>RESOURCES</small>
        </div>
        <div class="ribbon-group">
          <div class="ribbon-tools">
            <button
              v-for="row in rowKinds"
              :key="row.kind"
              class="ribbon-large"
              :title="row.hint"
              :disabled="!canEdit"
              @click="w.command('add', { kind: row.kind, value: row.value })"
            >
              <AppIcon :name="row.icon" :size="24" /><span>{{
                row.label
              }}</span>
            </button>
          </div>
          <small>INSERT</small>
        </div>
        <div class="ribbon-group">
          <div class="ribbon-tools">
            <div class="ribbon-stack">
              <button
                :disabled="!canEdit || !selected.length"
                @click="w.command('copy')"
              >
                <AppIcon name="copy" />Copy rows</button
              ><button
                :disabled="!canEdit || !clipboardReady"
                @click="w.command('paste')"
              >
                <AppIcon name="paste" />Paste rows
              </button>
            </div>
            <div class="ribbon-stack">
              <button
                :disabled="!canEdit || !selected.length"
                @click="w.command('duplicate')"
              >
                <AppIcon name="plus" />Duplicate</button
              ><button
                :disabled="!canEdit || !selected.length"
                @click="w.command('delete')"
              >
                <AppIcon name="trash" />Delete
              </button>
            </div>
          </div>
          <small>EDIT</small>
        </div>
        <div class="ribbon-group">
          <div class="ribbon-tools">
            <button
              class="ribbon-large"
              :disabled="!canEdit || selected.length !== 1"
              @click="w.command('move', { delta: -1 })"
            >
              <AppIcon name="up" :size="24" /><span>Move up</span></button
            ><button
              class="ribbon-large"
              :disabled="!canEdit || selected.length !== 1"
              @click="w.command('move', { delta: 1 })"
            >
              <AppIcon name="down" :size="24" /><span>Move down</span>
            </button>
          </div>
          <small>SEQUENCE</small>
        </div>
        <div class="ribbon-group">
          <div class="ribbon-tools">
            <button
              class="ribbon-large"
              :disabled="!canEdit || !state?.project"
              @click="w.command('analysis.apply')"
            >
              <AppIcon name="check" :size="24" /><span
                >Apply analysis</span
              ></button
            ><button
              class="ribbon-large"
              :disabled="!canEdit || !state?.project"
              @click="exportAnalysisOpen = true"
            >
              <AppIcon name="file" :size="24" /><span>Export analysis</span>
            </button>
          </div>
          <small>PROJECT</small>
        </div>
      </template>
      <div
        id="project-ribbon-tools"
        class="ribbon-tools-host"
        v-show="activeView !== 'analysis'"
      />
    </section>
    <div v-if="error" class="error-banner" role="alert">
      <AppIcon name="help" /><span>{{ error }}</span
      ><button
        class="icon-button"
        aria-label="Dismiss error"
        @click="error = ''"
      >
        <AppIcon name="close" :size="16" />
      </button>
    </div>
    <div class="workspace">
      <aside v-show="sidebar" class="explorer">
        <div class="panel-heading">
          <span>PROJECT EXPLORER</span
          ><button
            class="icon-button"
            aria-label="Hide explorer"
            @click="sidebar = false"
          >
            <AppIcon name="panel" :size="15" />
          </button>
        </div>
        <div class="explorer-project">
          <span class="project-icon"><AppIcon name="folder" :size="20" /></span>
          <div>
            <strong>{{ projectName }}</strong
            ><small>{{
              state?.project_open ? "Project working copy" : "No project open"
            }}</small>
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
        <form
          class="search-field"
          @submit.prevent="
            explorer === 'schedule' ? w.searchSchedule() : w.searchResources()
          "
        >
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
          <span>{{
            explorer === "schedule" ? "SCHEDULE ITEMS" : "RESOURCE LIBRARY"
          }}</span
          ><span
            >{{
              (explorer === "schedule" ? schedule : resources).length
            }}
            shown</span
          >
        </div>
        <nav
          class="item-list"
          :aria-label="
            explorer === 'schedule' ? 'Schedule items' : 'Resource library'
          "
        >
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
                }}<span
                  v-if="state?.code === item.code"
                  class="item-active-dot" /></span
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
              @click="
                addResource();
                form.code = item.code;
                resourceTab = 'library';
                resourceQuery = item.code;
                w.searchResources();
              "
            >
              <span class="item-code"
                ><AppIcon name="resource" :size="14" />{{ item.code }}</span
              ><span class="item-description">{{ item.description }}</span
              ><span class="item-unit">{{ item.rate }} / {{ item.unit }}</span>
            </button></template
          >
          <div
            v-if="!(explorer === 'schedule' ? schedule : resources).length"
            class="empty-explorer"
          >
            <AppIcon
              :name="state?.project_open ? 'search' : 'folder'"
              :size="30"
            /><strong>{{
              state?.project_open
                ? "No items to show"
                : "Your project starts here"
            }}</strong>
            <p>
              {{
                state?.project_open
                  ? "Search by code or description."
                  : "Open a GEstimator project to explore its schedule and resources."
              }}
            </p>
            <button
              v-if="!state?.project_open"
              class="button secondary"
              :disabled="uiBusy"
              @click="showFile('open')"
            >
              Open project
            </button>
          </div>
        </nav>
        <div v-if="state?.project_open" class="pagination">
          <button
            class="icon-button"
            aria-label="Previous page"
            :disabled="
              busy ||
              (explorer === 'schedule' ? schedulePage : resourcePage) === 0
            "
            @click="
              explorer === 'schedule'
                ? w.searchSchedule(schedulePage - 1)
                : w.searchResources(resourcePage - 1)
            "
          >
            <AppIcon name="up" :size="15" /></button
          ><span
            >Page
            {{
              (explorer === "schedule" ? schedulePage : resourcePage) + 1
            }}</span
          ><button
            class="icon-button"
            aria-label="Next page"
            :disabled="
              busy ||
              (explorer === 'schedule' ? schedule : resources).length < 100
            "
            @click="
              explorer === 'schedule'
                ? w.searchSchedule(schedulePage + 1)
                : w.searchResources(resourcePage + 1)
            "
          >
            <AppIcon name="down" :size="15" />
          </button>
        </div>
        <div class="explorer-foot">
          <AppIcon name="check" :size="14" /><span
            >Isolated working copy</span
          >
        </div>
      </aside>
      <main class="editor-pane">
        <ProjectViews
          ref="projectView"
          v-if="activeView !== 'analysis'"
          :view="activeView"
          :project-open="!!state?.project_open"
          @changed="w.refresh()"
          @history="projectHistory = $event"
          @busy="projectBusy = $event"
          @analysis="loadAnalysis"
        />
        <div v-show="activeView === 'analysis'" class="analysis-content">
          <div class="analysis-intro">
            <div class="breadcrumbs">
              Workspace<AppIcon name="chevron" :size="12" />{{ projectName
              }}<AppIcon name="chevron" :size="12" /><span>Rate analysis</span>
            </div>
            <div class="analysis-heading">
              <div>
                <div class="eyebrow">
                  RATE ANALYSIS<span v-if="state?.code" class="code-tag">{{
                    state.code
                  }}</span>
                </div>
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
                ><i />{{
                  state?.dirty ? "Unsaved changes" : "Up to date"
                }}</span
              >
            </div>
            <div class="analysis-metadata">
              <span
                ><AppIcon name="resource" :size="14" />{{
                  resourceCount
                }}
                resources</span
              ><span
                ><AppIcon name="group" :size="14" />{{
                  groups.length
                }}
                groups</span
              ><span v-if="state?.unit"
                >Unit <b>{{ state.unit }}</b></span
              ><span class="metadata-last"
                ><AppIcon name="check" :size="14" />Calculated in project
                order</span
              >
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
                ><span>{{
                  selected.length
                    ? selected.length + " selected"
                    : "Double-click a cell to edit"
                }}</span>
              </div>
              <button
                class="button small secondary"
                :disabled="!canEdit || !groups.length"
                @click="addResource"
              >
                <AppIcon name="plus" :size="15" />Add resource</button
              ><button
                class="icon-button"
                :title="expanded ? 'Collapse groups' : 'Expand groups'"
                :aria-label="expanded ? 'Collapse groups' : 'Expand groups'"
                @click="expanded = !expanded"
              >
                <AppIcon :name="expanded ? 'collapse' : 'expand'" :size="16" />
              </button>
            </div>
            <AnalysisTable
              ref="analysisTable"
              :rows="state?.rows || []"
              :busy="busy || !connected"
              :compact="compact"
              :expanded="expanded"
              @selection="selected = $event"
              @edit="edit"
              @action="w.command($event)"
            />
            <div class="table-caption">
              <span><i class="legend-dot group" />Group</span
              ><span><i class="legend-dot subtotal" />Subtotal</span
              ><span><i class="legend-dot adjustment" />Adjustment</span
              ><span class="spacer" /><span
                >{{ state?.rows.length || 0 }} calculation rows</span
              >
            </div>
          </section>
          <div class="rate-summary">
            <div class="summary-icon"><AppIcon name="sum" :size="22" /></div>
            <div>
              <strong>Calculated unit rate</strong
              ><small>Final result of the analysis sequence</small>
            </div>
            <span class="spacer" />
            <div class="summary-value">
              <strong>{{ state?.rate || "0.00" }}</strong
              ><span v-if="state?.unit">/ {{ state.unit }}</span>
            </div>
          </div>
        </div>
      </main>
      <aside v-show="inspector && activeView === 'analysis'" class="inspector">
        <div class="panel-heading">
          <span>INSPECTOR</span
          ><button
            class="icon-button"
            aria-label="Hide inspector"
            @click="inspector = false"
          >
            <AppIcon name="close" :size="15" />
          </button>
        </div>
        <div v-if="selection" class="inspector-body" :key="selection.id">
          <span class="row-badge" :class="'kind-' + selectedKind">{{
            selection.kind
          }}</span>
          <h2>
            {{ selection.code || selection.description || selection.kind }}
          </h2>
          <p class="inspector-hint">{{ selectionHint }}</p>
          <label
            v-if="selection.kind === 'Group' || selection.kind === 'Resource'"
            class="field"
            >{{
              selection.kind === "Group"
                ? "Group code"
                : "Resource code (replace entry)"
            }}<input
              :value="selection.code"
              :disabled="uiBusy"
              @change="editField($event, 'code')"
          /></label>
          <label class="field"
            >Description<textarea
              :value="selection.description"
              :disabled="uiBusy"
              rows="4"
              @change="editField($event, 'description')"
            /></label
          ><template v-if="!['Group', 'Subtotal'].includes(selection.kind)"
            ><label class="field"
              >{{
                selection.kind === "Resource"
                  ? "Quantity"
                  : selection.kind === "Round"
                    ? "Rounding places"
                    : "Factor"
              }}<input
                :value="selection.value"
                :disabled="uiBusy"
                inputmode="decimal"
                @change="editField($event, 'value')" /></label></template
          ><template v-if="selection.kind === 'Resource'"
            ><div class="field-pair">
              <label class="field"
                >Unit<input
                  :value="selection.unit"
                  :disabled="uiBusy"
                  @change="editField($event, 'unit')" /></label
              ><label class="field"
                >Base rate<input
                  :value="selection.rate"
                  :disabled="uiBusy"
                  inputmode="decimal"
                  @change="editField($event, 'rate')"
              /></label>
            </div>
            <div class="field-pair">
              <label class="field"
                >VAT %<input
                  :value="selection.vat"
                  :disabled="uiBusy"
                  inputmode="decimal"
                  @change="editField($event, 'vat')" /></label
              ><label class="field"
                >Discount %<input
                  :value="selection.discount"
                  :disabled="uiBusy"
                  inputmode="decimal"
                  @change="editField($event, 'discount')"
              /></label>
            </div>
            <div class="inspector-result">
              <span>Effective rate</span
              ><strong>{{ selection.effective_rate }}</strong>
            </div></template
          >
          <div class="inspector-result">
            <span>Calculated amount</span
            ><strong>{{ selection.amount }}</strong>
          </div>
          <div class="inspector-actions">
            <button
              class="button secondary"
              :disabled="uiBusy"
              @click="w.command('move', { delta: -1 })"
            >
              <AppIcon name="up" :size="15" />Move up</button
            ><button
              class="button secondary"
              :disabled="uiBusy"
              @click="w.command('move', { delta: 1 })"
            >
              <AppIcon name="down" :size="15" />Move down
            </button>
          </div>
          <button
            class="button danger full-width"
            :disabled="uiBusy"
            @click="w.command('delete')"
          >
            <AppIcon name="trash" :size="15" />Delete row
          </button>
        </div>
        <div v-else class="inspector-empty">
          <span class="inspector-empty-icon"
            ><AppIcon name="panel" :size="28"
          /></span>
          <h3>
            {{ selected.length ? "Multiple rows selected" : "A closer look" }}
          </h3>
          <p>
            {{
              selected.length
                ? "Use the ribbon to copy, duplicate or delete your selection."
                : "Select a row to edit its properties and inspect calculated values."
            }}
          </p>
          <div class="inspector-tip">
            <AppIcon name="help" :size="17" /><span
              >Use Ctrl / ⌘ + click to select multiple rows.</span
            >
          </div>
        </div>
        <div class="inspector-bottom">
          <span class="eyebrow">CALCULATION NOTES</span>
          <p>
            Weighted additions use the latest group or subtotal as their base.
            Totals follow the row sequence.
          </p>
          <button class="text-button" @click="helpOpen = true">
            Keyboard shortcuts<AppIcon name="chevron" :size="12" />
          </button>
        </div>
      </aside>
    </div>
    <footer class="statusbar" role="status">
      <span
        class="status-indicator"
        :class="{ working: busy, offline: !connected }"
      /><span>{{ status }}</span
      ><span
        v-if="state?.dirty || state?.workspace_dirty"
        class="status-unsaved"
        >Unsaved draft</span
      ><span class="spacer" /><span>Tab to navigate</span
      ><span class="status-divider" /><span>Ctrl + K to find</span
      ><span class="status-divider" /><span>{{
        state?.unit || "GEstimator"
      }}</span>
    </footer>
  </div>
  <Dialog
    :visible="fileMode !== null"
    modal
    :header="fileMode === 'open' ? 'Open project' : 'Save project copy'"
    class="workspace-dialog file-dialog"
    @update:visible="fileMode = null"
    ><p class="dialog-intro">
      {{
        fileMode === "open"
          ? "Choose an existing GEstimator project. You will edit a working copy."
          : "Save your analysis and dependent rates to a new project file."
      }}
    </p>
    <form @submit.prevent="submitFile">
      <label class="field"
        >Project file
        <div class="file-input">
          <input
            v-model="filePath"
            :placeholder="
              fileMode === 'open'
                ? '/path/to/project.eproj'
                : '/path/to/project-edited.eproj'
            "
            required
            autofocus
          /><button type="button" class="button secondary" @click="browse">
            <AppIcon name="folder" :size="16" />Browse
          </button>
        </div></label
      >
      <div v-if="error" class="dialog-error" role="alert">{{ error }}</div>
      <p class="field-hint">
        {{
          fileMode === "save"
            ? "Choose a new filename. Existing files cannot be overwritten."
            : "Supports version 2 .eproj projects."
        }}
      </p>
      <label v-if="fileMode === 'open' && recentProjects.length" class="field">
        Recent projects
        <select aria-label="Recent projects" :value="recentProjects.includes(filePath) ? filePath : ''"
          @change="filePath = ($event.target as HTMLSelectElement).value">
          <option value="">Choose a recent project</option>
          <option v-for="path in recentProjects" :key="path" :value="path">{{ path }}</option>
        </select>
        <button type="button" class="button secondary" @click="setRecentProjects([])">Clear recent projects</button>
      </label>
      <div v-if="fileMode === 'open' && recoveryProjects.length" class="field">
        <strong>Recover unsaved work</strong>
        <button v-for="copy in recoveryProjects" :key="copy.id" type="button"
          class="button secondary" :disabled="uiBusy" @click="recoverProject(copy.id)">
          Recover project from {{ new Date(copy.updated * 1000).toLocaleString() }}
        </button>
      </div>
      <div class="dialog-footer">
        <button type="button" class="button secondary" @click="fileMode = null">
          Cancel</button
        ><button class="button primary" :disabled="uiBusy || !filePath.trim()">
          <AppIcon
            :name="fileMode === 'open' ? 'folder' : 'save'"
            :size="16"
          />{{
            busy
              ? "Working…"
              : fileMode === "open"
                ? "Open project"
                : "Save copy"
          }}
        </button>
      </div>
    </form></Dialog
  >
  <Dialog
    v-model:visible="resourceOpen"
    modal
    header="Add resource"
    class="workspace-dialog resource-dialog"
    ><p class="dialog-intro">
      Add an existing library resource or create a custom definition.
    </p>
    <label class="field"
      >Destination group<select v-model="groupId">
        <option v-for="group in groups" :key="group.id" :value="group.id">
          {{ group.description }}
        </option>
      </select></label
    >
    <div class="dialog-tabs" role="tablist" aria-label="Resource source">
      <button
        role="tab"
        :aria-selected="resourceTab === 'library'"
        :class="{ active: resourceTab === 'library' }"
        @click="
          resourceTab = 'library';
          if (state?.project_open) w.searchResources();
        "
      >
        From library</button
      ><button
        role="tab"
        :aria-selected="resourceTab === 'custom'"
        :class="{ active: resourceTab === 'custom' }"
        @click="resourceTab = 'custom'"
      >
        Custom resource
      </button>
    </div>
    <label v-if="resourceTab === 'library'" class="field"
      >Resource source<select
        v-model="resourceSource"
        @change="w.searchResources()"
      >
        <option value="">Project resources</option>
        <option
          v-for="library in state?.libraries"
          :key="library.id"
          :value="library.id"
        >
          {{ library.name }}
        </option>
      </select></label
    >
    <template v-if="resourceTab === 'library'"
      ><form class="search-field" @submit.prevent="w.searchResources()">
        <AppIcon name="search" :size="16" /><input
          v-model="resourceQuery"
          placeholder="Search code or description…"
          aria-label="Search library"
        /><button
          class="button small secondary"
          :disabled="uiBusy || !state?.project_open"
        >
          Search
        </button>
      </form>
      <div class="resource-results">
        <button
          v-for="item in resources"
          :key="item.code"
          :disabled="uiBusy || !resourceTarget"
          @click="insertResource(item.code)"
        >
          <span
            ><b>{{ item.code }}</b
            ><small>{{ item.description }}</small></span
          ><span class="resource-price"
            >{{ item.rate }}<small>/ {{ item.unit }}</small></span
          ><AppIcon name="plus" :size="17" />
        </button>
        <div v-if="!resources.length" class="empty-library">
          {{
            state?.project_open
              ? "Search your project library to find a resource."
              : "Open a project to browse its resource library, or create a custom resource."
          }}
        </div>
      </div>
      <div class="pagination">
        <button
          class="text-button"
          :disabled="uiBusy || !resourcePage"
          @click="w.searchResources(resourcePage - 1)"
        >
          Previous</button
        ><span>Page {{ resourcePage + 1 }}</span
        ><button
          class="text-button"
          :disabled="uiBusy || resources.length < 100"
          @click="w.searchResources(resourcePage + 1)"
        >
          Next
        </button>
      </div></template
    >
    <form v-else @submit.prevent="insertResource()">
      <div class="field-pair">
        <label class="field"
          >Resource code<input
            v-model="form.code"
            required
            placeholder="e.g. MAT-001" /></label
        ><label class="field"
          >Unit<input v-model="form.unit" required placeholder="e.g. kg"
        /></label>
      </div>
      <label class="field"
        >Description<textarea
          v-model="form.description"
          required
          rows="3"
          placeholder="Describe the material, labour or equipment"
        />
      </label>
      <div class="field-pair">
        <label class="field"
          >Base rate<input
            v-model="form.rate"
            inputmode="decimal"
            required /></label
        ><label class="field"
          >Quantity<input v-model="form.qty" inputmode="decimal" required
        /></label>
      </div>
      <div class="field-pair">
        <label class="field"
          >VAT %<input v-model="form.vat" inputmode="decimal" /></label
        ><label class="field"
          >Discount %<input v-model="form.discount" inputmode="decimal"
        /></label>
      </div>
      <div v-if="error" class="dialog-error" role="alert">{{ error }}</div>
      <div class="dialog-footer">
        <button
          type="button"
          class="button secondary"
          @click="resourceOpen = false"
        >
          Cancel</button
        ><button class="button primary" :disabled="uiBusy || !resourceTarget">
          <AppIcon name="plus" :size="16" />Add resource
        </button>
      </div>
    </form></Dialog
  >
  <Dialog
    :visible="discardOpen"
    modal
    header="Keep your analysis changes?"
    class="workspace-dialog file-dialog"
    @update:visible="cancelDiscard"
    ><p class="dialog-intro">
      This workspace has unsaved changes. Save them before continuing, or discard the pending changes.
    </p>
    <div v-if="error" class="dialog-error" role="alert">{{ error }}</div>
    <div class="dialog-footer">
      <button
        class="button secondary"
        :disabled="uiBusy"
        @click="cancelDiscard"
      >
        Keep editing</button
      ><button class="button danger" :disabled="uiBusy" @click="discard">
        Discard changes</button
      ><button
        v-if="!pendingProject && state?.project"
        class="button secondary"
        :disabled="uiBusy"
        @click="applyAndContinue"
      >
        Apply and continue</button
      ><button
        v-if="state?.source_path"
        class="button secondary"
        :disabled="uiBusy"
        @click="saveProject"
      >
        Save project
      </button><button
        class="button primary"
        :disabled="uiBusy || !state?.project_open"
        @click="showFile('save')"
      >
        Save copy…
      </button>
    </div></Dialog
  >
  <Dialog
    v-model:visible="helpOpen"
    modal
    header="Keyboard shortcuts"
    class="workspace-dialog file-dialog"
    ><div class="shortcut-list">
      <div
        v-for="[label, key] in [
          ['Open project', 'Ctrl / ⌘ + O'],
          ['Save project', 'Ctrl / ⌘ + S'],
          ['Save project copy', 'Ctrl / ⌘ + Shift + S'],
          ['Find schedule or resource', 'Ctrl / ⌘ + K'],
          ['Undo / Redo', 'Ctrl / ⌘ + Z / Y'],
          ['Copy / Paste rows', 'Ctrl / ⌘ + C / V'],
          ['Duplicate selected rows', 'Ctrl / ⌘ + D'],
          ['Delete selected rows', 'Delete'],
          ['Navigate editable cells', 'Tab / Shift + Tab'],
        ]"
        :key="label"
      >
        <span>{{ label }}</span
        ><kbd>{{ key }}</kbd>
      </div>
    </div>
    <p class="field-hint">
      Text fields keep their normal editing shortcuts. Row paste uses the
      selected resource group.
    </p></Dialog
  >

  <Dialog
    v-model:visible="duplicateOpen"
    modal
    header="Duplicate resource definition"
    class="workspace-dialog file-dialog"
    ><p class="dialog-intro">
      Creates an independent definition under a new code, inserted after this
      entry with zero quantity.
    </p>
    <label class="field"
      >New resource code<input v-model="duplicateCode"
    /></label>
    <div v-if="error" class="dialog-error">{{ error }}</div>
    <div class="dialog-footer">
      <button
        class="button primary"
        :disabled="uiBusy || !duplicateCode"
        @click="
          w
            .command('resource.duplicate', { code: duplicateCode })
            .then((ok) => {
              if (ok) duplicateOpen = false;
            })
        "
      >
        Create independent resource
      </button>
    </div></Dialog
  >
  <Dialog
    v-model:visible="exportAnalysisOpen"
    modal
    header="Export analysis to Excel"
    class="workspace-dialog file-dialog"
    ><label class="field"
      >New Excel file
      <div class="file-input">
        <input
          v-model="exportAnalysisPath"
          placeholder="/path/to/analysis.xlsx"
        /><button
          class="button secondary"
          @click="
            save({
              filters: [{ name: 'Excel workbook', extensions: ['xlsx'] }],
            }).then((path) => {
              if (path) exportAnalysisPath = path;
            })
          "
        >
          Browse
        </button>
      </div></label
    >
    <div v-if="error" class="dialog-error">{{ error }}</div>
    <div class="dialog-footer">
      <button
        class="button primary"
        :disabled="uiBusy || !exportAnalysisPath"
        @click="exportAnalysis"
      >
        Export analysis
      </button>
    </div></Dialog
  >

  <Dialog
    v-model:visible="settingsOpen"
    modal
    header="Project settings"
    class="workspace-dialog file-dialog"
    ><label v-for="(value, key) in settings" :key="key" class="field"
      >{{ String(key).replaceAll("_", " ") }}<input v-model="settings[key]"
    /></label>
    <div v-if="error" class="dialog-error">{{ error }}</div>
    <div class="dialog-footer">
      <button class="button primary" :disabled="uiBusy" @click="saveSettings">
        Apply settings
      </button>
    </div></Dialog
  >
</template>
