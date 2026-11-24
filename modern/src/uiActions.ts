/** Lightweight action traces and consistent primary-field focus in dialogs. */
export function debugAction(action: string, details: Record<string, unknown> = {}) {
  console.debug("[GEstimator]", action, details);
}

export function dialogPrimary(dialog: Element) {
  const content = dialog.querySelector(".p-dialog-content") || dialog;
  const visible = (selector: string) =>
    Array.from(content.querySelectorAll<HTMLElement>(selector)).find(
      (field) =>
        !field.matches(":disabled,[readonly]") &&
        field.getClientRects().length &&
        getComputedStyle(field).visibility !== "hidden",
    );
  return (
    visible("[data-primary-input]") ||
    visible("[autofocus]") ||
    visible('.search-field input,input[type="search"]') ||
    visible("textarea") ||
    visible('input:not([type="checkbox"]):not([type="radio"]):not([type="hidden"])') ||
    visible("select")
  );
}

/** Wait for closing modal transitions before restoring a newly raised editor. */
export function afterDialogsClose(action: () => void | Promise<void>) {
  let cancelled = false;
  let observer: MutationObserver | undefined;
  let frame = 0;
  const run = () => {
    if (document.querySelector('[role="dialog"]')) return;
    observer?.disconnect();
    frame = requestAnimationFrame(() => {
      if (!cancelled) void action();
    });
  };
  if (document.querySelector('[role="dialog"]')) {
    observer = new MutationObserver(run);
    observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["role"] });
  }
  run();
  return () => {
    cancelled = true;
    observer?.disconnect();
    cancelAnimationFrame(frame);
  };
}

export function installUIActions() {
  document.addEventListener(
    "click",
    (event) => {
      const button = (event.target as Element)?.closest<HTMLElement>('button,[role="menuitem"],[role="tab"]');
      if (button)
        debugAction("ui.action", {
          action:
            button.getAttribute("aria-label") ||
            button.dataset.action ||
            (button.classList.contains("item-card") || button.classList.contains("library-item")
              ? "picker.item"
              : button.textContent?.trim().slice(0, 80)),
        });
    },
    true,
  );
  document.addEventListener(
    "keydown",
    (event) => {
      if ((event.ctrlKey || event.metaKey || event.altKey) && event.key.length < 20)
        debugAction("ui.shortcut", {
          key: event.key,
          ctrl: event.ctrlKey,
          meta: event.metaKey,
          alt: event.altKey,
          shift: event.shiftKey,
        });
    },
    true,
  );
  const focused = new WeakMap<Element, Element>();
  let previousDialogs = new Set<Element>();
  let scheduled = false;
  const focus = () => {
    scheduled = false;
    const mountedDialogs = Array.from(document.querySelectorAll<HTMLElement>('[role="dialog"]')).filter(
      (dialog) => dialog.getClientRects().length && getComputedStyle(dialog).visibility !== "hidden",
    );
    // A covered parent is still open. Keep its focus record so closing the child can restore its opener.
    for (const previous of previousDialogs)
      if (!mountedDialogs.includes(previous as HTMLElement)) focused.delete(previous);
    previousDialogs = new Set(mountedDialogs);
    const dialogs = mountedDialogs.filter((dialog) => !dialog.closest('[inert],[aria-hidden="true"]'));
    dialogs.sort(
      (a, b) =>
        Number(getComputedStyle(a.closest(".p-dialog-mask,.persistent-dialog-mask") || a).zIndex || 0) -
        Number(getComputedStyle(b.closest(".p-dialog-mask,.persistent-dialog-mask") || b).zIndex || 0),
    );
    const dialog = dialogs.at(-1);
    const field = dialog && dialogPrimary(dialog);
    if (dialog && field && focused.get(dialog) !== field) {
      // PrimeVue's enter transition also uses autofocus. Give it the same target.
      dialog.querySelectorAll("[autofocus]").forEach((other) => {
        if (other !== field) other.removeAttribute("autofocus");
      });
      field.setAttribute("autofocus", "");
      focused.set(dialog, field);
      field.focus({ preventScroll: true });
    }
  };
  new MutationObserver(() => {
    if (!scheduled) {
      scheduled = true;
      requestAnimationFrame(focus);
    }
  }).observe(document.documentElement, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ["style", "class", "role", "aria-hidden", "disabled"],
  });
}

/** Focus search in the frontmost dialog, otherwise in the visible editor. */
export function focusSearch() {
  const visible = (el: HTMLElement) =>
    !!el.getClientRects().length &&
    getComputedStyle(el).visibility !== "hidden" &&
    !el.closest('[inert],[aria-hidden="true"]');
  const dialogs = Array.from(document.querySelectorAll<HTMLElement>('[role="dialog"]')).filter(visible);
  dialogs.sort(
    (a, b) =>
      Number(getComputedStyle(a.closest(".p-dialog-mask,.persistent-dialog-mask") || a).zIndex || 0) -
      Number(getComputedStyle(b.closest(".p-dialog-mask,.persistent-dialog-mask") || b).zIndex || 0),
  );
  const scope = dialogs.at(-1) || document;
  const input = Array.from(scope.querySelectorAll<HTMLInputElement>('.search-field input,input[type="search"]')).find(
    (el) => visible(el) && !el.disabled,
  );
  input?.focus({ preventScroll: true });
  input?.select();
}
