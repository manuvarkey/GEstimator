<script setup lang="ts">
/** Author one to three explicit notes pages; templates render to escaped plain text. */
import { computed } from "vue";
const body = defineModel<string>({ default: "" });
const pages = computed(() => body.value.split("\f"));
function edit(index: number, value: string) {
  const next = [...pages.value];
  next[index] = value;
  body.value = next.join("\f");
}
</script>
<template>
  <div class="notes-pages">
    <label v-for="(page, index) in pages" :key="index"
      >Notes page {{ index + 1 }}
      <textarea
        :value="page"
        :aria-label="index ? `Notes text page ${index + 1}` : 'Notes text'"
        maxlength="20000"
        rows="16"
        data-multiline
        @input="edit(index, ($event.target as HTMLTextAreaElement).value)"
      />
    </label>
    <div class="page-actions">
      <button type="button" :disabled="pages.length >= 3" @click="body += '\f'">Add notes page</button>
      <button
        type="button"
        :disabled="pages.length < 2 || !!pages.at(-1)"
        @click="body = pages.slice(0, -1).join('\f')"
      >
        Remove empty last page
      </button>
    </div>
    <p class="field-hint">
      Jinja2 fields:
      <code v-pre
        >{{ name_of_work }}, {{ organization }}, {{ reference }}, {{ issue_date }}, {{ estimate_total }}, {{ title }},
        {{ item_count }}, {{ category_count }}</code
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
