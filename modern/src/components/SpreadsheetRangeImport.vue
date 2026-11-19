<script setup lang="ts">
import { formatMoney } from "../numberFormatting";
import { computed, ref, watch } from "vue";
import Dialog from "primevue/dialog";
import { open } from "@tauri-apps/plugin-dialog";
import { request } from "../backend";
import WorkbookSheetGrid from "./WorkbookSheetGrid.vue";

// Guided range import: choose a workbook and worksheet, click the first cell
// in the worksheet preview (Shift+click the last row), and review the parsed
// result before applying. Used for one analysis, several analyses and
// measurement records.
const visible = defineModel<boolean>({ required: true });
const props = defineProps<{
  apply: (params: Record<string, unknown>) => Promise<boolean>;
  error: string;
  measurement?: boolean;
  multiple?: boolean;
  /** Editable template columns, in order (measurement records). */
  columns?: string[];
}>();
const analysisColumns = ["Code", "Description", "Unit", "Quantity", "Rate", "Amount"];
const path = ref("");
const sheet = ref("");
const first = ref(1);
const last = ref<number>();
const column = ref(1);
const rateFirst = ref(false);
const commentPosition = ref(1);
const rounding = ref(-1);
const roundingOptions = [
  { value: -1, label: "Auto" },
  { value: 0, label: "As integer" },
  { value: 1, label: "To 1 decimal place" },
  { value: 2, label: "To 2 decimal places" },
  { value: 1.5, label: "To nearest multiple of 0.5" },
  { value: 2.5, label: "To nearest multiple of 0.05" },
];
const busy = ref(false);
const reviewing = ref(false);
const error = ref("");
type AnalysisLine = { kind: string; code?: string; description: string; unit?: string; qty?: string; rate?: string; amount?: string; remarks?: string };
const preview = ref<{ rows: number; resources: number; rate: string; items?: AnalysisLine[]; matched?: string[]; unmatched?: string[]; warnings?: string[];
  analyses?: { code: string; matched: boolean; description: string; current: string; rate: string; rows: number; resources: number }[] }>();
const workbook = ref<{ sheets: string[]; sheet: string; rows: string[][]; max_row: number; max_column: number }>();
const labels = computed(() => props.measurement ? props.columns ?? [] : rateFirst.value ? ["Code", "Description", "Unit", "Rate", "Quantity", "Amount"] : analysisColumns);
const title = computed(() => props.measurement ? "Import measurement records" : props.multiple ? "Import analyses from Excel" : "Import analysis from Excel");
const fileName = computed(() => path.value.split(/[\\/]/).pop() || "");
const lastColumn = computed(() => column.value + labels.value.length - 1);
// Records are read from the preview cells, matching the backend's row selection.
const records = computed(() => {
  if (!props.measurement || !workbook.value) return [];
  const end = Math.min(last.value || workbook.value.rows.length, workbook.value.rows.length);
  const rows: { row: number; values: string[] }[] = [];
  for (let row = first.value; row <= end; row++) {
    const values = labels.value.map((_, index) => workbook.value!.rows[row - 1]?.[column.value - 1 + index] ?? "");
    if (values.some(Boolean)) rows.push({ row, values });
  }
  return rows;
});
const ready = computed(() => props.measurement ? records.value.length > 0 : props.multiple ? !!preview.value?.matched?.length : !!preview.value);

function letter(value: number) {
  let text = "";
  for (let current = value; current > 0; current = Math.floor((current - 1) / 26)) text = String.fromCharCode(65 + ((current - 1) % 26)) + text;
  return text;
}
function params() {
  return { path: path.value, sheet: sheet.value || undefined, first_row: first.value,
    last_row: last.value || undefined, first_column: column.value, comment_position: commentPosition.value, rounding: rounding.value, rate_first: rateFirst.value };
}
async function loadSheet() {
  if (!path.value) return;
  busy.value = true;
  error.value = "";
  try {
    workbook.value = await request("workbook.sheet", { path: path.value, sheet: sheet.value || undefined, rows: props.measurement ? 2000 : 400 });
    if (!sheet.value) sheet.value = workbook.value!.sheet;
  } catch (reason) {
    workbook.value = undefined;
    error.value = String(reason);
  } finally {
    busy.value = false;
  }
}
async function browse() {
  try {
    const result = await open({ filters: [{ name: "Excel workbook", extensions: ["xlsx"] }] });
    if (typeof result === "string") { path.value = result; sheet.value = ""; await loadSheet(); }
  } catch (reason) {
    error.value = String(reason);
  }
}
function pick(row: number, col: number, keys: { shift: boolean }) {
  if (keys.shift) { if (row >= first.value) last.value = row; return; }
  first.value = row;
  column.value = Math.min(col, 101 - labels.value.length);
  if (last.value && last.value < row) last.value = undefined;
}
let reviewToken = 0;
let reviewTimer: ReturnType<typeof setTimeout> | undefined;
async function review() {
  if (props.measurement || !path.value || !workbook.value) return;
  const token = ++reviewToken;
  reviewing.value = true;
  error.value = "";
  try {
    const result = await request<typeof preview.value>(props.multiple ? "project.import_analysis_preview" : "analysis.import_preview", params());
    if (token === reviewToken) preview.value = result;
  } catch (reason) {
    if (token === reviewToken) { preview.value = undefined; error.value = String(reason); }
  } finally {
    if (token === reviewToken) reviewing.value = false;
  }
}
// Re-parse automatically as the range or options change.
watch([path, sheet, first, last, column, rateFirst, commentPosition, rounding], () => {
  preview.value = undefined;
  clearTimeout(reviewTimer);
  reviewTimer = setTimeout(() => void review(), 350);
});
watch(sheet, (value, previous) => { if (previous && value !== previous) void loadSheet(); });
async function apply() {
  if (!ready.value) return;
  busy.value = true;
  try {
    if (await props.apply(params())) visible.value = false;
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <Dialog v-model:visible="visible" modal :header="title" class="workspace-dialog range-import-dialog" :closable="!busy" :close-on-escape="!busy">
    <form class="range-import" @submit.prevent="workbook ? apply() : loadSheet()">
      <ol class="import-steps" aria-label="Steps">
        <li :class="{ done: !!workbook }">Choose a workbook</li>
        <li :class="{ done: !!workbook && (measurement ? records.length > 0 : !!preview) }">Click the first {{ measurement ? "record" : "code" }} cell</li>
        <li>Review and import</li>
      </ol>
      <div class="range-import-source">
        <label class="field">
          Workbook
          <div class="file-input">
            <input v-model="path" aria-label="Workbook" data-primary-input autofocus :disabled="busy" required placeholder="/path/to/workbook.xlsx" @change="sheet = ''; loadSheet()" />
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
      <template v-if="workbook">
        <div class="range-import-range">
          <label class="field">First row <input v-model.number="first" :disabled="busy" type="number" min="1" required /></label>
          <label class="field">Last row <input v-model.number="last" :disabled="busy" type="number" :min="first" placeholder="End of sheet" /></label>
          <label class="field">First column <input v-model.number="column" :disabled="busy" type="number" min="1" :max="101 - labels.length" required /></label>
          <p class="range-import-summary" role="status">Reading {{ letter(column) }}{{ first }}:{{ letter(lastColumn) }}{{ last || "…" }} from {{ fileName }}</p>
        </div>
        <p class="field-hint">
          {{ measurement
            ? `Click the first record's ${labels[0] || "first"} cell; Shift+click the last record row. Columns are read in template order: ${labels.join(", ")}.`
            : "Click the cell holding the item code above the analysis header (Description, Unit…); Shift+click a last row to stop early. Formula cells use the values saved by Excel or LibreOffice." }}
        </p>
        <WorkbookSheetGrid :cells="workbook.rows" :max-row="workbook.max_row" :max-column="workbook.max_column"
          :first-row="first" :last-row="last" :first-column="column" :labels="labels" @pick="pick" />
        <div v-if="!measurement" class="range-import-options">
          <label><input v-model="rateFirst" :disabled="busy" type="checkbox" /> Rate column comes before quantity</label>
          <label class="field">Resource comments <select aria-label="Resource comments" v-model="commentPosition" :disabled="busy"><option :value="0">Above resource</option><option :value="1">Below resource</option></select></label>
          <label class="field">Rounding <select aria-label="Rounding" v-model="rounding" :disabled="busy"><option v-for="option in roundingOptions" :key="option.value" :value="option.value">{{ option.label }}</option></select></label>
        </div>
        <section class="range-import-result" aria-label="Import preview">
          <header>
            <strong>Preview</strong>
            <span v-if="reviewing" class="field-hint">Reading worksheet…</span>
            <span v-else-if="measurement" role="status">{{ records.length }} record{{ records.length === 1 ? "" : "s" }} will be inserted{{ workbook.max_row > workbook.rows.length && !last ? " (rows beyond the preview are included)" : "" }}</span>
            <span v-else-if="preview && !multiple" role="status">{{ preview.rows }} analysis rows · {{ preview.resources }} resources · rate {{ formatMoney(preview.rate) }}</span>
            <span v-else-if="preview?.matched" role="status">{{ preview.matched.length }} matched · {{ preview.unmatched?.length ?? 0 }} not in this project</span>
          </header>
          <ul v-if="preview?.warnings?.length" class="import-warnings" aria-label="Import warnings">
            <li v-for="(warning, index) in preview.warnings.slice(0, 50)" :key="index">{{ warning }}</li>
          </ul>
          <div class="import-sample">
            <table v-if="measurement && records.length">
              <thead><tr><th>Row</th><th v-for="name in labels" :key="name">{{ name }}</th></tr></thead>
              <tbody><tr v-for="record in records.slice(0, 200)" :key="record.row"><td>{{ record.row }}</td><td v-for="(value, index) in record.values" :key="index">{{ value }}</td></tr></tbody>
            </table>
            <table v-else-if="preview?.items">
              <thead><tr><th>Type</th><th>Code</th><th>Description</th><th>Unit</th><th>Qty / factor</th><th>Rate</th><th>Amount</th></tr></thead>
              <tbody>
                <tr v-for="(line, index) in preview.items" :key="index" :class="'import-line-' + line.kind.toLowerCase()">
                  <td>{{ line.kind }}</td><td>{{ line.code }}</td><td>{{ line.description }}<small v-if="line.remarks" class="import-remark">{{ line.remarks }}</small></td>
                  <td>{{ line.unit }}</td><td class="numeric">{{ line.qty }}</td><td class="numeric">{{ line.rate ? formatMoney(line.rate) : "" }}</td><td class="numeric">{{ line.amount ? formatMoney(line.amount) : "" }}</td>
                </tr>
              </tbody>
            </table>
            <table v-else-if="preview?.analyses">
              <thead><tr><th>Code</th><th>Schedule item</th><th>Rows</th><th>Current rate</th><th>Imported rate</th><th>Status</th></tr></thead>
              <tbody>
                <tr v-for="item in preview.analyses" :key="item.code" :class="{ 'import-unmatched': !item.matched }">
                  <td>{{ item.code }}</td><td>{{ item.description }}</td><td class="numeric">{{ item.rows }}</td>
                  <td class="numeric">{{ item.current ? formatMoney(item.current) : "" }}</td><td class="numeric">{{ formatMoney(item.rate) }}</td>
                  <td>{{ item.matched ? "Will replace analysis" : "Not in project – skipped" }}</td>
                </tr>
              </tbody>
            </table>
            <p v-else-if="!reviewing" class="field-hint">Nothing to import yet. Click the first {{ measurement ? "record" : "code" }} cell in the worksheet above.</p>
          </div>
        </section>
      </template>
      <div v-if="error || props.error" class="dialog-error" role="alert">{{ error || props.error }}</div>
      <div class="dialog-footer">
        <button type="button" class="button secondary" :disabled="busy" @click="visible = false">Cancel</button>
        <button v-if="!workbook" class="button primary" :disabled="busy || !path">Open workbook</button>
        <button v-else type="button" class="button primary" :disabled="busy || reviewing || !ready" @click="apply">
          {{ measurement ? `Import ${records.length} record${records.length === 1 ? "" : "s"}` : multiple ? `Import ${preview?.matched?.length ?? 0} ${preview?.matched?.length === 1 ? "analysis" : "analyses"}` : "Replace analysis draft" }}
        </button>
      </div>
    </form>
  </Dialog>
</template>
