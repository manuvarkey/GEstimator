import { ref } from "vue";

/** Transient feedback (copy, paste, import results) shown in the status bar, then cleared. */
export const statusNotice = ref("");
let timer: ReturnType<typeof setTimeout> | undefined;

export function notify(message: string, timeout = 5000) {
  if (timer) clearTimeout(timer);
  statusNotice.value = message;
  timer = setTimeout(() => { statusNotice.value = ""; timer = undefined; }, timeout);
}
