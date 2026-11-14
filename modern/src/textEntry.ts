/** Match GTK text entry: Enter accepts, modified Enter inserts a line break. */
export function installTextEntry() {
  document.addEventListener("keydown", event => {
    const input = event.target;
    if (event.key === "Enter" && !event.isComposing && !event.shiftKey && !event.ctrlKey && !event.metaKey && input instanceof HTMLInputElement && ["text", "number", "search", "url"].includes(input.type) && !input.disabled && !input.closest("form,.tabulator")) {
      const dialog = input.closest('[role="dialog"]');
      const primary = dialog && Array.from(dialog.querySelectorAll<HTMLButtonElement>("button.button.primary")).filter(button => !button.disabled).at(-1);
      if (primary) { event.preventDefault(); event.stopPropagation(); input.blur(); primary.click(); }
      return;
    }
    if (event.key !== "Enter" || event.isComposing || !(input instanceof HTMLTextAreaElement) || input.disabled || input.readOnly || input.closest(".tabulator")) return;
    event.preventDefault();
    event.stopPropagation();
    if (event.shiftKey || event.ctrlKey || event.metaKey) {
      input.setRangeText("\n", input.selectionStart, input.selectionEnd, "end");
      input.dispatchEvent(new Event("input", { bubbles: true }));
      return;
    }
    const form = input.closest("form");
    const dialog = input.closest('[role="dialog"]');
    input.blur();
    if (form) form.requestSubmit();
    else if (dialog) {
      const primary = Array.from(dialog.querySelectorAll<HTMLButtonElement>("button.button.primary")).filter(button => !button.disabled).at(-1);
      primary?.click();
    }
  }, true);
}
