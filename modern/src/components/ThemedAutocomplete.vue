<script setup lang="ts">
import { ref } from "vue";
import AutoComplete from "primevue/autocomplete";
const value = defineModel<string>({ required: true });
const props = defineProps<{ label: string; suggestions: string[]; disabled?: boolean; placeholder?: string }>();
const matches = ref<string[]>([]);
function complete(event: { query: string }) {
  const query = event.query.trim().toLocaleLowerCase();
  matches.value = props.suggestions.filter(option => option.toLocaleLowerCase().includes(query));
}
function keyboard(event: KeyboardEvent) {
  if (event.key === 'Escape' && (event.target as HTMLInputElement).getAttribute('aria-expanded') === 'true') event.stopPropagation();
}
</script>
<template>
  <AutoComplete v-model="value" :suggestions="matches" :disabled="disabled" :placeholder="placeholder" :min-length="0" :delay="0" complete-on-focus class="themed-autocomplete" overlay-class="themed-autocomplete-options" :pt="{ pcInputText: { root: { 'aria-label': label } } }" @complete="complete" @keydown="keyboard" />
</template>
