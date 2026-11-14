<script setup lang="ts">
import { computed, ref } from "vue";
import Popover from "primevue/popover";
import AppIcon from "./AppIcon.vue";
const selected = defineModel<string[]>({ required: true });
const props = defineProps<{ categories: string[]; disabled: boolean }>();
const panel = ref<InstanceType<typeof Popover>>();
const query = ref("");
const opened = ref(false);
const filtered = computed(() => props.categories.filter(name => name.toLowerCase().includes(query.value.toLowerCase())));
function toggle(name: string) {
  selected.value = selected.value.includes(name) ? selected.value.filter(value => value !== name) : [...selected.value, name];
}
</script>
<template>
  <button class="button small secondary" type="button" aria-label="Filter categories" :aria-expanded="opened" :disabled="disabled" title="Show items in one or several categories. Clear the selection to show all categories." @click="panel?.toggle($event)"><AppIcon name="filter" :size="16" />{{ selected.length ? `${selected.length} categories` : 'All categories' }}</button>
  <Popover ref="panel" class="category-filter application-menu" @show="opened = true" @hide="opened = false">
    <input v-model="query" aria-label="Find categories" placeholder="Find categories…" />
    <div class="category-options" role="group" aria-label="Categories"><label v-for="name in filtered" :key="name"><input type="checkbox" :checked="selected.includes(name)" @change="toggle(name)" />{{ name || '(Uncategorised)' }}</label></div>
    <button class="text-button" :disabled="!selected.length" @click="selected = []">Show all categories</button>
  </Popover>
</template>
