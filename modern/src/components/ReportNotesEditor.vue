<script setup lang="ts">
/** Author one to six explicit notes pages; templates render to escaped plain text. */
import { computed, ref, watch } from "vue";
import SettingsTabs from "./SettingsTabs.vue";
const body = defineModel<string>({ default: "" });
const pages = computed(() => body.value.split("\f"));
const selected = ref("0");
const index = computed(() => Number(selected.value));
const tabs = computed(() => pages.value.map((_, i) => ({ key: String(i), label: "Page " + (i + 1) })));
watch(
  () => pages.value.length,
  (length) => {
    if (index.value >= length) selected.value = String(Math.max(0, length - 1));
  },
);
function add() {
  const nextIndex = pages.value.length;
  body.value += "\f";
  selected.value = String(nextIndex);
}
function remove() {
  const removed = index.value;
  const next = pages.value.filter((_, i) => i !== removed);
  body.value = next.join("\f");
  selected.value = String(Math.min(removed, next.length - 1));
}
function edit(index: number, value: string) {
  const next = [...pages.value];
  next[index] = value;
  body.value = next.join("\f");
}
</script>
<template>
  <div class="notes-pages">
    <SettingsTabs v-model="selected" :tabs="tabs" label="Notes pages">
      <label
        >Notes page {{ index + 1 }}
        <textarea
          :value="pages[index]"
          :aria-label="index ? `Notes text page ${index + 1}` : 'Notes text'"
          maxlength="20000"
          rows="16"
          data-multiline
          @input="edit(index, ($event.target as HTMLTextAreaElement).value)"
        />
      </label>
      <div class="page-actions">
        <button type="button" :disabled="pages.length >= 6" @click="add">Add notes page</button>
        <button type="button" :disabled="index === 0" @click="remove">Remove current page</button>
      </div>
    </SettingsTabs>
    <p class="field-hint">
      Jinja2 fields:
      <code v-pre
        >{{ name_of_work }}, {{ organization }}, {{ office }}, {{ reference }}, {{ issue_date }}, {{ estimate_total }},
        {{ title }}, {{ item_count }}, {{ category_count }}</code
      >. Text filters (upper, lower, title, trim, default) and if conditions are supported. Each page starts a new
      printed page; long text may flow further.
    </p>
  </div>
</template>
<style scoped>
label {
  display: grid;
  gap: 6px;
  margin-block: 12px;
}
textarea {
  min-height: 280px;
  resize: vertical;
}
.page-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.field-hint {
  color: var(--muted);
  font-size: var(--text-size-small);
  overflow-wrap: anywhere;
}
</style>
