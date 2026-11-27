<script setup lang="ts">
/** Shared editable signature captions and multiline blocks for estimate defaults and reports. */
import { computed, ref, watch } from "vue";
import SettingsTabs from "./SettingsTabs.vue";
import type { SignoffBlock } from "../reportTypes";
const blocks = defineModel<SignoffBlock[]>({ required: true });
defineProps<{ label: string }>();
const selected = ref("0");
const index = computed(() => Number(selected.value));
const tabs = computed(() => blocks.value.map((_, i) => ({ key: String(i), label: "Block " + (i + 1) })));
watch(
  () => blocks.value.length,
  (length) => {
    if (index.value >= length) selected.value = String(Math.max(0, length - 1));
  },
);
const block = computed(() => blocks.value[index.value]);
function add() {
  const nextIndex = blocks.value.length;
  blocks.value = [...blocks.value, { caption: "Signature", body: "" }];
  selected.value = String(nextIndex);
}
function remove() {
  const removed = index.value;
  const next = blocks.value.filter((_, i) => i !== removed);
  blocks.value = next;
  selected.value = String(Math.min(removed, next.length - 1));
}
</script>
<template>
  <div class="signoff-editor">
    <SettingsTabs v-model="selected" :tabs="tabs" :label="label">
      <div v-if="block">
        <label
          >Caption<input v-model="block.caption" :aria-label="`${label} block ${index + 1} caption`" maxlength="10000"
        /></label>
        <label
          >Signature text<textarea
            v-model="block.body"
            :aria-label="`${label} block ${index + 1} text`"
            rows="4"
            maxlength="10000"
            data-multiline
          />
        </label>
        <button type="button" :disabled="index === 0" @click="remove">Remove current block</button>
      </div>
      <button type="button" :disabled="blocks.length >= 6" @click="add">Add signature block</button>
    </SettingsTabs>
  </div>
</template>
<style scoped>
label {
  display: grid;
  gap: 4px;
  margin-block: 8px;
}
</style>
