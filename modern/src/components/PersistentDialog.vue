<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, useId, watch } from "vue";
import vFocusTrap from "primevue/focustrap";
import AppIcon from "./AppIcon.vue";
import { dialogPrimary } from "../uiActions";

// Lazy modal whose content stays mounted, including expensive table instances.
defineOptions({ inheritAttrs: false });
const visible = defineModel<boolean>("visible", { required: true });
const props = defineProps<{ header: string; busy: boolean }>();
const emit = defineEmits<{ show: [] }>();
const created = ref(false);
const panel = ref<HTMLElement>();
const heading = useId();
const zIndex = ref(1000);
let previous: HTMLElement | null = null;
function hasVisibleChildOverlay(): boolean {
  for (const el of Array.from(document.querySelectorAll<HTMLElement>(".p-popover, .themed-select-menu"))) {
    if (
      el.getClientRects().length > 0 &&
      getComputedStyle(el).display !== "none" &&
      getComputedStyle(el).visibility !== "hidden"
    ) {
      return true;
    }
  }
  return false;
}

function keyboard(event: KeyboardEvent) {
  if (!visible.value || event.key !== "Escape") return;
  // Let open child popovers (such as CategoryFilter) handle Escape first before closing the dialog.
  if (hasVisibleChildOverlay()) return;
  event.preventDefault();
  event.stopPropagation();
  if (!props.busy) visible.value = false;
}
watch(
  visible,
  async (opened) => {
    if (opened) {
      previous = document.activeElement as HTMLElement;
      // Reused pickers can open above a PrimeVue dialog (measurement properties).
      zIndex.value =
        Math.max(
          1000,
          ...Array.from(document.querySelectorAll<HTMLElement>(".p-dialog-mask,.persistent-dialog-mask"))
            .filter((mask) => mask.getClientRects().length && getComputedStyle(mask).visibility !== "hidden")
            .map((mask) => Number(getComputedStyle(mask).zIndex) || 0),
        ) + 1;
      created.value = true;
      document.addEventListener("keydown", keyboard, true);
      await nextTick();
      if (!visible.value) return;
      const field = panel.value && dialogPrimary(panel.value);
      field?.focus({ preventScroll: true });
      emit("show");
    } else {
      document.removeEventListener("keydown", keyboard, true);
      const opener = previous;
      previous = null;
      // The parent dialog may still be inert while the picker is closing.
      await nextTick();
      if (!visible.value) opener?.focus({ preventScroll: true });
    }
  },
  { immediate: true },
);
onBeforeUnmount(() => document.removeEventListener("keydown", keyboard, true));
</script>
<template>
  <Teleport to="body">
    <div
      v-if="created"
      class="persistent-dialog-mask"
      :style="{ zIndex }"
      :class="{ 'persistent-dialog-hidden': !visible }"
      :inert="!visible"
      :aria-hidden="!visible || undefined"
    >
      <section
        ref="panel"
        v-focus-trap
        :role="visible ? 'dialog' : undefined"
        :aria-modal="visible || undefined"
        :aria-labelledby="heading"
        class="workspace-dialog persistent-dialog"
        v-bind="$attrs"
      >
        <div class="p-dialog-header">
          <span :id="heading" class="p-dialog-title">{{ header }}</span
          ><button class="icon-button" aria-label="Close dialog" :disabled="busy" @click="visible = false">
            <AppIcon name="close" />
          </button>
        </div>
        <div class="p-dialog-content"><slot /></div>
      </section>
    </div>
  </Teleport>
</template>
