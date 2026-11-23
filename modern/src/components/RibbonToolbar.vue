<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";

const host = ref<HTMLElement>();
let resize: ResizeObserver;
let mutations: MutationObserver;
let fontChanges: MutationObserver;
let frame = 0;
const canvas = document.createElement("canvas");
const measure = canvas.getContext("2d");
function sizeCaptions(element: HTMLElement) {
  if (!measure) return;
  for (const button of Array.from(element.querySelectorAll<HTMLElement>(".ribbon-action:not(.ribbon-icon)"))) {
    const label = button.querySelector<HTMLElement>(".ribbon-label");
    const text = label?.textContent?.trim();
    if (!label || !text) continue;
    const style = getComputedStyle(label);
    measure.font = `${style.fontStyle} ${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
    const spacing = parseFloat(style.letterSpacing) || 0;
    const width = (value: string) => measure.measureText(value).width + Math.max(0, value.length - 1) * spacing;
    const words = text.split(/\s+/);
    let caption = width(text);
    for (let split = 1; split < words.length; split++) {
      caption = Math.min(
        caption,
        Math.max(width(words.slice(0, split).join(" ")), width(words.slice(split).join(" "))),
      );
    }
    caption = Math.min(80, Math.ceil(caption) + 1);
    const padding = getComputedStyle(button);
    const total = caption + parseFloat(padding.paddingLeft) + parseFloat(padding.paddingRight);
    button.style.setProperty("--ribbon-caption-width", `${caption}px`);
    button.style.setProperty("--ribbon-button-width", `${Math.max(52, Math.ceil(total))}px`);
  }
}
function fitNow() {
  const element = host.value;
  if (!element) return;
  element.querySelectorAll("[data-ribbon-mini]").forEach((button) => button.removeAttribute("data-ribbon-mini"));
  sizeCaptions(element);
  const groups = Array.from(element.querySelectorAll<HTMLElement>(".ribbon-group"));
  const width = () => groups.reduce((total, group) => total + group.getBoundingClientRect().width, 0);
  const style = getComputedStyle(element);
  const available = element.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
  // Degrade only as many actions as needed, keeping a constant ribbon depth.
  const buttons = Array.from(element.querySelectorAll<HTMLElement>(".ribbon-action"));
  for (const button of buttons.reverse()) {
    if (width() <= available) break;
    if (button.hasAttribute("data-ribbon-keep-label")) continue;
    if (button.getBoundingClientRect().width) button.dataset.ribbonMini = "true";
  }
}
function fit() {
  cancelAnimationFrame(frame);
  frame = requestAnimationFrame(fitNow);
}
defineExpose({
  prepare: () => {
    cancelAnimationFrame(frame);
    fitNow();
  },
});
onMounted(() => {
  resize = new ResizeObserver(fit);
  resize.observe(host.value!);
  mutations = new MutationObserver((records) => {
    // Cached views switch via v-show. Ignore the button sizing styles written
    // by fit itself, but refit when a ribbon container becomes visible.
    if (
      records.some(
        (record) => record.type !== "attributes" || !(record.target as Element).classList.contains("ribbon-action"),
      )
    )
      fit();
  });
  mutations.observe(host.value!, {
    childList: true,
    subtree: true,
    characterData: true,
    attributes: true,
    attributeFilter: ["style"],
  });
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
