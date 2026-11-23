<script setup lang="ts">
// Owns the analysis dialogs for one mounted document workspace.
import { computed, ref } from "vue";
import Dialog from "primevue/dialog";
import { exportWithWorkbookChooser } from "../workbookExport";
import { request } from "../backend";
import type { useWorkspace } from "../useWorkspace";
import AnalysisBatchDialog from "./AnalysisBatchDialog.vue";
import AnalysisRulesDialog from "./AnalysisRulesDialog.vue";
import AppIcon from "./AppIcon.vue";
import DatabasePicker from "./DatabasePicker.vue";
import SpreadsheetRangeImport from "./SpreadsheetRangeImport.vue";

const props = defineProps<{
  workspace: Pick<
    ReturnType<typeof useWorkspace>,
    "state" | "error" | "groups" | "selected" | "destinationGroup" | "resourceSource" | "command" | "run"
  >;
  busy: boolean;
  applyRules: (params: Record<string, unknown>) => Promise<boolean>;
}>();
const emit = defineEmits<{ manageLibraries: [] }>();
const { state, error, groups, selected, destinationGroup, resourceSource, command, run } = props.workspace;

const customResourceOpen = ref(false);
const libraryResourcesOpen = ref(false);
const importOpen = ref(false);
const templateOpen = ref(false);
const rulesOpen = ref(false);
const ruleIds = ref<string[]>([]);
const ruleCode = ref("");
const groupId = ref("");
const form = ref(emptyResource());
const resourceTarget = computed(() => groups.value.find((group) => group.id === groupId.value));

function emptyResource() {
  return {
    code: "",
    description: "",
    unit: "",
    rate: "0",
    qty: "0",
    vat: "0",
    discount: "0",
    reference: "",
    category: "",
    remarks: "",
  };
}

function defaultGroupId() {
  return destinationGroup.value?.id || groups.value[0]?.id || "";
}

/** Insert after the selected row when it belongs to the chosen group. */
function insertionTargetId() {
  return destinationGroup.value?.id === groupId.value ? selected.value[0]?.id || groupId.value : groupId.value;
}

function showResource(kind: "library" | "custom") {
  groupId.value = defaultGroupId();
  if (kind === "library") libraryResourcesOpen.value = true;
  else customResourceOpen.value = true;
}

function addLibraryResources(params: Record<string, unknown>) {
  return command("analysis.resources_add", { ...params, id: insertionTargetId() });
}

async function insertExplorerResource(code: string) {
  groupId.value = defaultGroupId();
  await insertResource(code);
}

async function insertResource(libraryCode?: string) {
  if (
    await command("resource.add", {
      id: insertionTargetId(),
      library: !!libraryCode,
      source: resourceSource.value,
      ...form.value,
      code: libraryCode || form.value.code,
    })
  ) {
    customResourceOpen.value = false;
    form.value = emptyResource();
  }
}

function showImport() {
  error.value = "";
  importOpen.value = true;
}

function showTemplate() {
  templateOpen.value = true;
}

function showRules(ids: string[], code: string) {
  ruleIds.value = ids;
  ruleCode.value = code;
  rulesOpen.value = true;
}

function exportWorkbook() {
  return exportWithWorkbookChooser(
    (state.value?.code || "analysis") + ".xlsx",
    (destination) =>
      run(async () => {
        await request("analysis.export_xlsx", destination);
      }, "Exporting analysis…"),
    (message) => {
      error.value = message;
    },
  );
}

// The shell dispatches workspace commands and guards shortcuts while the custom dialog opens.
defineExpose({
  customResourceOpen,
  showResource,
  insertExplorerResource,
  showImport,
  showTemplate,
  showRules,
  exportWorkbook,
});
</script>

<template>
  <DatabasePicker
    v-model="libraryResourcesOpen"
    analysis
    kind="resources"
    mode="add"
    :revision="state?.revision || 0"
    :target-ids="[]"
    :apply="addLibraryResources"
    :parent-error="error"
    @manage="emit('manageLibraries')"
  />
  <Dialog
    v-model:visible="customResourceOpen"
    modal
    header="Add custom resource"
    class="workspace-dialog resource-dialog"
  >
    <p class="dialog-intro">Create a resource definition and insert it into the selected analysis group.</p>
    <label class="field"
      >Destination group<select v-model="groupId">
        <option v-for="group in groups" :key="group.id" :value="group.id">
          {{ group.description }}
        </option>
      </select></label
    >
    <form @submit.prevent="insertResource()">
      <div class="field-pair">
        <label class="field">Resource code<input v-model="form.code" placeholder="Automatic if blank" /></label
        ><label class="field">Unit<input v-model="form.unit" required placeholder="e.g. kg" /></label>
      </div>
      <label class="field"
        >Description<textarea
          data-primary-input
          autofocus
          v-model="form.description"
          required
          rows="3"
          placeholder="Describe the material, labour or equipment"
        />
      </label>
      <div class="field-pair">
        <label class="field">Base rate<input v-model="form.rate" inputmode="decimal" required /></label
        ><label class="field">Quantity<input v-model="form.qty" inputmode="decimal" required /></label>
      </div>
      <div class="field-pair">
        <label class="field">Tax %<input v-model="form.vat" inputmode="decimal" /></label
        ><label class="field">Discount %<input v-model="form.discount" inputmode="decimal" /></label>
      </div>
      <div v-if="error" class="dialog-error" role="alert">{{ error }}</div>
      <div class="dialog-footer">
        <button type="button" class="button secondary" @click="customResourceOpen = false">Cancel</button
        ><button class="button primary" :disabled="busy || !resourceTarget">
          <AppIcon name="plus" :size="16" />Add resource
        </button>
      </div>
    </form>
  </Dialog>
  <SpreadsheetRangeImport
    v-if="importOpen"
    v-model="importOpen"
    :apply="(params) => command('analysis.import_xlsx', params)"
    :error="error"
  />
  <AnalysisBatchDialog
    v-if="templateOpen && state"
    v-model="templateOpen"
    template
    :selected="selected"
    :state="state"
    :apply="(params) => command('analysis.batch', params)"
  />
  <AnalysisRulesDialog
    v-if="rulesOpen && state"
    v-model="rulesOpen"
    :revision="state.revision"
    :ids="ruleIds"
    :code="ruleCode"
    :dirty="state.dirty"
    :apply="applyRules"
  />
</template>
