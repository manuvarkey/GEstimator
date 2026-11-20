import type { Editor } from "tabulator-tables";

/** Retain the displayed cell's typography, padding and tree prefix while editing. */
function textEditor(multiline: boolean): Editor {
  return (cell, onRendered, success, cancel, params) => {
    const element = cell.getElement();
    const style = getComputedStyle(element);
    const height = element.getBoundingClientRect().height;
    const verticalPadding = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom);
    const lineHeight = parseFloat(style.lineHeight) || parseFloat(style.fontSize) * 1.35;
    const contentHeight = Math.max(lineHeight, height - verticalPadding - parseFloat(style.borderTopWidth) - parseFloat(style.borderBottomWidth));
    const shell = document.createElement("div");
    shell.className = "table-text-editor-shell";
    shell.style.padding = style.padding;
    shell.style.height = height + "px";
    // Tabulator replaces the cell contents when editing starts. Keep its own
    // branch nodes in the first line of the editor so their indent stays in flow.
    const decorations = Array.from(element.children).filter(child =>
      child.matches(".tabulator-data-tree-branch,.tabulator-data-tree-branch-empty,.tabulator-data-tree-control,.tree-spacer"));
    if (decorations.length) {
      const prefix = document.createElement("span");
      prefix.className = "table-text-editor-prefix";
      prefix.append(...decorations);
      shell.appendChild(prefix);
    }
    const input = multiline ? document.createElement("textarea") : document.createElement("input");
    const originalValue = cell.getValue();
    const originalText = String(originalValue ?? "");
    input.value = originalText;
    input.className = "table-text-editor";
    if (input instanceof HTMLTextAreaElement) input.rows = 1;
    Object.assign(input.style, {
      height: contentHeight + "px", padding: "0", fontFamily: style.fontFamily,
      fontSize: style.fontSize, fontWeight: style.fontWeight, fontStyle: style.fontStyle,
      lineHeight: style.lineHeight, letterSpacing: style.letterSpacing, textAlign: style.textAlign,
    });
    shell.appendChild(input);
    let done = false;
    let currentHeight = height;
    const commit = () => {
      if (done) return;
      done = true;
      // Tabulator rebuilds the cell on success but skips tree layout for an unchanged value.
      if (input.value === originalText) cancel(originalValue);
      else success(input.value);
    };
    const resize = () => {
      if (!multiline || params.grow === false) return;
      input.style.height = "0px";
      const next = Math.max(contentHeight, input.scrollHeight);
      input.style.height = next + "px";
      const nextHeight = Math.max(height, next + verticalPadding);
      if (Math.abs(nextHeight - currentHeight) > 1) {
        currentHeight = nextHeight;
        shell.style.height = nextHeight + "px";
        cell.getRow().normalizeHeight();
      }
    };
    // Numeric cells (rates, quantities, percentages) are right-aligned. Their usual edit
    // replaces the whole value, so start with it selected; text cells keep the caret at the end.
    const numeric = params.selectAll ?? cell.getColumn().getDefinition().hozAlign === "right";
    onRendered(() => { input.focus({ preventScroll: true }); if (numeric) input.select(); });
    input.addEventListener("blur", commit);
    input.addEventListener("input", resize);
    input.addEventListener("keydown", raw => {
      const event = raw as KeyboardEvent;
      if (event.isComposing) return;
      if (event.key === "Home" || event.key === "End") event.stopPropagation();
      if (event.key === "Escape") { done = true; cancel(cell.getValue()); }
      else if (multiline && event.key === "Enter" && (event.shiftKey || event.ctrlKey || event.metaKey)) {
        event.preventDefault(); input.setRangeText("\n", input.selectionStart!, input.selectionEnd!, "end"); resize();
      } else if (event.key === "Enter") { event.preventDefault(); commit(); }
    });
    return shell;
  };
}

export const tableTextEditor = textEditor(true);
export const tableInputEditor = textEditor(false);
