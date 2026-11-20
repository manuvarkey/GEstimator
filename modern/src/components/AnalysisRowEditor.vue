<script setup lang="ts">
import AppIcon from "./AppIcon.vue";
import type { TemplateRow } from "../programSettings";
const rows = defineModel<TemplateRow[]>({ required: true });
withDefaults(defineProps<{ disabled?: boolean; prefix?: string }>(), { prefix: "Row" });
const kinds = ["Group", "Subtotal", "Weight", "Multiply", "Round"];
function move(index: number, delta: number) {
  const next = index + delta;
  if (next >= 0 && next < rows.value.length)
    [rows.value[index], rows.value[next]] = [rows.value[next]!, rows.value[index]!];
}
</script>
<template>
  <div class="template-rows">
    <div v-for="(row, index) in rows" :key="index" class="template-row">
      <label>{{ prefix }} {{ index + 1 }} type<select v-model="row.kind" :aria-label="`${prefix} ${index + 1} type`" :disabled="disabled"><option v-for="kind in kinds" :key="kind">{{ kind }}</option></select></label>
      <label>Description<input v-model="row.description" :aria-label="`${prefix} ${index + 1} description`" :disabled="disabled" /></label>
      <label>{{ row.kind === 'Group' ? 'Code' : 'Value' }}<input v-if="row.kind === 'Group'" v-model="row.code" :aria-label="`${prefix} ${index + 1} code`" :disabled="disabled" /><input v-else v-model="row.value" :aria-label="`${prefix} ${index + 1} value`" :disabled="disabled || row.kind === 'Subtotal'" /></label>
      <button class="icon-button" :aria-label="`Move ${prefix.toLowerCase()} ${index + 1} up`" :disabled="disabled || index === 0" title="Move this calculation row earlier in the template." @click="move(index, -1)"><AppIcon name="up" /></button>
      <button class="icon-button" :aria-label="`Move ${prefix.toLowerCase()} ${index + 1} down`" :disabled="disabled || index === rows.length - 1" title="Move this calculation row later in the template." @click="move(index, 1)"><AppIcon name="down" /></button>
      <button class="icon-button" :aria-label="`Remove ${prefix.toLowerCase()} ${index + 1}`" :disabled="disabled" title="Remove this row from the template. Save settings to retain the change." @click="rows.splice(index, 1)"><AppIcon name="trash" /></button>
    </div>
  </div>
  <button class="button small secondary" :disabled="disabled || rows.length >= 100" @click="rows.push({ kind: 'Group', description: 'Resource group', code: '', value: '' })">Add template row</button>
</template>
