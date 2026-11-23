<script setup lang="ts">
import { computed, nextTick, onMounted, onBeforeUnmount, ref, watch } from "vue";
import Dialog from "primevue/dialog";
import MeasurementRecordLayout from "./MeasurementRecordLayout.vue";
import MeasurementRecordRibbon from "./MeasurementRecordRibbon.vue";
import MeasurementPropertiesDialog from "./MeasurementPropertiesDialog.vue";
import type { ColumnDefinition, CellComponent } from "tabulator-tables";
import DataTable from "./DataTable.vue";
import AppIcon from "./AppIcon.vue";
import ProjectListRibbon from "./ProjectListRibbon.vue";
import ProjectImportDialogs from "./ProjectImportDialogs.vue";
import ResourceEditingDialogs from "./ResourceEditingDialogs.vue";
import ScheduleRateDiscrepancies from "./ScheduleRateDiscrepancies.vue";
import ScheduleEditingDialogs from "./ScheduleEditingDialogs.vue";
import ProjectDeletionDialog from "./ProjectDeletionDialog.vue";
import ProjectItemDialogs from "./ProjectItemDialogs.vue";
import ResourceUsage from "./ResourceUsage.vue";
import CategoryFilter from "./CategoryFilter.vue";
import { request } from "../backend";
import type { DataTableHandle, TableRow } from "../dataTableTypes";
import { groupMeasurementRows } from "../projectGridRows";
import { resourceItemFields, scheduleItemFields } from "../projectViewTypes";
import type {
  GridRow,
  GridState,
  ProjectItemField,
  View,
  ViewMemory,
  MeasurementTemplate,
  ProjectDatabaseSelection,
  ProjectItemMode,
} from "../projectViewTypes";
import { useMeasurementRecords } from "../useMeasurementRecords";
import { afterDialogsClose } from "../uiActions";
import { programSettings } from "../programSettings";
import { exportWithWorkbookChooser } from "../workbookExport";
import { useProjectGrid } from "../useProjectGrid";
import { projectViewShortcut } from "../projectViewShortcuts";
import { formatMoney } from "../numberFormatting";
import { vMiddleEllipsis } from "../middleEllipsis";
import { clearRowClipboard, copyRows, pasteRows, type ClipboardKind } from "../rowClipboard";
import { notify } from "../statusNotice";
import { activeDocument } from "../documents";
import { recallTabState, rememberTabState } from "../tabMemory";

const props = withDefaults(defineProps<{ view: View; projectOpen: boolean; active?: boolean; entryId?: string }>(), {
  active: true,
});
const emit = defineEmits<{
  changed: [];
  busy: [value: boolean];
  analysis: [code: string];
  entry: [id: string | undefined];
  history: [state: { undo: boolean; redo: boolean }];
  libraries: [];
  database: [selection: ProjectDatabaseSelection];
  analysisRules: [ids: string[]];
  applyRecords: [];
  discardRecords: [];
}>();
const state = ref<GridState>();
const rateDiscrepancies = ref<InstanceType<typeof ScheduleRateDiscrepancies>>();

const emptyRows: [] = [];
watch(
  () => [state.value?.undo, state.value?.redo, state.value?.measurement_draft, props.entryId, props.active],
  () =>
    emit("history", {
      undo: !!(props.entryId ? state.value?.measurement_draft?.undo : state.value?.undo),
      redo: !!(props.entryId ? state.value?.measurement_draft?.redo : state.value?.redo),
    }),
);
onBeforeUnmount(() => emit("history", { undo: false, redo: false }));
defineExpose({
  reload: () => refreshChanges(),
  focus: focusTable,
  revealCode: (code: string) => revealCode(code),
  handleKeyboard: keyboard,
  historyAction,
  applyRecords: (finish = false) => (finish ? finishRecords("apply") : command("draft.apply")),
  discardRecords: () => finishRecords("discard"),
  applyDatabase,
  lastError: () => error.value,
  exportWorkbook,
});
const busy = ref(false);
watch(busy, (value) => emit("busy", value));
onBeforeUnmount(() => emit("busy", false));
onBeforeUnmount(() => {
  const table = mainTable.value?.viewState();
  const records = rememberRecords();
  if (table && !source.value)
    rememberTabState(documentId, memoryKey, {
      query: query.value,
      categoryFilters: categoryFilters.value,
      page: page.value,
      table,
      records,
    } satisfies ViewMemory);
});
const error = ref("");
// View state saved when this project tab was switched away (see tabMemory.ts).
const documentId = activeDocument.value;
const memoryKey = "view:" + props.view;
const remembered = recallTabState<ViewMemory>(memoryKey);
const query = ref(remembered?.query ?? "");
const categoryFilters = ref<string[]>(remembered?.categoryFilters ?? []);
const source = ref("");
const usageOpen = ref(false);
const usageCode = ref<string>();
const page = ref(remembered?.page ?? 0);
const selected = ref<GridRow[]>([]);
const templates = ref<MeasurementTemplate[]>([]);
const mainTable = ref<DataTableHandle<GridRow>>();
const resourceEditingDialogs = ref<InstanceType<typeof ResourceEditingDialogs>>();
const scheduleEditingDialogs = ref<InstanceType<typeof ScheduleEditingDialogs>>();
const projectDeletionDialog = ref<InstanceType<typeof ProjectDeletionDialog>>();
const projectItemDialogs = ref<InstanceType<typeof ProjectItemDialogs>>();
const projectImportDialogs = ref<InstanceType<typeof ProjectImportDialogs>>();
const selectionIds = ref<string[]>();
const workingSelection = ref<string[]>([]);

const quantityRounding = ref("Round to .000");
const editableFields = computed<ProjectItemField[]>(() => [
  ...(props.view === "resources" ? resourceItemFields : scheduleItemFields),
]);
const one = computed(() => (selected.value.length === 1 ? selected.value[0] : undefined));
const selectedSchedule = computed(() => (one.value?.rowtype === "Schedule" ? one.value : undefined));
const selectedScheduleIds = computed(() =>
  selected.value.filter((row) => row.rowtype === "Schedule").map((row) => row.id),
);
const title = computed(
  () =>
    ({
      schedule: "Schedule of quantities",
      resources: "Resource library",
      measurement: "Measurements",
    })[props.view],
);
const isMeasurement = computed(() => props.view === "measurement");
const measurementCategories = computed(() =>
  isMeasurement.value ? groupMeasurementRows(state.value?.rows.filter((row) => !row.rowtype) ?? emptyRows) : emptyRows,
);
const mainRows = computed<GridRow[]>(() => {
  if (isMeasurement.value) return measurementCategories.value;
  const rows = state.value?.rows ?? emptyRows;
  return rateDiscrepancies.value?.highlight(rows) ?? rows;
});
const recordLayout = ref<InstanceType<typeof MeasurementRecordLayout>>();
// Measurement owners reuse this view's single command and busy/error boundary.
const {
  selectedRecord,
  selectedRecords,
  recordSelectionIds,
  activeMeasurement,
  recordPage,
  recordCount,
  recordsOpen,
  detailBusy,
  recordTable,
  descriptionDraft,
  recordRows,
  recordColumns,
  editMeasurementDescription,
  finishMeasurementDescription,
  syncMeasurementSummary,
  finishRecords,
  loadDetail,
  changeRecordPage,
  recordEdit,
  recordAction,
  restoreRecords,
  rememberRecords,
  invalidateDetail,
} = useMeasurementRecords({
  state,
  busy,
  error,
  selected,
  selectionIds,
  entryId: () => props.entryId,
  remembered: remembered?.records,
  command,
  run,
  focus: focusTable,
  focusDescription: () => recordLayout.value?.focusDescription(),
  changed: () => emit("changed"),
});
const measurementPropertiesDialog = ref<InstanceType<typeof MeasurementPropertiesDialog>>();
const measurementPropertiesContext = { state, one, error, activeMeasurement, command, loadDetail };

const { libraries, refresh, refreshChanges, revealCode, findAcross, load, search, goToPage } = useProjectGrid({
  props,
  state,
  busy,
  isMeasurement,
  query,
  categoryFilters,
  source,
  page,
  selectionIds,
  mainTable,
  rememberedTable: remembered?.table,
  activeMeasurement,
  recordPage,
  syncMeasurementSummary,
  restoreRecords,
  run,
  changed: () => emit("changed"),
});

let cancelFocus: (() => void) | undefined;
onBeforeUnmount(() => cancelFocus?.());
async function focusTable() {
  cancelFocus?.();
  await nextTick();
  if (!props.active) return;
  cancelFocus = afterDialogsClose(async () => {
    if (props.active) await (props.entryId ? recordTable.value : mainTable.value)?.focus();
  });
}

function editable(cell: CellComponent) {
  const row: Pick<TableRow, "rowtype"> = cell.getData();
  return row.rowtype !== "Category";
}
const columns = computed<ColumnDefinition[]>(() => {
  if (isMeasurement.value)
    return [
      {
        title: "DESCRIPTION / REMARKS",
        field: "description",
        minWidth: 260,
      },
      { title: "TYPE", field: "type", width: 180 },
      { title: "RECORDS", field: "count", width: 90 },
      { title: "TOTALS", field: "totals", width: 180 },
    ];
  const fields =
    props.view === "resources"
      ? ["code", "description", "unit", "rate", "vat", "discount", "reference"]
      : ["code", "description", "unit", "rate", "qty", "amount", "remarks"];
  return fields.map((field) => ({
    title: field === "vat" ? "TAX %" : field.toUpperCase(),
    field,
    minWidth: field === "description" ? 280 : 95,
    widthGrow: field === "description" ? 3 : 1,
    editor: field === "amount" ? undefined : field === "description" || field === "remarks" ? "textarea" : "input",
    editable: (cell) => !source.value && (field === "description" || editable(cell)),
    formatter: ["qty", "rate"].includes(field)
      ? (cell) => {
          const value = String(cell.getValue() ?? "");
          return value !== "" && Number(value) === 0 ? "" : value;
        }
      : "textarea",
    hozAlign: ["qty", "rate", "amount", "vat", "discount"].includes(field) ? "right" : "left",
  }));
});
async function run(work: () => Promise<void>) {
  if (busy.value) return false;
  busy.value = true;
  error.value = "";
  try {
    await work();
    return true;
  } catch (e) {
    error.value = String(e);
    // Cell editors update their local value before the backend accepts it.
    // Restore authoritative rows after a rejected edit or atomic batch.
    if (props.projectOpen) await refresh().catch(() => {});
    return false;
  } finally {
    busy.value = false;
  }
}
const rowActions = computed(() =>
  source.value
    ? []
    : [
        { label: "Add item after selection", action: "add" },
        ...(props.view === "schedule"
          ? [
              { label: "Add subitem", action: "child", itemOnly: true, single: true },
              { label: "Open analysis", action: "activate", itemOnly: true, single: true, leafOnly: true },
            ]
          : [
              {
                label: isMeasurement.value ? "Measurement properties…" : "Edit resource…",
                action: "properties",
                single: true,
                itemOnly: !isMeasurement.value,
              },
            ]),
        ...(props.view === "resources" ? [{ label: "Cut selected resources", action: "cut", itemOnly: true }] : []),
        { label: "Copy selected rows", action: "copy" },
        { label: "Paste rows here", action: "paste" },
        {
          label: "Duplicate selection",
          action: "duplicate",
          single: !isMeasurement.value,
          itemOnly: !isMeasurement.value,
        },
        { label: "Delete selection…", action: "delete" },
      ],
);
function rowAction(operation: string) {
  if (operation === "add") void showForm();
  else if (operation === "child") void showSubitem();
  else if (operation === "activate" && one.value) activateRow(one.value);
  else if (operation === "properties") {
    if (isMeasurement.value) measurementPropertiesDialog.value?.showProperties();
    else if (one.value?.rowtype !== "Category") void showForm("edit");
  } else if (operation === "delete") void deleteSelection();
  else if (operation === "duplicate" && !isMeasurement.value) {
    if (one.value && one.value.rowtype !== "Category") void showForm("duplicate");
  } else void command(operation);
}
function selectedItemIds() {
  return [
    ...new Set(
      selected.value.flatMap((row) =>
        isMeasurement.value && row.rowtype === "Category"
          ? [row.id, ...row._children.map((item) => item.id)]
          : [row.id],
      ),
    ),
  ].filter((id) => id !== "measurement:uncategorised");
}
async function command(operation: string, params: Record<string, unknown> = {}) {
  return run(async () => {
    const ids =
      isMeasurement.value && (operation === "add" || operation === "paste")
        ? selected.value.map((row) => row.id)
        : selectedItemIds();
    const clipboardParams = {
      revision: state.value?.revision,
      id: one.value?.id,
      ids,
      source: source.value,
      ...params,
    };
    const clipboardKind: ClipboardKind = operation.startsWith("record_") ? "records" : props.view;
    let result: { selected?: string[]; selected_records?: string[]; record_offset?: number } | undefined;
    if (operation === "copy" || operation === "record_copy") {
      notify(await copyRows(clipboardKind, clipboardParams));
      return;
    } else if (operation === "cut") {
      // GTK ResourceView: cut stores a reference; Paste moves the resources.
      await copyRows("resources", {
        ...clipboardParams,
        ids: selected.value.filter((row) => row.rowtype !== "Category").map((row) => row.id),
        cut: true,
      });
      notify("Resources cut. Select a resource or category and paste to move them.");
      return;
    } else if (operation === "paste" || operation === "record_paste") {
      const pasted = await pasteRows(clipboardKind, clipboardParams);
      result = pasted;
      if (pasted.moved) {
        await clearRowClipboard();
        notify("Resources moved.");
      } else
        notify(
          pasted.unlinked
            ? `Rows pasted. ${pasted.unlinked} missing schedule links were cleared; records and remarks were retained.`
            : "Rows pasted.",
          pasted.unlinked ? 10000 : 5000,
        );
    } else
      result = await request(
        operation.startsWith("project.")
          ? operation
          : (isMeasurement.value ? "measurement." : props.view + ".editor.") + operation,
        {
          revision: state.value?.revision,
          id: one.value?.id,
          ids,
          source: source.value,
          target_ids: workingSelection.value,
          ...(isMeasurement.value && operation === "move" && one.value?.rowtype === "Category"
            ? { category: true }
            : {}),
          ...params,
        },
      );
    if (result?.selected && isMeasurement.value) {
      activeMeasurement.value = result.selected.length === 1 ? result.selected[0] : undefined;
      recordPage.value = 0;
    }
    if (result?.record_offset !== undefined) recordPage.value = result.record_offset / 100;
    if (result?.selected && !isMeasurement.value) {
      query.value = "";
      categoryFilters.value = [];
    }
    if (!isMeasurement.value && !result?.selected && state.value?.view_seq !== undefined) await refreshChanges();
    else {
      const first = result?.selected?.[0];
      await refresh(!isMeasurement.value && !first?.startsWith("cat:") ? first : undefined);
    }
    if (result?.selected) selectionIds.value = result.selected;
    if (result?.selected_records) recordSelectionIds.value = result.selected_records;
    if (operation === "delete") {
      selected.value = [];
      activeMeasurement.value = undefined;
    }
    if (operation === "record_delete") selectedRecord.value = undefined;
    emit("changed");
  });
}
function deleteSelection() {
  if (!state.value) return;
  const revision = state.value.revision;
  if (isMeasurement.value) {
    const categories = selected.value.filter((row) => row.rowtype === "Category").length;
    if (categories) return projectDeletionDialog.value?.show(selectedItemIds(), revision, categories);
    return command("delete");
  }
  return projectDeletionDialog.value?.show(
    selected.value.map((row) => row.id),
    revision,
  );
}
watch(
  () => props.active,
  async (active) => {
    if (active) {
      await refreshChanges();
      await focusTable();
    } else cancelFocus?.();
  },
);
function showPriceUpdate() {
  showDatabase("rates");
}
function showDatabase(mode: ProjectDatabaseSelection["mode"] = "add") {
  if (!state.value || isMeasurement.value) return;
  error.value = "";
  emit("database", {
    kind: props.view === "resources" ? "resources" : "schedule",
    mode,
    revision: state.value.revision,
    targetIds: selected.value.map((row) => row.id),
  });
}
async function applyDatabase(params: Record<string, unknown>) {
  const { operation, ...values } = params;
  return command(String(operation), { ...values, ...(values.modify ? { settings: programSettings.value } : {}) });
}
async function select(rows: GridRow[]) {
  if (!rows.length && !selected.value.length) return;
  selected.value = rows;
  if (isMeasurement.value && rows.length === 1 && activeMeasurement.value !== rows[0].id) {
    activeMeasurement.value = rows[0].id;
    recordPage.value = 0;
    selectedRecord.value = undefined;
    selectedRecords.value = [];
    recordSelectionIds.value = undefined;
    if (props.entryId) await loadDetail();
  }
}
function showForm(mode: ProjectItemMode = "add", child = false) {
  return projectItemDialogs.value?.showItem(
    mode,
    one.value,
    selected.value.map((row) => row.id),
    child,
  );
}

function showSubitem() {
  if (props.view !== "schedule" || !one.value || one.value.rowtype === "Category") return;
  return showForm("add", true);
}
function activateRow(row: GridRow) {
  if (source.value) return;
  if (row.rowtype === "Category") {
    if (isMeasurement.value && row.id !== "measurement:uncategorised") {
      selected.value = [row];
      selectionIds.value = [row.id];
      void measurementPropertiesDialog.value?.showProperties();
    }
    return;
  }
  if (row.rowtype === "Schedule") {
    if (row.has_children) notify(`Item ${row.code} has subitems; open the analysis of a subitem instead.`);
    else emit("analysis", row.code);
  } else if (props.view === "resources") void showForm("edit");
  else if (row.type !== "Heading") emit("entry", row.id);
  else measurementPropertiesDialog.value?.showProperties();
}
async function edit(row: GridRow, field: string, value: string) {
  return command("edit", {
    id: row.id,
    field,
    value,
  });
}
async function pasteCells(edits: { id: string; field: string; value: string }[]) {
  await command(isMeasurement.value ? "record_edit_many" : "edit_many", {
    id: isMeasurement.value ? activeMeasurement.value : one.value?.id,
    edits,
  });
}
function historyAction(method: "undo" | "redo") {
  return command((props.entryId && state.value?.measurement_draft ? "draft." : "project.") + method);
}
function keyboard(event: KeyboardEvent) {
  const editingRecords = !!props.entryId;
  const shortcut = projectViewShortcut(event, {
    projectOpen: props.projectOpen,
    busy: busy.value,
    browsingSource: !!source.value,
    view: props.view,
    editingRecords,
    hasSelectedRecord: !!selectedRecord.value,
    selected: selected.value,
  });
  if (!shortcut) return;
  event.preventDefault();
  event.stopPropagation();
  switch (shortcut) {
    case "applyRecords":
      return emit("applyRecords");
    case "discardRecords":
      return emit("discardRecords");
    case "undo":
    case "redo":
      return void historyAction(shortcut);
    case "add":
      return void (editingRecords ? recordAction("add") : showForm());
    case "addSubitem":
      return void showSubitem();
    case "editAnalysis":
      if (one.value) activateRow(one.value);
      return;
    case "editProperties":
      return void measurementPropertiesDialog.value?.showProperties();
    case "editResource":
      return void showForm("edit");
    case "database":
      return showDatabase();
    case "colour":
      return void scheduleEditingDialogs.value?.showColour();
    case "cut":
      return void command("cut");
    case "copy":
      return void (editingRecords ? recordAction("copy") : command("copy"));
    case "duplicate":
      if (editingRecords) return void recordAction("duplicate");
      return void (isMeasurement.value ? command("duplicate") : showForm("duplicate"));
    case "delete":
      return void (editingRecords ? recordAction("delete") : deleteSelection());
    case "moveUp":
    case "moveDown": {
      const delta = shortcut === "moveUp" ? -1 : 1;
      return void (editingRecords ? recordAction("move", delta) : command("move", { delta }));
    }
    case "consume":
      return;
  }
}
async function refreshAfterMappedImport() {
  await run(refresh);
  emit("changed");
}
function exportWorkbook() {
  return exportWithWorkbookChooser(
    "estimate.xlsx",
    (destination) =>
      command("project.export_xlsx", {
        ...destination,
        break_lines: programSettings.value?.export_break_items ?? true,
      }),
    (message) => {
      error.value = message;
    },
  );
}
watch(
  () => props.view,
  async () => {
    workingSelection.value = [];
    invalidateDetail();
    selectedRecords.value = [];
    recordSelectionIds.value = undefined;
    query.value = "";
    categoryFilters.value = [];
    source.value = "";
    page.value = 0;
    selected.value = [];
    activeMeasurement.value = undefined;
    selectionIds.value = undefined;
    selectedRecord.value = undefined;
    recordPage.value = 0;
    await load();
  },
);
watch(() => props.projectOpen, load);
watch(source, async (value, previous) => {
  if (!previous) workingSelection.value = selected.value.map((row) => row.id);
  selected.value = [];
  selectionIds.value = undefined;
  page.value = 0;
  await load();
  if (!value) selectionIds.value = workingSelection.value;
});
onMounted(async () => {
  await load();
  if (props.projectOpen) templates.value = await request("measurement.templates");
  await focusTable();
});
watch(
  () => props.projectOpen,
  async (opened) => {
    if (opened) templates.value = await request("measurement.templates");
  },
);
</script>
<template>
  <section class="project-view" @keydown="keyboard">
    <h1 class="sr-only">{{ title }}</h1>
    <div v-if="!projectOpen" class="empty-explorer">
      <AppIcon name="folder" :size="35" /><strong>Open a project to use this editor.</strong>
    </div>
    <template v-else
      ><div v-if="error" class="dialog-error" role="alert">{{ error }}</div>
      <Teleport to="#project-ribbon-tools"
        ><div v-show="active" class="view-ribbon-tools">
          <MeasurementRecordRibbon
            v-if="isMeasurement && entryId"
            :busy="busy"
            :detail-busy="detailBusy"
            :has-selection="!!selectedRecord"
            @action="recordAction"
            @insert-multiple="
              recordCount = 10;
              recordsOpen = true;
            "
            @import-records="projectImportDialogs?.show('records')"
            @show-properties="measurementPropertiesDialog?.showProperties()"
          />
          <ProjectListRibbon
            v-else
            v-model:quantity-rounding="quantityRounding"
            :view="view"
            :busy="busy"
            :browsing-source="!!source"
            :has-rows="!!state?.total"
            :selected="selected"
            @show-database="showDatabase()"
            @show-price-update="showPriceUpdate"
            @add-item="showForm()"
            @add-subitem="showSubitem"
            @add-category="projectItemDialogs?.showCategory()"
            @duplicate="isMeasurement ? command('duplicate') : showForm('duplicate')"
            @cut="command('cut')"
            @copy="command('copy', { ids: isMeasurement ? selectedItemIds() : selected.map((row) => row.id) })"
            @paste="command('paste')"
            @delete-selection="deleteSelection"
            @edit-resource="showForm('edit')"
            @move-resources="resourceEditingDialogs?.showMove()"
            @move="command('move', { delta: $event })"
            @edit-analysis="selectedSchedule && emit('analysis', selectedSchedule.code)"
            @import-analyses="projectImportDialogs?.show('analyses')"
            @show-discrepancies="rateDiscrepancies?.show()"
            @edit-analysis-rules="
              emit(
                'analysisRules',
                selected.map((row) => row.id),
              )
            "
            @renumber-schedule="scheduleEditingDialogs?.showRenumber()"
            @show-schedule-colour="scheduleEditingDialogs?.showColour()"
            @refresh-schedule-rates="command('update_rates', { ids: selectedScheduleIds })"
            @update-selected-quantities="scheduleEditingDialogs?.showQuantities()"
            @show-resource-usage="
              usageCode = undefined;
              usageOpen = true;
            "
            @find-analyses="
              usageCode = one?.code;
              usageOpen = true;
            "
            @refresh-dependent-rates="command('rates')"
            @renumber-resources="resourceEditingDialogs?.showRenumber()"
            @sync-schedule-rates="command('sync_schedule')"
            @edit-records="one && activateRow(one)"
            @show-measurement-properties="measurementPropertiesDialog?.showProperties()"
            @update-quantities="command('update_quantities', { rounding: quantityRounding })"
            @import-workbook="projectImportDialogs?.show('mapped')"
            @export-workbook="exportWorkbook"
          /></div
      ></Teleport>
      <div v-if="state?.enrichment" class="project-filter-bar" role="note">
        <small class="enrichment-badge">AI-generated</small>
        <span>{{ state.enrichment.summary || "Optional database enrichment" }}</span>
        <button v-if="!source" class="text-button" :disabled="busy" @click="command('project.enrichment.clear')">
          Clear enrichment
        </button>
      </div>
      <div v-if="!isMeasurement" class="project-filter-bar">
        <form v-if="!isMeasurement" class="search-field project-search" @submit.prevent="search()">
          <AppIcon name="search" :size="16" /><input
            v-model="query"
            aria-label="Search project table"
            @keydown.up.down="mainTable?.step($event)"
            placeholder="Search codes and descriptions…"
          /><button class="button small secondary" :disabled="busy">Search</button>
        </form>
        <CategoryFilter v-model="categoryFilters" :categories="state?.categories || []" :disabled="busy" />
      </div>
      <div v-show="!entryId" class="table-panel project-main-grid">
        <DataTable
          ref="mainTable"
          :type-ahead="!isMeasurement"
          :type-ahead-find="findAcross"
          :active="active && !entryId"
          :key="source"
          :label="title"
          :render-all-rows="view === 'schedule'"
          :rows="mainRows"
          :columns="columns"
          :busy="busy"
          tree
          drag-select-rows
          :activate-on-double-click="isMeasurement"
          :select-ids="selectionIds"
          :actions="rowActions"
          :save-cell="edit"
          @action="rowAction"
          @selection="select"
          @paste="pasteCells"
          @paste-rows="(data) => command('paste', { clipboardData: data })"
          @activate="activateRow"
        />
      </div>
      <ScheduleRateDiscrepancies
        v-if="view === 'schedule'"
        ref="rateDiscrepancies"
        :revision="state?.revision"
        :source="source"
        :run="run"
      />
      <div
        v-if="view === 'schedule' && state"
        class="schedule-estimate-total"
        role="status"
        aria-label="Overall estimate total"
      >
        <span>Overall estimate total</span><strong>{{ formatMoney(state.grand_total ?? "0.00") }}</strong>
      </div>
      <div v-if="!isMeasurement" class="pagination">
        <button class="text-button" :disabled="busy || page === 0" @click="goToPage(page - 1)">Previous</button
        ><span>{{ state?.total || 0 }} items · Page {{ page + 1 }}</span
        ><button
          class="text-button"
          :disabled="busy || (page + 1) * 100 >= (state?.total || 0)"
          @click="goToPage(page + 1)"
        >
          Next
        </button>
      </div>
      <MeasurementRecordLayout
        v-if="isMeasurement && entryId"
        ref="recordLayout"
        v-model:description-draft="descriptionDraft"
        :entry-id="entryId"
        :active-measurement="activeMeasurement"
        :detail="state?.detail"
        :draft="state?.measurement_draft"
        :busy="busy"
        :detail-busy="detailBusy"
        @apply="emit('applyRecords')"
        @discard="emit('discardRecords')"
        @edit-description="editMeasurementDescription"
        @finish-description="finishMeasurementDescription"
        @change-page="changeRecordPage"
      >
        <template #links="{ detail }">
          <div class="measurement-links">
            <label v-for="(link, index) in detail.links" :key="index" class="field"
              >{{ link.label }} · Schedule code {{ Number(index) + 1 }}
              <div class="file-input">
                <input
                  :value="link.code"
                  :aria-label="'Schedule code ' + (Number(index) + 1)"
                  :disabled="busy"
                  @change="
                    command('link', {
                      id: activeMeasurement,
                      slot: Number(index),
                      code: ($event.target as HTMLInputElement).value,
                      remark: link.remark,
                    })
                  "
                /><button
                  class="icon-button"
                  :aria-label="'Choose schedule item ' + (Number(index) + 1)"
                  :disabled="busy"
                  title="Search project schedule codes and descriptions for this measured quantity."
                  @click="measurementPropertiesDialog?.showLinkPicker(Number(index))"
                >
                  <AppIcon name="search" />
                </button>
                <button
                  class="icon-button"
                  :aria-label="'Clear schedule link ' + (Number(index) + 1)"
                  :disabled="busy || (!link.code && !link.missing)"
                  title="Remove this schedule association while retaining measurement records and remarks."
                  @click="
                    command('link', { id: activeMeasurement, slot: Number(index), code: '', remark: link.remark })
                  "
                >
                  <AppIcon name="close" />
                </button>
              </div>
              <small
                v-if="link.description"
                v-middle-ellipsis="link.description + (link.unit ? ' (' + link.unit + ')' : '')"
                class="five-line-description"
                :title="link.description"
              /><input
                :value="link.remark"
                :aria-label="'Schedule item remark ' + (Number(index) + 1)"
                :disabled="busy"
                placeholder="Item remark"
                @change="
                  command('link', {
                    id: activeMeasurement,
                    slot: Number(index),
                    code: link.code,
                    remark: ($event.target as HTMLInputElement).value,
                  })
                "
              /><small v-if="link.missing" role="alert"
                >The linked schedule item is missing. Select another code.</small
              ></label
            >
          </div>
        </template>
        <template #default="{ detail }">
          <div class="table-panel measurement-record-grid">
            <DataTable
              ref="recordTable"
              drag-select-rows
              :active="active && !!entryId"
              :rows="recordRows"
              :columns="recordColumns"
              :busy="busy || detailBusy"
              :select-ids="recordSelectionIds"
              :label="detail.info.label + ' records'"
              :actions="[
                { label: 'Insert record', action: 'add' },
                { label: 'Duplicate record', action: 'duplicate' },
                { label: 'Copy record', action: 'copy' },
                { label: 'Paste records here', action: 'paste' },
                { label: 'Delete record', action: 'delete' },
              ]"
              @action="(operation) => recordAction(operation)"
              @selection="
                selectedRecords = $event;
                selectedRecord = $event[0];
              "
              :save-cell="recordEdit"
              @paste="pasteCells"
              @paste-rows="
                (data) =>
                  command('record_paste', {
                    id: activeMeasurement,
                    record_id: selectedRecord?.id,
                    record_ids: selectedRecords.map((row) => row.id),
                    clipboardData: data,
                  })
              "
            />
          </div>
        </template>
      </MeasurementRecordLayout>
    </template>
    <ResourceEditingDialogs
      v-if="view === 'resources'"
      ref="resourceEditingDialogs"
      :categories="state?.categories"
      :selection-count="selected.length"
      :busy="busy"
      :error="error"
      :run="run"
      :command="command"
    />
    <Dialog
      v-model:visible="recordsOpen"
      modal
      header="Insert measurement records"
      class="workspace-dialog file-dialog"
      :closable="!busy"
      :close-on-escape="!busy"
    >
      <form
        @submit.prevent="
          async () => {
            if (
              await command('record_add', { id: activeMeasurement, record_id: selectedRecord?.id, count: recordCount })
            )
              recordsOpen = false;
          }
        "
      >
        <p>Insert blank records after the selected record, or at the end. Undo removes the entire batch.</p>
        <label class="field"
          >Number of records<input
            v-model.number="recordCount"
            data-primary-input
            autofocus
            type="number"
            min="1"
            max="1000"
            required
            :disabled="busy"
        /></label>
        <p v-if="error" role="alert" class="dialog-error">{{ error }}</p>
        <div class="dialog-footer">
          <button type="button" class="button secondary" :disabled="busy" @click="recordsOpen = false">Cancel</button
          ><button class="button primary" :disabled="busy">Insert records</button>
        </div>
      </form>
    </Dialog>
    <MeasurementPropertiesDialog
      ref="measurementPropertiesDialog"
      :busy="busy"
      :context="measurementPropertiesContext"
    />
    <ProjectItemDialogs
      ref="projectItemDialogs"
      :view="view"
      :categories="state?.categories"
      :measurement-categories="measurementCategories"
      :templates="templates"
      :editable-fields="editableFields"
      :selected-item="one"
      :busy="busy"
      :error="error"
      :run="run"
      :command="command"
    />
    <ProjectDeletionDialog
      ref="projectDeletionDialog"
      :view="view"
      :busy="busy"
      :error="error"
      :run="run"
      :command="command"
    />
    <ProjectImportDialogs
      ref="projectImportDialogs"
      :view="view"
      :fields="editableFields"
      :revision="state?.revision"
      :measurement-id="activeMeasurement"
      :record-id="selectedRecord?.id"
      :error="error"
      :command="command"
      :refresh-after-mapped-import="refreshAfterMappedImport"
      @clear-error="error = ''"
    />
    <ResourceUsage
      v-if="view !== 'measurement'"
      v-model="usageOpen"
      :selected-code="usageCode"
      @analysis="emit('analysis', $event)"
    />
    <ScheduleEditingDialogs
      v-if="view === 'schedule'"
      ref="scheduleEditingDialogs"
      :selected-ids="selectedScheduleIds"
      :selected-colour="selectedSchedule?.colour"
      :busy="busy"
      :error="error"
      :command="command"
      @clear-error="error = ''"
    />
  </section>
</template>
