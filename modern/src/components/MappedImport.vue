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
const emit = defineEmits<{ imported: [result: { added: number; updated: number; skipped: number; warning_count?: number }] }>();
const names: Record<string, string> = {
  code: "Code", description: "Description", unit: "Unit", rate: "Rate", qty: "Quantity", remarks: "Remarks",
  category: "Category", parent: "Parent code", vat: "Tax %", discount: "Discount %", reference: "Reference",
};
const path = ref("");
const sheet = ref("");
const headerRow = ref(1);
const firstRow = ref<number>();
const lastRow = ref<number>();
const mapping = ref<Record<string, number>>({});
const policy = ref("error");
// GTK structured import: headings and subitems from codes (1.1.1 under 1.1).
const hierarchy = ref(true);
const busy = ref(false);
const error = ref("");
const counting = ref(false);
const counts = ref<{ added: number; updated: number; skipped: number; warnings?: string[]; warning_count?: number }>();
const countError = ref("");
const header = ref<{ sheets: string[]; headers: string[]; rows: string[][]; mapping: Record<string, number> }>();
const workbook = ref<{ sheets: string[]; sheet: string; rows: string[][]; max_row: number; max_column: number }>();
const tags = computed(() => Object.fromEntries(Object.entries(mapping.value).map(([field, index]) => [index + 1, names[field] ?? field])));
const sample = (field: string) => mapping.value[field] === undefined ? "" : header.value?.rows.find(row => row.some(Boolean))?.[mapping.value[field]] ?? "";
const dataFirst = computed(() => firstRow.value && firstRow.value > headerRow.value ? firstRow.value : headerRow.value + 1);
const dataRows = computed(() => Math.max(0, Math.min(lastRow.value || Infinity, workbook.value?.max_row ?? 0) - dataFirst.value + 1));

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
      request<typeof header.value>("project.import_preview", { path: path.value, sheet: sheet.value || undefined, header_row: headerRow.value, first_row: dataFirst.value }),
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
    header_row: headerRow.value, first_row: dataFirst.value, last_row: lastRow.value || undefined, mapping: mapping.value, duplicates: policy.value,
    ...(props.kind === "schedule" ? { hierarchy: hierarchy.value } : {}) };
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
watch([mapping, policy, () => header.value, firstRow, lastRow, hierarchy], () => { clearTimeout(timer); timer = setTimeout(() => void count(), 300); }, { deep: true });
watch(sheet, (value, previous) => { if (previous && value !== previous) { headerRow.value = 1; void load(); } });
/** Click: header row. Ctrl+click: first data row. Shift+click: last data row. */
async function pick(row: number, keys: { shift: boolean; ctrl: boolean }) {
  if (keys.shift) { if (row >= dataFirst.value) lastRow.value = row; return; }
  if (keys.ctrl) { if (row > headerRow.value) firstRow.value = row; if (lastRow.value && lastRow.value < row) lastRow.value = undefined; return; }
  if (row === headerRow.value) return;
  headerRow.value = row;
  firstRow.value = undefined;
  if (lastRow.value && lastRow.value <= row) lastRow.value = undefined;
  await load(false);
}
async function apply() {
  busy.value = true;
  error.value = "";
  try {
    const result = await request<{ added: number; updated: number; skipped: number; warning_count?: number }>("project.import_apply", params());
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
      </div>
      <div v-if="workbook" class="range-import-range">
        <label class="field">Header row <input v-model.number="headerRow" aria-label="Header row" type="number" min="1" :disabled="busy" @change="firstRow = undefined; load(false)" /></label>
        <label class="field">First data row <input v-model.number="firstRow" aria-label="First data row" type="number" :min="headerRow + 1" :placeholder="String(headerRow + 1)" :disabled="busy" /></label>
        <label class="field">Last data row <input v-model.number="lastRow" aria-label="Last data row" type="number" :min="dataFirst" placeholder="End of sheet" :disabled="busy" /></label>
        <p class="range-import-summary" role="status">Rows {{ dataFirst }}–{{ lastRow || workbook.max_row }} ({{ dataRows }} rows)</p>
      </div>
      <template v-if="workbook && header">
        <p class="field-hint">Click a row to use it as the header. Ctrl+click the first data row and Shift+click the last; by default every row below the header is imported. Columns are matched to fields by header name — adjust them below.</p>
        <WorkbookSheetGrid :cells="workbook.rows" :max-row="workbook.max_row" :max-column="workbook.max_column"
          :first-row="headerRow" :data-first="dataFirst" :last-row="lastRow" :first-column="1" :tags="tags" header @pick="(row, _column, keys) => pick(row, keys)" />
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
        <label v-if="kind === 'schedule'" class="import-option"><input v-model="hierarchy" type="checkbox" :disabled="busy" />
          <span>Deduce hierarchy from codes — uppercase description-only rows start a category, unpriced code rows are headings, and 1.1.1 becomes a subitem of 1.1</span></label>
        <section class="range-import-result" aria-label="Import preview">
          <header><strong>Preview</strong>
            <span v-if="mapping.code === undefined" class="field-hint">Choose the Code column to continue.</span>
            <span v-else-if="counting" class="field-hint">Checking {{ dataRows }} rows…</span>
            <span v-else-if="counts" role="status">{{ counts.added }} new · {{ counts.updated }} updated · {{ counts.skipped }} skipped{{ counts.warning_count ? ` · ${counts.warning_count} value${counts.warning_count === 1 ? "" : "s"} read as 0` : "" }}</span>
          </header>
          <ul v-if="counts?.warnings?.length" class="import-warnings" aria-label="Import warnings">
            <li v-for="(warning, index) in counts.warnings.slice(0, 50)" :key="index">{{ warning }}</li>
          </ul>
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
