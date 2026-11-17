import type { Editor } from "tabulator-tables";

/** Retain the displayed cell's typography, padding and tree prefix while editing. */
// TODO(user review): revise this tree-prefix treatment; it is provisional.
// See docs/migration/workbench-feedback.md: Latest user review.
function textEditor(multiline: boolean): Editor {
  return (cell, onRendered, success, cancel, params) => {
    const element = cell.getElement();
    const cellBox = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    const height = element.getBoundingClientRect().height;
    const verticalPadding = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom);
    const lineHeight = parseFloat(style.lineHeight) || parseFloat(style.fontSize) * 1.35;
    const contentHeight = Math.max(lineHeight, height - verticalPadding - parseFloat(style.borderTopWidth) - parseFloat(style.borderBottomWidth));
    const shell = document.createElement("div");
    shell.className = "table-text-editor-shell";
    shell.style.padding = style.padding;
    shell.style.height = height + "px";
    shell.style.position = "relative";
    let textInset = parseFloat(style.paddingLeft);
    for (const prefix of Array.from(element.children)) {
      if (prefix.matches('.tabulator-data-tree-branch,.tabulator-data-tree-branch-empty,.tabulator-data-tree-control,.tree-spacer') && prefix.getClientRects().length) {
        const box = prefix.getBoundingClientRect();
        const clone = prefix.cloneNode(true) as HTMLElement;
        Object.assign(clone.style, { position: "absolute", left: box.left - cellBox.left + "px", top: box.top - cellBox.top + "px",
          width: box.width + "px", height: box.height + "px", margin: "0", pointerEvents: "none" });
        clone.setAttribute("aria-hidden", "true");
        shell.appendChild(clone);
        textInset = Math.max(textInset, box.right - cellBox.left + (parseFloat(getComputedStyle(prefix).marginRight) || 0));
      }
    }
    const input = multiline ? document.createElement("textarea") : document.createElement("input");
    input.value = String(cell.getValue() ?? "");
    input.className = "table-text-editor";
    if (input instanceof HTMLTextAreaElement) input.rows = 1;
    Object.assign(input.style, {
      height: contentHeight + "px", padding: "0", fontFamily: style.fontFamily,
      fontSize: style.fontSize, fontWeight: style.fontWeight, fontStyle: style.fontStyle,
      lineHeight: style.lineHeight, letterSpacing: style.letterSpacing, textAlign: style.textAlign,
      marginLeft: Math.max(0, textInset - parseFloat(style.paddingLeft)) + "px",
    });
    shell.appendChild(input);
    let done = false;
    let currentHeight = height;
    const commit = () => { if (!done) { done = true; success(input.value); } };
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
    onRendered(() => { input.focus({ preventScroll: true }); });
    input.addEventListener("blur", commit);
    input.addEventListener("input", resize);
    input.addEventListener("keydown", raw => {
      const event = raw as KeyboardEvent;
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
