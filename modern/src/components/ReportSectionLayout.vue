<script setup lang="ts">
/** Edit presentation choices; Python validates fields and projects authoritative values. */
import { computed } from "vue";
import AppIcon from "./AppIcon.vue";
import type { ReportColumnKey, ReportSection, ReportSectionKind } from "../reportTypes";

const props = defineProps<{ kind: ReportSectionKind }>();
const columns = defineModel<ReportColumnKey[] | null>("columns", { default: null });
const orientation = defineModel<ReportSection["orientation"]>("orientation", { default: "auto" });
type Choice = { key: ReportColumnKey; title: string };
const common: Choice[] = [
  { key: "code", title: "Code" },
  { key: "description", title: "Description" },
  { key: "unit", title: "Unit" },
];
const choices: Partial<Record<ReportSectionKind, Choice[]>> = {
  abstract: [
    { key: "category", title: "Category" },
    { key: "amount", title: "Amount" },
  ],
  schedule: [
    ...common,
    { key: "quantity", title: "Quantity" },
    { key: "rate", title: "Rate" },
    { key: "amount", title: "Amount" },
    { key: "remarks", title: "Remarks" },
  ],
  resources: [
    ...common,
    { key: "rate", title: "Basic rate" },
    { key: "tax", title: "Tax %" },
    { key: "discount", title: "Discount %" },
    { key: "reference", title: "Reference" },
    { key: "category", title: "Category" },
  ],
  resource_usage: [
    ...common,
    { key: "quantity", title: "Quantity" },
    { key: "rate", title: "Adjusted rate" },
    { key: "amount", title: "Amount" },
    { key: "category", title: "Category" },
  ],
};
const label = computed(() => props.kind.replaceAll("_", " "));
const available = computed(() => choices[props.kind] ?? []);
const ordered = computed(() => {
  const selected = columns.value ?? [];
  return [
    ...selected.map((key) => available.value.find((choice) => choice.key === key)!),
    ...available.value.filter((choice) => !selected.includes(choice.key)),
  ];
});

function customize(enabled: boolean) {
  columns.value = enabled
    ? available.value
        .filter((choice) => props.kind !== "schedule" || choice.key !== "remarks")
        .map((choice) => choice.key)
    : null;
}
function toggle(key: ReportColumnKey) {
  if (!columns.value) return;
  columns.value = columns.value.includes(key)
    ? columns.value.filter((value) => value !== key)
    : [...columns.value, key];
}
function move(key: ReportColumnKey, direction: number) {
  if (!columns.value) return;
  const values = [...columns.value];
  const index = values.indexOf(key);
  const target = index + direction;
  if (index < 0 || target < 0 || target >= values.length) return;
  [values[index], values[target]] = [values[target]!, values[index]!];
  columns.value = values;
}
</script>

<template>
  <div class="section-layout">
    <label class="orientation"
      >Page orientation
      <select v-model="orientation" :aria-label="`${label} page orientation`">
        <option value="auto">Auto</option>
        <option value="portrait">Portrait</option>
        <option value="landscape">Landscape</option>
      </select>
    </label>
    <template v-if="available.length">
      <label
        ><input
          type="checkbox"
          :checked="columns !== null"
          :aria-label="`${label} custom columns`"
          @change="customize(($event.target as HTMLInputElement).checked)"
        />Customize columns</label
      >
      <ol v-if="columns !== null" :aria-label="`${label} columns`">
        <li v-for="choice in ordered" :key="choice.key">
          <label
            ><input
              type="checkbox"
              :checked="columns.includes(choice.key)"
              :disabled="columns.length === 1 && columns.includes(choice.key)"
              :aria-label="`Include ${label} ${choice.title} column`"
              @change="toggle(choice.key)"
            />{{ choice.title }}</label
          >
          <button
            class="icon-button"
            :aria-label="`Move ${label} ${choice.title} column up`"
            :disabled="!columns.includes(choice.key) || columns.indexOf(choice.key) === 0"
            @click="move(choice.key, -1)"
          >
            <AppIcon name="up" />
          </button>
          <button
            class="icon-button"
            :aria-label="`Move ${label} ${choice.title} column down`"
            :disabled="!columns.includes(choice.key) || columns.indexOf(choice.key) === columns.length - 1"
            @click="move(choice.key, 1)"
          >
            <AppIcon name="down" />
          </button>
        </li>
      </ol>
    </template>
    <p>Orientation applies to printed pages. Auto keeps the format’s default layout.</p>
  </div>
</template>

<style scoped>
.section-layout {
  margin-block: 12px;
}
.orientation {
  display: grid;
  gap: 4px;
  margin-block: 12px;
}
ol {
  list-style: none;
  padding: 0;
}
li {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-block: 6px;
}
li label {
  flex: 1;
}
p {
  color: var(--muted);
  font-size: var(--text-size-small);
}
</style>
