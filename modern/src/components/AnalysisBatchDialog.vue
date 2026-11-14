<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import Dialog from "primevue/dialog";
import AppIcon from "./AppIcon.vue";
import { request, type AnalysisRow, type AnalysisState, type RowKind } from "../backend";

interface TemplateRow { kind: Exclude<RowKind, "Resource">; description: string; value: string }
const props = defineProps<{
  template?: boolean;
  selected: AnalysisRow[];
  state: AnalysisState;
  apply: (params: Record<string, unknown>) => Promise<boolean>;
}>();
const visible = defineModel<boolean>({ required: true });
const kinds = ["Group", "Subtotal", "Weight", "Multiply", "Round"] as const;
const rows = ref<TemplateRow[]>([]);
const field = ref("description");
const value = ref("");
const busy = ref(false);
const error = ref("");
const status = ref("");
const preview = ref<AnalysisState>();
const prepared = ref<Record<string, unknown>>();
const fields = computed(() => {
  const common = ["description"];
  if (props.selected.every(row => ["Resource", "Weight", "Multiply", "Round"].includes(row.kind))) common.push("value");
  if (props.selected.every(row => row.kind === "Resource")) common.push("rate", "vat", "discount", "unit", "reference", "category", "remarks");
  return common;
});
const labels: Record<string, string> = { description: "Description", value: "Quantity / factor", rate: "Base rate", vat: "VAT %", discount: "Discount %", unit: "Unit", reference: "Reference", category: "Category", remarks: "Entry remarks" };
function invalidate() { preview.value = undefined; prepared.value = undefined; error.value = ""; }
watch([field, value, rows], invalidate, { deep: true });
watch(() => props.state.revision, invalidate);
async function defaults() {
  rows.value = await request<TemplateRow[]>("analysis.template_rows");
}
onMounted(async () => {
  if (!props.template) return;
  try {
    const stored = JSON.parse(localStorage.getItem("gestimator.analysis-template.v1") || "null");
    if (stored?.version === 1 && Array.isArray(stored.rows) && stored.rows.length > 0 && stored.rows.length <= 100 && stored.rows.every((row: TemplateRow) => row && kinds.includes(row.kind) && typeof row.description === "string" && row.description.length <= 10000 && typeof row.value === "string" && row.value.length <= 200)) {
      rows.value = stored.rows.map((row: TemplateRow) => ({ kind: row.kind, description: row.description, value: row.value }));
    } else await defaults();
  } catch {
    try { await defaults(); status.value = "Loaded shipped rows because the saved template could not be read."; }
    catch (failure) { error.value = String(failure); }
  }
});
async function saveTemplate() {
  await calculate();
  if (!preview.value) return;
  try {
    localStorage.setItem("gestimator.analysis-template.v1", JSON.stringify({ version: 1, rows: rows.value }));
    status.value = "Template saved for this application. No project data changed.";
  } catch { error.value = "The template could not be saved to application preferences."; }
}
function move(index: number, delta: number) {
  const next = index + delta;
  if (next < 0 || next >= rows.value.length) return;
  [rows.value[index], rows.value[next]] = [rows.value[next]!, rows.value[index]!];
}
async function calculate() {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    const operations = props.template
      ? rows.value.map(row => ({ method: "add", kind: row.kind, description: row.description, value: row.value }))
      : props.selected.map(row => ({ method: "edit", id: row.id, field: field.value, value: value.value }));
    const params = { revision: props.state.revision, id: props.selected[0]?.id, operations };
    preview.value = await request<AnalysisState>("analysis.batch.preview", params);
    prepared.value = params;
  } catch (failure) { invalidate(); error.value = String(failure); }
  finally { busy.value = false; }
}
async function apply() {
  if (!prepared.value || busy.value) return;
  busy.value = true;
  try {
    if (await props.apply(prepared.value)) visible.value = false;
    else { invalidate(); error.value = "The batch could not be applied. Check the editor error and preview again with the latest state."; }
  } finally { busy.value = false; }
}
const previewRows = computed(() => preview.value?.rows.flatMap(row => [row, ...(row._children || [])]) || []);
</script>

<template>
  <Dialog v-model:visible="visible" modal :header="template ? 'Custom analysis template' : 'Bulk edit analysis'" class="workspace-dialog batch-dialog" :closable="!busy" :close-on-escape="!busy">
    <p class="dialog-intro">{{ template ? 'Configure reusable calculation rows and preview their insertion after the selection. Saving this template changes application preferences only.' : `Set one field on ${selected.length} selected rows. Resource definition changes also affect other uses of the same resource in this draft.` }} Preview leaves the draft unchanged. Applying the preview is one analysis undo step; apply the analysis and save the project to retain it.</p>
    <template v-if="template">
      <div class="template-rows">
        <div v-for="(row, index) in rows" :key="index" class="template-row">
          <label>Row {{ index + 1 }} type<select v-model="row.kind" :disabled="busy"><option v-for="kind in kinds" :key="kind">{{ kind }}</option></select></label>
          <label>Description<input v-model="row.description" :aria-label="'Row ' + (index + 1) + ' description'" :disabled="busy" /></label>
          <label>Value<input v-model="row.value" :aria-label="'Row ' + (index + 1) + ' value'" :disabled="busy || ['Group', 'Subtotal'].includes(row.kind)" /></label>
          <button class="icon-button" :aria-label="'Move template row ' + (index + 1) + ' up'" :disabled="busy || index === 0" @click="move(index, -1)"><AppIcon name="up" /></button>
          <button class="icon-button" :aria-label="'Move template row ' + (index + 1) + ' down'" :disabled="busy || index === rows.length - 1" @click="move(index, 1)"><AppIcon name="down" /></button>
          <button class="icon-button" :aria-label="'Remove template row ' + (index + 1)" :disabled="busy" @click="rows.splice(index, 1)"><AppIcon name="trash" /></button>
        </div>
      </div>
      <div class="project-tools">
        <button class="button small secondary" :disabled="busy || rows.length >= 100" @click="rows.push({ kind: 'Group', description: 'Resource group', value: '' })">Add template row</button>
        <button class="button small secondary" :disabled="busy" @click="defaults().catch(failure => error = String(failure))">Load shipped rows</button>
        <button class="button small secondary" :disabled="busy || !rows.length" @click="saveTemplate">Save template</button>
      </div>
    </template>
    <template v-else>
      <label class="field">Field to change<select v-model="field" :disabled="busy"><option v-for="name in fields" :key="name" :value="name">{{ labels[name] }}</option></select></label>
      <label class="field">New value<textarea v-model="value" :disabled="busy" rows="2" /></label>
      <p class="field-hint">Numeric values accept bounded arithmetic such as 2*3. Fields must be editable on every selected row.</p>
    </template>
    <p v-if="status" role="status">{{ status }}</p>
    <p v-if="error" class="dialog-error" role="alert">{{ error }}</p>
    <div v-if="preview" class="batch-preview">
      <p role="status">Calculated rate: {{ state.rate }} → {{ preview.rate }} {{ state.unit ? '/ ' + state.unit : '' }}</p>
      <div class="import-sample"><table><thead><tr><th>Type / code</th><th>Description</th><th>Quantity / factor</th><th>Rate</th><th>Amount</th></tr></thead><tbody>
        <tr v-for="row in previewRows" :key="row.id"><td>{{ row.code || row.kind }}</td><td>{{ row.description }}</td><td>{{ row.value }}</td><td>{{ row.rate }}</td><td>{{ row.amount }}</td></tr>
      </tbody></table></div>
    </div>
    <div class="dialog-footer">
      <button class="button secondary" :disabled="busy || (template ? !rows.length : !selected.length)" @click="calculate">Preview changes</button>
      <button class="button primary" :disabled="busy || !preview" @click="apply">Apply batch</button>
    </div>
  </Dialog>
</template>
