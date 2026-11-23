<script setup lang="ts">
// Stage resource category and renumbering choices in the resource view.
import { ref } from "vue";
import Dialog from "primevue/dialog";
import { request } from "../backend";
import type { ViewCommand } from "../projectViewTypes";

const props = defineProps<{
  categories?: readonly string[];
  selectionCount: number;
  busy: boolean;
  error: string;
  run: (work: () => Promise<void>) => Promise<boolean>;
  command: ViewCommand;
}>();

const moveOpen = ref(false);
const moveCategory = ref("");
const renumberOpen = ref(false);
const resourcePrefixes = ref<string[]>([]);
const excludedPrefixes = ref<string[]>([]);

/** Start each move with the first category from the current view. */
function showMove() {
  moveCategory.value = props.categories?.[0] ?? "";
  moveOpen.value = true;
}

/** Load the current database prefixes and exclude them by default. */
async function showRenumber() {
  await props.run(async () => {
    const result = await request<{ prefixes: string[] }>("resources.editor.prefixes", {});
    resourcePrefixes.value = result.prefixes;
    excludedPrefixes.value = [...result.prefixes];
    renumberOpen.value = true;
  });
}

async function moveResources() {
  if (await props.command("move_to", { category: moveCategory.value })) moveOpen.value = false;
}

function togglePrefix(prefix: string) {
  excludedPrefixes.value = excludedPrefixes.value.includes(prefix)
    ? excludedPrefixes.value.filter((value) => value !== prefix)
    : [...excludedPrefixes.value, prefix];
}

async function renumberResources() {
  if (await props.command("renumber", { exclude: excludedPrefixes.value })) renumberOpen.value = false;
}

defineExpose({ showMove, showRenumber });
</script>

<template>
  <Dialog
    v-model:visible="moveOpen"
    modal
    header="Move resources"
    class="workspace-dialog file-dialog"
    :closable="!busy"
  >
    <form @submit.prevent="moveResources">
      <p>Move {{ selectionCount }} selected resources, retaining their codes and analysis links.</p>
      <label class="field"
        >Destination category<select v-model="moveCategory" data-primary-input autofocus :disabled="busy">
          <option v-for="category in categories" :key="category">{{ category }}</option>
        </select></label
      >
      <p v-if="error" class="dialog-error" role="alert">{{ error }}</p>
      <div class="dialog-footer">
        <button type="button" class="button secondary" :disabled="busy" @click="moveOpen = false">Cancel</button
        ><button class="button primary" :disabled="busy">Move resources</button>
      </div>
    </form>
  </Dialog>
  <Dialog v-model:visible="renumberOpen" modal header="Renumber resources" class="workspace-dialog">
    <p>
      Project resources are renumbered. Enable each database below to include its resources; excluded databases keep
      their codes.
    </p>
    <div class="database-toggle-list">
      <div v-for="prefix in resourcePrefixes" :key="prefix" class="database-toggle-row">
        <span>{{ prefix }}</span
        ><button
          type="button"
          class="button small secondary"
          role="switch"
          :aria-label="`Renumber ${prefix} resources`"
          :aria-checked="!excludedPrefixes.includes(prefix)"
          :disabled="busy"
          @click="togglePrefix(prefix)"
        >
          {{ excludedPrefixes.includes(prefix) ? "Excluded" : "Enabled" }}
        </button>
      </div>
    </div>
    <p v-if="!resourcePrefixes.length" class="field-hint">No database-prefixed resources in this project.</p>
    <div class="dialog-footer">
      <button class="button secondary" :disabled="busy" @click="renumberOpen = false">Cancel</button
      ><button class="button primary" :disabled="busy" @click="renumberResources">Renumber resources</button>
    </div>
  </Dialog>
</template>
