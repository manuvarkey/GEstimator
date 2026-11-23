<script setup lang="ts">
// Stage schedule edit choices and submit them through the project view.
import { ref } from "vue";
import Dialog from "primevue/dialog";
import type { ViewCommand } from "../projectViewTypes";
import { quantityRoundingOptions } from "../quantityRounding";

const props = defineProps<{
  selectedIds: readonly string[];
  selectedColour?: string | null;
  busy: boolean;
  error: string;
  command: ViewCommand;
}>();

const emit = defineEmits<{ clearError: [] }>();
const renumberOpen = ref(false);
const colourOpen = ref(false);
const scheduleQuantityOpen = ref(false);
const scheduleRounding = ref("Round to 0");
const defaultColour = "#ffe082";
const rowColour = ref(defaultColour);
const rowColours = [
  "#ffffff",
  "#eeeeee",
  "#ffe082",
  "#ffcc80",
  "#ffab91",
  "#f8bbd0",
  "#e1bee7",
  "#c5cae9",
  "#bbdefb",
  "#b2dfdb",
  "#c8e6c9",
  "#dcedc8",
  "#795548",
  "#455a64",
  "#263238",
  "#000000",
];

function showRenumber() {
  emit("clearError");
  renumberOpen.value = true;
}

/** Start the palette at the saved colour for a single selected row, if valid. */
function showColour() {
  const colour = props.selectedColour ?? "";
  rowColour.value = /^#[0-9a-f]{6}$/i.test(colour) ? colour.toLowerCase() : defaultColour;
  emit("clearError");
  colourOpen.value = true;
}

/** Retain the last rounding choice while the schedule view stays mounted. */
function showQuantities() {
  emit("clearError");
  scheduleQuantityOpen.value = true;
}

async function renumberSchedule() {
  if (await props.command("renumber")) renumberOpen.value = false;
}

async function applyRowColour(colour: string | null) {
  if (await props.command("colour", { ids: props.selectedIds, colour })) colourOpen.value = false;
}

async function updateSelectedQuantities() {
  if (await props.command("update_quantities", { ids: props.selectedIds, rounding: scheduleRounding.value }))
    scheduleQuantityOpen.value = false;
}

defineExpose({ showRenumber, showColour, showQuantities });
</script>

<template>
  <Dialog v-model:visible="renumberOpen" modal header="Renumber schedule" class="workspace-dialog">
    <p class="dialog-intro">
      Assign item codes in category and hierarchy order throughout the project. Sub-analysis codes are kept.
    </p>
    <div v-if="error" class="dialog-error" role="alert">{{ error }}</div>
    <div class="dialog-footer">
      <button class="button secondary" :disabled="busy" @click="renumberOpen = false">Cancel</button>
      <button class="button primary" :disabled="busy" @click="renumberSchedule">Renumber</button>
    </div>
  </Dialog>
  <Dialog v-model:visible="colourOpen" modal header="Schedule row colour" class="workspace-dialog">
    <label class="field">
      Row colour
      <div class="colour-palette" role="group" aria-label="Row colour palette">
        <button
          v-for="colour in rowColours"
          :key="colour"
          type="button"
          :aria-label="'Colour ' + colour"
          :aria-pressed="rowColour === colour"
          :style="{ backgroundColor: colour }"
          @click="rowColour = colour"
        />
      </div>
    </label>
    <div v-if="error" class="dialog-error" role="alert">{{ error }}</div>
    <div class="dialog-footer">
      <button class="button secondary" :disabled="busy" @click="applyRowColour(null)">Clear colour</button>
      <button class="button primary" :disabled="busy" @click="applyRowColour(rowColour)">Apply colour</button>
    </div>
  </Dialog>
  <Dialog
    v-model:visible="scheduleQuantityOpen"
    modal
    header="Update selected schedule quantities"
    class="workspace-dialog"
  >
    <p class="dialog-intro">Use linked measurement totals for the selected schedule items.</p>
    <label class="field">
      Quantity rounding
      <select v-model="scheduleRounding" :disabled="busy">
        <option v-for="option in quantityRoundingOptions" :key="option">{{ option }}</option>
      </select>
    </label>
    <div v-if="error" class="dialog-error" role="alert">{{ error }}</div>
    <div class="dialog-footer">
      <button class="button primary" :disabled="busy" @click="updateSelectedQuantities">Update quantities</button>
    </div>
  </Dialog>
</template>
