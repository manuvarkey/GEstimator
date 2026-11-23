<script setup lang="ts">
// Stage deletion confirmation against the selection and revision that were previewed.
import { ref } from "vue";
import Dialog from "primevue/dialog";
import { request } from "../backend";
import type { View, ViewCommand } from "../projectViewTypes";

interface DeletePreview {
  items: number;
  categories: number;
  used_resources: string[];
  measurement_references: number;
}

type DeletePolicy = "protect" | "unused" | "all";

const props = defineProps<{
  view: View;
  busy: boolean;
  error: string;
  run: (work: () => Promise<void>) => Promise<boolean>;
  command: ViewCommand;
}>();

const deleteOpen = ref(false);
const deletion = ref<DeletePreview & { ids: string[]; revision: number }>();

/** Preview schedule or resource deletion, or stage a selected measurement category. */
async function show(ids: string[], revision: number, measurementCategories = 0) {
  if (props.view === "measurement") {
    deletion.value = {
      ids,
      revision,
      items: ids.length,
      categories: measurementCategories,
      used_resources: [],
      measurement_references: 0,
    };
    deleteOpen.value = true;
    return;
  }

  // Use the same IDs and revision for the preview and the eventual write.
  const ok = await props.run(async () => {
    const preview = await request<DeletePreview>(props.view + ".editor.delete_preview", { ids, revision });
    deletion.value = { ...preview, ids, revision };
  });
  if (!ok || !deletion.value) return;

  const { items, categories, used_resources, measurement_references } = deletion.value;
  if (categories || used_resources.length || measurement_references || items > 1) {
    deleteOpen.value = true;
  } else {
    await confirmDeletion("protect");
  }
}

async function confirmDeletion(policy: DeletePolicy) {
  if (!deletion.value) return;
  const { ids, revision } = deletion.value;
  if (await props.command(props.view === "measurement" ? "delete" : "delete_many", { ids, revision, policy })) {
    deleteOpen.value = false;
    deletion.value = undefined;
  }
}

defineExpose({ show });
</script>

<template>
  <Dialog
    v-model:visible="deleteOpen"
    modal
    header="Delete selected items"
    class="workspace-dialog file-dialog"
    :closable="!busy"
  >
    <template v-if="deletion">
      <p class="dialog-intro">
        Delete {{ deletion.items }} item{{ deletion.items === 1 ? "" : "s"
        }}{{
          deletion.categories
            ? ` and ${deletion.categories} ${deletion.categories === 1 ? "category" : "categories"}`
            : ""
        }}? Category contents and child items are included. You can undo this operation.
      </p>
      <p v-if="deletion.used_resources.length" class="dialog-intro">
        {{ deletion.used_resources.length }}
        {{ deletion.used_resources.length === 1 ? "resource is" : "resources are" }}
        used in analyses. Deleting them also removes their analysis entries and recalculates dependent rates.
      </p>
      <p v-if="deletion.measurement_references" class="dialog-intro">
        {{ deletion.measurement_references }} measurement associations will be cleared. Measurement records and remarks
        will be retained.
      </p>
      <div v-if="error" class="dialog-error">{{ error }}</div>
      <div class="dialog-footer">
        <button class="button secondary" :disabled="busy" @click="deleteOpen = false">Cancel</button>
        <button
          v-if="deletion.used_resources.length"
          class="button danger"
          :disabled="busy"
          @click="confirmDeletion('unused')"
        >
          Delete unused
        </button>
        <button
          class="button danger"
          :disabled="busy"
          @click="confirmDeletion(deletion.used_resources.length ? 'all' : 'protect')"
        >
          {{ deletion.used_resources.length ? "Delete including used" : "Delete selected" }}
        </button>
      </div>
    </template>
  </Dialog>
</template>
