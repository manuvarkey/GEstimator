import type { ObjectDirective } from "vue";

const segmenter = typeof Intl.Segmenter === "function"
  ? new Intl.Segmenter(undefined, { granularity: "grapheme" })
  : undefined;

function fit(element: HTMLElement, text: string) {
  element.textContent = text;
  if (!element.clientWidth || element.scrollHeight <= element.clientHeight) return;

  const parts = segmenter ? Array.from(segmenter.segment(text), part => part.segment) : Array.from(text);
  const shortened = (count: number) => {
    const left = Math.ceil(count / 2);
    const right = Math.floor(count / 2);
    return parts.slice(0, left).join("").trimEnd() + "…" +
      parts.slice(parts.length - right).join("").trimStart();
  };
  let low = 0;
  let high = parts.length - 1;
  while (low < high) {
    const count = Math.ceil((low + high) / 2);
    element.textContent = shortened(count);
    if (element.scrollHeight <= element.clientHeight) low = count;
    else high = count - 1;
  }
  element.textContent = shortened(low);
}

const observed = new WeakMap<HTMLElement, { text: string; observer: ResizeObserver }>();
export const vMiddleEllipsis: ObjectDirective<HTMLElement, string> = {
  mounted(element, { value }) {
    const state = {
      text: value.trim(),
      observer: new ResizeObserver(() => fit(element, state.text)),
    };
    observed.set(element, state);
    fit(element, state.text);
    state.observer.observe(element);
  },
  updated(element, { value, oldValue }) {
    const state = observed.get(element)!;
    if (value === oldValue) return;
    state.text = value.trim();
    fit(element, state.text);
  },
  beforeUnmount(element) { observed.get(element)?.observer.disconnect(); },
};
