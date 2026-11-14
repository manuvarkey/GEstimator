<script setup lang="ts">
import { ref, onMounted } from "vue";
import Dialog from "primevue/dialog";
import AnalysisRowEditor from "./AnalysisRowEditor.vue";
import { programSettings, programSettingsWarning, initializeProgramSettings, saveProgramSettings, shippedProgramSettings, type ProgramSettings } from "../programSettings";
const visible = defineModel<boolean>({ required: true });
const draft = ref<ProgramSettings>();
const tab = ref("general");
const busy = ref(false);
const error = ref("");
const sections = [{ key: "general", label: "General" }, { key: "default", label: "Default analysis template" }, { key: "modify", label: "Library Modify & Add" }];
function navigate(event: KeyboardEvent, index: number) {
  const last = sections.length - 1;
  const next = event.key === "ArrowRight" ? (index + 1) % sections.length : event.key === "ArrowLeft" ? (index + last) % sections.length : event.key === "Home" ? 0 : event.key === "End" ? last : -1;
  if (next < 0) return;
  event.preventDefault();
  document.getElementById("settings-tab-" + sections[next]!.key)?.focus();
}
onMounted(async () => {
  try { await initializeProgramSettings(); draft.value = programSettings.value ? JSON.parse(JSON.stringify(programSettings.value)) : await shippedProgramSettings(); }
  catch (failure) { error.value = String(failure); }
});
async function save() {
  if (!draft.value || busy.value) return;
  busy.value = true; error.value = "";
  try { await saveProgramSettings(draft.value); visible.value = false; }
  catch (failure) { error.value = String(failure); }
  finally { busy.value = false; }
}
async function reset() {
  busy.value = true; error.value = "";
  try { draft.value = await shippedProgramSettings(); }
  catch (failure) { error.value = String(failure); }
  finally { busy.value = false; }
}
</script>
<template>
  <Dialog v-model:visible="visible" modal header="Program settings" class="workspace-dialog program-settings-dialog" :closable="!busy" :close-on-escape="!busy">
    <p class="dialog-intro">Application preferences apply to future operations and are saved separately from projects. Cancel keeps the current settings.</p>
    <p v-if="programSettingsWarning" class="dialog-error" role="status">{{ programSettingsWarning }}</p>
    <div class="settings-tabs" role="tablist" aria-label="Program settings sections">
      <button v-for="(section, index) in sections" :id="'settings-tab-' + section.key" :key="section.key" role="tab" :tabindex="tab === section.key ? 0 : -1" :aria-selected="tab === section.key" :aria-controls="'settings-panel-' + section.key" :disabled="busy" @click="tab = section.key" @keydown="navigate($event, index)">{{ section.label }}</button>
    </div>
    <section v-if="draft" :id="'settings-panel-' + tab" role="tabpanel" :aria-labelledby="'settings-tab-' + tab">
      <template v-if="tab === 'general'">
        <h3>Export options</h3>
        <label class="library-remember"><input v-model="draft.export_break_items" type="checkbox" :disabled="busy" />Break item descriptions across multiple rows in exported workbooks</label>
      </template>
      <template v-else-if="tab === 'default'">
        <p class="field-hint">Used by Analysis → Default rows and when opening an analysis with no calculation rows. An empty template leaves blank analyses empty.</p>
        <AnalysisRowEditor v-model="draft.ana_default_rows" prefix="Default row" :disabled="busy" />
      </template>
      <template v-else>
        <label class="field">Schedule rate multiplier<input v-model="draft.sch_rate_mult_factor" :disabled="busy" /></label>
        <p class="field-hint">Applied by Add item from database → Modify & Add. Arithmetic is accepted and rounded to five places using the existing currency rules. Plain addition retains the database rate.</p>
        <label class="field">Trailing analysis rows to replace<input v-model.number="draft.ana_copy_delete_rows" type="number" min="0" max="5" step="1" :disabled="busy" /></label>
        <p class="field-hint">Replacement applies when the count is non-zero, the replacement is not empty and the source analysis contains more rows than the count.</p>
        <p class="field-hint">Rows substituted by the Modify & Add action after deleting the configured number of trailing analysis rows. Sub-analyses are imported with their original calculations.</p>
        <AnalysisRowEditor v-model="draft.ana_copy_rows" prefix="Modify row" :disabled="busy" />
      </template>
    </section>
    <p v-if="error" role="alert" class="dialog-error">{{ error }}</p>
    <div class="dialog-footer"><button class="button secondary" :disabled="busy || !draft" @click="reset">Restore shipped defaults</button><button class="button secondary" :disabled="busy" @click="visible = false">Cancel</button><button class="button primary" :disabled="busy || !draft" @click="save">Save program settings</button></div>
  </Dialog>
</template>
