<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { request } from "../backend";
import { renderMarkdown } from "../markdown";

/** Read-only notes of an attached database, loaded when first expanded. */
const props = defineProps<{ source: string; name: string }>();
const open = ref(false);
const text = ref<string>();
const error = ref("");
const html = computed(() => renderMarkdown(text.value ?? ""));
watch(() => props.source, () => { text.value = undefined; error.value = ""; open.value = false; });
async function toggle(event: Event) {
  open.value = (event.target as HTMLDetailsElement).open;
  if (!open.value || text.value !== undefined) return;
  try { text.value = (await request<{ notes: string }>("library.notes", { id: props.source })).notes; }
  catch (failure) { error.value = String(failure); }
}
</script>
<template>
  <details class="database-notes" :open="open" @toggle="toggle">
    <summary>Database notes</summary>
    <p v-if="error" class="dialog-error" role="alert">{{ error }}</p>
    <p v-else-if="text === undefined" class="field-hint">Loading…</p>
    <div v-else class="notes-preview markdown" :aria-label="'Notes for ' + name" v-html="html || '<p class=&quot;field-hint&quot;>No notes.</p>'" />
  </details>
</template>
