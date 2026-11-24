<script setup lang="ts">
// Coordinate the project workbook dialogs opened from the retained view ribbons.
import { ref } from "vue";
import MappedImport from "./MappedImport.vue";
import SpreadsheetRangeImport from "./SpreadsheetRangeImport.vue";
import type { View, ViewCommand } from "../projectViewTypes";
import { notify } from "../statusNotice";

const props = defineProps<{
  view: View;
  fields: string[];
  revision?: number;
  measurementId?: string;
  recordId?: string;
  error: string;
  command: ViewCommand;
  refreshAfterMappedImport: (added: number) => Promise<void>;
}>();
const emit = defineEmits<{ clearError: [] }>();
const mappedOpen = ref(false);
const analysesOpen = ref(false);
const recordsOpen = ref(false);

/** Open a fresh import dialog for the selected ribbon action. */
function show(kind: "mapped" | "analyses" | "records") {
  if (kind === "mapped") mappedOpen.value = true;
  else if (kind === "analyses") analysesOpen.value = true;
  else {
    emit("clearError");
    recordsOpen.value = true;
  }
}

async function mappedImportDone(result: { added: number; updated: number; skipped: number; warning_count?: number }) {
  await props.refreshAfterMappedImport(result.added);
  notify(
    `Imported ${result.added} new, ${result.updated} updated, ${result.skipped} skipped${result.warning_count ? `; ${result.warning_count} non-numeric values imported as 0` : ""}.`,
    8000,
  );
}

function applyAnalyses(params: Record<string, unknown>) {
  return props.command("project.import_analysis_apply", params);
}

function applyRecords(params: Record<string, unknown>) {
  return props.command("record_import", { ...params, id: props.measurementId, record_id: props.recordId });
}

defineExpose({ show });
</script>

<template>
  <MappedImport
    v-if="mappedOpen"
    v-model="mappedOpen"
    :kind="view === 'resources' ? 'resources' : 'schedule'"
    :fields="fields"
    :revision="revision"
    @imported="mappedImportDone"
  />
  <SpreadsheetRangeImport v-if="analysesOpen" v-model="analysesOpen" multiple :apply="applyAnalyses" :error="error" />
  <SpreadsheetRangeImport
    v-if="recordsOpen"
    v-model="recordsOpen"
    measurement
    :measurement-id="measurementId"
    :apply="applyRecords"
    :error="error"
  />
</template>
