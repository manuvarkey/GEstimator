<script setup lang="ts">
/** Shared keyboard navigation for settings and numbered editor pages. */
import { useId } from "vue";
const selected = defineModel<string>({ required: true });
const props = defineProps<{ tabs: { key: string; label: string }[]; label: string; disabled?: boolean }>();
const id = useId();
function navigate(event: KeyboardEvent, index: number) {
  const count = props.tabs.length;
  const target =
    event.key === "ArrowRight"
      ? (index + 1) % count
      : event.key === "ArrowLeft"
        ? (index + count - 1) % count
        : event.key === "Home"
          ? 0
          : event.key === "End"
            ? count - 1
            : -1;
  if (target < 0) return;
  event.preventDefault();
  const tab = props.tabs[target]!;
  selected.value = tab.key;
  document.getElementById(id + "-" + tab.key)?.focus();
}
</script>
<template>
  <div class="settings-tabs" role="tablist" :aria-label="label">
    <button
      v-for="(tab, index) in tabs"
      :id="id + '-' + tab.key"
      :key="tab.key"
      type="button"
      role="tab"
      :tabindex="selected === tab.key ? 0 : -1"
      :aria-selected="selected === tab.key"
      :aria-controls="id + '-panel'"
      :disabled="disabled"
      @click="selected = tab.key"
      @keydown="navigate($event, index)"
    >
      {{ tab.label }}
    </button>
  </div>
  <div :id="id + '-panel'" role="tabpanel" :aria-labelledby="id + '-' + selected">
    <slot />
  </div>
</template>
