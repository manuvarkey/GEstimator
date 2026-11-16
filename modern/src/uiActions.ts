/** Lightweight action traces and consistent primary-field focus in dialogs. */
export function debugAction(action: string, details: Record<string, unknown> = {}) {
  console.debug("[GEstimator]", action, details);
}

export function installUIActions() {
  document.addEventListener("click", event => {
    const button = (event.target as Element)?.closest<HTMLElement>('button,[role="menuitem"],[role="tab"]');
    if (button) debugAction("ui.action", { action: button.getAttribute("aria-label") || button.dataset.action || ((button.classList.contains("item-card") || button.classList.contains("library-item")) ? "picker.item" : button.textContent?.trim().slice(0, 80)) });
  }, true);
  document.addEventListener("keydown", event => {
    if ((event.ctrlKey || event.metaKey || event.altKey) && event.key.length < 20)
      debugAction("ui.shortcut", { key: event.key, ctrl: event.ctrlKey, meta: event.metaKey, alt: event.altKey, shift: event.shiftKey });
  }, true);
  const focused = new WeakMap<Element, Element>();
  let scheduled = false;
  const focus = () => {
    scheduled = false;
    for (const dialog of Array.from(document.querySelectorAll<HTMLElement>('[role="dialog"]'))) {
      if (!dialog.getClientRects().length) { focused.delete(dialog); continue; }
      const primary = dialog.querySelector<HTMLElement>('[data-primary-input]:not(:disabled),[autofocus]:not(:disabled)');
      if (focused.has(dialog) && (!primary || focused.get(dialog) === primary)) continue;
      const field = dialog.querySelector<HTMLElement>('[data-primary-input]:not(:disabled),[autofocus]:not(:disabled)')
        || dialog.querySelector<HTMLElement>('.search-field input:not(:disabled),textarea:not(:disabled),input:not(:disabled):not([type="checkbox"]):not([type="hidden"]),select:not(:disabled)');
      if (field) { focused.set(dialog, field); field.focus({ preventScroll: true }); }
    }
  };
  new MutationObserver(() => {
    if (!scheduled) { scheduled = true; requestAnimationFrame(focus); }
  }).observe(document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ["style", "aria-hidden"] });
}
