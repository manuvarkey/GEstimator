<script setup lang="ts">
import ThemedAutocomplete from "./ThemedAutocomplete.vue";
import { computed, nextTick, onMounted, onBeforeUnmount, ref, watch } from "vue";
import Dialog from "primevue/dialog";
import PersistentDialog from "./PersistentDialog.vue";
import { open, save } from "@tauri-apps/plugin-dialog";
import type { ColumnDefinition, CellComponent } from "tabulator-tables";
import DataTable from "./DataTable.vue";
import AppIcon from "./AppIcon.vue";
import SpreadsheetRangeImport from "./SpreadsheetRangeImport.vue";
import MappedImport from "./MappedImport.vue";
import ResourceUsage from "./ResourceUsage.vue";
import CategoryFilter from "./CategoryFilter.vue";
import { request } from "../backend";
import type { GridRow, GridState, View, ViewMemory, MeasurementTemplate } from "../projectViewTypes";
import { useMeasurementRecords } from "../useMeasurementRecords";
import { useMeasurementProperties } from "../useMeasurementProperties";
import { afterDialogsClose } from "../uiActions";
import { programSettings } from "../programSettings";
import { useLiveSearch } from "../liveSearch";
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
  database: [options: { kind: "schedule" | "resources"; mode: "add" | "rates"; revision: number; targetIds: string[] }];
  analysisRules: [ids: string[]];
  applyRecords: [];
  discardRecords: [];
}>();
const state = ref<GridState>();
const discrepancy = ref<any>();
const excludedPrefixes = ref<string[]>([]);
const resourceRenumberOpen = ref(false);
const resourcePrefixes = ref<string[]>([]);
async function showDiscrepancies() {
  await run(async () => {
    const result = await request<any>("schedule.editor.discrepancies", {});
    if (state.value?.revision === result.revision && !source.value) discrepancy.value = result;
  });
}
async function showResourceRenumber() {
  await run(async () => {
    const result = await request<{ prefixes: string[] }>("resources.editor.prefixes", {});
    resourcePrefixes.value = result.prefixes;
    excludedPrefixes.value = [...result.prefixes];
    resourceRenumberOpen.value = true;
  });
}

const emptyRows: GridRow[] = [];
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
  revealCode,
  handleKeyboard: keyboard,
  historyAction: (method: "undo" | "redo") =>
    command(props.entryId && state.value?.measurement_draft ? "draft." + method : "project." + method),
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
watch(categoryFilters, () => {
  void search();
});
let searchedQuery = "";
const liveSearch = useLiveSearch(
  query,
  () => searchedQuery,
  () => (isMeasurement.value ? Promise.resolve(true) : search()),
);
const source = ref("");
watch([() => state.value?.revision, source, () => props.view], () => {
  discrepancy.value = undefined;
});
const libraries = ref<{ id: string; name: string }[]>([]);
const usageOpen = ref(false);
const usageCode = ref<string>();
const page = ref(remembered?.page ?? 0);
const selected = ref<GridRow[]>([]);
const templates = ref<MeasurementTemplate[]>([]);
const templateInfo = computed(() => templates.value.find((template) => template.code === form.value.template));
const mainTable = ref<InstanceType<typeof DataTable>>();
const selectionIds = ref<string[]>();
const workingSelection = ref<string[]>([]);
const moveResourcesOpen = ref(false);
const moveCategory = ref("");
const formOpen = ref(false);
const formMode = ref("add");
const form = ref<Record<string, string>>({});
const categoryOpen = ref(false);
const categoryName = ref("");
const colourOpen = ref(false);
const renumberOpen = ref(false);
const rowColour = ref("#ffe082");
const rowColours = [
  "#ffffff",
  "#eeeeee",
  "#ffe082",
  "#ffcc80",
  "#ffab91",
  "#f8bbd0",
  "#e1bee7",
  "#c5cae9",
  "#bbdefb",
  "#b2dfdb",
  "#c8e6c9",
  "#dcedc8",
  "#795548",
  "#455a64",
  "#263238",
  "#000000",
];
const scheduleQuantityOpen = ref(false);
const scheduleRounding = ref("Round to 0");
const deleteOpen = ref(false);
const deletion = ref<{
  ids: string[];
  revision: number;
  items: number;
  categories: number;
  used_resources: string[];
  measurement_references: number;
}>();
const importOpen = ref(false);
const recordImportOpen = ref(false);
const multiAnalysisImportOpen = ref(false);

const quantityRounding = ref("Round to .000");
const roundingOptions = [
  "Round within 1%",
  "Round within 5%",
  "Round within 10%",
  "Round to 10000",
  "Round to 1000",
  "Round to 100",
  "Round to 10",
  "Round to 0",
  "Round to .0",
  "Round to .00",
  "Round to .000",
  "No rounding",
];
const importFields = computed(() =>
  props.view === "resources"
    ? ["code", "description", "unit", "rate", "vat", "discount", "reference", "category"]
    : ["code", "description", "unit", "rate", "qty", "remarks", "category", "parent"],
);
const one = computed(() => (selected.value.length === 1 ? selected.value[0] : undefined));
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
const mainRows = computed(() => {
  if (!isMeasurement.value) {
    const marks = new Map((discrepancy.value?.rows || []).map((row: any) => [row.id, row.colour]));
    const decorate = (row: GridRow): GridRow => ({
      ...row,
      ...(discrepancy.value && props.view === "schedule" && marks.has(row.id) ? { colour: marks.get(row.id) } : {}),
      ...(row._children ? { _children: row._children.map(decorate) } : {}),
    });
    return discrepancy.value ? (state.value?.rows || []).map(decorate) : state.value?.rows || emptyRows;
  }
  const categories: GridRow[] = [];
  let current: GridRow | undefined;
  for (const row of state.value?.rows || []) {
    if (row.type === "Heading") {
      current = { ...row, rowtype: "Category", type: "", _children: [] };
      categories.push(current);
    } else {
      if (!current) {
        current = {
          id: "measurement:uncategorised",
          rowtype: "Category",
          type: "",
          description: "Uncategorised",
          _children: [],
        };
        categories.push(current);
      }
      current._children.push(row);
    }
  }
  return categories;
});
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
  measurementDescription,
  descriptionDraft,
  fullMeasurementTitle,
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
  changed: () => emit("changed"),
});
const {
  propertiesOpen,
  propertiesCategory,
  propertiesDetail,
  properties,
  pickerOpen,
  pickerQuery,
  pickerPage,
  pickerItems,
  pickerBusy,
  pickerError,
  showProperties,
  saveProperties,
  searchLinks,
  showLinkPicker,
  chooseLink,
} = useMeasurementProperties({ state, one, error, activeMeasurement, command, loadDetail });

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
  return cell.getData().rowtype !== "Category";
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
    if (isMeasurement.value) showProperties();
    else if (one.value?.rowtype !== "Category") void showForm("edit");
  } else if (operation === "delete") void deleteSelection();
  else if (operation === "duplicate" && !isMeasurement.value) {
    if (one.value && one.value.rowtype !== "Category") void showForm("duplicate");
  } else void command(operation);
}
async function refresh(revealId?: string) {
  if (!props.projectOpen) {
    state.value = undefined;
    return;
  }
  if (!isMeasurement.value) libraries.value = await request("library.list");
  const detailOnly = isMeasurement.value && !!props.entryId && !!state.value;
  searchedQuery = query.value;
  const next = await request<GridState>(
    isMeasurement.value ? (detailOnly ? "measurement.detail" : "measurement.state") : props.view + ".editor.state",
    {
      query: query.value,
      categories: categoryFilters.value,
      source: source.value,
      offset: page.value * 100,
      id: props.entryId ? activeMeasurement.value : undefined,
      record_offset: recordPage.value * 100,
      reveal_id: revealId,
    },
  );
  state.value = detailOnly ? { ...state.value!, ...next } : next;
  if (props.entryId && state.value.detail && state.value.measurement_draft?.id !== props.entryId) {
    await request("measurement.draft.open", { id: props.entryId, revision: state.value.revision });
    Object.assign(
      state.value,
      await request("measurement.detail", { id: props.entryId, record_offset: recordPage.value * 100 }),
    );
    emit("changed");
  }
  syncMeasurementSummary();
  if (!isMeasurement.value) {
    const retained = categoryFilters.value.filter((name) => state.value?.categories?.includes(name));
    if (retained.length !== categoryFilters.value.length) {
      categoryFilters.value = retained;
      page.value = 0;
      await refresh(revealId);
      return;
    }
  }
  if (isMeasurement.value && state.value?.detail) recordPage.value = state.value.detail.offset / 100;
  if (!isMeasurement.value) page.value = (state.value?.offset || 0) / 100;
}
function selectedItemIds() {
  return [
    ...new Set(
      selected.value.flatMap((row) =>
        isMeasurement.value && row.rowtype === "Category"
          ? [row.id, ...(row._children || []).map((item: GridRow) => item.id)]
          : [row.id],
      ),
    ),
  ].filter((id) => id !== "measurement:uncategorised");
}
async function command(operation: string, params: Record<string, unknown> = {}) {
  return run(async () => {
    const clipboardParams = {
      revision: state.value?.revision,
      id: one.value?.id,
      ids: selectedItemIds(),
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
          ids: selectedItemIds(),
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
    else await refresh(!isMeasurement.value ? result?.selected?.[0] : undefined);
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
async function deleteSelection() {
  if (isMeasurement.value) {
    if (selected.value.some((row) => row.rowtype === "Category")) {
      const ids = selectedItemIds();
      deletion.value = {
        ids,
        revision: state.value!.revision,
        items: ids.length,
        categories: selected.value.filter((row) => row.rowtype === "Category").length,
        used_resources: [],
        measurement_references: 0,
      };
      deleteOpen.value = true;
    } else await command("delete");
    return;
  }
  const ids = selected.value.map((row) => row.id);
  const revision = state.value!.revision;
  const ok = await run(async () => {
    const preview = await request<Omit<NonNullable<typeof deletion.value>, "ids" | "revision">>(
      props.view + ".editor.delete_preview",
      { ids, revision },
    );
    deletion.value = { ...preview, ids, revision };
  });
  if (!ok) return;
  if (
    deletion.value!.categories ||
    deletion.value!.used_resources.length ||
    deletion.value!.measurement_references ||
    deletion.value!.items > 1
  ) {
    deleteOpen.value = true;
  } else {
    await confirmDeletion("protect");
  }
}
async function confirmDeletion(policy: "protect" | "unused" | "all") {
  if (!deletion.value) return;
  if (
    await command(isMeasurement.value ? "delete" : "delete_many", {
      ids: deletion.value.ids,
      revision: deletion.value.revision,
      policy,
    })
  ) {
    deleteOpen.value = false;
    deletion.value = undefined;
  }
}
async function revealCode(code: string) {
  if (isMeasurement.value) return;
  const rows = (values: GridRow[]): GridRow[] => values.flatMap((row) => [row, ...rows(row._children || [])]);
  let row = rows(state.value?.rows || []).find((row) => row.code === code);
  if (!row) {
    const result = await request<{ id: string }>(props.view + ".editor.locate", { code });
    query.value = "";
    categoryFilters.value = [];
    await refresh(result.id);
    row = rows(state.value?.rows || []).find((row) => row.id === result.id);
  }
  if (row) selectionIds.value = [row.id];
}
/** Type-ahead on the main table: load the page holding the next match and select it. */
async function findAcross(text: string, from: string | undefined, direction: 1 | -1) {
  if (isMeasurement.value || busy.value || !props.projectOpen) return false;
  try {
    const next = await request<GridState & { found_id?: string | null }>(props.view + ".editor.state", {
      query: searchedQuery,
      categories: categoryFilters.value,
      source: source.value,
      offset: page.value * 100,
      find: text,
      find_from: from,
      find_direction: direction,
    });
    if (!next.found_id) return false;
    state.value = next;
    page.value = (next.offset || 0) / 100;
    selectionIds.value = [next.found_id];
    return true;
  } catch {
    return false;
  }
}
async function refreshChanges() {
  if (!state.value || isMeasurement.value || source.value) {
    await load();
    return;
  }
  const flatten = (rows: GridRow[]): GridRow[] => rows.flatMap((row) => [row, ...flatten(row._children || [])]);
  const current = flatten(state.value.rows);
  const update = async () => {
    const next = await request<GridState>(props.view + ".editor.state", {
      since: state.value!.view_seq,
      visible_ids: current.map((row) => row.id),
      query: query.value,
      categories: categoryFilters.value,
      offset: page.value * 100,
    });
    if (next.delta) {
      for (const update of next.updates || []) Object.assign(current.find((row) => row.id === update.id) || {}, update);
      Object.assign(state.value!, {
        revision: next.revision,
        view_seq: next.view_seq,
        undo: next.undo,
        redo: next.redo,
        enrichment: next.enrichment,
        grand_total: next.grand_total,
      });
      await mainTable.value?.patchRows(next.updates || []);
    } else state.value = next;
    await nextTick();
    await mainTable.value?.redraw();
  };
  if (busy.value) await update();
  else await run(update);
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
let pendingView = remembered?.table;
async function load() {
  const result = await run(refresh);
  // The first load with the project open restores the remembered rows and scroll.
  if (pendingView && mainTable.value && state.value) {
    const view = pendingView;
    pendingView = undefined;
    await mainTable.value.restoreViewState(view);
  }
  await restoreRecords();
  return result;
}
/** Load the first page of results for the current search and filters. */
async function search() {
  liveSearch.cancel();
  return goToPage(0);
}
async function goToPage(index: number) {
  page.value = index;
  await mainTable.value?.scrollToTop();
  return load();
}
function showRowColour() {
  rowColour.value = /^#[0-9a-f]{6}$/i.test(one.value?.colour ?? "") ? one.value?.colour.toLowerCase() : "#ffe082";
  error.value = "";
  colourOpen.value = true;
}
async function applyRowColour(colour: string | null) {
  if (await command("colour", { ids: selectedScheduleIds.value, colour })) colourOpen.value = false;
}
async function renumberSchedule() {
  if (await command("renumber")) renumberOpen.value = false;
}
async function updateSelectedQuantities() {
  if (
    await command("update_quantities", {
      ids: selectedScheduleIds.value,
      rounding: scheduleRounding.value,
    })
  )
    scheduleQuantityOpen.value = false;
}
function showPriceUpdate() {
  showDatabase("rates");
}
function showDatabase(mode: "add" | "rates" = "add") {
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
async function showForm(mode = "add", child = false) {
  formMode.value = mode;
  form.value = {
    code: "",
    description: "",
    unit: "",
    rate: "0",
    qty: "0",
    vat: "0",
    discount: "0",
    category: one.value?.category || (one.value?.rowtype === "Category" ? one.value.description : ""),
    parent: "",
    reference: "",
    template: isMeasurement.value ? "_1_NLBH" : "",
    ...(mode === "duplicate" ? { code: one.value?.code + "-copy" } : {}),
    ...(mode === "edit"
      ? Object.fromEntries(importFields.value.map((field) => [field, String(one.value?.[field] ?? "")]))
      : {}),
  };
  if (isMeasurement.value) {
    form.value.category =
      one.value?.rowtype === "Category"
        ? one.value.description
        : mainRows.value.find((category) => category._children?.some((row: GridRow) => row.id === one.value?.id))
            ?.description || "";
  }
  if (mode === "add" && !isMeasurement.value) {
    if (
      !(await run(async () => {
        Object.assign(
          form.value,
          await request(props.view + ".editor.defaults", { ids: selected.value.map((row) => row.id), child }),
        );
      }))
    )
      return;
  }
  formOpen.value = true;
}
async function showSubitem() {
  if (props.view !== "schedule" || !one.value || one.value.rowtype === "Category") return;
  await showForm("add", true);
}
async function submit() {
  if (formMode.value === "edit") {
    const edits = Object.entries(form.value)
      .filter(([field, value]) => importFields.value.includes(field) && value !== String(one.value?.[field] ?? ""))
      .map(([field, value]) => ({ id: one.value!.id, field, value }));
    if (!edits.length || (await command("edit_many", { edits }))) formOpen.value = false;
    return;
  }
  const op = isMeasurement.value ? (formMode.value === "duplicate" ? "duplicate" : "add") : formMode.value;
  if (
    await command(
      op,
      isMeasurement.value
        ? {
            template: form.value.template,
            description: form.value.description,
            id: mainRows.value.find(
              (category) => category.description === form.value.category && category.id !== "measurement:uncategorised",
            )?.id,
          }
        : { data: form.value },
    )
  )
    formOpen.value = false;
}
function activateRow(row: GridRow) {
  if (source.value) return;
  if (row.rowtype === "Category") {
    if (isMeasurement.value && row.id !== "measurement:uncategorised") {
      selected.value = [row];
      selectionIds.value = [row.id];
      void showProperties();
    }
    return;
  }
  if (props.view === "schedule") {
    if (row.has_children) notify(`Item ${row.code} has subitems; open the analysis of a subitem instead.`);
    else emit("analysis", row.code);
  } else if (props.view === "resources") void showForm("edit");
  else if (row.type !== "Heading") emit("entry", row.id);
  else showProperties();
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
function keyboard(event: KeyboardEvent) {
  if (event.defaultPrevented || !props.projectOpen || busy.value || document.querySelector('[role="dialog"]')) return;
  if ((event.target as HTMLElement).closest("input,textarea,select,[contenteditable=true]")) return;
  if (event.ctrlKey || event.metaKey) {
    const key = event.key.toLowerCase();
    if (props.entryId && (event.key === "Enter" || event.key === "Escape")) {
      event.preventDefault();
      event.stopPropagation();
      if (event.key === "Enter") emit("applyRecords");
      else emit("discardRecords");
      return;
    }
    if (key === "z" || key === "y") {
      event.preventDefault();
      event.stopPropagation();
      void command(
        (props.entryId && state.value?.measurement_draft ? "draft." : "project.") +
          (key === "y" || event.shiftKey ? "redo" : "undo"),
      );
      return;
    }
  }
  const target = event.target as HTMLElement;
  if (source.value) return;
  const records = !!props.entryId;
  if (event.ctrlKey || event.metaKey) {
    const key = event.key.toLowerCase();
    if (key === "i") {
      event.preventDefault();
      event.stopPropagation();
      if (records) void recordAction("add");
      else if (event.shiftKey && props.view === "schedule") showSubitem();
      else showForm();
      return;
    }
    if (key === "e" && props.view === "schedule" && one.value?.rowtype === "Schedule") {
      event.preventDefault();
      event.stopPropagation();
      activateRow(one.value);
      return;
    }
    if (key === "e" && one.value && props.view !== "schedule") {
      event.preventDefault();
      event.stopPropagation();
      if (isMeasurement.value) showProperties();
      else if (one.value.rowtype !== "Category") void showForm("edit");
      return;
    }
    if (key === "l" && props.view !== "measurement") {
      event.preventDefault();
      event.stopPropagation();
      showDatabase();
      return;
    }
    if (key === "m" && props.view === "schedule" && selectedScheduleIds.value.length) {
      event.preventDefault();
      event.stopPropagation();
      showRowColour();
      return;
    }
  }
  if (!target.closest(".project-grid")) return;
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "x" && props.view === "resources" && !records) {
    event.preventDefault();
    event.stopPropagation();
    if (selected.value.some((row) => row.rowtype !== "Category")) void command("cut");
    return;
  }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "c") {
    event.preventDefault();
    event.stopPropagation();
    if (records ? !!selectedRecord.value : !!selected.value.length)
      void (records ? recordAction("copy") : command("copy"));
    return;
  }
  if (records ? !selectedRecord.value : !selected.value.length) return;
  const duplicate = (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "d";
  const remove = event.key === "Delete";
  const delta = event.altKey && event.key === "ArrowUp" ? -1 : event.altKey && event.key === "ArrowDown" ? 1 : 0;
  if (!duplicate && !remove && !delta) return;
  event.preventDefault();
  event.stopPropagation();
  if (records) void recordAction(duplicate ? "duplicate" : remove ? "delete" : "move", delta || undefined);
  else if (remove) void deleteSelection();
  else if (duplicate) {
    if (isMeasurement.value) void command("duplicate");
    else if (one.value && one.value.rowtype !== "Category") showForm("duplicate");
  } else if (isMeasurement.value || one.value) void command("move", { delta });
}
async function importDone(result: { added: number; updated: number; skipped: number; warning_count?: number }) {
  await run(async () => {
    await refresh();
  });
  emit("changed");
  notify(
    `Imported ${result.added} new, ${result.updated} updated, ${result.skipped} skipped${result.warning_count ? `; ${result.warning_count} non-numeric values imported as 0` : ""}.`,
    8000,
  );
}
async function exportWorkbook() {
  try {
    const path = await save({
      filters: [{ name: "Excel workbook", extensions: ["xlsx"] }],
      defaultPath: "estimate.xlsx",
    });
    if (typeof path === "string")
      await command("project.export_xlsx", { path, break_lines: programSettings.value?.export_break_items ?? true });
  } catch (reason) {
    error.value = String(reason);
  }
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
          <template v-if="isMeasurement && entryId">
            <div class="ribbon-group">
              <div class="ribbon-actions">
                <button
                  class="ribbon-action"
                  aria-label="Add record"
                  :disabled="busy || detailBusy"
                  @click="recordAction('add')"
                >
                  <AppIcon name="plus" /><span class="ribbon-label">Add record</span>
                </button>
                <button
                  class="ribbon-action"
                  aria-label="Add multiple records"
                  :disabled="busy || detailBusy"
                  @click="
                    recordCount = 10;
                    recordsOpen = true;
                  "
                >
                  <AppIcon name="rows" /><span class="ribbon-label">Add multiple records</span>
                </button>
                <button
                  class="ribbon-action"
                  aria-label="Duplicate record"
                  :disabled="busy || !selectedRecord"
                  @click="recordAction('duplicate')"
                >
                  <AppIcon name="duplicate" /><span class="ribbon-label">Duplicate record</span>
                </button>
              </div>
              <small>CREATE</small>
            </div>
            <div class="ribbon-group">
              <div class="ribbon-actions">
                <button
                  class="ribbon-action ribbon-icon"
                  aria-label="Copy record"
                  :disabled="busy || !selectedRecord"
                  @click="recordAction('copy')"
                >
                  <AppIcon name="copy" /><span class="ribbon-label">Copy record</span>
                </button>
                <button
                  class="ribbon-action ribbon-icon"
                  aria-label="Paste record"
                  :disabled="busy"
                  @click="recordAction('paste')"
                >
                  <AppIcon name="paste" /><span class="ribbon-label">Paste record</span>
                </button>
                <button
                  class="ribbon-action ribbon-icon danger"
                  aria-label="Delete record"
                  :disabled="busy || !selectedRecord"
                  @click="recordAction('delete')"
                >
                  <AppIcon name="trash" /><span class="ribbon-label">Delete record</span>
                </button>
              </div>
              <small>EDIT</small>
            </div>
            <div class="ribbon-group">
              <div class="ribbon-actions">
                <button
                  class="ribbon-action ribbon-icon"
                  aria-label="Move record up"
                  :disabled="busy || !selectedRecord"
                  @click="recordAction('move', -1)"
                >
                  <AppIcon name="up" /><span class="ribbon-label">Move up</span>
                </button>
                <button
                  class="ribbon-action ribbon-icon"
                  aria-label="Move record down"
                  :disabled="busy || !selectedRecord"
                  @click="recordAction('move', 1)"
                >
                  <AppIcon name="down" /><span class="ribbon-label">Move down</span>
                </button>
              </div>
              <small>ARRANGE</small>
            </div>
            <div class="ribbon-group">
              <div class="ribbon-actions">
                <button
                  class="ribbon-action"
                  aria-label="Import records…"
                  :disabled="busy || detailBusy"
                  @click="
                    error = '';
                    recordImportOpen = true;
                  "
                >
                  <AppIcon name="import" /><span class="ribbon-label">Import records</span>
                </button>
                <button
                  class="ribbon-action"
                  aria-label="Properties…"
                  :disabled="busy || detailBusy"
                  @click="showProperties"
                >
                  <AppIcon name="settings" /><span class="ribbon-label">Properties</span>
                </button>
              </div>
              <small>MEASUREMENT</small>
            </div>
          </template>
          <template v-else>
            <div v-if="!isMeasurement" class="ribbon-group">
              <div class="ribbon-actions">
                <button
                  class="ribbon-action"
                  :aria-label="view === 'schedule' ? 'Add item from database' : 'Add resources from database'"
                  title="Select items from attached databases in a separate dialog. The working table and its insertion selection remain in place (Ctrl+L)."
                  :disabled="busy"
                  @click="showDatabase()"
                >
                  <AppIcon name="database" /><span class="ribbon-label">Add from database</span>
                </button>
                <button
                  v-if="view === 'resources'"
                  class="ribbon-action"
                  aria-label="Refresh selected rates from database"
                  title="Choose an attached database, preview rates matching selected project codes, and apply as one undoable update."
                  :disabled="busy || !selected.length"
                  @click="showPriceUpdate"
                >
                  <AppIcon name="refresh" /><span class="ribbon-label">Database rates</span>
                </button>
              </div>
              <small>DATABASE</small>
            </div>
            <template v-if="!source">
              <div class="ribbon-group">
                <div class="ribbon-actions">
                  <button
                    class="ribbon-action"
                    :aria-label="isMeasurement ? 'Add measurement' : 'Add item'"
                    :title="
                      isMeasurement
                        ? 'Add a measurement using a shipped template in the selected category (Ctrl+I).'
                        : 'Create an item in the selected category with its code, description and numeric fields (Ctrl+I).'
                    "
                    :disabled="busy"
                    @click="showForm()"
                  >
                    <AppIcon name="plus" :size="15" /><span class="ribbon-label">Add item</span>
                  </button>
                  <button
                    v-if="view === 'schedule'"
                    class="ribbon-action"
                    aria-label="Add subitem"
                    title="Create a subitem of the selected item; with a subitem selected, add another subitem under the same item. Its category follows the parent; the parent code is filled in for you (Ctrl+Shift+I)."
                    :disabled="busy || !one || one.rowtype === 'Category'"
                    @click="showSubitem"
                  >
                    <AppIcon name="child" /><span class="ribbon-label">Add subitem</span>
                  </button>
                  <button
                    class="ribbon-action"
                    aria-label="Add category"
                    title="Create an empty category to organize items in the current project table."
                    :disabled="busy"
                    @click="categoryOpen = true"
                  >
                    <AppIcon name="category" /><span class="ribbon-label">Add category</span>
                  </button>
                  <button
                    class="ribbon-action"
                    aria-label="Duplicate"
                    title="Create a separate copy of the selected item. Measurement selections are duplicated in their current order."
                    :disabled="busy || (isMeasurement ? !selected.length : !one || one.rowtype === 'Category')"
                    @click="isMeasurement ? command('duplicate') : showForm('duplicate')"
                  >
                    <AppIcon name="duplicate" /><span class="ribbon-label">Duplicate</span>
                  </button>
                </div>
                <small>CREATE</small>
              </div>
              <div class="ribbon-group">
                <div class="ribbon-actions">
                  <button
                    v-if="view === 'resources'"
                    class="ribbon-action ribbon-icon"
                    aria-label="Cut"
                    title="Cut the selected resources. Paste after a resource or on a category moves them there, keeping their codes and analysis links. Works within this project only (Ctrl+X)."
                    :disabled="busy || !selected.some((row) => row.rowtype !== 'Category')"
                    @click="command('cut')"
                  >
                    <AppIcon name="cut" /><span class="ribbon-label">Cut</span></button
                  ><button
                    class="ribbon-action ribbon-icon"
                    aria-label="Copy"
                    title="Copy selected items or categories, including off-page contents, to the system clipboard for use in this or another GEstimator window (Ctrl+C)."
                    :disabled="busy || !selected.length"
                    @click="command('copy', { ids: isMeasurement ? selectedItemIds() : selected.map((row) => row.id) })"
                  >
                    <AppIcon name="copy" /><span class="ribbon-label">Copy</span></button
                  ><button
                    class="ribbon-action ribbon-icon"
                    aria-label="Paste"
                    title="Paste rows copied from the same editor in any GEstimator window at the selection, numbered from it: schedule subitems go under a selected heading; rows from another project keep their resources under that project's code. Cut resources move. Undo restores the previous state (Ctrl+V)."
                    :disabled="busy"
                    @click="command('paste')"
                  >
                    <AppIcon name="paste" /><span class="ribbon-label">Paste</span>
                  </button>
                  <button
                    class="ribbon-action ribbon-icon danger"
                    aria-label="Delete"
                    title="Preview deletion of selected items and category contents before confirming. Project Undo restores the operation."
                    :disabled="busy || !selected.length"
                    @click="deleteSelection"
                  >
                    <AppIcon name="trash" /><span class="ribbon-label">Delete</span>
                  </button>
                  <template v-if="view === 'resources'">
                    <button
                      class="ribbon-action ribbon-icon"
                      aria-label="Edit resource"
                      title="Edit all fields of the selected resource together. Only changed fields are saved, as one undoable operation (Ctrl+E). Enter edits the focused cell."
                      :disabled="busy || !one || one.rowtype === 'Category'"
                      @click="showForm('edit')"
                    >
                      <AppIcon name="edit" /><span class="ribbon-label">Edit resource</span>
                    </button>
                    <button
                      class="ribbon-action ribbon-icon"
                      aria-label="Move resources…"
                      title="Move selected definitions to another category without making copies or breaking analysis links. Undo restores their previous categories."
                      :disabled="busy || !selected.length || selected.some((row) => row.rowtype === 'Category')"
                      @click="
                        moveCategory = state?.categories?.[0] || '';
                        moveResourcesOpen = true;
                      "
                    >
                      <AppIcon name="category" /><span class="ribbon-label">Move resources</span>
                    </button>
                  </template>
                </div>
                <small>EDIT</small>
              </div>
              <div class="ribbon-group">
                <div class="ribbon-actions">
                  <button
                    class="ribbon-action ribbon-icon"
                    :disabled="
                      busy || (isMeasurement ? !selected.length || one?.id === 'measurement:uncategorised' : !one)
                    "
                    aria-label="Move item up"
                    title="Move the selected item or category earlier among its siblings while preserving its contents and links."
                    @click="command('move', { delta: -1 })"
                  >
                    <AppIcon name="up" /><span class="ribbon-label">Move up</span></button
                  ><button
                    class="ribbon-action ribbon-icon"
                    :disabled="
                      busy || (isMeasurement ? !selected.length || one?.id === 'measurement:uncategorised' : !one)
                    "
                    aria-label="Move item down"
                    title="Move the selected item or category later among its siblings while preserving its contents and links."
                    @click="command('move', { delta: 1 })"
                  >
                    <AppIcon name="down" /><span class="ribbon-label">Move down</span>
                  </button>
                </div>
                <small>ARRANGE</small>
              </div>
              <div v-if="view === 'schedule'" class="ribbon-group">
                <div class="ribbon-actions ribbon-actions-wide">
                  <button
                    class="ribbon-action"
                    aria-label="Edit analysis"
                    :title="
                      one?.has_children
                        ? 'Items with subitems are priced through their subitems; select a subitem to edit its analysis.'
                        : 'Open the selected schedule item in the Analysis editor to inspect and edit its rate calculation.'
                    "
                    :disabled="busy || !one || one.rowtype === 'Category' || one.has_children"
                    @click="one && emit('analysis', one.code)"
                  >
                    <AppIcon name="edit" /><span class="ribbon-label">Edit analysis</span>
                  </button>
                  <button
                    class="ribbon-action"
                    aria-label="Import multiple analyses"
                    :disabled="busy || !!source"
                    @click="multiAnalysisImportOpen = true"
                  >
                    <AppIcon name="import" /><span class="ribbon-label">Import analyses</span>
                  </button>
                  <button
                    class="ribbon-action"
                    aria-label="Show rate discrepancies"
                    :disabled="busy || !!source"
                    @click="showDiscrepancies"
                  >
                    <AppIcon name="search" /><span class="ribbon-label">Rate discrepancies</span>
                  </button>
                  <button
                    class="ribbon-action"
                    aria-label="Bulk edit analysis…"
                    title="Match and modify analysis rows across selected schedule items/categories or the whole schedule. Preview ordered rules and rate changes before applying as one project undo step."
                    :disabled="busy"
                    @click="
                      emit(
                        'analysisRules',
                        selected.map((row) => row.id),
                      )
                    "
                  >
                    <AppIcon name="filter" /><span class="ribbon-label">Bulk edit analysis</span>
                  </button>
                  <button
                    class="ribbon-action"
                    aria-label="Renumber schedule…"
                    title="Choose numbering options for the schedule hierarchy. Item links are preserved and the operation can be undone."
                    :disabled="busy || !state?.total"
                    @click="
                      error = '';
                      renumberOpen = true;
                    "
                  >
                    <AppIcon name="calculate" /><span class="ribbon-label">Renumber schedule…</span>
                  </button>
                  <button
                    class="ribbon-action"
                    aria-label="Row colour…"
                    title="Apply or clear a saved background colour for selected schedule items. Categories and unselected descendants are excluded."
                    :disabled="busy || !selectedScheduleIds.length"
                    @click="showRowColour"
                  >
                    <AppIcon name="colour" /><span class="ribbon-label">Row colour…</span>
                  </button>
                  <button
                    class="ribbon-action"
                    aria-label="Refresh selected rates"
                    title="Recalculate the selected schedule analyses and dependent rates using the current project resources."
                    :disabled="busy || !selectedScheduleIds.length"
                    @click="command('update_rates', { ids: selectedScheduleIds })"
                  >
                    <AppIcon name="refresh" /><span class="ribbon-label">Refresh rates</span>
                  </button>
                  <button
                    class="ribbon-action"
                    aria-label="Quantities from measurements…"
                    title="Choose a rounding rule and update only the selected schedule items from their linked measurement totals."
                    :disabled="busy || !selectedScheduleIds.length"
                    @click="
                      error = '';
                      scheduleQuantityOpen = true;
                    "
                  >
                    <AppIcon name="ruler" /><span class="ribbon-label">Measured quantities</span>
                  </button>
                  <button
                    class="ribbon-action"
                    aria-label="Resource usage"
                    title="View aggregate project resource quantities and amounts, search totals, and navigate to referencing analyses."
                    :disabled="busy"
                    @click="
                      usageCode = undefined;
                      usageOpen = true;
                    "
                  >
                    <AppIcon name="chart" /><span class="ribbon-label">Resource usage</span>
                  </button>
                </div>
                <small>SCHEDULE</small>
              </div>
              <div v-if="view === 'resources'" class="ribbon-group">
                <div class="ribbon-actions ribbon-actions-wide">
                  <button
                    class="ribbon-action"
                    aria-label="Resource usage"
                    title="View aggregate project resource quantities and amounts, search totals, and navigate to referencing analyses."
                    :disabled="busy"
                    @click="
                      usageCode = undefined;
                      usageOpen = true;
                    "
                  >
                    <AppIcon name="chart" /><span class="ribbon-label">Resource usage</span>
                  </button>
                  <button
                    class="ribbon-action"
                    aria-label="Find analyses"
                    title="Find schedule analyses that use the selected resource directly or through nested sub-analyses."
                    :disabled="busy || !one || one.rowtype === 'Category'"
                    @click="
                      usageCode = one?.code;
                      usageOpen = true;
                    "
                  >
                    <AppIcon name="link" /><span class="ribbon-label">Find analyses</span>
                  </button>
                  <button
                    class="ribbon-action"
                    aria-label="Update dependent rates"
                    title="Recalculate schedule rates affected by the current resource definitions in the project working copy."
                    :disabled="busy"
                    @click="command('rates')"
                  >
                    <AppIcon name="refresh" /><span class="ribbon-label">Refresh rates</span>
                  </button>
                  <button
                    v-if="view === 'resources'"
                    class="ribbon-action"
                    :disabled="busy || !!source"
                    @click="showResourceRenumber"
                  >
                    <AppIcon name="edit" /><span class="ribbon-label">Renumber resources</span>
                  </button>
                  <button
                    v-if="view === 'resources'"
                    class="ribbon-action"
                    :disabled="busy || !!source || !selected.length"
                    @click="command('sync_schedule')"
                  >
                    <AppIcon name="refresh" /><span class="ribbon-label">Rates from schedule</span>
                  </button>
                </div>
                <small>RESOURCES</small>
              </div>
              <div v-if="isMeasurement" class="ribbon-group">
                <div class="ribbon-actions">
                  <button
                    class="ribbon-action"
                    data-ribbon-keep-label
                    aria-label="Edit records"
                    :disabled="busy || !one || one.rowtype === 'Category'"
                    @click="one && activateRow(one)"
                  >
                    <AppIcon name="edit" /><span class="ribbon-label">Edit records</span>
                  </button>
                  <button
                    class="ribbon-action"
                    data-ribbon-keep-label
                    aria-label="Properties…"
                    :disabled="busy || !one || one.id === 'measurement:uncategorised'"
                    @click="showProperties"
                  >
                    <AppIcon name="settings" /><span class="ribbon-label">Properties</span>
                  </button>
                </div>
                <small>MEASUREMENT</small>
              </div>
              <div v-if="isMeasurement" class="ribbon-group">
                <div class="ribbon-actions ribbon-measure-actions">
                  <select v-model="quantityRounding" aria-label="Quantity rounding">
                    <option v-for="option in roundingOptions" :key="option">
                      {{ option }}
                    </option>
                  </select>
                  <button
                    class="ribbon-action"
                    aria-label="Update schedule quantities"
                    title="Update schedule quantities from linked measurement totals using the selected rounding rule. Project Undo restores the previous quantities."
                    :disabled="busy"
                    @click="command('update_quantities', { rounding: quantityRounding })"
                  >
                    <AppIcon name="calculate" /><span class="ribbon-label">Update quantities</span>
                  </button>
                </div>
                <small>QUANTITIES</small>
              </div>
              <div class="ribbon-group">
                <div class="ribbon-actions">
                  <button
                    v-if="!isMeasurement"
                    class="ribbon-action"
                    aria-label="Import workbook"
                    title="Preview a schedule or resource worksheet, map columns and choose how duplicate codes are handled before importing."
                    :disabled="busy"
                    @click="importOpen = true"
                  >
                    <AppIcon name="import" /><span class="ribbon-label">Import workbook</span>
                  </button>
                  <button
                    class="ribbon-action"
                    aria-label="Export workbook"
                    title="Export the project to an Excel workbook containing Schedule, Resources, Measurements, Resource Usage and Analysis sheets."
                    :disabled="busy"
                    @click="exportWorkbook"
                  >
                    <AppIcon name="export" /><span class="ribbon-label">Export workbook</span>
                  </button>
                </div>
                <small>WORKBOOK</small>
              </div>
            </template>
          </template>
        </div></Teleport
      >
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
      <div v-if="view === 'schedule' && discrepancy" role="status">
        {{ discrepancy.counts.items }} items · {{ discrepancy.counts.mismatch }} mismatches · ≤0.10:
        {{ discrepancy.counts.small }} · ≤1.00: {{ discrepancy.counts.medium }} · >1.00:
        {{ discrepancy.counts.large }} · Missing analysis: {{ discrepancy.counts.missing }}
        <button class="button secondary" @click="discrepancy = undefined">Clear highlighting</button>
        <details>
          <summary>Stored / calculated rates</summary>
          <div v-for="row in discrepancy.rows" :key="row.id">
            {{ row.code }}: {{ formatMoney(row.stored) }} /
            {{ row.calculated == null ? "Missing analysis" : formatMoney(row.calculated) }}
          </div>
        </details>
      </div>
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
      <div
        v-if="isMeasurement && entryId"
        class="measurement-draft-header draft-headerbar"
        role="region"
        aria-label="Measurement records draft"
      >
        <strong :title="state?.detail?.info.note">{{
          state?.detail?.id === entryId ? state.detail.info.label : "Measurement records"
        }}</strong>
        <button
          class="button small danger"
          aria-label="Discard records"
          title="Discard this draft and return to Measurements."
          :disabled="busy || detailBusy || !state?.measurement_draft"
          @click="emit('discardRecords')"
        >
          <AppIcon name="close" /><span>Discard records</span>
        </button>
        <button
          class="button small primary"
          aria-label="Apply records"
          title="Apply records, links and properties to the working project as one undo step (Ctrl+Enter). Return to Measurements after applying. Save the project to retain them on disk."
          :disabled="busy || detailBusy || !state?.measurement_draft"
          @click="emit('applyRecords')"
        >
          <AppIcon name="check" /><span>Apply records</span>
        </button>
      </div>
      <div v-if="isMeasurement && entryId" class="measurement-entry-heading">
        <textarea
          v-if="descriptionDraft !== undefined"
          ref="measurementDescription"
          v-model="descriptionDraft"
          class="measurement-entry-title"
          aria-label="Measurement description / remarks"
          rows="1"
          @blur="finishMeasurementDescription"
          @keydown.esc.stop.prevent="descriptionDraft = undefined"
        />
        <h2
          v-else
          v-middle-ellipsis="fullMeasurementTitle || 'Measurement entry'"
          class="measurement-entry-title five-line-description"
          :title="fullMeasurementTitle"
          :aria-label="fullMeasurementTitle"
          @dblclick="editMeasurementDescription"
        />
        <button
          class="button small secondary"
          aria-label="Edit measurement description / remarks"
          :disabled="busy || state?.detail?.id !== entryId"
          @mousedown.prevent
          @click="descriptionDraft === undefined ? editMeasurementDescription() : measurementDescription?.focus()"
        >
          <AppIcon name="edit" />Edit description
        </button>

        <span class="draft-badge" :class="{ dirty: state?.measurement_draft?.dirty }">{{
          state?.measurement_draft?.dirty ? "Unsaved records" : "Up to date"
        }}</span>
      </div>
      <template v-if="isMeasurement && entryId && state && state.detail && state.detail.id === activeMeasurement">
        <div class="measurement-links">
          <label v-for="(link, index) in state.detail.links" :key="index" class="field"
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
                @click="showLinkPicker(Number(index))"
              >
                <AppIcon name="search" />
              </button>
              <button
                class="icon-button"
                :aria-label="'Clear schedule link ' + (Number(index) + 1)"
                :disabled="busy || (!link.code && !link.missing)"
                title="Remove this schedule association while retaining measurement records and remarks."
                @click="command('link', { id: activeMeasurement, slot: Number(index), code: '', remark: link.remark })"
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
        <div class="measurement-record-summary"><strong>Measurement records</strong></div>
        <div class="table-panel measurement-record-grid">
          <DataTable
            ref="recordTable"
            drag-select-rows
            :active="active && !!entryId"
            :rows="recordRows"
            :columns="recordColumns"
            :busy="busy || detailBusy"
            :select-ids="recordSelectionIds"
            :label="state.detail.info.label + ' records'"
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
        <div class="measurement-total-row" role="status" aria-label="All measurement records total">
          <span>Total · all records</span
          ><strong
            ><template v-for="(total, index) in state.detail.totals" :key="index"
              ><span v-if="index"> · </span>{{ state.detail.links[index]?.label || `Quantity ${Number(index) + 1}` }}:
              {{ total }} {{ state.detail.links[index]?.unit || "" }}</template
            ></strong
          >
        </div>
        <div class="pagination">
          <button
            class="text-button"
            :disabled="busy || detailBusy || !state.detail.offset"
            @click="changeRecordPage(-1)"
          >
            Previous records
          </button>
          <span>{{ state.detail.total_records }} records · Page {{ Math.floor(state.detail.offset / 100) + 1 }}</span>
          <button
            class="text-button"
            :disabled="busy || detailBusy || state.detail.offset + 100 >= state.detail.total_records"
            @click="changeRecordPage(1)"
          >
            Next records
          </button>
        </div>
      </template>
    </template>
    <Dialog
      v-model:visible="moveResourcesOpen"
      modal
      header="Move resources"
      class="workspace-dialog file-dialog"
      :closable="!busy"
    >
      <form
        @submit.prevent="
          async () => {
            if (await command('move_to', { category: moveCategory })) moveResourcesOpen = false;
          }
        "
      >
        <p>Move {{ selected.length }} selected resources, retaining their codes and analysis links.</p>
        <label class="field"
          >Destination category<select v-model="moveCategory" data-primary-input autofocus :disabled="busy">
            <option v-for="category in state?.categories" :key="category">{{ category }}</option>
          </select></label
        >
        <p v-if="error" class="dialog-error" role="alert">{{ error }}</p>
        <div class="dialog-footer">
          <button type="button" class="button secondary" :disabled="busy" @click="moveResourcesOpen = false">
            Cancel</button
          ><button class="button primary" :disabled="busy">Move resources</button>
        </div>
      </form>
    </Dialog>
    <Dialog v-model:visible="resourceRenumberOpen" modal header="Renumber resources" class="workspace-dialog">
      <p>
        Project resources are renumbered. Enable each database below to include its resources; excluded databases keep
        their codes.
      </p>
      <div class="database-toggle-list">
        <div v-for="prefix in resourcePrefixes" :key="prefix" class="database-toggle-row">
          <span>{{ prefix }}</span
          ><button
            type="button"
            class="button small secondary"
            role="switch"
            :aria-label="`Renumber ${prefix} resources`"
            :aria-checked="!excludedPrefixes.includes(prefix)"
            :disabled="busy"
            @click="
              excludedPrefixes = excludedPrefixes.includes(prefix)
                ? excludedPrefixes.filter((value) => value !== prefix)
                : [...excludedPrefixes, prefix]
            "
          >
            {{ excludedPrefixes.includes(prefix) ? "Excluded" : "Enabled" }}
          </button>
        </div>
      </div>
      <p v-if="!resourcePrefixes.length" class="field-hint">No database-prefixed resources in this project.</p>
      <div class="dialog-footer">
        <button class="button secondary" :disabled="busy" @click="resourceRenumberOpen = false">Cancel</button
        ><button
          class="button primary"
          :disabled="busy"
          @click="
            async () => {
              if (await command('renumber', { exclude: excludedPrefixes })) resourceRenumberOpen = false;
            }
          "
        >
          Renumber resources
        </button>
      </div>
    </Dialog>
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
    <Dialog
      v-model:visible="propertiesOpen"
      modal
      :header="propertiesCategory ? 'Edit measurement category' : 'Measurement properties'"
      class="workspace-dialog measurement-properties-dialog"
      :closable="!busy"
      :close-on-escape="!busy"
    >
      <form @submit.prevent="saveProperties">
        <p v-if="propertiesDetail" class="dialog-intro">{{ propertiesDetail.info.note }}</p>
        <label class="field"
          >{{ propertiesCategory ? "Category name" : "Description / remarks"
          }}<textarea
            v-model="properties.description"
            data-primary-input
            autofocus
            :disabled="busy"
            :rows="propertiesCategory ? 1 : 3"
          />
        </label>
        <div class="measurement-properties-fields">
          <label v-for="(link, index) in properties.links" :key="index" class="field"
            >{{ link.label }} · Schedule code {{ index + 1 }}
            <div class="file-input">
              <input v-model="link.code" :aria-label="'Property schedule code ' + (index + 1)" :disabled="busy" />
              <button
                type="button"
                class="icon-button"
                :aria-label="'Choose property schedule item ' + (index + 1)"
                @click="showLinkPicker(index)"
              >
                <AppIcon name="search" />
              </button>
              <button
                type="button"
                class="icon-button"
                :aria-label="'Clear property schedule link ' + (index + 1)"
                @click="link.code = ''"
              >
                <AppIcon name="close" />
              </button>
            </div>
            <input
              v-model="link.remark"
              :aria-label="'Property item remark ' + (index + 1)"
              placeholder="Item remark / column label"
              :disabled="busy"
            />
          </label>
        </div>
        <p v-if="propertiesDetail?.property_groups.length" class="field-hint">
          Numeric constants accept arithmetic; saving stores the evaluated number.
        </p>
        <div class="measurement-property-groups">
          <fieldset v-for="group in propertiesDetail?.property_groups || []" :key="group.label">
            <legend>{{ group.label }}</legend>
            <label v-for="field in group.fields" :key="field.index" class="field"
              >{{ field.label
              }}<input
                v-model="properties.user_data[Number(field.index)]"
                :aria-label="field.caption"
                :inputmode="field.numeric ? 'decimal' : 'text'"
                :disabled="busy"
            /></label>
          </fieldset>
        </div>
        <p v-if="error" role="alert" class="dialog-error">{{ error }}</p>
        <div class="dialog-footer">
          <button type="button" class="button secondary" :disabled="busy" @click="propertiesOpen = false">Cancel</button
          ><button class="button primary" :disabled="busy">Save properties</button>
        </div>
      </form>
    </Dialog>
    <PersistentDialog
      :busy="pickerBusy"
      v-model:visible="pickerOpen"
      modal
      header="Choose schedule item"
      class="workspace-dialog resource-dialog"
    >
      <form
        class="search-field"
        @submit.prevent="
          pickerPage = 0;
          searchLinks();
        "
      >
        <input
          v-model="pickerQuery"
          data-primary-input
          autofocus
          aria-label="Find linked schedule item"
          placeholder="Code or description…"
        /><button class="button small secondary" :disabled="pickerBusy">Search</button>
      </form>
      <p v-if="pickerError" role="alert" class="dialog-error">{{ pickerError }}</p>
      <div class="library-results">
        <button
          v-for="item in pickerItems"
          :key="item.code"
          class="library-item"
          :disabled="pickerBusy"
          :title="item.description"
          @click="chooseLink(item.code)"
        >
          <span
            ><b>{{ item.code }}</b
            ><small v-middle-ellipsis="item.description" class="five-line-description" /></span
          ><span>{{ item.unit }}</span>
        </button>
        <p v-if="!pickerBusy && !pickerItems.length">No schedule items match this search.</p>
      </div>
      <div class="pagination">
        <button
          class="text-button"
          :disabled="pickerBusy || !pickerPage"
          @click="
            pickerPage--;
            searchLinks();
          "
        >
          Previous</button
        ><span>Page {{ pickerPage + 1 }}</span
        ><button
          class="text-button"
          :disabled="pickerBusy || pickerItems.length < 100"
          @click="
            pickerPage++;
            searchLinks();
          "
        >
          Next
        </button>
      </div>
    </PersistentDialog>
    <Dialog
      v-model:visible="formOpen"
      modal
      :header="formMode === 'duplicate' ? 'Duplicate item' : formMode === 'edit' ? 'Edit item' : 'Add item'"
      class="workspace-dialog resource-dialog"
      ><form @submit.prevent="submit">
        <template v-if="isMeasurement"
          ><label v-if="formMode === 'add'" class="field"
            >Measurement template<select v-model="form.template">
              <optgroup v-for="group in ['General', 'Civil', 'E&M']" :key="group" :label="group">
                <option
                  v-for="template in templates.filter((item) => item.group === group)"
                  :key="template.code"
                  :value="template.code"
                >
                  {{ template.label }}
                </option>
              </optgroup></select
            ><small v-if="templateInfo"
              >{{ templateInfo.summary }} {{ templateInfo.note }}<br />Inputs: {{ templateInfo.inputs.join(", ") }} ·
              {{ templateInfo.outputs }} linked {{ templateInfo.outputs === 1 ? "quantity" : "quantities" }}</small
            ></label
          ><label class="field"
            >Category<select v-model="form.category">
              <option value="">Uncategorised</option>
              <option
                v-for="category in mainRows.filter((row) => row.id !== 'measurement:uncategorised')"
                :key="category.id"
                :value="category.description"
              >
                {{ category.description }}
              </option>
            </select></label
          ><label class="field"
            >Description / remarks<textarea data-primary-input autofocus v-model="form.description" rows="3" /></label
        ></template>
        <template v-else
          ><label class="field"
            >New code<input v-model="form.code" aria-label="New code" :required="formMode !== 'add'" /><small
              v-if="formMode === 'add'"
              >Suggested from the current numbering pattern. Edit it, or leave blank to generate a code when
              inserting.</small
            ></label
          ><template v-if="formMode !== 'duplicate'"
            ><label class="field"
              >Description<textarea data-primary-input autofocus v-model="form.description" rows="3" />
            </label>
            <div class="field-pair">
              <label class="field">Unit<input v-model="form.unit" /></label
              ><label class="field">Rate<input v-model="form.rate" required /></label>
            </div>
            <label class="field"
              >Category<ThemedAutocomplete
                v-model="form.category"
                label="Category"
                :suggestions="state?.categories || []"
                :disabled="busy" /></label
            ><template v-if="view === 'schedule'"
              ><label class="field">Quantity<input v-model="form.qty" /></label
              ><label class="field">Parent code (optional)<input v-model="form.parent" /></label
            ></template>
            <div v-else class="field-pair">
              <label class="field">Tax %<input v-model="form.vat" /></label
              ><label class="field">Discount %<input v-model="form.discount" /></label></div></template
        ></template>
        <div v-if="error" class="dialog-error">{{ error }}</div>
        <div class="dialog-footer">
          <button type="button" class="button secondary" @click="formOpen = false">Cancel</button
          ><button class="button primary" :disabled="busy">
            {{ formMode === "duplicate" ? "Duplicate" : formMode === "edit" ? "Save item" : "Add item" }}
          </button>
        </div>
      </form></Dialog
    >
    <Dialog
      v-model:visible="deleteOpen"
      modal
      header="Delete selected items"
      class="workspace-dialog file-dialog"
      :closable="!busy"
    >
      <template v-if="deletion">
        <p class="dialog-intro">
          Delete {{ deletion.items }} item{{ deletion.items === 1 ? "" : "s"
          }}{{
            deletion.categories
              ? ` and ${deletion.categories} ${deletion.categories === 1 ? "category" : "categories"}`
              : ""
          }}? Category contents and child items are included. You can undo this operation.
        </p>
        <p v-if="deletion.used_resources.length" class="dialog-intro">
          {{ deletion.used_resources.length }}
          {{ deletion.used_resources.length === 1 ? "resource is" : "resources are" }}
          used in analyses. Deleting them also removes their analysis entries and recalculates dependent rates.
        </p>
        <p v-if="deletion.measurement_references" class="dialog-intro">
          {{ deletion.measurement_references }} measurement associations will be cleared. Measurement records and
          remarks will be retained.
        </p>
        <div v-if="error" class="dialog-error">{{ error }}</div>
        <div class="dialog-footer">
          <button class="button secondary" :disabled="busy" @click="deleteOpen = false">Cancel</button>
          <button
            v-if="deletion.used_resources.length"
            class="button danger"
            :disabled="busy"
            @click="confirmDeletion('unused')"
          >
            Delete unused
          </button>
          <button
            class="button danger"
            :disabled="busy"
            @click="confirmDeletion(deletion.used_resources.length ? 'all' : 'protect')"
          >
            {{ deletion.used_resources.length ? "Delete including used" : "Delete selected" }}
          </button>
        </div>
      </template>
    </Dialog>
    <Dialog v-model:visible="categoryOpen" modal header="Add category" class="workspace-dialog file-dialog"
      ><label class="field">Category name<input v-model="categoryName" data-primary-input autofocus /></label>
      <div class="dialog-footer">
        <button
          class="button primary"
          :disabled="busy || !categoryName"
          @click="
            command(isMeasurement ? 'add' : 'category_add', {
              description: categoryName,
              ...(isMeasurement ? { category: true } : {}),
            }).then((ok) => {
              if (ok) categoryOpen = false;
            })
          "
        >
          Add category
        </button>
      </div></Dialog
    >
    <MappedImport
      v-if="importOpen"
      v-model="importOpen"
      :kind="view === 'resources' ? 'resources' : 'schedule'"
      :fields="importFields"
      :revision="state?.revision"
      @imported="importDone"
    />
    <SpreadsheetRangeImport
      v-if="multiAnalysisImportOpen"
      v-model="multiAnalysisImportOpen"
      multiple
      :apply="(params) => command('project.import_analysis_apply', params)"
      :error="error"
    />
    <SpreadsheetRangeImport
      v-if="recordImportOpen"
      v-model="recordImportOpen"
      measurement
      :measurement-id="activeMeasurement"
      :apply="
        (params) =>
          command('record_import', {
            ...params,
            id: activeMeasurement,
            record_id: selectedRecord?.id,
          })
      "
      :error="error"
    />
    <ResourceUsage
      v-if="view !== 'measurement'"
      v-model="usageOpen"
      :selected-code="usageCode"
      @analysis="emit('analysis', $event)"
    />
    <Dialog v-model:visible="renumberOpen" modal header="Renumber schedule" class="workspace-dialog">
      <p class="dialog-intro">
        Assign item codes in category and hierarchy order throughout the project. Sub-analysis codes are kept.
      </p>
      <div v-if="error" class="dialog-error" role="alert">{{ error }}</div>
      <div class="dialog-footer">
        <button class="button secondary" :disabled="busy" @click="renumberOpen = false">Cancel</button>
        <button class="button primary" :disabled="busy" @click="renumberSchedule">Renumber</button>
      </div>
    </Dialog>
    <Dialog v-model:visible="colourOpen" modal header="Schedule row colour" class="workspace-dialog">
      <label class="field">
        Row colour
        <div class="colour-palette" role="group" aria-label="Row colour palette">
          <button
            v-for="colour in rowColours"
            :key="colour"
            type="button"
            :aria-label="'Colour ' + colour"
            :aria-pressed="rowColour === colour"
            :style="{ backgroundColor: colour }"
            @click="rowColour = colour"
          />
        </div>
      </label>
      <div v-if="error" class="dialog-error" role="alert">{{ error }}</div>
      <div class="dialog-footer">
        <button class="button secondary" :disabled="busy" @click="applyRowColour(null)">Clear colour</button>
        <button class="button primary" :disabled="busy" @click="applyRowColour(rowColour)">Apply colour</button>
      </div>
    </Dialog>
    <Dialog
      v-model:visible="scheduleQuantityOpen"
      modal
      header="Update selected schedule quantities"
      class="workspace-dialog"
    >
      <p class="dialog-intro">Use linked measurement totals for the selected schedule items.</p>
      <label class="field">
        Quantity rounding
        <select v-model="scheduleRounding" :disabled="busy">
          <option v-for="option in roundingOptions" :key="option">{{ option }}</option>
        </select>
      </label>
      <div v-if="error" class="dialog-error" role="alert">{{ error }}</div>
      <div class="dialog-footer">
        <button class="button primary" :disabled="busy" @click="updateSelectedQuantities">Update quantities</button>
      </div>
    </Dialog>
  </section>
</template>
