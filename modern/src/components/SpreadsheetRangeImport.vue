<script setup lang="ts">
import { formatMoney } from "../numberFormatting";
import { ref, watch } from "vue";
import Dialog from "primevue/dialog";
import { open } from "@tauri-apps/plugin-dialog";
import { request } from "../backend";

const visible = defineModel<boolean>({ required: true });
const props = defineProps<{
  apply: (params: Record<string, unknown>) => Promise<boolean>;
  error: string;
  measurement?: boolean;
  multiple?: boolean;
}>();
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
  { value: 0, label: "As Integer" },
  { value: 1, label: "To 1 Decimal Place" },
  { value: 2, label: "To 2 Decimal Places" },
  { value: 1.5, label: "To nearest multiple of 0.5" },
  { value: 2.5, label: "To nearest multiple of 0.05" },
];
const busy = ref(false);
const error = ref("");
const preview = ref<{ rows: number; resources: number; rate: string; matched?: string[]; unmatched?: string[] }>();
watch([path, sheet, first, last, column, rateFirst, commentPosition, rounding], () => { preview.value = undefined; });

function params() {
  return { path: path.value, sheet: sheet.value, first_row: first.value,
    last_row: last.value || undefined, first_column: column.value, comment_position: commentPosition.value, rounding: rounding.value, rate_first: rateFirst.value };
}
async function browse() {
  try {
    const result = await open({ filters: [{ name: "Excel workbook", extensions: ["xlsx"] }] });
    if (typeof result === "string") path.value = result;
  } catch (reason) {
    error.value = String(reason);
  }
}
async function review() {
  busy.value = true;
  error.value = "";
  preview.value = undefined;
  try {
    preview.value = await request(props.multiple ? "project.import_analysis_preview" : "analysis.import_preview", params());
  } catch (reason) {
    error.value = String(reason);
  } finally {
    busy.value = false;
  }
}
async function apply() {
  if (props.multiple && !preview.value?.matched?.length) return;
  busy.value = true;
  try {
    if (await props.apply(params())) visible.value = false;
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <Dialog v-model:visible="visible" modal :header="measurement ? 'Import measurement records' : 'Import analysis from Excel'"
    class="workspace-dialog" :closable="!busy" :close-on-escape="!busy">
    <form @submit.prevent="measurement ? apply() : review()">
      <label class="field">
        Workbook
        <div class="file-input">
          <input v-model="path" aria-label="Workbook" data-primary-input autofocus :disabled="busy" required />
          <button type="button" class="button secondary" :disabled="busy" @click="browse">Browse</button>
        </div>
      </label>
      <label class="field">Worksheet name <input v-model="sheet" :disabled="busy" placeholder="First worksheet" /></label>
      <label class="field">First row <input v-model.number="first" :disabled="busy" type="number" min="1" required /></label>
      <label class="field">Last row <input v-model.number="last" :disabled="busy" type="number" min="1" /></label>
      <label class="field">First column number <input v-model.number="column" :disabled="busy" type="number" min="1" max="100" required /></label>
      <label v-if="!measurement"><input v-model="rateFirst" :disabled="busy" type="checkbox" /> Rate column precedes quantity</label>
      <template v-if="!measurement">
        <label class="field">Resource comments <select aria-label="Resource comments" v-model="commentPosition" :disabled="busy"><option :value="0">Above resource</option><option :value="1">Below resource</option></select></label>
        <label class="field">Rounding <select aria-label="Rounding" v-model="rounding" :disabled="busy"><option v-for="option in roundingOptions" :key="option.value" :value="option.value">{{ option.label }}</option></select></label>
      </template>
      <p v-if="preview?.matched" role="status">Matched: {{ preview.matched.join(", ") || "None" }}. Unmatched: {{ preview.unmatched?.join(", ") || "None" }}.</p>
      <p class="field-hint" v-if="measurement">Select data rows with editable template columns in order. Omit calculated columns and headers.</p>
      <p class="field-hint" v-else>Include the item code above the six-column analysis header. Formula cells use values saved by Excel or LibreOffice.</p>
      <p v-if="preview && !multiple" role="status">{{ preview.rows }} analysis rows, {{ preview.resources }} resources, parsed rate {{ formatMoney(preview.rate) }}.</p>
      <div v-if="error || props.error" class="dialog-error" role="alert">{{ error || props.error }}</div>
      <div class="dialog-footer">
        <button v-if="measurement" class="button primary" :disabled="busy || !path">Import records</button>
        <template v-else>
          <button class="button secondary" :disabled="busy || !path">Preview analysis</button>
          <button type="button" class="button primary" :disabled="busy || !preview || (multiple && !preview.matched?.length)" @click="apply">{{ multiple ? "Import matched analyses" : "Replace analysis draft" }}</button>
        </template>
      </div>
    </form>
  </Dialog>
</template>
