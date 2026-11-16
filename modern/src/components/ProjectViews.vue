<script setup lang="ts">
import { computed, nextTick, onMounted, onBeforeUnmount, ref, watch } from "vue";
import Dialog from "primevue/dialog";
import { open, save } from "@tauri-apps/plugin-dialog";
import type { ColumnDefinition, CellComponent } from "tabulator-tables";
import DataTable from "./DataTable.vue";
import AppIcon from "./AppIcon.vue";
import SpreadsheetRangeImport from "./SpreadsheetRangeImport.vue";
import ResourceUsage from "./ResourceUsage.vue";
import CategoryFilter from "./CategoryFilter.vue";
import { request } from "../backend";
import { programSettings } from "../programSettings";
import { copyRows, pasteRows, type ClipboardKind } from "../rowClipboard";

type View = "schedule" | "resources" | "measurement";
interface GridRow {
  id: string;
  [key: string]: any;
}
interface GridState {
  rows: GridRow[];
  total?: number;
  offset?: number;
  undo: boolean;
  redo: boolean;
  revision: number;
  caption?: string;
  detail?: any;
  categories?: string[];
  enrichment?: { ai_generated: boolean; summary: string } | null;
}
const props = defineProps<{ view: View; projectOpen: boolean }>();
const emit = defineEmits<{
  changed: [];
  busy: [value: boolean];
  analysis: [code: string];
  history: [state: { undo: boolean; redo: boolean }];
  libraries: [];
  database: [options: { kind: "schedule" | "resources"; mode: "add" | "rates"; revision: number; targetIds: string[] }];
  analysisRules: [ids: string[]];
}>();
const state = ref<GridState>();
const emptyRows: GridRow[] = [];
watch(
  () => [state.value?.undo, state.value?.redo],
  () =>
    emit("history", { undo: !!state.value?.undo, redo: !!state.value?.redo }),
);
onBeforeUnmount(() => emit("history", { undo: false, redo: false }));
defineExpose({
  reload: () => load(),
  handleKeyboard: keyboard,
  historyAction: (method: "undo" | "redo") => command("project." + method),
  applyDatabase,
  lastError: () => error.value,
  exportWorkbook: () => {
    exportOpen.value = true;
  },
});
const busy = ref(false);
watch(busy, (value) => emit("busy", value));
onBeforeUnmount(() => emit("busy", false));
const error = ref("");
const clipboardMessage = ref("");
const query = ref("");
const categoryFilters = ref<string[]>([]);
watch(categoryFilters, () => { page.value = 0; void load(); });
const source = ref("");
const libraries = ref<{ id: string; name: string }[]>([]);
const usageOpen = ref(false);
const usageCode = ref<string>();
const page = ref(0);
const selected = ref<GridRow[]>([]);
const selectedRecord = ref<GridRow>();
const selectedRecords = ref<GridRow[]>([]);
const recordSelectionIds = ref<string[]>();
const templates = ref<{ code: string; name: string; label: string; group: string; summary: string; note: string; inputs: string[]; outputs: number }[]>([]);
const templateInfo = computed(() => templates.value.find(template => template.code === form.value.template));
const recordPage = ref(0);
const recordCount = ref(10);
const recordsOpen = ref(false);
const propertiesOpen = ref(false);
const properties = ref<{ description: string; links: { code: string; remark: string; label: string }[]; user_data: string[] }>({ description: "", links: [], user_data: [] });
const propertiesRevision = ref(0);
const pickerOpen = ref(false);
const pickerSlot = ref(0);
const pickerQuery = ref("");
const pickerPage = ref(0);
const pickerItems = ref<{ code: string; description: string; unit: string }[]>([]);
const pickerBusy = ref(false);
const detailBusy = ref(false);
const pickerError = ref("");
let selectionRequest = 0;
const mainTable = ref<InstanceType<typeof DataTable>>();
const recordTable = ref<InstanceType<typeof DataTable>>();
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
const importPath = ref("");
const importSheet = ref("");
const importPreview = ref<{
  sheets: string[];
  headers: string[];
  rows: string[][];
  mapping: Record<string, number>;
}>();
const importMapping = ref<Record<string, number>>({});
const importPolicy = ref("error");
const headerRow = ref(1);
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
const importResult = ref("");
const importFields = computed(() =>
  props.view === "resources"
    ? [
        "code",
        "description",
        "unit",
        "rate",
        "vat",
        "discount",
        "reference",
        "category",
      ]
    : [
        "code",
        "description",
        "unit",
        "rate",
        "qty",
        "remarks",
        "category",
        "parent",
      ],
);
const exportOpen = ref(false);
const exportPath = ref("");
const activeMeasurement = ref<string>();
const one = computed(() =>
  selected.value.length === 1 ? selected.value[0] : undefined,
);
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
function editable(cell: CellComponent) {
  return cell.getData().rowtype !== "Category";
}
const columns = computed<ColumnDefinition[]>(() => {
  if (isMeasurement.value)
    return [
      { title: "TYPE", field: "type", width: 180 },
      {
        title: "DESCRIPTION / REMARKS",
        field: "description",
        editor: "textarea",
        minWidth: 260,
      },
      { title: "RECORDS", field: "count", width: 90 },
      { title: "TOTALS", field: "totals", width: 180 },
    ];
  const fields =
    props.view === "resources"
      ? [
          "code",
          "description",
          "unit",
          "rate",
          "vat",
          "discount",
          "reference",
        ]
      : [
          "code",
          "description",
          "unit",
          "rate",
          "qty",
          "amount",
          "remarks",
        ];
  return fields.map((field) => ({
    title: field.toUpperCase(),
    field,
    minWidth: field === "description" ? 280 : 95,
    widthGrow: field === "description" ? 3 : 1,
    editor:
      field === "amount"
        ? undefined
        : field === "description" || field === "remarks"
          ? "textarea"
          : "input",
    editable: (cell) =>
      !source.value && (field === "description" || editable(cell)),
    hozAlign: ["qty", "rate", "amount", "vat", "discount"].includes(field)
      ? "right"
      : "left",
  }));
});
const recordColumns = computed<ColumnDefinition[]>(
  () =>
    state.value?.detail?.columns.map((c: any) => ({
      title: c.title,
      titleFormatter: () => { const label = document.createElement("span"); label.className = "measurement-column-title"; label.textContent = c.title; return label; },
      field: c.field,
      minWidth: c.width || 80,
      width: c.expand ? undefined : c.width || 80,
      widthGrow: c.expand ? 1 : 0,
      hozAlign: c.numeric ? "right" : "left",
      cssClass: c.editable ? "" : "measurement-derived",
      headerTooltip: () => { const label = document.createElement("span"); label.textContent = c.editable ? `${c.title}: editable measurement input; arithmetic expressions are retained` : `${c.title}: calculated by the measurement template; read-only`; return label; },
      editor: c.editable ? "textarea" : undefined,
      editable: !!c.editable,
      formatter: (cell: CellComponent) => {
        const element = document.createElement("span");
        element.className = "measurement-cell-value";
        element.textContent = String(cell.getData()._display?.[cell.getField()] ?? cell.getValue() ?? "");
        return element;
      },
      variableHeight: true,
    })) || [],
);
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
const rowActions = computed(() => source.value ? [] : [
  { label: "Add item after selection", action: "add" },
  ...(props.view === "schedule" ? [{ label: "Add subitem", action: "child", itemOnly: true, single: true }, { label: "Open analysis", action: "activate", itemOnly: true, single: true }] : [{ label: isMeasurement.value ? "Measurement properties…" : "Edit resource…", action: "properties", single: true, itemOnly: !isMeasurement.value }]),
  { label: "Copy selected rows", action: "copy" }, { label: "Paste rows here", action: "paste" },
  { label: "Duplicate selection", action: "duplicate", single: !isMeasurement.value, itemOnly: !isMeasurement.value }, { label: "Delete selection…", action: "delete" },
]);
function rowAction(operation: string) {
  if (operation === "add") void showForm();
  else if (operation === "child") void showSubitem();
  else if (operation === "activate" && one.value) activateRow(one.value);
  else if (operation === "properties") { if (isMeasurement.value) showProperties(); else if (one.value?.rowtype !== "Category") void showForm("edit"); }
  else if (operation === "delete") void deleteSelection();
  else if (operation === "duplicate" && !isMeasurement.value) { if (one.value && one.value.rowtype !== "Category") void showForm("duplicate"); }
  else void command(operation);
}
async function refresh(revealId?: string) {
  if (!props.projectOpen) {
    state.value = undefined;
    return;
  }
  if (!isMeasurement.value) libraries.value = await request("library.list");
  state.value = await request(
    isMeasurement.value ? "measurement.state" : props.view + ".editor.state",
    {
      query: query.value,
      categories: categoryFilters.value,
      source: source.value,
      offset: page.value * 100,
      id: activeMeasurement.value,
      record_offset: recordPage.value * 100,
      reveal_id: revealId,
    },
  );
  if (!isMeasurement.value) {
    const retained = categoryFilters.value.filter(name => state.value?.categories?.includes(name));
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
async function command(
  operation: string,
  params: Record<string, unknown> = {},
) {
  return run(async () => {
    clipboardMessage.value = "";
    const clipboardParams = { revision: state.value?.revision, id: one.value?.id, ids: selected.value.map(row => row.id), source: source.value, ...params };
    const clipboardKind: ClipboardKind = operation.startsWith("record_") ? "records" : props.view;
    let result: { selected?: string[]; selected_records?: string[]; record_offset?: number } | undefined;
    if (operation === "copy" || operation === "record_copy") {
      clipboardMessage.value = await copyRows(clipboardKind, clipboardParams);
      return;
    } else if (operation === "paste" || operation === "record_paste") {
      const pasted = await pasteRows(clipboardKind, clipboardParams);
      result = pasted;
      clipboardMessage.value = pasted.unlinked ? `Rows pasted. ${pasted.unlinked} missing schedule links were cleared; records and remarks were retained.` : "Rows pasted.";
    } else result = await request(
      operation.startsWith("project.")
        ? operation
        : (isMeasurement.value ? "measurement." : props.view + ".editor.") +
            operation,
      {
        revision: state.value?.revision,
        id: one.value?.id,
        ids: selected.value.map((row) => row.id),
        source: source.value,
        target_ids: workingSelection.value,
        ...params,
      },
    );
    if (result?.selected && isMeasurement.value) {
      activeMeasurement.value = result.selected.length === 1 ? result.selected[0] : undefined;
      recordPage.value = 0;
    }
    if (result?.record_offset !== undefined) recordPage.value = result.record_offset / 100;
    if (result?.selected && !isMeasurement.value) { query.value = ""; categoryFilters.value = []; }
    await refresh(!isMeasurement.value ? result?.selected?.[0] : undefined);
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
    await command("delete");
    return;
  }
  const ids = selected.value.map((row) => row.id);
  const revision = state.value!.revision;
  const ok = await run(async () => {
    const preview = await request<
      Omit<NonNullable<typeof deletion.value>, "ids" | "revision">
    >(props.view + ".editor.delete_preview", { ids, revision });
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
    await command("delete_many", {
      ids: deletion.value.ids,
      revision: deletion.value.revision,
      policy,
    })
  ) {
    deleteOpen.value = false;
    deletion.value = undefined;
  }
}
async function load() {
  await run(refresh);
}
function showRowColour() {
  rowColour.value = /^#[0-9a-f]{6}$/i.test(one.value?.colour ?? "")
    ? one.value?.colour.toLowerCase()
    : "#ffe082";
  error.value = "";
  colourOpen.value = true;
}
async function applyRowColour(colour: string | null) {
  if (await command("colour", { ids: selectedScheduleIds.value, colour }))
    colourOpen.value = false;
}
async function renumberSchedule() {
  if (await command("renumber")) renumberOpen.value = false;
}
async function updateSelectedQuantities() {
  if (await command("update_quantities", {
    ids: selectedScheduleIds.value,
    rounding: scheduleRounding.value,
  }))
    scheduleQuantityOpen.value = false;
}
function showPriceUpdate() {
  showDatabase("rates");
}
function showDatabase(mode: "add" | "rates" = "add") {
  if (!state.value || isMeasurement.value) return;
  error.value = "";
  emit("database", { kind: props.view === "resources" ? "resources" : "schedule", mode, revision: state.value.revision, targetIds: selected.value.map(row => row.id) });
}
async function applyDatabase(params: Record<string, unknown>) {
  const { operation, ...values } = params;
  return command(String(operation), { ...values, ...(values.modify ? { settings: programSettings.value } : {}) });
}
async function select(rows: GridRow[]) {
  if (!rows.length && !selected.value.length) return;
  selected.value = rows;
  if (isMeasurement.value && rows.length === 1 &&
      activeMeasurement.value !== rows[0].id) {
    activeMeasurement.value = rows[0].id;
    recordPage.value = 0;
    selectedRecord.value = undefined;
    selectedRecords.value = [];
    recordSelectionIds.value = undefined;
    await loadDetail();
  }
}
async function loadDetail() {
  const token = ++selectionRequest;
  const identity = activeMeasurement.value;
  detailBusy.value = true;
  try {
    const detail = await request<Partial<GridState>>("measurement.detail", { id: identity, record_offset: recordPage.value * 100 });
    if (token === selectionRequest && identity === activeMeasurement.value && state.value && (detail.revision ?? 0) >= state.value.revision)
      { state.value = { ...state.value, ...detail }; if (detail.detail) recordPage.value = detail.detail.offset / 100; }
  } catch (reason) { if (token === selectionRequest) error.value = String(reason); }
  finally { if (token === selectionRequest) detailBusy.value = false; }
}
async function changeRecordPage(delta: number) {
  recordPage.value = Math.max(0, recordPage.value + delta);
  selectedRecord.value = undefined;
  selectedRecords.value = [];
  recordSelectionIds.value = undefined;
  await loadDetail();
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
    template: "",
    ...(mode === "duplicate" ? { code: one.value?.code + "-copy" } : {}),
    ...(mode === "edit" ? Object.fromEntries(importFields.value.map(field => [field, String(one.value?.[field] ?? "")])) : {}),
  };
  if (mode === "add" && !isMeasurement.value) {
    if (!await run(async () => {
      Object.assign(form.value, await request(props.view + ".editor.defaults", { ids: selected.value.map(row => row.id), child }));
    })) return;
  }
  formOpen.value = true;
}
async function showSubitem() {
  if (props.view !== "schedule" || !one.value || one.value.rowtype === "Category") return;
  await showForm("add", true);
}
async function submit() {
  if (formMode.value === "edit") {
    const edits = Object.entries(form.value).filter(([field, value]) => importFields.value.includes(field) && value !== String(one.value?.[field] ?? ""))
      .map(([field, value]) => ({ id: one.value!.id, field, value }));
    if (!edits.length || await command("edit_many", { edits })) formOpen.value = false;
    return;
  }
  const op = isMeasurement.value
    ? formMode.value === "duplicate"
      ? "duplicate"
      : "add"
    : formMode.value;
  if (
    await command(
      op,
      isMeasurement.value
        ? { template: form.value.template, description: form.value.description }
        : { data: form.value },
    )
  )
    formOpen.value = false;
}
async function showProperties() {
  if (!one.value || !state.value) return;
  const identity = one.value.id;
  if (one.value.type !== "Heading" && state.value.detail?.id !== identity) await loadDetail();
  if (one.value?.id !== identity) return;
  const detail = state.value.detail;
  properties.value = { description: one.value.description, links: detail?.links.map((link: any) => ({ code: link.code, remark: link.remark, label: link.label })) || [], user_data: detail?.user_data.map((field: any) => field.value) || [] };
  propertiesRevision.value = state.value.revision;
  error.value = "";
  propertiesOpen.value = true;
}
async function saveProperties() {
  if (await command("properties", { id: one.value?.id, revision: propertiesRevision.value, ...properties.value })) propertiesOpen.value = false;
}
async function searchLinks() {
  pickerBusy.value = true;
  pickerError.value = "";
  try { pickerItems.value = await request("schedule.list", { query: pickerQuery.value, offset: pickerPage.value * 100 }); }
  catch (reason) { pickerError.value = String(reason); }
  finally { pickerBusy.value = false; }
}
async function showLinkPicker(slot: number) {
  pickerSlot.value = slot;
  pickerQuery.value = "";
  pickerPage.value = 0;
  pickerOpen.value = true;
  await searchLinks();
}
async function chooseLink(code: string) {
  if (propertiesOpen.value) properties.value.links[pickerSlot.value]!.code = code;
  else if (!await command("link", { id: activeMeasurement.value, slot: pickerSlot.value, code, remark: state.value?.detail.links[pickerSlot.value].remark || "" })) return;
  pickerOpen.value = false;
}
function activateRow(row: GridRow) {
  if (source.value || row.rowtype === "Category") return;
  if (props.view === "schedule") emit("analysis", row.code);
  else if (props.view === "resources") void showForm("edit");
  else if (state.value?.detail) void nextTick(() => recordTable.value?.focus());
  else showProperties();
}
async function edit(row: GridRow, field: string, value: string) {
  return command("edit", {
    id: row.id,
    field,
    value,
  });
}
async function pasteCells(
  edits: { id: string; field: string; value: string }[],
) {
  await command(isMeasurement.value ? "record_edit_many" : "edit_many", {
    id: isMeasurement.value ? activeMeasurement.value : one.value?.id,
    edits,
  });
}
function keyboard(event: KeyboardEvent) {
  if (event.defaultPrevented || !props.projectOpen || busy.value || document.querySelector('[role="dialog"]')) return;
  if (
    (event.target as HTMLElement).closest(
      "input,textarea,select,[contenteditable=true]",
    )
  )
    return;
  if (event.ctrlKey || event.metaKey) {
    const key = event.key.toLowerCase();
    if (key === "z" || key === "y") {
      event.preventDefault();
      event.stopPropagation();
      void command(
        key === "y" || event.shiftKey ? "project.redo" : "project.undo",
      );
      return;
    }
  }
  const target = event.target as HTMLElement;
  if (source.value) return;
  const records = !!target.closest(".measurement-record-grid");
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
      emit("analysis", one.value.code);
      return;
    }
    if (key === "e" && one.value && props.view !== "schedule") {
      event.preventDefault(); event.stopPropagation();
      if (isMeasurement.value) showProperties(); else if (one.value.rowtype !== "Category") void showForm("edit");
      return;
    }
    if (key === "l" && props.view !== "measurement") {
      event.preventDefault(); event.stopPropagation();
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
  const delta = event.altKey && event.key === "ArrowUp" ? -1
    : event.altKey && event.key === "ArrowDown" ? 1 : 0;
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
async function recordEdit(row: GridRow, field: string, value: string) {
  return command("record_edit", {
    id: activeMeasurement.value,
    record_id: row.id,
    field,
    value,
  });
}
async function recordAction(operation: string, delta?: number) {
  await command("record_" + operation, {
    id: activeMeasurement.value,
    record_id: selectedRecord.value?.id,
    record_ids: selectedRecords.value.map(row => row.id),
    delta,
  });
}
async function previewImport() {
  await run(async () => {
    importPreview.value = await request("project.import_preview", {
      path: importPath.value,
      sheet: importSheet.value || undefined,
      header_row: headerRow.value,
    });
    importMapping.value = Object.fromEntries(
      Object.entries(importPreview.value!.mapping).filter(([field]) =>
        importFields.value.includes(field),
      ),
    );
  });
}
async function browseImport() {
  try {
    const path = await open({
      multiple: false,
      filters: [{ name: "Excel workbook", extensions: ["xlsx"] }],
    });
    if (typeof path === "string") {
      importPath.value = path;
      await previewImport();
    }
  } catch (e) {
    error.value = String(e);
  }
}
async function applyImport() {
  await run(async () => {
    const result = await request<{
      added: number;
      updated: number;
      skipped: number;
    }>("project.import_apply", {
      revision: state.value?.revision,
      kind: props.view,
      path: importPath.value,
      sheet: importSheet.value || undefined,
      header_row: headerRow.value,
      mapping: importMapping.value,
      duplicates: importPolicy.value,
    });
    await refresh();
    emit("changed");
    importOpen.value = false;
    importResult.value = `Imported ${result.added} new, ${result.updated} updated, ${result.skipped} skipped.`;
  });
}
async function exportBrowse() {
  try {
    const path = await save({
      filters: [{ name: "Excel workbook", extensions: ["xlsx"] }],
    });
    if (path) exportPath.value = path;
  } catch (e) {
    error.value = String(e);
  }
}
watch(
  () => props.view,
  async () => {
    workingSelection.value = [];
    selectionRequest++;
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
  if (!previous) workingSelection.value = selected.value.map(row => row.id);
  selected.value = [];
  selectionIds.value = undefined;
  page.value = 0;
  await load();
  if (!value) selectionIds.value = workingSelection.value;
});
onMounted(async () => {
  await load();
  if (props.projectOpen)
    templates.value = await request("measurement.templates");
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
      <AppIcon name="folder" :size="35" /><strong
        >Open a project to use this editor.</strong
      >
    </div>
    <template v-else
      ><p v-if="importResult" role="status">{{ importResult }}</p>
      <p v-if="clipboardMessage" role="status">{{ clipboardMessage }}</p>
      <div v-if="error" class="dialog-error" role="alert">{{ error }}</div>
      <Teleport to="#project-ribbon-tools"
        ><div class="view-ribbon-tools">
          <div v-if="!isMeasurement" class="ribbon-group">
            <div class="ribbon-actions">
              <button class="ribbon-action" :aria-label="view === 'schedule' ? 'Add item from database' : 'Add resources from database'" title="Select items from attached databases in a separate dialog. The working table and its insertion selection remain in place (Ctrl+L)." :disabled="busy" @click="showDatabase()"><AppIcon name="database" /><span class="ribbon-label">Add from database</span></button>
              <button v-if="view === 'resources'" class="ribbon-action" aria-label="Refresh selected rates from database" title="Choose an attached database, preview rates matching selected project codes, and apply as one undoable update." :disabled="busy || !selected.length" @click="showPriceUpdate"><AppIcon name="refresh" /><span class="ribbon-label">Database rates</span></button>
            </div><small>DATABASE</small>
          </div>
          <template v-if="!source">
          <div class="ribbon-group">
            <div class="ribbon-actions">
            <button
              class="ribbon-action"
              :aria-label="isMeasurement ? 'Add measurement' : 'Add item'"
              :title="isMeasurement ? 'Add a heading or a custom measurement item using a shipped measurement template (Ctrl+I).' : 'Create an item in the selected category with its code, description and numeric fields (Ctrl+I).'"
              :disabled="busy"
              @click="showForm()"
            >
              <AppIcon name="plus" :size="15" /><span class="ribbon-label">Add item</span>
            </button>
            <button v-if="view === 'schedule'" class="ribbon-action" aria-label="Add subitem"
              title="Create a child of the selected schedule item. Its category follows the parent; the parent code is filled in for you (Ctrl+Shift+I)."
              :disabled="busy || !one || one.rowtype === 'Category'" @click="showSubitem">
              <AppIcon name="child" /><span class="ribbon-label">Add subitem</span>
            </button>
            <button
              v-if="!isMeasurement"
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
              class="ribbon-action ribbon-icon"
              aria-label="Copy"
              title="Copy selected items or categories, including off-page contents, to the system clipboard for use in this or another GEstimator window (Ctrl+C)."
              :disabled="busy || !selected.length"
              @click="command('copy', { ids: selected.map((row) => row.id) })"
            >
              <AppIcon name="copy" /><span class="ribbon-label">Copy</span></button
            ><button
              class="ribbon-action ribbon-icon"
              aria-label="Paste"
              title="Paste rows copied from the same editor in any GEstimator window. Schedule and resource code collisions receive a copy suffix; measurement links match schedule codes. Undo restores the previous state (Ctrl+V)."
              :disabled="busy"
              @click="command('paste')"
            >
              <AppIcon name="paste" /><span class="ribbon-label">Paste</span>
            </button>
            <button class="ribbon-action ribbon-icon danger" aria-label="Delete" title="Preview deletion of selected items and category contents before confirming. Project Undo restores the operation."
              :disabled="busy || !selected.length" @click="deleteSelection">
              <AppIcon name="trash" /><span class="ribbon-label">Delete</span></button>
            </div>
            <small>EDIT</small>
          </div>
          <div class="ribbon-group">
            <div class="ribbon-actions">
            <button
              class="ribbon-action ribbon-icon"
              :disabled="busy || (isMeasurement ? !selected.length : !one)"
              aria-label="Move item up"
              title="Move the selected item or category earlier among its siblings while preserving its contents and links."
              @click="command('move', { delta: -1 })"
            >
              <AppIcon name="up" /><span class="ribbon-label">Move up</span></button
            ><button
              class="ribbon-action ribbon-icon"
              :disabled="busy || (isMeasurement ? !selected.length : !one)"
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
              title="Open the selected schedule item in the Analysis editor to inspect and edit its rate calculation."
              :disabled="busy || !one || one.rowtype === 'Category'"
              @click="one && emit('analysis', one.code)"
            >
              <AppIcon name="edit" /><span class="ribbon-label">Edit analysis</span>
            </button>
            <button class="ribbon-action" aria-label="Bulk edit analysis…" title="Match and modify analysis rows across selected schedule items/categories or the whole schedule. Preview ordered rules and rate changes before applying as one project undo step." :disabled="busy" @click="emit('analysisRules', selected.map(row => row.id))"><AppIcon name="filter" /><span class="ribbon-label">Bulk edit analysis</span></button>
            <button
              class="ribbon-action"
              aria-label="Renumber schedule…"
              title="Choose numbering options for the schedule hierarchy. Item links are preserved and the operation can be undone."
              :disabled="busy || !state?.total"
              @click="error = ''; renumberOpen = true"
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
              @click="error = ''; scheduleQuantityOpen = true"
            >
              <AppIcon name="ruler" /><span class="ribbon-label">Measured quantities</span>
            </button>
            <button
              class="ribbon-action"
              aria-label="Resource usage"
              title="View aggregate project resource quantities and amounts, search totals, and navigate to referencing analyses."
              :disabled="busy"
              @click="usageCode = undefined; usageOpen = true"
            >
              <AppIcon name="chart" /><span class="ribbon-label">Resource usage</span>
            </button>
            </div>
            <small>SCHEDULE</small>
          </div>
          <div v-if="view === 'resources'" class="ribbon-group">
            <div class="ribbon-actions ribbon-actions-wide">
            <button class="ribbon-action ribbon-icon" aria-label="Edit resource" title="Edit all fields of the selected resource together. Only changed fields are saved, as one undoable operation (Ctrl+E). Enter edits the focused cell." :disabled="busy || !one || one.rowtype === 'Category'" @click="showForm('edit')"><AppIcon name="edit" /><span class="ribbon-label">Edit resource</span></button>
            <button class="ribbon-action ribbon-icon" aria-label="Move resources…" title="Move selected definitions to another category without making copies or breaking analysis links. Undo restores their previous categories." :disabled="busy || !selected.length || selected.some(row => row.rowtype === 'Category')" @click="moveCategory = state?.categories?.[0] || ''; moveResourcesOpen = true"><AppIcon name="category" /><span class="ribbon-label">Move resources</span></button>
            <button
              class="ribbon-action"
              aria-label="Resource usage"
              title="View aggregate project resource quantities and amounts, search totals, and navigate to referencing analyses."
              :disabled="busy"
              @click="usageCode = undefined; usageOpen = true"
            >
              <AppIcon name="chart" /><span class="ribbon-label">Resource usage</span>
            </button>
            <button
              class="ribbon-action"
              aria-label="Find analyses"
              title="Find schedule analyses that use the selected resource directly or through nested sub-analyses."
              :disabled="busy || !one || one.rowtype === 'Category'"
              @click="usageCode = one?.code; usageOpen = true"
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
            </div>
            <small>RESOURCES</small>
          </div>
          <div v-if="isMeasurement" class="ribbon-group">
            <div class="ribbon-actions ribbon-measure-actions">
            <select
              v-model="quantityRounding"
              aria-label="Quantity rounding"
            >
              <option v-for="option in roundingOptions" :key="option">
                {{ option }}
              </option>
            </select>
            <button
              class="ribbon-action"
              aria-label="Update schedule quantities"
              title="Update schedule quantities from linked measurement totals using the selected rounding rule. Project Undo restores the previous quantities."
              :disabled="busy"
              @click="
                command('update_quantities', { rounding: quantityRounding })
              "
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
              @click="exportOpen = true"
            >
              <AppIcon name="export" /><span class="ribbon-label">Export workbook</span>
            </button>
          </div>
          <small>WORKBOOK</small>
          </div>
          </template>
        </div></Teleport
      >
      <div v-if="state?.enrichment" class="project-filter-bar" role="note">
        <small class="enrichment-badge">AI-generated</small>
        <span>{{ state.enrichment.summary || 'Optional database enrichment' }}</span>
        <button v-if="!source" class="text-button" :disabled="busy" @click="command('project.enrichment.clear')">Clear enrichment</button>
      </div>
      <div v-if="!isMeasurement" class="project-filter-bar"><form
        v-if="!isMeasurement"
        class="search-field project-search"
        @submit.prevent="
          page = 0;
          load();
        "
      >
        <AppIcon name="search" :size="16" /><input
          v-model="query"
          aria-label="Search project table"
          placeholder="Search codes and descriptions…"
        /><button class="button small secondary" :disabled="busy">
          Search
        </button>
      </form><CategoryFilter v-model="categoryFilters" :categories="state?.categories || []" :disabled="busy" /></div>
      <label v-else class="field measurement-caption"
        >Measurement caption<input
          :value="state?.caption"
          :disabled="busy"
          @change="
            command('caption', {
              value: ($event.target as HTMLInputElement).value,
            })
          "
      /></label>
      <div class="table-panel project-main-grid">
        <DataTable
          ref="mainTable"
          :key="source"
          :label="title"
          :rows="state?.rows || emptyRows"
          :columns="columns"
          :busy="busy"
          :tree="!isMeasurement"
          :select-ids="selectionIds"
          :actions="rowActions"
          :save-cell="edit"
          @action="rowAction"
          @selection="select"
          @paste="pasteCells"
          @paste-rows="data => command('paste', { clipboardData: data })"
          @activate="activateRow"
        />
      </div>
      <div v-if="!isMeasurement" class="pagination">
        <button
          class="text-button"
          :disabled="busy || page === 0"
          @click="
            page--;
            load();
          "
        >
          Previous</button
        ><span>{{ state?.total || 0 }} items · Page {{ page + 1 }}</span
        ><button
          class="text-button"
          :disabled="busy || (page + 1) * 100 >= (state?.total || 0)"
          @click="
            page++;
            load();
          "
        >
          Next
        </button>
      </div>
      <template v-if="isMeasurement && selected.length === 1 && state && state.detail && state.detail.id === activeMeasurement">
        <div class="measurement-summary">
          <strong :title="state.detail.info.summary + ' ' + state.detail.info.note">{{ state.detail.info.label }}</strong>
          <button class="button small secondary" title="Edit description, schedule links and template properties together. Save applies one undoable change; Cancel leaves the item unchanged (Ctrl+E)." @click="showProperties"><AppIcon name="settings" />Properties…</button>
        </div>
        <div class="measurement-links">
          <label
            v-for="(link, index) in state.detail.links"
            :key="index"
            class="field"
            >{{ link.label }} · Schedule code {{ Number(index) + 1
            }}<div class="file-input"><input
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
            /><button class="icon-button" :aria-label="'Choose schedule item ' + (Number(index) + 1)" :disabled="busy" title="Search project schedule codes and descriptions for this measured quantity." @click="showLinkPicker(Number(index))"><AppIcon name="search" /></button>
            <button class="icon-button" :aria-label="'Clear schedule link ' + (Number(index) + 1)" :disabled="busy || (!link.code && !link.missing)" title="Remove this schedule association while retaining measurement records and remarks." @click="command('link', { id: activeMeasurement, slot: Number(index), code: '', remark: link.remark })"><AppIcon name="close" /></button></div>
            <small v-if="link.description" :title="link.description">{{ link.description }} <span v-if="link.unit">({{ link.unit }})</span></small><input
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
        <div class="project-tools">
          <strong>Measurement records</strong
          ><button
            class="button small secondary"
            :disabled="busy"
            @click="recordAction('add')"
          >
            <AppIcon name="plus" :size="15" />Add record</button
          ><button class="icon-button" aria-label="Add multiple records" title="Insert 1 to 1000 blank records in one operation. Undo removes the complete batch." :disabled="busy" @click="recordCount = 10; recordsOpen = true"><AppIcon name="rows" /></button
          ><button
            class="button small secondary"
            :disabled="busy"
            @click="error = ''; recordImportOpen = true"
          >
            <AppIcon name="import" :size="15" />Import records…</button
          ><button
            class="button small secondary"
            :disabled="busy || !selectedRecord"
            @click="recordAction('duplicate')"
          >
            <AppIcon name="duplicate" :size="15" />Duplicate record</button
          ><button
            class="button small danger"
            :disabled="busy || !selectedRecord"
            @click="recordAction('delete')"
          >
            <AppIcon name="trash" :size="15" />Delete record</button
          ><button
            class="button small secondary"
            :disabled="busy || !selectedRecord"
            title="Copy selected records in their current order to the system clipboard for use in any measurement item with the same template (Ctrl+C in the records table)."
            @click="recordAction('copy')"
          >
            <AppIcon name="copy" :size="15" />Copy record</button
          ><button
            class="button small secondary"
            :disabled="busy"
            title="Insert a copied record after the selected record, or at the end. The destination must use the same measurement template; Undo restores the previous records (Ctrl+V in the records table)."
            @click="recordAction('paste')"
          >
            <AppIcon name="paste" :size="15" />Paste record</button
          ><button
            class="icon-button"
            :disabled="busy || !selectedRecord"
            aria-label="Move record up"
            title="Move record up"
            @click="recordAction('move', -1)"
          >
            <AppIcon name="up" /></button
          ><button
            class="icon-button"
            :disabled="busy || !selectedRecord"
            aria-label="Move record down"
            title="Move record down"
            @click="recordAction('move', 1)"
          >
            <AppIcon name="down" /></button
          ><span class="spacer" /><span
            >Totals: {{ state.detail.totals.join(" · ") }}</span
          >
        </div>
        <div class="table-panel measurement-record-grid">
          <DataTable
            ref="recordTable"
            :rows="state.detail.rows"
            :columns="recordColumns"
            :busy="busy || detailBusy"
            :select-ids="recordSelectionIds"
            :label="state.detail.info.label + ' records'"
            :actions="[{ label: 'Insert record', action: 'add' }, { label: 'Duplicate record', action: 'duplicate' }, { label: 'Copy record', action: 'copy' }, { label: 'Paste records here', action: 'paste' }, { label: 'Delete record', action: 'delete' }]"
            @action="operation => recordAction(operation)"
            @selection="selectedRecords = $event; selectedRecord = $event[0]"
            :save-cell="recordEdit"
            @paste="pasteCells"
            @paste-rows="data => command('record_paste', { id: activeMeasurement, record_id: selectedRecord?.id, record_ids: selectedRecords.map(row => row.id), clipboardData: data })"
          />
        </div>
        <div class="pagination">
          <button class="text-button" :disabled="busy || detailBusy || !state.detail.offset" @click="changeRecordPage(-1)">Previous records</button>
          <span>{{ state.detail.total_records }} records · Page {{ Math.floor(state.detail.offset / 100) + 1 }}</span>
          <button class="text-button" :disabled="busy || detailBusy || state.detail.offset + 100 >= state.detail.total_records" @click="changeRecordPage(1)">Next records</button>
        </div>
      </template>
    </template>
    <Dialog v-model:visible="moveResourcesOpen" modal header="Move resources" class="workspace-dialog file-dialog" :closable="!busy">
      <form @submit.prevent="async () => { if (await command('move_to', { category: moveCategory })) moveResourcesOpen = false; }">
        <p>Move {{ selected.length }} selected resources, retaining their codes and analysis links.</p>
        <label class="field">Destination category<select v-model="moveCategory" :disabled="busy"><option v-for="category in state?.categories" :key="category">{{ category }}</option></select></label>
        <p v-if="error" class="dialog-error" role="alert">{{ error }}</p><div class="dialog-footer"><button type="button" class="button secondary" :disabled="busy" @click="moveResourcesOpen = false">Cancel</button><button class="button primary" :disabled="busy">Move resources</button></div>
      </form>
    </Dialog>
    <Dialog v-model:visible="recordsOpen" modal header="Insert measurement records" class="workspace-dialog file-dialog" :closable="!busy" :close-on-escape="!busy">
      <form @submit.prevent="async () => { if (await command('record_add', { id: activeMeasurement, record_id: selectedRecord?.id, count: recordCount })) recordsOpen = false; }">
        <p>Insert blank records after the selected record, or at the end. Undo removes the entire batch.</p>
        <label class="field">Number of records<input v-model.number="recordCount" type="number" min="1" max="1000" required :disabled="busy" /></label>
        <p v-if="error" role="alert" class="dialog-error">{{ error }}</p>
        <div class="dialog-footer"><button type="button" class="button secondary" :disabled="busy" @click="recordsOpen = false">Cancel</button><button class="button primary" :disabled="busy">Insert records</button></div>
      </form>
    </Dialog>
    <Dialog v-model:visible="propertiesOpen" modal header="Measurement properties" class="workspace-dialog measurement-properties-dialog" :closable="!busy" :close-on-escape="!busy">
      <form @submit.prevent="saveProperties">
        <p v-if="state?.detail" class="dialog-intro">{{ state.detail.info.note }}</p>
        <label class="field">Description / remarks<textarea v-model="properties.description" :disabled="busy" rows="3" /></label>
        <div class="measurement-properties-fields">
          <label v-for="(link, index) in properties.links" :key="index" class="field">{{ link.label }} · Schedule code {{ index + 1 }}
            <div class="file-input"><input v-model="link.code" :aria-label="'Property schedule code ' + (index + 1)" :disabled="busy" />
              <button type="button" class="icon-button" :aria-label="'Choose property schedule item ' + (index + 1)" @click="showLinkPicker(index)"><AppIcon name="search" /></button>
              <button type="button" class="icon-button" :aria-label="'Clear property schedule link ' + (index + 1)" @click="link.code = ''"><AppIcon name="close" /></button></div>
            <input v-model="link.remark" :aria-label="'Property item remark ' + (index + 1)" placeholder="Item remark / column label" :disabled="busy" />
          </label>
        </div>
        <p v-if="state?.detail?.property_groups.length" class="field-hint">Numeric constants accept arithmetic; saving stores the evaluated number.</p>
        <div class="measurement-property-groups">
          <fieldset v-for="group in state?.detail?.property_groups || []" :key="group.label"><legend>{{ group.label }}</legend>
            <label v-for="field in group.fields" :key="field.index" class="field">{{ field.label }}<input v-model="properties.user_data[Number(field.index)]" :aria-label="field.caption" :inputmode="field.numeric ? 'decimal' : 'text'" :disabled="busy" /></label>
          </fieldset>
        </div>
        <p v-if="error" role="alert" class="dialog-error">{{ error }}</p>
        <div class="dialog-footer"><button type="button" class="button secondary" :disabled="busy" @click="propertiesOpen = false">Cancel</button><button class="button primary" :disabled="busy">Save properties</button></div>
      </form>
    </Dialog>
    <Dialog v-model:visible="pickerOpen" modal header="Choose schedule item" class="workspace-dialog resource-dialog">
      <form class="search-field" @submit.prevent="pickerPage = 0; searchLinks()"><input v-model="pickerQuery" aria-label="Find linked schedule item" placeholder="Code or description…" /><button class="button small secondary" :disabled="pickerBusy">Search</button></form>
      <p v-if="pickerError" role="alert" class="dialog-error">{{ pickerError }}</p>
      <div class="library-results">
        <button v-for="item in pickerItems" :key="item.code" class="library-item" :disabled="pickerBusy" :title="item.description" @click="chooseLink(item.code)"><span><b>{{ item.code }}</b><small>{{ item.description }}</small></span><span>{{ item.unit }}</span></button>
        <p v-if="!pickerBusy && !pickerItems.length">No schedule items match this search.</p>
      </div>
      <div class="pagination"><button class="text-button" :disabled="pickerBusy || !pickerPage" @click="pickerPage--; searchLinks()">Previous</button><span>Page {{ pickerPage + 1 }}</span><button class="text-button" :disabled="pickerBusy || pickerItems.length < 100" @click="pickerPage++; searchLinks()">Next</button></div>
    </Dialog>
    <Dialog
      v-model:visible="formOpen"
      modal
      :header="formMode === 'duplicate' ? 'Duplicate item' : formMode === 'edit' ? 'Edit item' : 'Add item'"
      class="workspace-dialog resource-dialog"
      ><form @submit.prevent="submit">
        <template v-if="isMeasurement"
          ><label v-if="formMode === 'add'" class="field"
            >Measurement template<select v-model="form.template">
              <option value="">Heading</option>
              <optgroup v-for="group in ['General', 'Civil', 'E&M']" :key="group" :label="group">
                <option v-for="template in templates.filter(item => item.group === group)" :key="template.code" :value="template.code">{{ template.label }}</option>
              </optgroup>
            </select><small v-if="templateInfo">{{ templateInfo.summary }} {{ templateInfo.note }}<br />Inputs: {{ templateInfo.inputs.join(', ') }} · {{ templateInfo.outputs }} linked {{ templateInfo.outputs === 1 ? 'quantity' : 'quantities' }}</small></label
          ><label class="field"
            >Description / remarks<textarea
              v-model="form.description"
              rows="3"
            /></label
        ></template>
        <template v-else
          ><label class="field"
            >New code<input v-model="form.code" aria-label="New code" :required="formMode !== 'add'" /><small v-if="formMode === 'add'">Suggested using the GTK numbering rules. Edit it, or leave blank to generate a code when inserting.</small></label
          ><template v-if="formMode !== 'duplicate'"
            ><label class="field"
              >Description<textarea
                v-model="form.description"
                rows="3"
              />
            </label>
            <div class="field-pair">
              <label class="field">Unit<input v-model="form.unit" /></label
              ><label class="field"
                >Rate<input v-model="form.rate" required
              /></label>
            </div>
            <label class="field"
              >Category<input
                v-model="form.category"
                list="project-categories"
              /><datalist id="project-categories">
                <option v-for="category in state?.categories" :key="category">
                  {{ category }}
                </option>
              </datalist></label
            ><template v-if="view === 'schedule'"
              ><label class="field">Quantity<input v-model="form.qty" /></label
              ><label class="field"
                >Parent code (optional)<input v-model="form.parent" /></label
            ></template>
            <div v-else class="field-pair">
              <label class="field">VAT %<input v-model="form.vat" /></label
              ><label class="field"
                >Discount %<input v-model="form.discount"
              /></label></div></template
        ></template>
        <div v-if="error" class="dialog-error">{{ error }}</div>
        <div class="dialog-footer">
          <button
            type="button"
            class="button secondary"
            @click="formOpen = false"
          >
            Cancel</button
          ><button class="button primary" :disabled="busy">
            {{ formMode === "duplicate" ? "Duplicate" : formMode === 'edit' ? 'Save item' : "Add item" }}
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
          }}? Category contents and child items are included. You can undo this
          operation.
        </p>
        <p v-if="deletion.used_resources.length" class="dialog-intro">
          {{ deletion.used_resources.length }}
          {{
            deletion.used_resources.length === 1
              ? "resource is"
              : "resources are"
          }}
          used in analyses. Deleting them also removes their analysis entries
          and recalculates dependent rates.
        </p>
        <p v-if="deletion.measurement_references" class="dialog-intro">
          {{ deletion.measurement_references }} measurement associations will be
          cleared. Measurement records and remarks will be retained.
        </p>
        <div v-if="error" class="dialog-error">{{ error }}</div>
        <div class="dialog-footer">
          <button
            class="button secondary"
            :disabled="busy"
            @click="deleteOpen = false"
          >
            Cancel
          </button>
          <button
            v-if="deletion.used_resources.length"
            class="button secondary"
            :disabled="busy"
            @click="confirmDeletion('unused')"
          >
            Delete unused
          </button>
          <button
            class="button danger"
            :disabled="busy"
            @click="
              confirmDeletion(
                deletion.used_resources.length ? 'all' : 'protect',
              )
            "
          >
            {{
              deletion.used_resources.length
                ? "Delete including used"
                : "Delete selected"
            }}
          </button>
        </div>
      </template>
    </Dialog>
    <Dialog
      v-model:visible="categoryOpen"
      modal
      header="Add category"
      class="workspace-dialog file-dialog"
      ><label class="field"
        >Category name<input v-model="categoryName"
      /></label>
      <div class="dialog-footer">
        <button
          class="button primary"
          :disabled="busy || !categoryName"
          @click="
            command('category_add', { description: categoryName }).then(
              (ok) => {
                if (ok) categoryOpen = false;
              },
            )
          "
        >
          Add category
        </button>
      </div></Dialog
    >
    <Dialog
      v-model:visible="exportOpen"
      modal
      header="Export project workbook"
      class="workspace-dialog file-dialog"
      ><p class="dialog-intro">
        Exports the applied working copy using the original schedule, resource,
        measurement and analysis spreadsheet writers.
      </p>
      <label class="field"
        >New Excel file
        <div class="file-input">
          <input
            v-model="exportPath"
            placeholder="/path/to/estimate.xlsx"
          /><button class="button secondary" @click="exportBrowse">
            Browse
          </button>
        </div></label
      >
      <div v-if="error" class="dialog-error">{{ error }}</div>
      <div class="dialog-footer">
        <button
          class="button primary"
          :disabled="busy || !exportPath"
          @click="
            command('project.export_xlsx', { path: exportPath, break_lines: programSettings?.export_break_items ?? true }).then((ok) => {
              if (ok) exportOpen = false;
            })
          "
        >
          Export workbook
        </button>
      </div></Dialog
    >
    <Dialog
      v-model:visible="importOpen"
      modal
      header="Import spreadsheet"
      class="workspace-dialog resource-dialog"
      ><p class="dialog-intro">
        Map worksheet columns into this editor. The whole import is one undoable
        transaction.
      </p>
      <label class="field"
        >Workbook
        <div class="file-input">
          <input v-model="importPath" aria-label="Workbook" /><button
            class="button secondary"
            @click="browseImport"
          >
            Browse</button
          ><button
            class="button secondary"
            :disabled="busy || !importPath"
            @click="previewImport"
          >
            Preview
          </button>
        </div></label
      ><template v-if="importPreview"
        ><div class="field-pair">
          <label class="field"
            >Worksheet<select v-model="importSheet" @change="previewImport">
              <option value="">First worksheet</option>
              <option v-for="sheet in importPreview.sheets" :key="sheet">
                {{ sheet }}
              </option>
            </select></label
          ><label class="field"
            >Header row<input
              v-model.number="headerRow"
              type="number"
              min="1"
              @change="previewImport"
          /></label>
        </div>
        <div class="import-mapping">
          <label v-for="field in importFields" :key="field" class="field"
            >{{ field
            }}<select
              :value="importMapping[field] ?? ''"
              @change="
                ($event.target as HTMLSelectElement).value === ''
                  ? delete importMapping[field]
                  : (importMapping[field] = Number(
                      ($event.target as HTMLSelectElement).value,
                    ))
              "
            >
              <option value="">Do not import</option>
              <option
                v-for="(header, index) in importPreview.headers"
                :key="index"
                :value="index"
              >
                {{ index + 1 }} · {{ header }}
              </option>
            </select></label
          >
        </div>
        <label class="field"
          >Existing codes<select v-model="importPolicy">
            <option value="error">Reject duplicates</option>
            <option value="skip">Skip existing codes</option>
            <option value="update">Update existing items</option>
          </select></label
        >
        <div class="import-sample">
          <table>
            <thead>
              <tr>
                <th
                  v-for="(header, index) in importPreview.headers"
                  :key="index"
                >
                  {{ header }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, index) in importPreview.rows" :key="index">
                <td v-for="(value, col) in row" :key="col">{{ value }}</td>
              </tr>
            </tbody>
          </table>
        </div></template
      >
      <div v-if="error" class="dialog-error">{{ error }}</div>
      <div class="dialog-footer">
        <button
          class="button primary"
          :disabled="busy || !importPreview || importMapping.code === undefined"
          @click="applyImport"
        >
          Import rows
        </button>
      </div></Dialog
    >
    <SpreadsheetRangeImport v-if="recordImportOpen" v-model="recordImportOpen" measurement
      :apply="(params) => command('record_import', {
        ...params, id: activeMeasurement, record_id: selectedRecord?.id,
      })" :error="error" />
    <ResourceUsage
      v-if="view !== 'measurement'"
      v-model="usageOpen"
      :selected-code="usageCode"
      @analysis="emit('analysis', $event)"
    />
    <Dialog
      v-model:visible="renumberOpen"
      modal
      header="Renumber schedule"
      class="workspace-dialog"
    >
      <p class="dialog-intro">Assign item codes in category and hierarchy order throughout the project. Sub-analysis codes are kept.</p>
      <div v-if="error" class="dialog-error" role="alert">{{ error }}</div>
      <div class="dialog-footer">
        <button class="button secondary" :disabled="busy" @click="renumberOpen = false">
          Cancel
        </button>
        <button class="button primary" :disabled="busy" @click="renumberSchedule">
          Renumber
        </button>
      </div>
    </Dialog>
    <Dialog
      v-model:visible="colourOpen"
      modal
      header="Schedule row colour"
      class="workspace-dialog"
    >
      <label class="field">
        Row colour
        <input v-model="rowColour" type="color" :disabled="busy" />
      </label>
      <div v-if="error" class="dialog-error" role="alert">{{ error }}</div>
      <div class="dialog-footer">
        <button class="button secondary" :disabled="busy" @click="applyRowColour(null)">
          Clear colour
        </button>
        <button class="button primary" :disabled="busy" @click="applyRowColour(rowColour)">
          Apply colour
        </button>
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
        <button class="button primary" :disabled="busy" @click="updateSelectedQuantities">
          Update quantities
        </button>
      </div>
    </Dialog>
  </section>
</template>
