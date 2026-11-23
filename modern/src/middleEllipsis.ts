import type { ObjectDirective } from "vue";

const segmenter =
  typeof Intl.Segmenter === "function" ? new Intl.Segmenter(undefined, { granularity: "grapheme" }) : undefined;

function fit(element: HTMLElement, text: string) {
  element.textContent = text;
  if (!element.clientWidth) return;
  const style = getComputedStyle(element);
  const lineHeight = parseFloat(style.lineHeight) || 20;
  const maxHeight = parseFloat(style.maxHeight) || lineHeight * 5;
  const targetHeight = Math.min(element.clientHeight || maxHeight, maxHeight);
  if (element.scrollHeight <= targetHeight + 1) return;

  const parts = segmenter ? Array.from(segmenter.segment(text), (part) => part.segment) : Array.from(text);
  const shortened = (count: number) => {
    const left = Math.ceil(count / 2);
    const right = Math.floor(count / 2);
    return (
      parts.slice(0, left).join("").trimEnd() +
      "…" +
      parts
        .slice(parts.length - right)
        .join("")
        .trimStart()
    );
  };
  let low = 0;
  let high = parts.length - 1;
  while (low < high) {
    const count = Math.ceil((low + high) / 2);
    element.textContent = shortened(count);
    if (element.scrollHeight <= targetHeight + 1) low = count;
    else high = count - 1;
  }
  element.textContent = shortened(low);
}

interface ObservedState {
  text: string;
  lastWidth: number;
  observer: ResizeObserver;
}

const observed = new WeakMap<HTMLElement, ObservedState>();
export const vMiddleEllipsis: ObjectDirective<HTMLElement, string> = {
  mounted(element, { value }) {
    const state: ObservedState = {
      text: (value || "").trim(),
      lastWidth: 0,
      observer: new ResizeObserver((entries) => {
        for (const entry of entries) {
          const width = Math.round(entry.contentRect.width);
          if (width && width !== state.lastWidth) {
            state.lastWidth = width;
            fit(element, state.text);
          }
        }
      }),
    };
    observed.set(element, state);
    fit(element, state.text);
    state.lastWidth = Math.round(element.clientWidth);
    state.observer.observe(element);
  },
  updated(element, { value, oldValue }) {
    const state = observed.get(element);
    if (!state || value === oldValue) return;
    state.text = (value || "").trim();
    fit(element, state.text);
  },
  beforeUnmount(element) {
    observed.get(element)?.observer.disconnect();
  },
};
