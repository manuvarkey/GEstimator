<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from "vue";

// Keep form bindings on the original select. Only its presentation is enhanced;
// value choices use a listbox rather than a command menu.
const target = ref<HTMLSelectElement>();
const options = ref<{ label: string; value: string; disabled: boolean; group: string }[]>([]);
const active = ref(-1);
const panel = ref<HTMLElement>();
const placement = ref<Record<string, string>>({});
let prefix = "";
let typedAt = 0;
function close() {
  target.value?.setAttribute("aria-expanded", "false");
  target.value?.removeAttribute("aria-controls");
  target.value?.removeAttribute("aria-activedescendant");
  target.value = undefined;
}
function position() {
  if (!target.value || !panel.value) return;
  const rect = target.value.getBoundingClientRect();
  const below = window.innerHeight - rect.bottom - 8;
  const above = rect.top - 8;
  const upward = below < 180 && above > below;
  const height = Math.min(320, Math.max(60, upward ? above : below));
  const masks = Array.from(document.querySelectorAll<HTMLElement>('.p-dialog-mask,.persistent-dialog-mask'));
  placement.value = {
    position: 'fixed', width: Math.min(rect.width, window.innerWidth - 16) + 'px',
    left: Math.max(8, Math.min(rect.left, window.innerWidth - rect.width - 8)) + 'px',
    top: (upward ? Math.max(8, rect.top - Math.min(panel.value.scrollHeight, height)) : rect.bottom + 3) + 'px',
    maxHeight: height + 'px', zIndex: String(Math.max(1200, ...masks.map(mask => (Number(getComputedStyle(mask).zIndex) || 0) + 1))),
  };
}
async function show(select: HTMLSelectElement) {
  if (target.value === select) { close(); return; }
  close();
  prefix = ""; typedAt = 0;
  target.value = select;
  options.value = Array.from(select.options).filter(o => !o.hidden).map(o => ({
    label: o.label, value: o.value, disabled: o.disabled || (o.parentElement instanceof HTMLOptGroupElement && o.parentElement.disabled),
    group: o.parentElement instanceof HTMLOptGroupElement ? o.parentElement.label : '',
  }));
  active.value = options.value.findIndex(o => o.value === select.value && !o.disabled);
  select.setAttribute('aria-expanded', 'true');
  select.setAttribute('aria-controls', 'workspace-dropdown-options');
  select.focus();
  await nextTick(); position(); reveal();
}
function reveal() {
  if (active.value < 0) return;
  target.value?.setAttribute('aria-activedescendant', 'workspace-option-' + active.value);
  document.getElementById('workspace-option-' + active.value)?.scrollIntoView({ block: 'nearest' });
}
function move(delta: number) {
  for (let i = active.value + delta; i >= 0 && i < options.value.length; i += delta) {
    if (!options.value[i]!.disabled) { active.value = i; void nextTick(reveal); return; }
  }
}
function choose(index: number) {
  const select = target.value, option = options.value[index];
  if (!select || !option || option.disabled) return;
  select.value = option.value;
  select.dispatchEvent(new Event('input', { bubbles: true }));
  select.dispatchEvent(new Event('change', { bubbles: true }));
  close(); select.focus();
}
function pointer(event: MouseEvent) {
  if (event.button !== 0) return;
  const select = event.target;
  if (select instanceof HTMLSelectElement && !select.disabled && !select.multiple && select.size <= 1) {
    event.preventDefault(); void show(select);
  } else if (!panel.value?.contains(event.target as Node)) close();
}
function keyboard(event: KeyboardEvent) {
  if (!(event.target instanceof HTMLSelectElement) || event.target.disabled || event.target.multiple || event.target.size > 1 || event.ctrlKey || event.metaKey) return;
  if (!target.value) {
    if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(event.key)) { event.preventDefault(); event.stopPropagation(); void show(event.target); }
    return;
  }
  if (event.key === 'Tab') { close(); return; }
  if (!['ArrowDown', 'ArrowUp', 'Home', 'End', 'Enter', ' ', 'Escape'].includes(event.key) && event.key.length !== 1) return;
  event.preventDefault(); event.stopPropagation();
  if (event.key === 'Escape') close();
  else if (event.key === 'Enter' || event.key === ' ') choose(active.value);
  else if (event.key === 'ArrowDown') move(1);
  else if (event.key === 'ArrowUp') move(-1);
  else if (event.key === 'Home') { active.value = -1; move(1); }
  else if (event.key === 'End') { active.value = options.value.length; move(-1); }
  else {
    prefix = (Date.now() - typedAt > 700 ? '' : prefix) + event.key.toLocaleLowerCase(); typedAt = Date.now();
    const index = options.value.findIndex(o => !o.disabled && o.label.toLocaleLowerCase().startsWith(prefix));
    if (index >= 0) { active.value = index; void nextTick(reveal); }
  }
}
function blur(event: FocusEvent) { if (event.target === target.value) close(); }
onMounted(() => {
  document.addEventListener('mousedown', pointer, true); document.addEventListener('keydown', keyboard, true);
  document.addEventListener('focusout', blur, true); window.addEventListener('resize', close); document.addEventListener('scroll', position, true);
});
onBeforeUnmount(() => {
  close(); document.removeEventListener('mousedown', pointer, true); document.removeEventListener('keydown', keyboard, true);
  document.removeEventListener('focusout', blur, true); window.removeEventListener('resize', close); document.removeEventListener('scroll', position, true);
});
</script>
<template>
  <Teleport to="body">
    <div v-if="target" id="workspace-dropdown-options" ref="panel" class="themed-dropdown" role="listbox" :aria-label="target.getAttribute('aria-label') || 'Choose option'" :style="placement" @mousedown.prevent>
      <template v-for="(option, index) in options" :key="index">
        <div v-if="option.group && (index === 0 || option.group !== options[index - 1]?.group)" class="dropdown-group" role="presentation">{{ option.group }}</div>
        <div :id="'workspace-option-' + index" role="option" :aria-selected="option.value === target.value" :aria-disabled="option.disabled" :class="{ active: index === active, disabled: option.disabled }" @mousemove="!option.disabled && (active = index)" @click="choose(index)">{{ option.label }}</div>
      </template>
    </div>
  </Teleport>
</template>
