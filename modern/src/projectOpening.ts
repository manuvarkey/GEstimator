import { invoke, isTauri } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { getCurrentWebview } from "@tauri-apps/api/webview";

/** Call only after reconnect. The callback must settle after Save/Discard/Cancel,
 * not merely after displaying the unsaved dialog. */
export async function installProjectOpening(
  openGuarded: (path: string) => Promise<void>,
  reportError: (message: string) => void,
): Promise<() => void> {
  if (!isTauri()) return () => {};
  let stopped = false;
  let chain = Promise.resolve();
  const enqueue = (paths: string[]) => {
    chain = chain.then(async () => {
      for (const path of paths) {
        if (stopped) return;
        if (!/\.eproj$/i.test(path)) {
          reportError(`Not a GEstimator project: ${path}`);
          continue;
        }
        try { await openGuarded(path); }
        catch (error) { reportError(String(error)); }
      }
    });
  };
  const drain = async () => {
    try { enqueue(await invoke<string[]>("take_project_open_requests")); }
    catch (error) { reportError(String(error)); }
  };
  const unlisten = await listen("project-open-available", () => { void drain(); });
  let undrop: (() => void) | undefined;
  try {
    undrop = await getCurrentWebview().onDragDropEvent(event => {
      if (event.payload.type === "drop") enqueue(event.payload.paths);
    });
    await drain();
  } catch (error) { unlisten(); undrop?.(); throw error; }
  return () => { stopped = true; unlisten(); undrop?.(); };
}
