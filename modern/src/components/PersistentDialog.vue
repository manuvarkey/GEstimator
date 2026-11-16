<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, useId, watch } from "vue";
import vFocusTrap from "primevue/focustrap";
import AppIcon from "./AppIcon.vue";

// Lazy modal whose content stays mounted, including expensive table instances.
defineOptions({ inheritAttrs: false });
const visible = defineModel<boolean>("visible", { required: true });
const props = defineProps<{ header: string; busy: boolean }>();
const emit = defineEmits<{ show: [] }>();
const created = ref(false);
const panel = ref<HTMLElement>();
const heading = useId();
let previous: HTMLElement | null = null;
function keyboard(event: KeyboardEvent) {
  if (!visible.value || event.key !== "Escape" || event.defaultPrevented) return;
  if (document.querySelector('.p-popover,.themed-select-menu')) return;
  event.preventDefault(); event.stopPropagation();
  if (!props.busy) visible.value = false;
}
watch(visible, async opened => {
  if (opened) {
    previous = document.activeElement as HTMLElement;
    created.value = true;
    document.addEventListener("keydown", keyboard);
    await nextTick();
    panel.value?.querySelector<HTMLElement>('input:not(:disabled),select:not(:disabled),button:not(:disabled)')?.focus({ preventScroll: true });
    emit("show");
  } else {
    document.removeEventListener("keydown", keyboard);
    previous?.focus({ preventScroll: true });
  }
}, { immediate: true });
onBeforeUnmount(() => document.removeEventListener("keydown", keyboard));
</script>
<template>
  <Teleport to="body">
    <div v-if="created" class="persistent-dialog-mask" :class="{ 'persistent-dialog-hidden': !visible }" :inert="!visible" :aria-hidden="!visible || undefined">
      <section ref="panel" v-focus-trap :role="visible ? 'dialog' : undefined" :aria-modal="visible || undefined" :aria-labelledby="heading" class="workspace-dialog persistent-dialog" v-bind="$attrs">
        <div class="p-dialog-header"><span :id="heading" class="p-dialog-title">{{ header }}</span><button class="icon-button" aria-label="Close dialog" :disabled="busy" @click="visible = false"><AppIcon name="close" /></button></div>
        <div class="p-dialog-content"><slot /></div>
      </section>
    </div>
  </Teleport>
</template>
