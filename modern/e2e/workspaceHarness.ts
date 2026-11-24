import { test, expect, type Page } from "@playwright/test";
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { createInterface } from "node:readline";
import { resolve } from "node:path";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";

export const python = resolve(process.platform === "win32" ? "../.venv/Scripts/python.exe" : "../.venv/bin/python");

// Only the Tauri transport is replaced. Every analysis command runs in real Python.
export let child: ChildProcessWithoutNullStreams;
export let directory: string;
let measurementDelay = 0;
export let systemClipboard = "";
let clipboardUnavailable = false;
export let frontendRequests: string[] = [];
export let frontendCalls: { method: string; params: Record<string, any> }[] = [];
export let nativeDialogResults: (string | null)[] = [];
let backend: ReturnType<typeof createBackend>;
export let requestTimings: { method: string; start: number; end: number }[] = [];
export function call(method: string, params: Record<string, unknown> = {}, session?: string) {
  return backend.call(method, params, session);
}
export function createBackend() {
  const pending = new Map<string, { resolve: (value: any) => void; reject: (error: Error) => void }>();
  let sequence = 0;
  const process = spawn(python, ["-m", "modern.backend"], {
    cwd: resolve(".."),
    env: { ...globalThis.process.env, GESTIMATOR_AUTO_DATABASES: "0" },
  });
  createInterface({ input: process.stdout }).on("line", (line) => {
    const message = JSON.parse(line);
    if (message.event) return;
    pending.get(message.id)?.resolve(message);
    pending.delete(message.id);
  });
  process.stderr.on("data", (data) => console.error(String(data)));
  process.on("close", () => {
    for (const request of pending.values()) request.reject(new Error("Backend closed"));
    pending.clear();
  });
  return {
    child: process,
    call(method: string, params: Record<string, unknown> = {}, session?: string) {
      const id = String(++sequence);
      return new Promise<any>((resolve, reject) => {
        pending.set(id, { resolve, reject });
        process.stdin.write(JSON.stringify({ id, method, params, session }) + "\n");
      });
    },
  };
}
export function startBackend() {
  backend = createBackend();
  child = backend.child;
}
export async function connectDesktop(page: Page, transport = call) {
  await page.exposeBinding("backendTransport", async (_source, request) => {
    frontendCalls.push(request);
    const timing = { method: request.method, start: performance.now(), end: 0 };
    requestTimings.push(timing);
    try {
      return await transportCall(request);
    } finally {
      timing.end = performance.now();
    }
  });
  async function transportCall(request: any) {
    frontendRequests.push(request.method + (request.params?.source ? ":library" : ""));
    if (request.method === "measurement.state" && measurementDelay)
      await new Promise((resolve) => setTimeout(resolve, measurementDelay));
    return transport(request.method, request.params, request.session);
  }
  await page.exposeBinding("nativeDialogTransport", () => nativeDialogResults.shift() ?? null);
  await page.exposeBinding("clipboardTransport", (_source, method, text) => {
    if (clipboardUnavailable) throw new Error("Clipboard unavailable");
    if (method === "write_text") systemClipboard = text;
    return systemClipboard;
  });
  await page.addInitScript(() => {
    // The MCP server is off by default (Program Settings). Most scenarios use it, so it is
    // enabled here unless a test asks for the shipped default (window.name "mcp-default").
    if (window.name !== "mcp-default" && !localStorage.getItem("gestimator.program-settings.v1"))
      localStorage.setItem(
        "gestimator.program-settings.v1",
        JSON.stringify({ version: 1, settings: { mcp_enabled: true } }),
      );
    (window as any).isTauri = true;
    let callbackId = 0;
    (window as any).__TAURI_EVENT_PLUGIN_INTERNALS__ = {
      unregisterListener: () => {},
    };
    (window as any).__TAURI_INTERNALS__ = {
      metadata: { currentWindow: { label: "main" }, currentWebview: { label: "main" } },
      transformCallback: (callback: (event: any) => void) => {
        ((window as any).tauriCallbacks ||= {})[++callbackId] = callback;
        return callbackId;
      },
      invoke: (method: string, args: any) => {
        if (method === "desktop_font")
          return (window as any).startupFontGate || Promise.resolve({ family: "Iosevka", size: "11pt" });
        if (method === "take_project_open_requests")
          return Promise.resolve((window as any).osOpenRequests?.splice(0) || []);
        if (method === "plugin:event|listen") {
          ((window as any).tauriListeners ||= {})[args.event] = args.handler;
          return Promise.resolve(1);
        }
        if (method.startsWith("plugin:event|")) return Promise.resolve(1);
        if (method === "backend_request")
          return (window as any).backendTransport(args.request).then((response: any) => {
            if (args.request.method === "project.open" && response.result)
              (window as any).openedProjectPath = args.request.params.path;
            return response;
          });
        if (method.startsWith("plugin:clipboard-manager|"))
          return (window as any).clipboardTransport(method.split("|")[1], args?.text);
        if (method === "read_clipboard_text" || method === "write_clipboard_text")
          return (window as any).clipboardTransport(
            method === "read_clipboard_text" ? "read_text" : "write_text",
            args?.text,
          );
        if (method.startsWith("plugin:dialog|")) return (window as any).nativeDialogTransport();
        if (method.startsWith("plugin:window|")) {
          ((window as any).windowCommands ||= []).push(method);
          if (method === "plugin:window|show")
            (window as any).startupAtShow = {
              theme: document.documentElement.dataset.theme,
              family: getComputedStyle(document.documentElement).fontFamily,
              size: getComputedStyle(document.documentElement).fontSize,
              fonts: document.fonts.status,
              landing: !!document.querySelector(".project-landing .landing-action"),
              ribbonSized: !!document.querySelector('.ribbon-action[style*="--ribbon-button-width"]'),
            };
          return Promise.resolve();
        }
        throw new Error("Unexpected desktop command: " + method);
      },
    };
  });
  await page.goto("/");
  await expect(page.getByText("Calculation engine connected")).toBeVisible();
  await expect.poll(() => page.evaluate(() => (window as any).windowCommands || [])).toContain("plugin:window|show");
  // The app starts on the landing page (Schedule); most scenarios begin in the scratch analysis.
  await page.locator("#view-analysis").click();
}
/** Install the real Python bridge and a fresh workspace for each test in a spec. */
export function useWorkspaceHarness() {
  test.beforeEach(async ({ page }) => {
    directory = await mkdtemp(resolve(tmpdir(), "gestimator-ui-"));
    measurementDelay = 0;
    systemClipboard = "";
    clipboardUnavailable = false;
    frontendRequests = [];
    frontendCalls = [];
    nativeDialogResults = [];
    startBackend();
    await connectDesktop(page);
  });
  test.afterEach(async () => {
    child.stdin.end();
    await new Promise<void>((resolve) => child.once("close", () => resolve()));
    await rm(directory, { recursive: true, force: true });
  });
}

export const desktopControls = {
  setClipboard(text: string) {
    systemClipboard = text;
  },
  failClipboard() {
    clipboardUnavailable = true;
  },
  delayMeasurements(ms: number) {
    measurementDelay = ms;
  },
  resetCalls() {
    frontendCalls = [];
  },
};

/** Hold one backend request so a test can drive input before its response. */
export async function holdNextRequest(page: Page, method: string) {
  await page.evaluate((heldMethod) => {
    const bridge = window as Window & {
      backendTransport: (request: { method: string }) => Promise<unknown>;
      resumeHeldRequest?: () => void;
    };
    const send = bridge.backendTransport;
    bridge.backendTransport = async (request) => {
      if (request.method === heldMethod) {
        bridge.backendTransport = send;
        await new Promise<void>((resolve) => (bridge.resumeHeldRequest = resolve));
      }
      return send(request);
    };
  }, method);
  return () =>
    page.evaluate(() => {
      const resume = Reflect.get(window, "resumeHeldRequest");
      Reflect.deleteProperty(window, "resumeHeldRequest");
      resume();
    });
}

export async function openFixture(page: Page, path: string) {
  const hasRecent = await page.evaluate(
    () => JSON.parse(localStorage.getItem("gestimator.recent-projects") || "[]").length > 0,
  );
  if (!hasRecent) nativeDialogResults.push(path);
  await page.locator(".titlebar").getByRole("button", { name: "Open project", exact: true }).click();
  if (hasRecent) {
    const dialog = page.getByRole("dialog", { name: "Open project", exact: true });
    await dialog.getByLabel("Project file").fill(path);
    await dialog.getByRole("button", { name: "Open project", exact: true }).click();
    await expect(dialog).not.toBeVisible();
  }
  await expect.poll(() => page.evaluate(() => (window as any).openedProjectPath)).toBe(path);
}
export async function applyRecordsIfDirty(page: Page) {
  const apply = page.locator(".draft-headerbar").getByRole("button", { name: "Apply records", exact: true });
  if (await apply.isVisible()) {
    await expect(page.locator(".measurement-record-grid .project-grid")).toHaveAttribute("aria-busy", "false");
    if ((await call("state")).result.measurement_draft?.dirty) {
      await apply.click();
      await expect(page.getByRole("grid", { name: "Measurements", exact: true })).toBeVisible();
      await openMeasurementEntry(page);
    }
  }
}
export async function finishMeasurementEntry(page: Page) {
  const discard = page.getByRole("button", { name: "Discard records", exact: true });
  if (await discard.isVisible()) await discard.click();
}
export async function openMeasurementEntry(page: Page) {
  if (await page.locator(".measurement-record-grid").isVisible()) return;
  if ((await page.locator("#view-measurement").getAttribute("aria-selected")) !== "true") return;
  const list = page.getByRole("grid", { name: "Measurements", exact: true });
  const selected = list.locator('.tabulator-row.tabulator-selected[data-kind="Resource"]');
  const row = (await selected.count()) ? selected.first() : list.locator('.tabulator-row[data-kind="Resource"]').last();
  await row.locator('[tabulator-field="description"]').dblclick();
  await expect(page.locator(".measurement-record-grid")).toBeVisible();
}
export async function pasteDocument(page: Page, selector: string, data: string) {
  await page.locator(selector).evaluate((table, text) => {
    const clipboardData = new DataTransfer();
    clipboardData.setData("text/plain", text);
    table.dispatchEvent(new ClipboardEvent("paste", { bubbles: true, cancelable: true, clipboardData }));
  }, data);
}
export async function openDatabaseManager(page: Page) {
  await applyRecordsIfDirty(page);
  await page.locator("#view-databases").click();
  await page.locator(".ribbon").getByRole("button", { name: "Attach database…", exact: true }).click();
  return page.getByRole("dialog", { name: "Attach resource / schedule library", exact: true });
}
export async function attachDatabase(page: Page, path: string, returnView = "schedule") {
  const manager = await openDatabaseManager(page);
  await manager.getByLabel("Library project", { exact: true }).fill(path);
  await manager.getByRole("button", { name: "Attach library", exact: true }).click();
  await expect(manager.locator(".attached-database").first()).toBeVisible();
  await expect(manager).toBeVisible();
  await manager.getByRole("button", { name: "Close database manager", exact: true }).click();
  await expect(manager).not.toBeVisible();
  await applyRecordsIfDirty(page);
  await page.locator("#view-" + returnView).click();
}

export async function refinementFixture(page: Page) {
  const { execFileSync } = await import("node:child_process");
  const path = resolve(directory, "refinements.eproj");
  execFileSync(python, ["-m", "modern.e2e.create_fixture", path], { cwd: resolve("..") });
  execFileSync(
    python,
    [
      "-c",
      "import sys;from estimator.data.schedule import ScheduleDatabase,ScheduleItemModel,ResourceItemModel;from estimator.undo import Stack;d=ScheduleDatabase(Stack());d.open_database(sys.argv[1]);d.insert_item_atomic(ScheduleItemModel('B','Masonry','m2',rate=5,qty=1,category='Other'));d.insert_schedule_category_atomic('Empty');d.insert_resource(ResourceItemModel('L','Worker','day',5,category='Labour'));d.close_database()",
      path,
    ],
    { cwd: resolve("..") },
  );
  await openFixture(page, path);
  await applyRecordsIfDirty(page);
  await page.locator("#view-schedule").click();
  return path;
}
