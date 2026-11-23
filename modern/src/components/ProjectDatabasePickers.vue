<script setup lang="ts">
// Keep each project database picker's state alive across editor switches.
import { ref } from "vue";
import type { ProjectDatabaseSelection } from "../projectViewTypes";
import DatabasePicker from "./DatabasePicker.vue";

const props = defineProps<{
  projectSession: number;
  projectView?: {
    applyDatabase: (params: Record<string, unknown>) => Promise<boolean>;
    lastError: () => string;
  };
}>();
const emit = defineEmits<{ manage: [] }>();

interface PickerState {
  open: boolean;
  revision: number;
  targetIds: string[];
}

const addKinds = ["schedule", "resources"] as const;
const addPickers = ref<Record<ProjectDatabaseSelection["kind"], PickerState>>({
  schedule: { open: false, revision: 0, targetIds: [] },
  resources: { open: false, revision: 0, targetIds: [] },
});
const ratesPicker = ref<PickerState & { kind: ProjectDatabaseSelection["kind"] }>({
  open: false,
  kind: "resources",
  revision: 0,
  targetIds: [],
});
const error = ref("");

/** Open the appropriate picker with the target IDs and their original revision. */
function show({ kind, mode, revision, targetIds }: ProjectDatabaseSelection) {
  error.value = "";
  if (mode === "rates") {
    ratesPicker.value = { kind, open: true, revision, targetIds };
    return;
  }
  addPickers.value[kind] = { open: true, revision, targetIds };
}

/** Reuse the project view's command and surface its error inside the picker. */
async function apply(params: Record<string, unknown>) {
  const ok = (await props.projectView?.applyDatabase(params)) ?? false;
  error.value = ok
    ? ""
    : props.projectView?.lastError() ||
      "The import could not be applied. Close the picker, refresh the project and try again.";
  return ok;
}

defineExpose({ show });
</script>

<template>
  <DatabasePicker
    v-for="kind in addKinds"
    :key="projectSession + kind"
    v-model="addPickers[kind].open"
    :kind="kind"
    mode="add"
    :revision="addPickers[kind].revision"
    :target-ids="addPickers[kind].targetIds"
    :apply="apply"
    :parent-error="error"
    @manage="emit('manage')"
  />
  <DatabasePicker
    :key="projectSession + 'rates'"
    v-model="ratesPicker.open"
    :kind="ratesPicker.kind"
    mode="rates"
    :revision="ratesPicker.revision"
    :target-ids="ratesPicker.targetIds"
    :apply="apply"
    :parent-error="error"
    @manage="emit('manage')"
  />
</template>
