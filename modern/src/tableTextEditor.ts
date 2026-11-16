import type { Editor } from "tabulator-tables";

/** Match the existing row on entry; grow only when edited text needs another line. */
export const tableTextEditor: Editor = (cell, onRendered, success, cancel, params) => {
  const input = document.createElement("textarea");
  const height = Math.max(24, cell.getElement().getBoundingClientRect().height);
  input.value = String(cell.getValue() ?? "");
  input.className = "table-text-editor";
  input.rows = 1;
  input.style.height = height + "px";
  let done = false;
  const commit = () => { if (!done) { done = true; success(input.value); } };
  const resize = () => {
    if (params.grow === false) return;
    input.style.height = "0px";
    const next = Math.max(height, input.scrollHeight);
    input.style.height = next + "px";
    if (next > height) cell.getRow().normalizeHeight();
  };
  onRendered(() => { input.focus({ preventScroll: true }); });
  input.addEventListener("blur", commit);
  input.addEventListener("input", resize);
  input.addEventListener("keydown", event => {
    if (event.key === "Escape") { done = true; cancel(cell.getValue()); }
    else if (event.key === "Enter" && (event.shiftKey || event.ctrlKey || event.metaKey)) {
      event.preventDefault(); input.setRangeText("\n", input.selectionStart, input.selectionEnd, "end"); resize();
    } else if (event.key === "Enter") { event.preventDefault(); commit(); }
  });
  return input;
};
