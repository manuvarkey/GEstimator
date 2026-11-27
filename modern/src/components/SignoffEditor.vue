<script setup lang="ts">
/** Shared editable signature captions and multiline blocks for estimate defaults and reports. */
import type { SignoffBlock } from "../reportTypes";
const blocks = defineModel<SignoffBlock[]>({ required: true });
defineProps<{ label: string }>();
</script>
<template>
  <div class="signoff-editor">
    <fieldset v-for="(block, index) in blocks" :key="index">
      <legend>{{ label }} · block {{ index + 1 }}</legend>
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
      <button
        type="button"
        :disabled="blocks.length === 1"
        @click="blocks = blocks.filter((_, position) => position !== index)"
      >
        Remove block {{ index + 1 }}
      </button>
    </fieldset>
    <button
      type="button"
      :disabled="blocks.length >= 6"
      @click="blocks = [...blocks, { caption: 'Signature', body: '' }]"
    >
      Add signature block
    </button>
  </div>
</template>
<style scoped>
fieldset {
  margin: 10px 0;
  border: 1px solid var(--line);
  min-width: 0;
}
label {
  display: grid;
  gap: 4px;
  margin-block: 8px;
}
</style>
