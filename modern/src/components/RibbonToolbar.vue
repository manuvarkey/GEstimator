<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";

const host = ref<HTMLElement>();
let resize: ResizeObserver;
let mutations: MutationObserver;
let fontChanges: MutationObserver;
let frame = 0;
function fit() {
  cancelAnimationFrame(frame);
  frame = requestAnimationFrame(() => {
    const element = host.value;
    if (!element) return;
    element.removeAttribute("data-compact");
    const groups = Array.from(element.querySelectorAll<HTMLElement>(".ribbon-group"));
    const width = groups.reduce((total, group) => total + group.getBoundingClientRect().width, 0);
    const style = getComputedStyle(element);
    const available = element.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
    if (width > available) element.dataset.compact = "true";
  });
}
onMounted(() => {
  resize = new ResizeObserver(fit);
  resize.observe(host.value!);
  mutations = new MutationObserver(fit);
  mutations.observe(host.value!, { childList: true, subtree: true, characterData: true });
  fontChanges = new MutationObserver(fit);
  fontChanges.observe(document.documentElement, { attributes: true, attributeFilter: ["style"] });
  document.fonts.addEventListener("loadingdone", fit);
  void document.fonts.ready.then(fit);
});
onBeforeUnmount(() => {
  resize?.disconnect();
  mutations?.disconnect();
  fontChanges?.disconnect();
  document.fonts.removeEventListener("loadingdone", fit);
  cancelAnimationFrame(frame);
});
</script>

<template>
  <section ref="host" class="ribbon"><slot /></section>
</template>
