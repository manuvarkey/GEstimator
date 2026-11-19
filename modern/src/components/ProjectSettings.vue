<script setup lang="ts">
import { computed, ref, watch } from "vue";
import Dialog from "primevue/dialog";
import { request } from "../backend";
import { renderMarkdown } from "../markdown";

// Project properties, including author notes (Markdown) describing the
// database for people and MCP clients: scope, rate basis, revision, conventions.
const visible = defineModel<boolean>({ required: true });
const props = defineProps<{ revision?: number; busy: boolean }>();
const emit = defineEmits<{ saved: [] }>();
const settings = ref({ project_name: "", project_item_code: "", project_resource_code: "", project_metadata: "" });
const tab = ref<"write" | "preview">("write");
const saving = ref(false);
const error = ref("");
const preview = computed(() => renderMarkdown(settings.value.project_metadata));

watch(visible, async open => {
  if (!open) return;
  error.value = "";
  tab.value = "write";
  try { settings.value = { ...settings.value, ...await request<typeof settings.value>("project.settings") }; }
  catch (reason) { error.value = String(reason); }
}, { immediate: true });

async function save() {
  saving.value = true;
  error.value = "";
  try {
    await request("project.settings.edit", { revision: props.revision, settings: settings.value });
    visible.value = false;
    emit("saved");
  } catch (reason) { error.value = String(reason); }
  finally { saving.value = false; }
}
</script>
<template>
  <Dialog v-model:visible="visible" modal header="Project settings" class="workspace-dialog project-settings-dialog" :closable="!saving">
    <form class="project-settings" @submit.prevent="save">
      <label class="field">Project name<input v-model="settings.project_name" data-primary-input autofocus :disabled="saving" /></label>
      <div class="field-pair">
        <label class="field">Item code prefix<input v-model="settings.project_item_code" :disabled="saving" /></label>
        <label class="field">Resource code prefix<input v-model="settings.project_resource_code" :disabled="saving" /></label>
      </div>
      <div class="field">
        <div class="notes-heading">
          <span id="project-notes-label">Database notes</span>
          <div class="notes-tabs" role="tablist" aria-label="Database notes view">
            <button type="button" role="tab" :aria-selected="tab === 'write'" :class="{ active: tab === 'write' }" @click="tab = 'write'">Write</button>
            <button type="button" role="tab" :aria-selected="tab === 'preview'" :class="{ active: tab === 'preview' }" @click="tab = 'preview'">Preview</button>
          </div>
        </div>
        <textarea v-if="tab === 'write'" v-model="settings.project_metadata" class="notes-editor" aria-labelledby="project-notes-label" :disabled="saving"
          placeholder="# Scope&#10;Describe the source, rate basis, revision date and conventions. **Bold**, *italics*, lists and headings are supported." />
        <div v-else class="notes-preview markdown" aria-labelledby="project-notes-label" v-html="preview || '<p class=&quot;field-hint&quot;>Nothing to preview.</p>'" />
        <p class="field-hint">Shown to MCP clients with this database. Markdown: # headings, **bold**, *italics*, `code`, - lists, &gt; quotes.</p>
      </div>
      <div v-if="error" class="dialog-error" role="alert">{{ error }}</div>
      <div class="dialog-footer">
        <button type="button" class="button secondary" :disabled="saving" @click="visible = false">Cancel</button>
        <button class="button primary" :disabled="saving || busy">Apply settings</button>
      </div>
    </form>
  </Dialog>
</template>
