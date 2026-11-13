<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from "vue";
import Dialog from "primevue/dialog";
import { open, save } from "@tauri-apps/plugin-dialog";
import type { ColumnDefinition, CellComponent } from "tabulator-tables";
import DataTable from "./DataTable.vue";
import AppIcon from "./AppIcon.vue";
import ResourceUsage from "./ResourceUsage.vue";
import { request } from "../backend";

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
}
const props = defineProps<{ view: View; projectOpen: boolean }>();
const emit = defineEmits<{
  changed: [];
  busy: [value: boolean];
  analysis: [code: string];
  history: [state: { undo: boolean; redo: boolean }];
}>();
const state = ref<GridState>();
watch(
  () => [state.value?.undo, state.value?.redo],
  () =>
    emit("history", { undo: !!state.value?.undo, redo: !!state.value?.redo }),
);
onBeforeUnmount(() => emit("history", { undo: false, redo: false }));
defineExpose({
  historyAction: (method: "undo" | "redo") => command("project." + method),
  exportWorkbook: () => {
    exportOpen.value = true;
  },
});
const busy = ref(false);
watch(busy, (value) => emit("busy", value));
onBeforeUnmount(() => emit("busy", false));
const error = ref("");
const query = ref("");
const source = ref("");
const libraries = ref<{ id: string; name: string }[]>([]);
const libraryOpen = ref(false);
const libraryPath = ref("");
const usageOpen = ref(false);
const usageCode = ref<string>();
const priceOpen = ref(false);
const priceLibrary = ref("");
const priceResult = ref("");
const pricePreview = ref<{
  ids: string[];
  revision: number;
  changed: number;
  unchanged: number;
  unmatched: number;
}>();
const page = ref(0);
const selected = ref<GridRow[]>([]);
const selectedRecord = ref<GridRow>();
const templates = ref<{ code: string; name: string }[]>([]);
const formOpen = ref(false);
const formMode = ref("add");
const form = ref<Record<string, string>>({});
const categoryOpen = ref(false);
const categoryName = ref("");
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
          "category",
        ]
      : [
          "code",
          "description",
          "unit",
          "rate",
          "qty",
          "amount",
          "remarks",
          "category",
          "parent",
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
      field: c.field,
      minWidth: 110,
      editor: c.editable ? "textarea" : undefined,
      editable: !!c.editable,
      formatter: "textarea",
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
    return false;
  } finally {
    busy.value = false;
  }
}
async function refresh() {
  if (!props.projectOpen) {
    state.value = undefined;
    return;
  }
  libraries.value = await request("library.list");
  state.value = await request(
    isMeasurement.value ? "measurement.state" : props.view + ".editor.state",
    {
      query: query.value,
      source: source.value,
      offset: page.value * 100,
      id: activeMeasurement.value,
    },
  );
}
async function command(
  operation: string,
  params: Record<string, unknown> = {},
) {
  return run(async () => {
    await request(
      operation.startsWith("project.")
        ? operation
        : (isMeasurement.value ? "measurement." : props.view + ".editor.") +
            operation,
      {
        revision: state.value?.revision,
        id: one.value?.id,
        source: source.value,
        ...params,
      },
    );
    await refresh();
    if (operation === "delete") {
      selected.value = [];
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
function showPriceUpdate() {
  priceLibrary.value = libraries.value[0]?.id ?? "";
  pricePreview.value = undefined;
  priceResult.value = "";
  error.value = "";
  priceOpen.value = true;
}
async function previewPriceUpdate() {
  pricePreview.value = undefined;
  const ids = selected.value.map((row) => row.id);
  const revision = state.value!.revision;
  await run(async () => {
    const result = await request<
      Pick<NonNullable<typeof pricePreview.value>, "changed" | "unchanged" | "unmatched">
    >("resources.editor.price_preview", {
      ids,
      revision,
      library: priceLibrary.value,
    });
    pricePreview.value = { ...result, ids, revision };
  });
}
async function applyPriceUpdate() {
  if (!pricePreview.value) return;
  const { ids, revision, changed } = pricePreview.value;
  if (await command("price_update", { ids, revision, library: priceLibrary.value })) {
    priceResult.value = changed === 1
      ? "Updated prices for 1 resource."
      : `Updated prices for ${changed} resources.`;
    priceOpen.value = false;
  }
}
async function select(rows: GridRow[]) {
  selected.value = rows;
  if (
    isMeasurement.value &&
    rows.length === 1 &&
    activeMeasurement.value !== rows[0].id
  ) {
    activeMeasurement.value = rows[0].id;
    await load();
  }
}
function showForm(mode = "add") {
  formMode.value = mode;
  form.value = {
    code: "",
    description: "",
    unit: "",
    rate: "0",
    qty: "0",
    vat: "0",
    discount: "0",
    category: one.value?.category || "",
    parent: "",
    reference: "",
    template: "",
    ...(mode === "duplicate" ? { code: one.value?.code + "-copy" } : {}),
  };
  formOpen.value = true;
}
async function submit() {
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
async function edit(row: GridRow, field: string, value: string) {
  await command(isMeasurement.value ? "edit" : "edit", {
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
    }
  }
}
async function recordEdit(row: GridRow, field: string, value: string) {
  await command("record_edit", {
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
    delta,
  });
}
async function attachLibrary() {
  await run(async () => {
    libraries.value = await request("library.attach", {
      path: libraryPath.value,
    });
    libraryOpen.value = false;
    emit("changed");
  });
}
async function browseLibrary() {
  try {
    const path = await open({
      multiple: false,
      filters: [{ name: "GEstimator library", extensions: ["eproj"] }],
    });
    if (typeof path === "string") libraryPath.value = path;
  } catch (e) {
    error.value = String(e);
  }
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
    query.value = "";
    source.value = "";
    page.value = 0;
    selected.value = [];
    activeMeasurement.value = undefined;
    await load();
  },
);
watch(() => props.projectOpen, load);
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
    <div class="analysis-heading">
      <div>
        <div class="eyebrow">PROJECT WORKSPACE</div>
        <h1>{{ title }}</h1>
        <p>
          Edits are applied to the project working copy. Save a project copy to
          keep them.
        </p>
      </div>
    </div>
    <div v-if="!projectOpen" class="empty-explorer">
      <AppIcon name="folder" :size="35" /><strong
        >Open a project to use this editor.</strong
      >
    </div>
    <template v-else
      ><p v-if="importResult" role="status">{{ importResult }}</p>
      <p v-if="priceResult" role="status">{{ priceResult }}</p>
      <div v-if="error" class="dialog-error" role="alert">{{ error }}</div>
      <Teleport to="#project-ribbon-tools"
        ><div class="view-ribbon-tools">
          <div v-if="!isMeasurement" class="project-tools">
            <label class="source-selector"
              >Data source
              <select
                v-model="source"
                :disabled="busy"
                @change="
                  selected = [];
                  page = 0;
                  load();
                "
              >
                <option value="">Project working copy</option>
                <option
                  v-for="library in libraries"
                  :key="library.id"
                  :value="library.id"
                >
                  {{ library.name }} (library)
                </option>
              </select></label
            ><button
              class="button secondary"
              :disabled="busy"
              @click="libraryOpen = true"
            >
              Attach library…</button
            ><button
              v-if="source"
              class="button primary"
              :disabled="busy || !selected.length"
              @click="
                command('add_from_library', {
                  ids: selected.map((row) => row.id),
                })
              "
            >
              Import selected into project
            </button>
          </div>
          <div v-show="!source" class="project-tools">
            <button
              class="button secondary"
              :disabled="busy"
              @click="showForm()"
            >
              <AppIcon name="plus" :size="15" />{{
                isMeasurement ? "Add measurement" : "Add item"
              }}
            </button>
            <button
              v-if="!isMeasurement"
              class="button secondary"
              :disabled="busy"
              @click="categoryOpen = true"
            >
              Add category
            </button>
            <button
              class="button secondary"
              :disabled="busy || !one || one.rowtype === 'Category'"
              @click="showForm('duplicate')"
            >
              Duplicate
            </button>
            <button
              class="button danger"
              :disabled="busy || !selected.length"
              @click="deleteSelection"
            >
              Delete
            </button>
            <button
              class="button secondary"
              :disabled="busy || !selected.length"
              @click="command('copy', { ids: selected.map((row) => row.id) })"
            >
              Copy</button
            ><button
              class="button secondary"
              :disabled="busy"
              @click="command('paste')"
            >
              Paste
            </button>
            <button
              class="icon-button"
              :disabled="busy || !one"
              aria-label="Move item up"
              @click="command('move', { delta: -1 })"
            >
              <AppIcon name="up" /></button
            ><button
              class="icon-button"
              :disabled="busy || !one"
              aria-label="Move item down"
              @click="command('move', { delta: 1 })"
            >
              <AppIcon name="down" />
            </button>
            <button
              v-if="view === 'schedule'"
              class="button primary"
              :disabled="busy || !one || one.rowtype === 'Category'"
              @click="one && emit('analysis', one.code)"
            >
              Edit analysis
            </button>
            <button
              v-if="view === 'resources'"
              class="button secondary"
              :disabled="busy"
              @click="usageCode = undefined; usageOpen = true"
            >
              Resource usage
            </button>
            <button
              v-if="view === 'resources'"
              class="button secondary"
              :disabled="busy || !one || one.rowtype === 'Category'"
              @click="usageCode = one?.code; usageOpen = true"
            >
              Find analyses
            </button>
            <button
              v-if="view === 'resources'"
              class="button secondary"
              :disabled="busy || !selected.length || !libraries.length"
              @click="showPriceUpdate"
            >
              Update prices from library…
            </button>
            <button
              v-if="view === 'resources'"
              class="button secondary"
              :disabled="busy"
              @click="command('rates')"
            >
              Update dependent rates
            </button>
            <select
              v-if="isMeasurement"
              v-model="quantityRounding"
              aria-label="Quantity rounding"
            >
              <option v-for="option in roundingOptions" :key="option">
                {{ option }}
              </option>
            </select>
            <button
              v-if="isMeasurement"
              class="button secondary"
              :disabled="busy"
              @click="
                command('update_quantities', { rounding: quantityRounding })
              "
            >
              Update schedule quantities
            </button>
            <button
              v-if="!isMeasurement"
              class="button secondary"
              :disabled="busy"
              @click="importOpen = true"
            >
              Import workbook
            </button>
            <span class="spacer" /><button
              class="button secondary"
              :disabled="busy"
              @click="exportOpen = true"
            >
              Export workbook
            </button>
          </div>
        </div></Teleport
      >
      <form
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
      </form>
      <label v-else class="field"
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
          :key="source"
          :rows="state?.rows || []"
          :columns="columns"
          :busy="busy"
          :tree="!isMeasurement"
          @selection="select"
          @edit="edit"
          @paste="pasteCells"
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
      <template v-if="isMeasurement && state?.detail">
        <div class="measurement-links">
          <label
            v-for="(link, index) in state.detail.links"
            :key="index"
            class="field"
            >Schedule code {{ Number(index) + 1
            }}<input
              :value="link.code"
              :disabled="busy"
              @change="
                command('link', {
                  id: activeMeasurement,
                  slot: Number(index),
                  code: ($event.target as HTMLInputElement).value,
                  remark: link.remark,
                })
              "
            /><input
              :value="link.remark"
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
          ><label
            v-for="(field, index) in state.detail.user_data"
            :key="'user' + index"
            class="field"
            >{{ field.caption
            }}<input
              :value="field.value"
              :disabled="busy"
              @change="
                command('userdata', {
                  id: activeMeasurement,
                  slot: Number(index),
                  value: ($event.target as HTMLInputElement).value,
                })
              "
          /></label>
        </div>
        <div class="project-tools">
          <strong>Measurement records</strong
          ><button
            class="button small secondary"
            :disabled="busy"
            @click="recordAction('add')"
          >
            Add record</button
          ><button
            class="button small secondary"
            :disabled="busy || !selectedRecord"
            @click="recordAction('duplicate')"
          >
            Duplicate record</button
          ><button
            class="button small danger"
            :disabled="busy || !selectedRecord"
            @click="recordAction('delete')"
          >
            Delete record</button
          ><button
            class="button small secondary"
            :disabled="busy || !selectedRecord"
            @click="recordAction('copy')"
          >
            Copy record</button
          ><button
            class="button small secondary"
            :disabled="busy"
            @click="recordAction('paste')"
          >
            Paste record</button
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
            :rows="state.detail.rows"
            :columns="recordColumns"
            :busy="busy"
            @selection="selectedRecord = $event[0]"
            @edit="recordEdit"
            @paste="pasteCells"
          />
        </div>
      </template>
    </template>
    <Dialog
      v-model:visible="formOpen"
      modal
      :header="formMode === 'duplicate' ? 'Duplicate item' : 'Add item'"
      class="workspace-dialog resource-dialog"
      ><form @submit.prevent="submit">
        <template v-if="isMeasurement"
          ><label v-if="formMode === 'add'" class="field"
            >Measurement template<select v-model="form.template">
              <option value="">Heading</option>
              <option
                v-for="template in templates"
                :key="template.code"
                :value="template.code"
              >
                {{ template.name }}
              </option>
            </select></label
          ><label class="field"
            >Description / remarks<textarea
              v-model="form.description"
              rows="3"
            /></label
        ></template>
        <template v-else
          ><label class="field"
            >New code<input v-model="form.code" required /></label
          ><template v-if="formMode === 'add'"
            ><label class="field"
              >Description<textarea
                v-model="form.description"
                required
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
            {{ formMode === "duplicate" ? "Duplicate" : "Add item" }}
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
            command('project.export_xlsx', { path: exportPath }).then((ok) => {
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
    <ResourceUsage
      v-if="view === 'resources'"
      v-model="usageOpen"
      :selected-code="usageCode"
      @analysis="emit('analysis', $event)"
    />
    <Dialog
      v-model:visible="priceOpen"
      modal
      header="Update resource prices from library"
      class="workspace-dialog"
    >
      <p>Update the rate, VAT, discount and reference of selected resources with matching codes.</p>
      <label class="field">
        Price library
        <select v-model="priceLibrary" :disabled="busy" @change="pricePreview = undefined">
          <option v-for="library in libraries" :key="library.id" :value="library.id">
            {{ library.name }}
          </option>
        </select>
      </label>
      <p v-if="pricePreview" role="status">
        {{ pricePreview.changed }} to update, {{ pricePreview.unchanged }} already current,
        {{ pricePreview.unmatched }} without a matching code.
      </p>
      <div v-if="error" class="dialog-error" role="alert">{{ error }}</div>
      <div class="dialog-footer">
        <button class="button secondary" :disabled="busy" @click="previewPriceUpdate">
          Preview updates
        </button>
        <button class="button primary" :disabled="busy || !pricePreview?.changed" @click="applyPriceUpdate">
          Update prices
        </button>
      </div>
    </Dialog>
    <Dialog
      v-model:visible="libraryOpen"
      modal
      header="Attach resource / schedule library"
      class="workspace-dialog file-dialog"
      ><p class="dialog-intro">
        Browses an isolated copy. Imported items are added to the project
        working copy; the library file is preserved.
      </p>
      <label class="field"
        >Library project
        <div class="file-input">
          <input v-model="libraryPath" /><button
            class="button secondary"
            @click="browseLibrary"
          >
            Browse
          </button>
        </div></label
      >
      <div v-if="error" class="dialog-error">{{ error }}</div>
      <div class="dialog-footer">
        <button
          class="button primary"
          :disabled="busy || !libraryPath"
          @click="attachLibrary"
        >
          Attach library
        </button>
      </div></Dialog
    >
  </section>
</template>
