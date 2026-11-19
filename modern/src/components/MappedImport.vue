<script setup lang="ts">
import { computed, ref, watch } from "vue";
import Dialog from "primevue/dialog";
import { open } from "@tauri-apps/plugin-dialog";
import { request } from "../backend";
import WorkbookSheetGrid from "./WorkbookSheetGrid.vue";

// Schedule/resource worksheet import: pick the header row in the worksheet
// preview, map columns to fields (sample values shown), and see how many rows
// will be added, updated or skipped before importing.
const visible = defineModel<boolean>({ required: true });
const props = defineProps<{ kind: "schedule" | "resources"; fields: string[]; revision?: number }>();
const emit = defineEmits<{ imported: [result: { added: number; updated: number; skipped: number }] }>();
const names: Record<string, string> = {
  code: "Code", description: "Description", unit: "Unit", rate: "Rate", qty: "Quantity", remarks: "Remarks",
  category: "Category", parent: "Parent code", vat: "Tax %", discount: "Discount %", reference: "Reference",
};
const path = ref("");
const sheet = ref("");
const headerRow = ref(1);
const mapping = ref<Record<string, number>>({});
const policy = ref("error");
const busy = ref(false);
const error = ref("");
const counting = ref(false);
const counts = ref<{ added: number; updated: number; skipped: number }>();
const countError = ref("");
const header = ref<{ sheets: string[]; headers: string[]; rows: string[][]; mapping: Record<string, number> }>();
const workbook = ref<{ sheets: string[]; sheet: string; rows: string[][]; max_row: number; max_column: number }>();
const tags = computed(() => Object.fromEntries(Object.entries(mapping.value).map(([field, index]) => [index + 1, names[field] ?? field])));
const sample = (field: string) => mapping.value[field] === undefined ? "" : header.value?.rows.find(row => row.some(Boolean))?.[mapping.value[field]] ?? "";
const dataRows = computed(() => Math.max(0, (workbook.value?.max_row ?? 0) - headerRow.value));

function letter(value: number) {
  let text = "";
  for (let current = value; current > 0; current = Math.floor((current - 1) / 26)) text = String.fromCharCode(65 + ((current - 1) % 26)) + text;
  return text;
}
async function load(resetMapping = true) {
  if (!path.value) return;
  busy.value = true;
  error.value = "";
  try {
    const [grid, preview] = await Promise.all([
      request<typeof workbook.value>("workbook.sheet", { path: path.value, sheet: sheet.value || undefined, rows: 300 }),
      request<typeof header.value>("project.import_preview", { path: path.value, sheet: sheet.value || undefined, header_row: headerRow.value }),
    ]);
    workbook.value = grid;
    header.value = preview;
    if (!sheet.value) sheet.value = grid!.sheet;
    if (resetMapping || !Object.keys(mapping.value).length)
      mapping.value = Object.fromEntries(Object.entries(preview!.mapping).filter(([field]) => props.fields.includes(field)));
  } catch (reason) {
    error.value = String(reason);
  } finally {
    busy.value = false;
  }
}
async function browse() {
  try {
    const result = await open({ multiple: false, filters: [{ name: "Excel workbook", extensions: ["xlsx"] }] });
    if (typeof result === "string") { path.value = result; sheet.value = ""; headerRow.value = 1; await load(); }
  } catch (reason) { error.value = String(reason); }
}
function setColumn(field: string, value: string) {
  const next = { ...mapping.value };
  if (value === "") delete next[field];
  else next[field] = Number(value);
  mapping.value = next;
}
function params() {
  return { revision: props.revision, kind: props.kind, path: path.value, sheet: sheet.value || undefined,
    header_row: headerRow.value, mapping: mapping.value, duplicates: policy.value };
}
let token = 0;
let timer: ReturnType<typeof setTimeout> | undefined;
async function count() {
  if (!header.value || mapping.value.code === undefined) { counts.value = undefined; return; }
  const current = ++token;
  counting.value = true;
  countError.value = "";
  try {
    const result = await request<{ added: number; updated: number; skipped: number }>("project.import_apply", { ...params(), dry_run: true });
    if (current === token) counts.value = result;
  } catch (reason) {
    if (current === token) { counts.value = undefined; countError.value = String(reason).replace(/^Error: /, ""); }
  } finally {
    if (current === token) counting.value = false;
  }
}
watch([mapping, policy, () => header.value], () => { clearTimeout(timer); timer = setTimeout(() => void count(), 300); }, { deep: true });
watch(sheet, (value, previous) => { if (previous && value !== previous) { headerRow.value = 1; void load(); } });
async function pickHeader(row: number) {
  if (row === headerRow.value) return;
  headerRow.value = row;
  await load();
}
async function apply() {
  busy.value = true;
  error.value = "";
  try {
    const result = await request<{ added: number; updated: number; skipped: number }>("project.import_apply", params());
    visible.value = false;
    emit("imported", result);
  } catch (reason) {
    error.value = String(reason);
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <Dialog v-model:visible="visible" modal :header="kind === 'schedule' ? 'Import schedule from Excel' : 'Import resources from Excel'"
    class="workspace-dialog range-import-dialog" :closable="!busy" :close-on-escape="!busy">
    <form class="range-import" @submit.prevent="header ? apply() : load()">
      <ol class="import-steps" aria-label="Steps">
        <li :class="{ done: !!header }">Choose a workbook</li>
        <li :class="{ done: mapping.code !== undefined }">Click the header row and check the columns</li>
        <li>Review and import</li>
      </ol>
      <div class="range-import-source">
        <label class="field">Workbook
          <div class="file-input">
            <input v-model="path" aria-label="Workbook" data-primary-input autofocus :disabled="busy" required placeholder="/path/to/workbook.xlsx" @change="sheet = ''; headerRow = 1; load()" />
            <button type="button" class="button secondary" :disabled="busy" @click="browse">Browse…</button>
          </div>
        </label>
        <label class="field">Worksheet
          <select v-model="sheet" aria-label="Worksheet" :disabled="busy || !workbook">
            <option v-if="!workbook" value="">First worksheet</option>
            <option v-for="name in workbook?.sheets ?? []" :key="name" :value="name">{{ name }}</option>
          </select>
        </label>
        <label class="field">Header row <input v-model.number="headerRow" aria-label="Header row" type="number" min="1" :disabled="busy || !workbook" @change="load()" /></label>
      </div>
      <template v-if="workbook && header">
        <p class="field-hint">Click a row in the worksheet to use it as the header; every row below it is imported. Columns are matched to fields by header name — adjust them below.</p>
        <WorkbookSheetGrid :cells="workbook.rows" :max-row="workbook.max_row" :max-column="workbook.max_column"
          :first-row="headerRow" :first-column="1" :tags="tags" header @pick="row => pickHeader(row)" />
        <div class="mapping-table" role="table" aria-label="Column mapping">
          <div role="row" class="mapping-head"><span role="columnheader">Field</span><span role="columnheader">Worksheet column</span><span role="columnheader">First value</span></div>
          <div v-for="field in fields" :key="field" role="row" class="mapping-row">
            <label role="cell" :for="'map-' + field">{{ names[field] ?? field }}<abbr v-if="field === 'code'" title="Required">*</abbr></label>
            <select role="cell" :id="'map-' + field" :aria-label="(names[field] ?? field) + ' column'" :value="mapping[field] ?? ''" :disabled="busy"
              @change="setColumn(field, ($event.target as HTMLSelectElement).value)">
              <option value="">Do not import</option>
              <option v-for="(name, index) in header.headers" :key="index" :value="index">{{ letter(index + 1) }} · {{ name || "(no header)" }}</option>
            </select>
            <span role="cell" class="mapping-sample">{{ sample(field) }}</span>
          </div>
        </div>
        <label class="field">When a code already exists
          <select v-model="policy" aria-label="Existing codes" :disabled="busy">
            <option value="error">Stop and report it</option>
            <option value="skip">Skip that row</option>
            <option value="update">Update the existing {{ kind === "schedule" ? "item" : "resource" }}</option>
          </select>
        </label>
        <section class="range-import-result" aria-label="Import preview">
          <header><strong>Preview</strong>
            <span v-if="mapping.code === undefined" class="field-hint">Choose the Code column to continue.</span>
            <span v-else-if="counting" class="field-hint">Checking {{ dataRows }} rows…</span>
            <span v-else-if="counts" role="status">{{ counts.added }} new · {{ counts.updated }} updated · {{ counts.skipped }} skipped</span>
          </header>
          <p v-if="countError" class="dialog-error" role="alert">{{ countError }}</p>
        </section>
      </template>
      <div v-if="error" class="dialog-error" role="alert">{{ error }}</div>
      <div class="dialog-footer">
        <button type="button" class="button secondary" :disabled="busy" @click="visible = false">Cancel</button>
        <button v-if="!header" class="button primary" :disabled="busy || !path">Open workbook</button>
        <button v-else type="button" class="button primary" :disabled="busy || counting || !counts || !!countError" @click="apply">
          Import {{ counts ? counts.added + counts.updated : "" }} {{ counts && counts.added + counts.updated === 1 ? "row" : "rows" }}
        </button>
      </div>
    </form>
  </Dialog>
</template>
