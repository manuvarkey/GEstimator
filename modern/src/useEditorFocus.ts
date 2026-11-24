import { nextTick, onBeforeUnmount, watch } from "vue";
import { afterDialogsClose } from "./uiActions";

/** Queue one focus handoff to the active grid after its command and any dialog close. */
export function useEditorFocus(active: () => boolean, focusGrid: () => Promise<void> | undefined) {
  let cancel: (() => void) | undefined;
  let disposed = false;
  function cancelPending() {
    cancel?.();
    cancel = undefined;
  }

  watch(active, (visible) => {
    if (!visible) cancelPending();
  });
  onBeforeUnmount(() => {
    disposed = true;
    cancelPending();
  });

  return async function focusEditor() {
    await nextTick();
    if (disposed || !active()) return;
    cancelPending();
    cancel = afterDialogsClose(async () => {
      if (active()) await focusGrid();
    });
  };
}
