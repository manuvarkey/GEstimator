import { onBeforeUnmount, watch, type Ref } from "vue";
import { programSettings } from "./programSettings";

export const liveSearchDelay = 300;

/**
 * Search while typing when the "Search as you type" program setting is on.
 *
 * `searched` returns the query the view last loaded, so typing back to it, or a
 * load the view ran itself, does not search again. `search` may return false
 * when the view is busy; the search is then retried once the view is free.
 */
export function useLiveSearch(query: Ref<string>, searched: () => string, search: () => Promise<boolean | void>) {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const cancel = () => { if (timer !== undefined) clearTimeout(timer); timer = undefined; };
  const schedule = () => {
    cancel();
    timer = setTimeout(async () => {
      timer = undefined;
      if (!programSettings.value?.live_search || query.value === searched()) return;
      if (await search() === false) schedule();
    }, liveSearchDelay);
  };
  watch(query, () => { if (programSettings.value?.live_search) schedule(); });
  onBeforeUnmount(cancel);
  // A submitted search runs at once; drop the pending one.
  return { cancel };
}
