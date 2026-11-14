<script setup lang="ts">
import { computed, nextTick, onMounted, onBeforeUnmount, ref } from "vue";
import Menu from "primevue/menu";
import type { MenuItem } from "primevue/menuitem";
import AppIcon from "./AppIcon.vue";

// Keep native select values, labels and form behavior, but use the app's themed
// popup for pointer/keyboard interaction on every select, including dialogs.
const menu = ref<InstanceType<typeof Menu>>();
const target = ref<HTMLSelectElement>();
const items = ref<MenuItem[]>([]);
const opened = ref(false);
const width = computed(() => Math.max(220, target.value?.getBoundingClientRect().width || 0) + "px");
function choose(option: HTMLOptionElement) {
  if (!target.value) return;
  target.value.value = option.value;
  target.value.dispatchEvent(new Event("input", { bubbles: true }));
  target.value.dispatchEvent(new Event("change", { bubbles: true }));
  target.value.focus();
}
async function show(select: HTMLSelectElement) {
  if (target.value === select && opened.value) { menu.value?.hide(); return; }
  menu.value?.hide();
  target.value = select;
  select.setAttribute("aria-controls", "themed-select-options");
  const model: MenuItem[] = [];
  let currentGroup: HTMLOptGroupElement | null = null;
  let children = model;
  for (const option of Array.from(select.options)) {
    if (option.hidden) continue;
    const group = option.parentElement instanceof HTMLOptGroupElement ? option.parentElement : null;
    if (group !== currentGroup) {
      currentGroup = group;
      children = model;
      if (group) { children = []; model.push({ label: group.label, items: children }); }
    }
    children.push({ label: option.label, selected: option.selected, disabled: option.disabled || !!group?.disabled, command: () => choose(option) });
  }
  items.value = model;
  await nextTick();
  menu.value?.show({ currentTarget: select, target: select } as unknown as Event);
}
function pointer(event: MouseEvent) {
  if (!(event.target instanceof HTMLSelectElement) || event.target.disabled || event.target.multiple || event.target.size > 1) return;
  event.preventDefault();
  void show(event.target);
}
function keyboard(event: KeyboardEvent) {
  if (!(event.target instanceof HTMLSelectElement) || event.target.disabled || event.target.multiple || event.target.size > 1 || !["Enter", " ", "ArrowDown", "ArrowUp"].includes(event.key)) return;
  event.preventDefault(); event.stopPropagation();
  void show(event.target);
}
onMounted(() => { document.addEventListener("mousedown", pointer, true); document.addEventListener("keydown", keyboard, true); });
onBeforeUnmount(() => { document.removeEventListener("mousedown", pointer, true); document.removeEventListener("keydown", keyboard, true); });
</script>
<template>
  <Menu ref="menu" id="themed-select-options" popup :model="items" class="application-menu themed-select-menu" :style="{ minWidth: width }" :aria-label="target?.getAttribute('aria-label') || 'Choose option'" @show="opened = true; target?.setAttribute('aria-expanded', 'true')" @hide="opened = false; target?.setAttribute('aria-expanded', 'false')">
    <template #item="{ item, props }"><a v-bind="props.action" class="application-menu-item" :aria-current="item.selected ? 'true' : undefined"><AppIcon :name="item.selected ? 'check' : 'blank'" :size="16" /><span>{{ item.label }}</span></a></template>
  </Menu>
</template>
