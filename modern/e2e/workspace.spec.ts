import { test, expect, type Page } from "@playwright/test";
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { createInterface } from "node:readline";
import { resolve } from "node:path";
import { mkdtemp, readFile, rm, copyFile, rename } from "node:fs/promises";
import { tmpdir } from "node:os";

const python = resolve(
  process.platform === "win32"
    ? "../.venv/Scripts/python.exe"
    : "../.venv/bin/python",
);

// Only the Tauri transport is replaced. Every analysis command runs in real Python.
let child: ChildProcessWithoutNullStreams;
let directory: string;
let measurementDelay = 0;
let systemClipboard = "";
let clipboardUnavailable = false;
let frontendRequests: string[] = [];
let frontendCalls: { method: string; params: Record<string, any> }[] = [];
let nativeDialogResults: (string | null)[] = [];
let backend: ReturnType<typeof createBackend>;
let requestTimings: { method: string; start: number; end: number }[] = [];
function call(method: string, params: Record<string, unknown> = {}, session?: string) {
  return backend.call(method, params, session);
}
function createBackend() {
  const pending = new Map<string, { resolve: (value: any) => void; reject: (error: Error) => void }>();
  let sequence = 0;
  const process = spawn(python, ["-m", "modern.backend"], {
    cwd: resolve(".."),
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
function startBackend() {
  backend = createBackend();
  child = backend.child;
}
async function connectDesktop(page: Page, transport = call) {
  await page.exposeBinding("backendTransport", async (_source, request) => {
    frontendCalls.push(request);
    const timing = { method: request.method, start: performance.now(), end: 0 };
    requestTimings.push(timing);
    try { return await transportCall(request); } finally { timing.end = performance.now(); }
  });
  async function transportCall(request: any) {
    frontendRequests.push(request.method + (request.params?.source ? ":library" : ""));
    if (request.method === "measurement.state" && measurementDelay)
      await new Promise(resolve => setTimeout(resolve, measurementDelay));
    return transport(request.method, request.params, request.session);
  }
  await page.exposeBinding("nativeDialogTransport", () => nativeDialogResults.shift() ?? null);
  await page.exposeBinding("clipboardTransport", (_source, method, text) => {
    if (clipboardUnavailable) throw new Error("Clipboard unavailable");
    if (method === "write_text") systemClipboard = text;
    return systemClipboard;
  });
  await page.addInitScript(() => {
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
        if (method === "take_project_open_requests") return Promise.resolve((window as any).osOpenRequests?.splice(0) || []);
        if (method === "plugin:event|listen") {
          ((window as any).tauriListeners ||= {})[args.event] = args.handler;
          return Promise.resolve(1);
        }
        if (method.startsWith("plugin:event|")) return Promise.resolve(1);
        if (method === "backend_request")
          return (window as any).backendTransport(args.request).then((response: any) => {
            if (args.request.method === "project.open" && response.result) (window as any).openedProjectPath = args.request.params.path;
            return response;
          });
        if (method.startsWith("plugin:clipboard-manager|"))
          return (window as any).clipboardTransport(method.split("|")[1], args?.text);
        if (method.startsWith("plugin:dialog|")) return (window as any).nativeDialogTransport();
        if (method.startsWith("plugin:window|")) {
          ((window as any).windowCommands ||= []).push(method);
          if (method === "plugin:window|show") (window as any).startupAtShow = {
            theme: document.documentElement.dataset.theme,
            family: getComputedStyle(document.documentElement).fontFamily,
            size: getComputedStyle(document.documentElement).fontSize,
            fonts: document.fonts.status,
            landing: !!document.querySelector('.project-landing .landing-action'),
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

async function openFixture(page: Page, path: string) {
  const hasRecent = await page.evaluate(() => JSON.parse(localStorage.getItem("gestimator.recent-projects") || "[]").length > 0);
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
async function applyRecordsIfDirty(page: Page) {
  const apply = page.locator(".draft-headerbar").getByRole("button", { name: "Apply records", exact: true });
  if (await apply.isVisible()) {
    await expect(page.locator(".measurement-record-grid .project-grid")).toHaveAttribute("aria-busy", "false");
    if ((await call('state')).result.measurement_draft?.dirty) {
      await apply.click();
      await expect(page.getByRole('grid', { name: 'Measurements', exact: true })).toBeVisible();
      await openMeasurementEntry(page);
    }
  }
}
async function finishMeasurementEntry(page: Page) {
  const discard = page.getByRole('button', { name: 'Discard records', exact: true });
  if (await discard.isVisible()) await discard.click();
}
async function openMeasurementEntry(page: Page) {
  if (await page.locator(".measurement-record-grid").isVisible()) return;
  if (await page.locator("#view-measurement").getAttribute("aria-selected") !== "true") return;
  const list = page.getByRole("grid", { name: "Measurements", exact: true });
  const selected = list.locator('.tabulator-row.tabulator-selected[data-kind="Resource"]');
  const row = await selected.count() ? selected.first() : list.locator('.tabulator-row[data-kind="Resource"]').last();
  await row.locator('[tabulator-field="description"]').dblclick();
  await expect(page.locator(".measurement-record-grid")).toBeVisible();
}
async function pasteDocument(page: Page, selector: string, data: string) {
  await page.locator(selector).evaluate((table, text) => {
    const clipboardData = new DataTransfer();
    clipboardData.setData("text/plain", text);
    table.dispatchEvent(new ClipboardEvent("paste", { bubbles: true, cancelable: true, clipboardData }));
  }, data);
}
async function openDatabaseManager(page: Page) {
  await applyRecordsIfDirty(page);
  await page.locator("#view-databases").click();
  await page.locator(".ribbon").getByRole("button", { name: "Attach database…", exact: true }).click();
  return page.getByRole("dialog", { name: "Attach resource / schedule library", exact: true });
}
async function attachDatabase(page: Page, path: string, returnView = "schedule") {
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

async function refinementFixture(page: Page) {
  const { execFileSync } = await import("node:child_process");
  const path = resolve(directory, "refinements.eproj");
  execFileSync(python, ["-m", "modern.e2e.create_fixture", path], { cwd: resolve("..") });
  execFileSync(python, ["-c", "import sys;from estimator.data.schedule import ScheduleDatabase,ScheduleItemModel,ResourceItemModel;from estimator.undo import Stack;d=ScheduleDatabase(Stack());d.open_database(sys.argv[1]);d.insert_item_atomic(ScheduleItemModel('B','Masonry','m2',rate=5,qty=1,category='Other'));d.insert_schedule_category_atomic('Empty');d.insert_resource(ResourceItemModel('L','Worker','day',5,category='Labour'));d.close_database()", path], { cwd: resolve("..") });
  await openFixture(page, path);
  await applyRecordsIfDirty(page);
  await page.locator("#view-schedule").click();
  return path;
}

test("compact contrast, category filters, expanded trees and client window controls", async ({ page }) => {
  await refinementFixture(page);
  const grid = page.locator(".project-view:visible .project-main-grid");
  await expect(grid.locator('.tabulator-col[tabulator-field="category"],.tabulator-col[tabulator-field="parent"]')).toHaveCount(0);
  await expect(grid.locator(".tabulator-data-tree-control")).toHaveCount(0);
  await expect(grid.locator('.tabulator-row[data-kind="Group"] [tabulator-field="description"]').first()).toHaveCSS("font-weight", "700");
  await page.getByRole("button", { name: "Switch to light theme", exact: true }).click();
  await expect(grid.locator('.tabulator-row [tabulator-field="code"]').filter({ hasText: /^A$/ })).toHaveCSS("color", "rgb(42, 42, 49)");
  expect(await grid.boundingBox()).not.toBeNull();
  expect((await grid.boundingBox())!.y).toBeLessThan(220);
  await page.getByRole("button", { name: "Filter categories", exact: true }).click();
  const categories = page.getByRole("group", { name: "Categories", exact: true });
  await categories.getByRole("checkbox", { name: "Other", exact: true }).check();
  await expect(grid.getByText("Foundation", { exact: true })).toHaveCount(0);
  await expect(grid.getByText("Masonry", { exact: true })).toBeVisible();
  await categories.getByRole("checkbox", { name: "Work", exact: true }).check();
  await expect(grid.getByText("Foundation", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Show all categories", exact: true }).click();
  await page.getByRole("button", { name: "Filter categories", exact: true }).click();
  await applyRecordsIfDirty(page);
  await page.locator("#view-resources").click();
  await expect(grid.locator('.tabulator-col[tabulator-field="category"]')).toHaveCount(0);
  await page.getByRole("button", { name: "Filter categories", exact: true }).click();
  await categories.getByRole("checkbox", { name: "Labour", exact: true }).check();
  await expect(grid.getByText("Material", { exact: true })).toHaveCount(0);
  await expect(grid.getByText("Worker", { exact: true })).toBeVisible();
  await categories.getByRole("checkbox", { name: "Materials", exact: true }).check();
  await expect(grid.getByText("Material", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Filter categories", exact: true }).click();
  const minor = page.locator('.ribbon-actions').filter({ has: page.getByRole("button", { name: "Copy", exact: true }) });
  expect((await minor.evaluate(element => getComputedStyle(element).gridTemplateRows)).split(" ")).toHaveLength(3);
  await expect(minor.locator('.ribbon-label').filter({ hasText: /^Copy$/ })).toBeVisible();
  // Resources stack Cut / Copy / Paste in one column (GTK clipboard order).
  const buttons = await minor.locator('.ribbon-action[aria-label="Cut"],.ribbon-action[aria-label="Copy"],.ribbon-action[aria-label="Paste"]').evaluateAll(elements => elements.map(element => element.getBoundingClientRect()));
  expect(new Set(buttons.map(button => Math.round(button.top))).size).toBe(3);
  expect(Math.max(...buttons.map(button => button.left)) - Math.min(...buttons.map(button => button.left))).toBeLessThan(1);
  const full = page.locator('.ribbon-action:visible').filter({ has: page.locator('.ribbon-label').filter({ hasText: /^Add from database$/ }) });
  expect((await full.boundingBox())!.width).toBeLessThan(80);
  expect(await full.locator(".ribbon-label").evaluate(element => element.scrollHeight <= element.clientHeight + 1)).toBe(true);
  await expect(page.locator(".titlebar-project")).toHaveAttribute("data-tauri-drag-region", "");
  for (const name of ["Minimize window", "Maximize or restore window", "Close window"]) await page.locator(".window-controls").getByRole("button", { name, exact: true }).click();
  expect(await page.evaluate(() => (window as any).windowCommands)).toEqual(expect.arrayContaining(["plugin:window|minimize", "plugin:window|toggle_maximize", "plugin:window|close"]));
  await page.screenshot({ path: "test-results/compact-light-categories.png", animations: "disabled" });
});

test("landing page starts, opens and reopens recent projects when none is open", async ({ page }) => {
  const landing = page.getByRole("region", { name: "Start an estimate" });
  // Analysis keeps its scratch workspace; project views show the landing page.
  await expect(landing).not.toBeVisible();
  await page.locator("#view-schedule").click();
  await expect(landing).toBeVisible();
  await expect(landing).toContainText("Projects you open or save appear here.");
  await expect(page.getByText("Open a project to use this editor.")).not.toBeVisible();
  const { execFileSync } = await import("node:child_process");
  const project = resolve(directory, "landing.eproj");
  execFileSync(python, ["-m", "modern.e2e.create_fixture", project], { cwd: resolve("..") });
  // Open… goes straight to the system picker.
  nativeDialogResults.push(project);
  await landing.getByRole("button", { name: /Open project/ }).click();
  await expect(landing).not.toBeVisible();
  await expect(page.locator(".project-view:visible .project-main-grid")).toContainText("Foundation");
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem("gestimator.recent-projects") || "[]"))).toContain(project);
  // A fresh session without an open project lists the recent project.
  child.stdin.end();
  await new Promise<void>((resolve) => child.once("close", () => resolve()));
  startBackend();
  await page.reload();
  await expect(page.getByText("Calculation engine connected")).toBeVisible();
  // Startup shows the landing page directly.
  const recent = landing.getByRole("list", { name: "Recent projects" });
  await expect(recent.getByRole("button", { name: /landing/ })).toBeVisible();
  await recent.getByRole("button", { name: /landing/ }).click();
  await expect(landing).not.toBeVisible();
  await expect(page.locator(".project-view:visible .project-main-grid .tabulator-row").first()).toBeVisible();
});

test("project tabs keep separate projects in a vertical rail", async ({ page }) => {
  const landing = page.getByRole("region", { name: "Start an estimate" });
  const rail = page.getByRole("navigation", { name: "Open projects" });
  const tabs = rail.getByRole("tab");
  const grid = page.locator(".project-view:visible .project-main-grid");
  const { execFileSync } = await import("node:child_process");
  const project = resolve(directory, "tabs.eproj");
  execFileSync(python, ["-m", "modern.e2e.create_fixture", project], { cwd: resolve("..") });
  await page.locator("#view-schedule").click();
  await expect(tabs).toHaveCount(1);
  nativeDialogResults.push(project);
  await landing.getByRole("button", { name: /Open project/ }).click();
  await expect(grid).toContainText("Foundation");
  // New project while a project is open: a second tab, the first stays open.
  await page.locator(".titlebar").getByRole("button", { name: "New project", exact: true }).click();
  await expect(tabs).toHaveCount(2);
  await expect(tabs.nth(1)).toHaveAttribute("aria-selected", "true");
  await expect(grid).toBeVisible();
  await expect(grid).not.toContainText("Foundation");
  await page.mouse.move(1, 1);
  await page.screenshot({ path: "test-results/project-tabs.png", animations: "disabled" });
  // Switching back restores the first project from its own session.
  await tabs.nth(0).click();
  await expect(tabs.nth(0)).toHaveAttribute("aria-selected", "true");
  await expect(grid).toContainText("Foundation");
  // Opening the already open project switches to its tab instead of duplicating it.
  await tabs.nth(1).click();
  await expect(grid).not.toContainText("Foundation");
  await page.locator(".titlebar").getByRole("button", { name: "Open project", exact: true }).click();
  const openDialog = page.getByRole("dialog", { name: /Open project/ });
  await openDialog.getByLabel("Project file").fill(project);
  await openDialog.getByLabel("Project file").press("Enter");
  await expect(tabs.nth(0)).toHaveAttribute("aria-selected", "true");
  await expect(tabs).toHaveCount(2);
  // The add tile opens an empty tab with the landing page; closing it keeps the others.
  await rail.getByRole("button", { name: "New project tab", exact: true }).click();
  await expect(tabs).toHaveCount(3);
  await expect(landing).toBeVisible();
  await tabs.nth(2).hover();
  await rail.getByRole("button", { name: "Close Empty tab", exact: true }).click();
  await expect(tabs).toHaveCount(2);
  await expect(grid).toBeVisible();
  // Ctrl+Tab cycles tabs; Ctrl+W closes a clean tab.
  const selected = await tabs.evaluateAll(items => items.findIndex(item => item.getAttribute("aria-selected") === "true"));
  await page.keyboard.press("Control+Tab");
  await expect(tabs.nth(1 - selected)).toHaveAttribute("aria-selected", "true");
  // Shortcuts wait until the remounted tab finished connecting.
  await expect(async () => {
    await page.keyboard.press("Control+o");
    await expect(page.getByRole("dialog", { name: /Open project/ })).toBeVisible({ timeout: 500 });
  }).toPass();
});

test("resources cut and paste moves them like GTK", async ({ page }) => {
  await refinementFixture(page);
  await page.locator("#view-resources").click();
  const grid = page.locator(".project-view:visible .project-main-grid");
  const ribbon = page.locator(".ribbon");
  const codes = () => grid.locator(".tabulator-row").evaluateAll(items => items.map(item => item.querySelector('[tabulator-field="code"]')?.textContent?.trim() || item.querySelector('[tabulator-field="description"]')?.textContent?.trim()));
  const code = (value: string) => grid.locator('[tabulator-field="code"]').filter({ hasText: new RegExp(`^${value}$`) });
  await code("R").click();
  await ribbon.getByRole("button", { name: "Cut", exact: true }).click();
  await expect.poll(() => { try { return JSON.parse(systemClipboard).cut; } catch { return null; } }).toEqual(["R"]);
  await code("L").click();
  await ribbon.getByRole("button", { name: "Paste", exact: true }).click();
  // Moved after the selected resource, into its category, keeping its code.
  await expect.poll(async () => { const list = await codes(); return list[list.indexOf("L") + 1]; }).toBe("R");
  // The reference is used once; the clipboard is cleared after the move.
  expect(systemClipboard).toBe("");
  await page.locator(".titlebar").getByRole("button", { name: "Undo", exact: true }).click();
  await expect.poll(async () => { const list = await codes(); return list[list.indexOf("L") + 1]; }).not.toBe("R");
});

test("landing page creates a new project", async ({ page }) => {
  const landing = page.getByRole("region", { name: "Start an estimate" });
  await page.locator("#view-measurement").click();
  await expect(landing).toBeVisible();
  await page.screenshot({ path: "test-results/project-landing.png", animations: "disabled" });
  await landing.getByRole("button", { name: /New project/ }).click();
  await expect(landing).not.toBeVisible();
  await expect(page.locator(".project-view:visible .project-main-grid")).toBeVisible();
});

test("numeric edits select the value, tax shows only entered decimals and clipboard feedback is transient", async ({ page }) => {
  await refinementFixture(page);
  const main = page.locator(".project-view:visible .project-main-grid");
  const row = (code: string) => main.locator('.tabulator-row').filter({ has: page.locator('[tabulator-field="code"]').filter({ hasText: new RegExp(`^${code}$`) }) });
  const active = main.locator('.tabulator-cell.tabulator-editing input,.tabulator-cell.tabulator-editing textarea');
  const selection = () => active.evaluate(el => { const input = el as HTMLInputElement; return [input.selectionStart, input.selectionEnd, input.value.length]; });
  await row("A").locator('[tabulator-field="rate"]').click();
  await page.keyboard.press("Enter");
  const [start, end, length] = await selection();
  expect([start, end]).toEqual([0, length]);
  expect(length).toBeGreaterThan(0);
  await page.keyboard.type("7");
  await page.keyboard.press("Enter");
  await expect(row("A").locator('[tabulator-field="rate"]')).toHaveText("7");
  await row("A").locator('[tabulator-field="description"]').dblclick();
  const [textStart, textEnd] = await selection();
  expect(textStart).toBe(textEnd);
  await page.keyboard.press("Escape");
  await applyRecordsIfDirty(page);
  await page.locator("#view-resources").click();
  await expect(row("L").locator('[tabulator-field="vat"]')).toHaveText("0");
  await row("L").locator('[tabulator-field="vat"]').dblclick();
  await active.fill("2.5");
  await active.press("Enter");
  await expect(row("L").locator('[tabulator-field="vat"]')).toHaveText("2.5");
  await row("L").locator('[tabulator-field="vat"]').dblclick();
  await active.fill("18");
  await active.press("Enter");
  await expect(row("L").locator('[tabulator-field="vat"]')).toHaveText("18");
  await row("L").locator('[tabulator-field="description"]').click();
  await page.locator(".ribbon").getByRole("button", { name: "Copy", exact: true }).click();
  const statusbar = page.locator(".statusbar");
  await expect(statusbar.locator(".status-notice")).toContainText("Rows copied");
  await expect(page.locator('.project-view:visible p[role="status"]')).toHaveCount(0);
  await expect(statusbar.locator(".status-notice")).toHaveCount(0, { timeout: 8000 });
});
test("cell navigation commits with Tab and Enter across schedule resources measurements and analysis", async ({ page }) => {
  await refinementFixture(page);
  const main = page.locator(".project-view:visible .project-main-grid");
  const row = (code: string) => main.locator('.tabulator-row').filter({ has: page.locator('[tabulator-field="code"]').filter({ hasText: new RegExp(`^${code}$`) }) });
  const active = (grid = main) => grid.locator('.tabulator-cell.tabulator-editing input,.tabulator-cell.tabulator-editing textarea');
  const field = async (name: string, grid = main) => { await expect(grid.locator(`.cell-focused[tabulator-field="${name}"] input,.cell-focused[tabulator-field="${name}"] textarea`)).toBeFocused(); };
  await row("A").locator('[tabulator-field="rate"]').click();
  await page.keyboard.press("Enter");
  await active().fill("2*3");
  await active().press("Tab");
  await field("qty");
  await expect(row("A").locator('[tabulator-field="rate"]')).toHaveText("6");
  await active().fill("2");
  await active().press("Tab");
  await field("remarks");
  await expect(row("A").locator('[tabulator-field="amount"]')).toHaveText("12.00");
  await active().fill("Accepted remark");
  await active().press("Shift+Tab");
  await field("qty");
  await active().press("Enter");
  await expect(row("B").locator('[tabulator-field="qty"] input')).toBeFocused();
  await active().fill("4");
  await active().press("Tab");
  await active().press("Escape");
  await row("A").locator('[tabulator-field="qty"]').click();
  await page.keyboard.press("Enter");
  await expect(row("A").locator('[tabulator-field="qty"] input')).toBeFocused();
  await active().press("Shift+Tab");
  await field("rate");
  await active().fill("1/0");
  await active().press("Tab");
  await field("rate");
  await expect(active()).toHaveValue("1/0");
  await active().fill("8");
  await active().press("Tab");
  await field("qty");
  await active().press("Escape");
  await applyRecordsIfDirty(page);
  await page.locator("#view-resources").click();
  await row("R").locator('[tabulator-field="rate"]').click();
  await page.keyboard.press("Enter");
  await active().fill("2*3");
  await active().press("Tab");
  await field("vat");
  await active().fill("5");
  await active().press("Shift+Tab");
  await field("rate");
  await active().press("Enter");
  await expect(row("L").locator('[tabulator-field="rate"] input')).toBeFocused();
  await active().press("Escape");
  await applyRecordsIfDirty(page);
  await page.locator("#view-measurement").click();
  await page.getByRole("button", { name: "Add measurement", exact: true }).click();
  const add = page.getByRole("dialog", { name: "Add item", exact: true });
  await add.getByLabel("Measurement template").selectOption("_1_NLBH");
  await add.getByLabel("Description / remarks").fill("Dimensions");
  await add.getByRole("button", { name: "Add item", exact: true }).click();
  await expect(add).not.toBeVisible();
  await openMeasurementEntry(page);
  for (let index = 0; index < 2; index++) await page.getByRole("button", { name: "Add record", exact: true }).click();
  const records = page.locator(".measurement-record-grid");
  await records.locator('.tabulator-row [tabulator-field="c1"]').first().click();
  await page.keyboard.press("Enter");
  await expect(active(records)).toHaveCount(0);
  await records.locator('.tabulator-row [tabulator-field="c2"]').first().click();
  await page.keyboard.press("Enter");
  await active(records).fill("2*3");
  await active(records).press("Tab");
  await field("c3", records);
  await active(records).fill("2+2");
  await active(records).press("Enter");
  await field("c3", records);
  await active(records).fill("2");
  await active(records).press("Shift+Tab");
  await field("c2", records);
  await active(records).press("Escape");
  await records.locator('.tabulator-row [tabulator-field="c2"]').first().click();
  await page.keyboard.press("Enter");
  await expect(active(records)).toHaveValue("2*3");
  await active(records).press("Shift+Tab");
  await field("c0", records);
  await active(records).fill("Record");
  await active(records).press("Shift+Enter");
  await active(records).pressSequentially("Second line");
  await active(records).press("Enter");
  await field("c0", records);
  await expect(records.locator('.tabulator-row [tabulator-field="c0"]').first()).toHaveText("Record\nSecond line");
  await active(records).press("Escape");
  await applyRecordsIfDirty(page);
  await page.locator("#view-schedule").click();
  await row("A").locator('[tabulator-field="description"]').click();
  await page.getByRole("button", { name: "Edit analysis", exact: true }).click();
  const analysis = page.getByRole("grid", { name: "Rate analysis table", exact: true });
  await analysis.locator('.tabulator-row[data-kind="Subtotal"] [tabulator-field="description"]').click();
  await page.getByRole("button", { name: "Round off", exact: true }).click();
  await analysis.locator('.tabulator-row[data-kind="Resource"] [tabulator-field="value"]').click();
  await page.keyboard.press("Enter");
  await active(analysis).fill("2*3");
  await active(analysis).press("Tab");
  await active(analysis).press("Escape");
  await analysis.locator('.tabulator-row[data-kind="Resource"] [tabulator-field="value"]').click();
  await page.locator(".inspector").getByLabel("Base rate", { exact: true }).fill("5");
  await page.locator(".inspector").getByLabel("Base rate", { exact: true }).press("Tab");
  await page.locator(".inspector").getByLabel("Tax %", { exact: true }).fill("10");
  await page.locator(".inspector").getByLabel("Tax %", { exact: true }).press("Tab");
  await expect(page.locator(".summary-value")).toContainText("33.00");
  await analysis.locator('.tabulator-row[data-kind="Resource"] [tabulator-field="value"]').click();
  await page.keyboard.press("Enter");
  await active(analysis).press("Enter");
  await expect(analysis.locator('.tabulator-row[data-kind="Round"] [tabulator-field="value"] input')).toBeFocused();
  await active(analysis).press("Escape");
  await analysis.locator('.tabulator-row[data-kind="Resource"] [tabulator-field="value"]').click();
  await page.keyboard.press("Enter");
  await expect(analysis.locator('.tabulator-row[data-kind="Resource"] [tabulator-field="value"] input')).toBeFocused();
  await active(analysis).press("Escape");
  await expect(analysis.locator(".tabulator-data-tree-control")).toHaveCount(0);
  await page.setViewportSize({ width: 1100, height: 1000 });
  await analysis.locator('.tabulator-row[data-kind="Resource"] [tabulator-field="value"]').click();
  await page.keyboard.press("Enter");
  const editorBounds = (await active(analysis).boundingBox())!;
  const fixedHeader = analysis.locator('.tabulator-col[tabulator-field="amount"]');
  await expect(fixedHeader).toHaveCSS("background-color", "rgb(59, 59, 69)");
  expect(editorBounds.x + editorBounds.width).toBeLessThanOrEqual((await fixedHeader.boundingBox())!.x + 1);
});

test("MCP write mode refreshes the UI and protects in-progress cell edits", async ({ page }) => {
  await page.clock.install();
  await page.reload();
  const path = await refinementFixture(page);
  const original = await readFile(path);
  const { createServer } = await import("node:net");
  const port = await new Promise<number>((resolve, reject) => {
    const server = createServer(); server.once("error", reject);
    server.listen(0, "127.0.0.1", () => { const port = (server.address() as { port: number }).port; server.close(error => error ? reject(error) : resolve(port)); });
  });
  await applyRecordsIfDirty(page);
  await page.locator("#view-mcp").click();
  await page.getByRole("button", { name: "Configure MCP server", exact: true }).click();
  const config = page.getByRole("dialog", { name: "Configure MCP server", exact: true });
  await config.getByLabel("Port", { exact: true }).fill(String(port));
  await config.getByLabel("Access mode", { exact: true }).selectOption({ label: "Read and write" });
  await config.getByRole("button", { name: "Save settings", exact: true }).click();
  await expect(config.getByText("MCP settings saved.", { exact: true })).toBeVisible();
  await config.getByRole("button", { name: "Close MCP settings", exact: true }).click();
  await page.getByRole("button", { name: "Start MCP server", exact: true }).click();
  await expect(page.getByRole("button", { name: "Stop MCP server", exact: true })).toBeEnabled();
  const connection = (await call("mcp.status")).result;
  async function agent(name: string, args: Record<string, unknown> = {}, write = false) {
    const revision = (await call("state")).result.revision;
    const response = await fetch(connection.url, { method: "POST", headers: { Authorization: "Bearer " + connection.token, "Content-Type": "application/json", Accept: "application/json, text/event-stream" }, body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/call", params: { name, arguments: { ...args, ...(write ? { if_revision: revision } : {}) } } }) });
    const value = (await response.json()).result;
    expect(value.isError).toBe(false);
    return value.structuredContent;
  }
  const item = (await agent("get_items", { kind: "schedule", codes: ["A"] })).data.items[0];
  await applyRecordsIfDirty(page);
  await page.locator("#view-schedule").click();
  await agent("upsert_items", { kind: "schedule", items: [{ code: item.code, description: "Edited by agent" }] }, true);
  await page.clock.runFor(1600);
  const grid = page.locator(".project-view:visible .project-main-grid");
  await expect(grid.getByText("Edited by agent", { exact: true })).toBeVisible();
  const qty = grid.locator('.tabulator-row').filter({ has: page.locator('[tabulator-field="code"]').filter({ hasText: /^A$/ }) }).locator('[tabulator-field="qty"]');
  await qty.click();
  await page.keyboard.press("Enter");
  await qty.locator("input").fill("13");
  await agent("upsert_items", { kind: "schedule", items: [{ code: item.code, description: "Agent changed another field" }] }, true);
  await page.clock.runFor(1700);
  await expect(qty.locator("input")).toHaveValue("13");
  await qty.locator("input").press("Tab");
  await expect(page.locator(".project-view:visible").getByRole("alert")).toContainText("Stale");
  await expect(qty.locator("input")).toHaveValue("13");
  await qty.locator("input").press("Tab");
  await expect(qty).toHaveText("13");
  await expect(grid.getByText("Agent changed another field", { exact: true })).toBeVisible();
  await grid.locator('.tabulator-editing textarea').press("Escape");
  await agent("edit_analysis", { code: "A", ops: [{ action: "edit", id: "r0:0", field: "value", value: "3" }] }, true);
  await page.clock.runFor(1700);
  await page.locator(".ribbon").getByRole("button", { name: "Edit analysis", exact: true }).click();
  await expect(page.getByRole("dialog", { name: /Unsaved analysis/ })).toHaveCount(0);
  await expect(page.locator(".summary-value")).toContainText("30.00");
  await agent("project", { action: "new", discard: true }, true);
  await page.clock.runFor(1700);
  await expect(page.locator('.analysis-heading h1')).toHaveText("Select a schedule item");
  await expect(page.getByRole("grid", { name: "Rate analysis table" }).locator(".tabulator-row")).toHaveCount(0);
  await applyRecordsIfDirty(page);
  await page.locator("#view-mcp").click();
  await page.getByRole("button", { name: "Stop MCP server", exact: true }).click();
  expect(await readFile(path)).toEqual(original);
});

test("database tab attaches multiple sources and editor dialogs add items and refresh selected rates", async ({ page }) => {
  const { execFileSync } = await import("node:child_process");
  const first = resolve(directory, "picker-first.eproj");
  const second = resolve(directory, "picker-second.eproj");
  for (const [file, rate] of [[first, "25"], [second, "30"]]) execFileSync(python, ["-m", "modern.e2e.create_fixture", file, rate], { cwd: resolve("..") });
  execFileSync(python, ["-c", "import sys;from decimal import Decimal;from estimator.data.schedule import ScheduleDatabase,ResourceItemModel;from estimator.undo import Stack;d=ScheduleDatabase(Stack());d.open_database(sys.argv[1]);d.insert_resource(ResourceItemModel('NEW-R','New database resource','kg',Decimal('7'),category='Other'));d.close_database()", second], { cwd: resolve("..") });
  const originals = [await readFile(first), await readFile(second)];
  await page.locator(".titlebar").getByRole("button", { name: "New project", exact: true }).click();
  await applyRecordsIfDirty(page);
  await page.locator("#view-databases").click();
  await page.locator(".ribbon").getByRole("button", { name: "Attach database…", exact: true }).click();
  const manager = page.getByRole("dialog", { name: "Attach resource / schedule library", exact: true });
  for (const [index, path] of [first, second].entries()) {
    await manager.getByLabel("Library project", { exact: true }).fill(path);
    await manager.getByRole("button", { name: "Attach library", exact: true }).click();
    await expect(manager.locator(".attached-database")).toHaveCount(index + 1);
    await expect(manager).toBeVisible();
  }
  await manager.getByRole("button", { name: "Close database manager", exact: true }).click();
  await expect(manager).not.toBeVisible();
  await expect(page.locator(".database-view")).toHaveCount(0);
  await expect(page.locator(".project-view:visible h1")).toHaveText("Schedule of quantities");
  await applyRecordsIfDirty(page);
  await page.locator("#view-schedule").click();
  const ribbon = page.locator(".ribbon");
  await expect(ribbon.getByLabel("Data source")).toHaveCount(0);
  await ribbon.getByRole("button", { name: "Add item from database", exact: true }).click();
  const picker = page.getByRole("dialog", { name: "Add item from database", exact: true });
  await expect(picker).toHaveCSS("opacity", "1");
  await page.screenshot({ path: "test-results/database-item-picker.png", animations: "disabled" });
  await picker.locator('[tabulator-field="description"]').filter({ hasText: "Foundation" }).click();
  await picker.getByRole("button", { name: "Add selected items", exact: true }).click();
  await expect(picker).not.toBeVisible();
  const grid = page.locator(".project-view:visible .project-main-grid");
  await expect(grid.locator('.tabulator-selected [tabulator-field="code"]')).toHaveText("A");
  await expect(grid.locator('.tabulator-row [tabulator-field="rate"]').last()).toHaveText("50");
  await expect(ribbon.getByRole("button", { name: "Refresh selected rates from database", exact: true })).toHaveCount(0);
  await applyRecordsIfDirty(page);
  await page.locator("#view-resources").click();
  await grid.locator('.tabulator-row [tabulator-field="code"]').filter({ hasText: /^R$/ }).click();
  await ribbon.getByRole("button", { name: "Refresh selected rates from database", exact: true }).click();
  const rates = page.getByRole("dialog", { name: "Refresh selected rates from database", exact: true });
  await rates.getByLabel("Database", { exact: true }).selectOption({ label: "picker-second" });
  await rates.getByRole("button", { name: "Preview rate changes", exact: true }).click();
  await expect(rates).toContainText("1 changed");
  await rates.getByRole("button", { name: "Apply database rates", exact: true }).click();
  await expect(rates).not.toBeVisible();
  await expect(grid.locator('.tabulator-row [tabulator-field="rate"]').last()).toHaveText("30");
  await page.locator(".titlebar").getByRole("button", { name: "Undo", exact: true }).click();
  await expect(grid.locator('.tabulator-row [tabulator-field="rate"]').last()).toHaveText("25");
  await ribbon.getByRole("button", { name: "Add resources from database", exact: true }).click();
  const resources = page.getByRole("dialog", { name: "Add resources from database", exact: true });
  await resources.getByLabel("Database", { exact: true }).selectOption({ index: 1 });
  await resources.locator('[tabulator-field="code"]').filter({ hasText: /^NEW-R$/ }).click();
  await resources.getByRole("button", { name: "Add selected items", exact: true }).click();
  await expect(resources).not.toBeVisible();
  await expect(grid.locator('.tabulator-selected [tabulator-field="code"]')).toHaveText("NEW-R");
  expect(await readFile(first)).toEqual(originals[0]);
  expect(await readFile(second)).toEqual(originals[1]);
});

for (const kind of ["schedule", "resources"] as const) test(`database ${kind} picker filters categories, selects rows by dragging and imports the double-clicked item`, async ({ page }) => {
  const { execFileSync } = await import("node:child_process");
  const source = await refinementFixture(page);
  const original = await readFile(source);
  const second = resolve(directory, "another-library.eproj");
  execFileSync(python, ["-m", "modern.e2e.create_fixture", second, "22"], { cwd: resolve("..") });
  await page.locator(".titlebar").getByRole("button", { name: "New project", exact: true }).click();
  await attachDatabase(page, source, kind);
  await attachDatabase(page, second, kind);
  const title = kind === "schedule" ? "Add item from database" : "Add resources from database";
  const firstCategory = kind === "schedule" ? "Work" : "Materials";
  const secondCategory = kind === "schedule" ? "Other" : "Labour";
  const firstCode = kind === "schedule" ? "A" : "R";
  const secondCode = kind === "schedule" ? "B" : "L";
  const description = kind === "schedule" ? "Foundation" : "Material";
  const ribbon = page.locator(".ribbon");
  const picker = page.getByRole("dialog", { name: title, exact: true });
  const grid = picker.locator(".database-picker-grid");
  const code = (value: string) => grid.locator('.tabulator-row [tabulator-field="code"]').filter({ hasText: new RegExp(`^${value}$`) });
  const categories = page.getByRole("group", { name: "Categories", exact: true });
  await ribbon.getByRole("button", { name: title, exact: true }).click();
  await expect(code(firstCode)).toBeVisible();
  await picker.getByRole("button", { name: "Filter categories", exact: true }).click();
  await categories.getByRole("checkbox", { name: secondCategory, exact: true }).check();
  await expect(code(firstCode)).toHaveCount(0);
  await expect(code(secondCode)).toBeVisible();
  await categories.getByRole("checkbox", { name: firstCategory, exact: true }).check();
  await expect(code(firstCode)).toBeVisible();
  await picker.getByRole("button", { name: "Filter categories", exact: true }).click();
  await picker.getByLabel("Find database items").fill(description);
  await picker.getByRole("button", { name: "Search", exact: true }).click();
  await expect(code(secondCode)).toHaveCount(0);
  await code(firstCode).click();
  await expect(picker.locator(".pagination")).toContainText("1 selected");
  await picker.getByLabel("Database", { exact: true }).selectOption({ index: 1 });
  await expect(picker.locator(".pagination")).toContainText("0 selected");
  await expect(picker.getByRole("button", { name: "Filter categories", exact: true })).toHaveText("All categories");
  await expect(grid.locator('.tabulator-row [tabulator-field="rate"]').last()).toHaveText(kind === "schedule" ? "44" : "22");
  await picker.getByRole("button", { name: "Filter categories", exact: true }).click();
  await expect(categories.getByRole("checkbox", { name: secondCategory, exact: true })).toHaveCount(0);
  await picker.getByRole("button", { name: "Filter categories", exact: true }).click();
  await picker.getByLabel("Find database items").fill("");
  await picker.getByLabel("Database", { exact: true }).selectOption({ index: 0 });
  await expect(code(secondCode)).toBeVisible();
  await expect(code(firstCode)).toHaveCSS("user-select", "none");
  const start = (await code(firstCode).boundingBox())!;
  const end = (await code(secondCode).boundingBox())!;
  await page.mouse.move(start.x + 25, start.y + start.height / 2);
  await page.mouse.down();
  await page.mouse.move(end.x + 80, end.y + end.height / 2, { steps: 12 });
  await page.mouse.up();
  await expect(picker.locator(".pagination")).toContainText("2 selected");
  await expect(grid.locator('.tabulator-selected[data-kind="Group"]')).toHaveCount(0);
  await expect(grid.locator(".cell-range-selected,.cell-focused")).toHaveCount(0);
  expect(await page.evaluate(() => window.getSelection()?.toString())).toBe("");
  // Selected rows are highlighted without hover (the shell row surface must not hide them).
  await page.mouse.move(1, 1);
  const background = (row: string) => grid.locator(row).first().evaluate(element => getComputedStyle(element).backgroundColor);
  expect(await background('.tabulator-row.tabulator-selected')).not.toBe(await background('.tabulator-row:not(.tabulator-selected)'));
  await page.screenshot({ path: `test-results/database-${kind}-row-selection.png`, animations: "disabled" });
  await picker.getByRole("button", { name: "Add selected items", exact: true }).click();
  await expect(picker).not.toBeVisible();
  const project = page.locator(".project-view:visible .project-main-grid");
  await expect(project.locator('.tabulator-row [tabulator-field="code"]').filter({ hasText: new RegExp(`^(${firstCode}|${secondCode})$`) })).toHaveCount(2);
  await page.locator(".titlebar").getByRole("button", { name: "Undo", exact: true }).click();
  await expect(project.locator('.tabulator-row [tabulator-field="code"]').filter({ hasText: new RegExp(`^(${firstCode}|${secondCode})$`) })).toHaveCount(0);
  await ribbon.getByRole("button", { name: title, exact: true }).click();
  await code(firstCode).click();
  // Keep another item selected: activation must import the clicked row, not the selection.
  await code(secondCode).dblclick({ modifiers: ["Control"] });
  await expect(picker).not.toBeVisible();
  await expect(project.locator('.tabulator-row [tabulator-field="code"]').filter({ hasText: new RegExp(`^${secondCode}$`) })).toBeVisible();
  await expect(project.locator('.tabulator-row [tabulator-field="code"]').filter({ hasText: new RegExp(`^${firstCode}$`) })).toHaveCount(0);
  expect(await readFile(source)).toEqual(original);
});

test("database pickers retain their table, source, filters, selection, page and scroll between editor switches", async ({ page }) => {
  const { execFileSync } = await import("node:child_process");
  const source = resolve(directory, "persistent.eproj");
  execFileSync(python, ["-m", "modern.e2e.create_fixture", source], { cwd: resolve("..") });
  execFileSync(python, ["-c", "import sys;from estimator.data.schedule import ScheduleDatabase,ScheduleItemModel,ResourceItemModel;from estimator.undo import Stack;d=ScheduleDatabase(Stack());d.open_database(sys.argv[1]);[(d.insert_item_atomic(ScheduleItemModel('X'+str(i),'Extra schedule '+str(i),'m',rate=1,qty=1,category='Work')),d.insert_resource(ResourceItemModel('Z'+str(i),'Extra resource '+str(i),'kg',1,category='Materials'))) for i in range(140)];d.close_database()", source], { cwd: resolve("..") });
  await page.locator(".titlebar").getByRole("button", { name: "New project", exact: true }).click();
  await attachDatabase(page, source);
  for (const kind of ["schedule", "resources"] as const) {
    await applyRecordsIfDirty(page);
    await page.locator("#view-" + kind).click();
    const title = kind === "schedule" ? "Add item from database" : "Add resources from database";
    const open = () => page.locator(".ribbon").getByRole("button", { name: title, exact: true }).click();
    const picker = page.getByRole("dialog", { name: title, exact: true });
    await open();
    await picker.getByLabel("Find database items").fill("Extra");
    await picker.getByRole("button", { name: "Search", exact: true }).click();
    await picker.getByRole("button", { name: "Filter categories", exact: true }).click();
    await page.getByRole("group", { name: "Categories", exact: true }).getByRole("checkbox", { name: kind === "schedule" ? "Work" : "Materials", exact: true }).check();
    await expect(picker.locator(".pagination")).toContainText("140 items");
    await picker.getByRole("button", { name: "Filter categories", exact: true }).click();
    await picker.getByRole("button", { name: "Next", exact: true }).click();
    await expect(picker.locator(".pagination")).toContainText("Page 2");
    const table = picker.locator(".project-grid");
    await table.locator('.tabulator-row[data-kind="Resource"] [tabulator-field="code"]').first().click();
    await expect(picker.locator(".pagination")).toContainText("1 selected");
    const scroll = await table.locator(".tabulator-tableholder").evaluate(element => { element.scrollTop = 300; return element.scrollTop; });
    expect(scroll).toBeGreaterThan(100);
    await table.evaluate(element => (window as any).cachedPicker = element);
    const reads = frontendRequests.filter(method => method === kind + ".editor.state:library").length;
    await picker.getByRole("button", { name: "Cancel", exact: true }).click();
    await expect(picker).not.toBeVisible();
    await expect(page.getByRole("button", { name: "New project", exact: true })).toBeEnabled();
    await applyRecordsIfDirty(page);
    await page.locator("#view-analysis").click();
    await applyRecordsIfDirty(page);
    await page.locator("#view-" + kind).click();
    await open();
    await expect(picker.getByLabel("Find database items")).toHaveValue("Extra");
    await expect(picker.getByRole("button", { name: "Filter categories", exact: true })).toHaveText("1 categories");
    await expect(picker.locator(".pagination")).toContainText("Page 2 · 1 selected");
    expect(await table.evaluate(element => element === (window as any).cachedPicker)).toBe(true);
    expect(await table.locator(".tabulator-tableholder").evaluate(element => element.scrollTop)).toBeCloseTo(scroll, 0);
    expect(frontendRequests.filter(method => method === kind + ".editor.state:library")).toHaveLength(reads);
    if (kind === "resources") {
      await picker.getByRole("button", { name: "Add selected items", exact: true }).click();
      await expect(picker).not.toBeVisible();
      await page.locator(".ribbon").getByRole("button", { name: "Refresh selected rates from database", exact: true }).click();
      await page.getByRole("dialog", { name: "Refresh selected rates from database", exact: true }).getByRole("button", { name: "Cancel", exact: true }).click();
      await open();
      await expect(picker.locator(".pagination")).toContainText("Page 2 · 1 selected");
      expect(await table.locator(".tabulator-tableholder").evaluate(element => element.scrollTop)).toBeCloseTo(scroll, 0);
      expect(frontendRequests.filter(method => method === kind + ".editor.state:library")).toHaveLength(reads);
    }
    await page.keyboard.press("Escape");
    await expect(picker).not.toBeVisible();
  }
});

test("project analysis rules preview multiple items, apply once, undo and return from analysis safely", async ({ page }) => {
  const { execFileSync } = await import("node:child_process");
  const path = resolve(directory, "analysis-rules.eproj");
  execFileSync(python, ["-m", "modern.e2e.create_fixture", path], { cwd: resolve("..") });
  execFileSync(python, ["-c", "import sys,copy;from decimal import Decimal;from estimator.data.schedule import ScheduleDatabase;from estimator.undo import Stack;d=ScheduleDatabase(Stack());d.open_database(sys.argv[1]);a=d.get_item('A',modify_res_code=False);a.add_ana_weight('OH',Decimal('0.1'));a.add_ana_sum('TOTAL WITH OH');a.evaluate_results();a.update_rate();d.insert_item_atomic(a,update=True);b=copy.deepcopy(a);b.code='B';b.description='Second work';d.insert_item_atomic(b);d.close_database()", path], { cwd: resolve("..") });
  const original = await readFile(path);
  await openFixture(page, path);
  await applyRecordsIfDirty(page);
  await page.locator("#view-schedule").click();
  const ribbon = page.locator(".ribbon"), grid = page.locator(".project-view:visible .project-main-grid");
  for (const name of ["Duplicate", "Add subitem"]) await expect(ribbon.getByRole("button", { name, exact: true })).not.toHaveClass(/ribbon-icon/);
  await grid.locator('.tabulator-row [tabulator-field="code"]').filter({ hasText: /^A$/ }).click();
  await grid.locator('.tabulator-row [tabulator-field="code"]').filter({ hasText: /^B$/ }).click({ modifiers: ["Control"] });
  await ribbon.getByRole("button", { name: "Bulk edit analysis…", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Bulk edit analysis", exact: true });
  await expect(dialog.getByLabel("Schedule scope")).toHaveValue("selected");
  await dialog.getByLabel("Rule 1 condition 1 value", { exact: true }).fill("OH");
  await dialog.getByLabel("Rule 1 new value", { exact: true }).fill("1/0");
  await dialog.getByRole("button", { name: "Preview changes", exact: true }).click();
  await expect(dialog.getByRole("alert")).toContainText("Invalid numeric");
  await dialog.getByLabel("Rule 1 new value", { exact: true }).fill("0.2");
  await dialog.getByRole("button", { name: "Add rule", exact: true }).click();
  await dialog.getByLabel("Rule 2 action", { exact: true }).selectOption("replace_text");
  await dialog.getByLabel("Rule 2 field to change", { exact: true }).selectOption("description");
  await dialog.getByLabel("Rule 2 find text", { exact: true }).fill("OH");
  await dialog.getByLabel("Rule 2 new value", { exact: true }).fill("Overhead");
  await dialog.getByRole("button", { name: "Preview changes", exact: true }).click();
  await expect(dialog.locator(".batch-preview")).toContainText("2 of 2 scoped analyses change");
  await expect(dialog.locator(".batch-preview table").first().locator("tbody tr").first().locator("td").nth(2)).toHaveText(/^24(?:\.00)?$/);
  await expect(grid.locator('.tabulator-row [tabulator-field="rate"]').filter({ hasText: /^22(?:\.00)?$/ })).toHaveCount(2);
  await dialog.getByLabel("Rule 1 new value", { exact: true }).fill("0.3");
  await expect(dialog.getByRole("button", { name: "Apply rules", exact: true })).toBeDisabled();
  await dialog.getByLabel("Rule 1 new value", { exact: true }).fill("0.2");
  await dialog.getByRole("button", { name: "Preview changes", exact: true }).click();
  await expect(dialog.getByRole("button", { name: "Apply rules", exact: true })).toBeEnabled();
  await page.screenshot({ path: "test-results/project-analysis-rules.png", animations: "disabled" });
  await dialog.getByRole("button", { name: "Apply rules", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  await expect(grid.locator('.tabulator-row [tabulator-field="rate"]').filter({ hasText: /^24(?:\.00)?$/ })).toHaveCount(2);
  await page.locator(".titlebar").getByRole("button", { name: "Undo", exact: true }).click();
  await expect(grid.locator('.tabulator-row [tabulator-field="rate"]').filter({ hasText: /^22(?:\.00)?$/ })).toHaveCount(2);
  await grid.locator('.tabulator-row [tabulator-field="code"]').filter({ hasText: /^A$/ }).click();
  await ribbon.getByRole("button", { name: "Edit analysis", exact: true }).click();
  await expect(ribbon.getByRole("button", { name: "Bulk edit analysis…", exact: true })).not.toBeVisible();
  await expect(ribbon.getByRole("button", { name: "Duplicate", exact: true })).not.toHaveClass(/ribbon-icon/);
  await page.getByRole('button', { name: 'Discard analysis', exact: true }).click();
  await expect(grid).toBeVisible();
  await ribbon.getByRole("button", { name: "Bulk edit analysis…", exact: true }).click();
  await expect(dialog.getByLabel("Schedule scope")).toHaveValue("selected");
  await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
  await grid.locator('.tabulator-row [tabulator-field="code"]').filter({ hasText: /^A$/ }).click();
  await ribbon.getByRole("button", { name: "Edit analysis", exact: true }).click();
  await page.locator('.analysis-table .tabulator-row[data-kind="Weight"] [tabulator-field="value"]').dblclick();
  await page.locator('.analysis-table [tabulator-field="value"] input').fill("0.3");
  await page.locator('.analysis-table [tabulator-field="value"] input').press("Enter");
  await expect(page.locator(".draft-badge")).toContainText("Unsaved changes");
  await applyRecordsIfDirty(page);
  await page.keyboard.press("Alt+ArrowLeft");
  const discard = page.getByRole("dialog", { name: "Keep your analysis changes?", exact: true });
  await expect(discard).toBeVisible();
  await discard.getByRole("button", { name: "Apply and continue", exact: true }).click();
  await expect(grid).toBeVisible();
  expect(await readFile(path)).toEqual(original);
});

test("bulk-edit condition groups use typed operators and reusable presets without saving project scope", async ({ page }) => {
  const uiErrors: string[] = [];
  page.on("pageerror", error => uiErrors.push(error.message));
  const { execFileSync } = await import("node:child_process");
  const path = resolve(directory, "grouped-rules.eproj");
  execFileSync(python, ["-m", "modern.e2e.create_fixture", path], { cwd: resolve("..") });
  execFileSync(python, ["-c", "import sys;from decimal import Decimal;from estimator.data.schedule import ScheduleDatabase;from estimator.undo import Stack;d=ScheduleDatabase(Stack());d.open_database(sys.argv[1]);a=d.get_item('A',modify_res_code=False);a.add_ana_weight('OH',Decimal('0.1'));a.add_ana_weight('Profit',Decimal('0.15'));a.add_ana_round('Say',Decimal(2));a.evaluate_results();a.update_rate();d.insert_item_atomic(a,update=True);d.close_database()", path], { cwd: resolve("..") });
  const source = await readFile(path);
  await openFixture(page, path);
  await applyRecordsIfDirty(page);
  await page.locator("#view-schedule").click();
  await page.locator('.project-main-grid .tabulator-row [tabulator-field="code"]').filter({ hasText: /^A$/ }).click();
  const open = () => page.locator(".ribbon").getByRole("button", { name: "Bulk edit analysis…", exact: true }).click();
  await open();
  const dialog = page.getByRole("dialog", { name: "Bulk edit analysis", exact: true });
  await dialog.getByLabel("Rule 1 condition 1 field", { exact: true }).selectOption("value");
  const operator = dialog.getByLabel("Rule 1 condition 1 operator", { exact: true });
  await expect(operator.locator('option[value="contains"]')).toHaveCount(0);
  await operator.selectOption("is_empty");
  await expect(dialog.getByLabel("Rule 1 condition 1 value", { exact: true })).toHaveCount(0);
  await operator.selectOption("between");
  await dialog.getByLabel("Rule 1 condition 1 value", { exact: true }).fill("0.05");
  await dialog.getByLabel("Rule 1 condition 1 upper value", { exact: true }).fill("1/5");
  await dialog.getByRole("button", { name: "Add rule 1 group", exact: true }).click();
  const group = dialog.getByRole("group", { name: "Rule 1 group 2 conditions", exact: true });
  await expect(group.getByLabel("Rule 1 group 2 condition mode", { exact: true })).toHaveValue("any");
  await group.getByRole("button", { name: "Add rule 1 group 2 condition", exact: true }).click();
  await group.getByLabel("Rule 1 group 2 condition 1 value", { exact: true }).fill("OH");
  await group.getByRole("button", { name: "Add rule 1 group 2 condition", exact: true }).click();
  await group.getByLabel("Rule 1 group 2 condition 2 value", { exact: true }).fill("profit");
  await dialog.getByLabel("Rule 1 new value", { exact: true }).fill("0.25");
  const before = (await call("state")).result;
  await dialog.getByLabel("Preset name", { exact: true }).fill("Overhead and profit");
  await dialog.getByRole("button", { name: "Save preset", exact: true }).click();
  await expect(dialog.getByRole("status")).toContainText("Rule preset saved");
  expect((await call("state")).result).toEqual(before);
  const saved = await page.evaluate(() => JSON.parse(localStorage.getItem("gestimator.analysis-rules.v1")!).presets[0]);
  expect(Object.keys(saved).sort()).toEqual(["id", "name", "rules"]);
  await dialog.getByRole("button", { name: "Preview changes", exact: true }).click();
  await expect(dialog.locator(".batch-preview")).toContainText("Rule 1: 2 matches");
  expect((await call("state")).result).toEqual(before);
  await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
  await page.reload();
  await expect(page.getByText("Calculation engine connected")).toBeVisible();
  await applyRecordsIfDirty(page);
  await page.locator("#view-schedule").click();
  await open();
  expect(uiErrors).toEqual([]);
  await expect(dialog).toBeVisible();
  await dialog.getByLabel("Saved rule preset", { exact: true }).selectOption({ label: "Overhead and profit" });
  await expect(dialog.getByRole("status")).toContainText("Preset loaded");
  await expect(dialog.getByLabel("Schedule scope", { exact: true })).toHaveValue("all");
  await expect(dialog.getByLabel("Rule 1 condition 1 upper value", { exact: true })).toHaveValue("1/5");
  await expect(group.getByLabel("Rule 1 group 2 condition 2 value", { exact: true })).toHaveValue("profit");
  await expect(dialog.getByRole("button", { name: "Apply rules", exact: true })).toBeDisabled();
  await dialog.getByRole("button", { name: "Preview changes", exact: true }).click();
  await expect(dialog.getByRole("button", { name: "Apply rules", exact: true })).toBeEnabled();
  await page.screenshot({ path: "test-results/nested-analysis-rule-preset.png", animations: "disabled" });
  await dialog.getByRole("button", { name: "Delete saved rule preset", exact: true }).click();
  await expect(dialog.getByRole("status").filter({ hasText: "Preset deleted" })).toBeVisible();
  await expect(dialog.getByLabel("Rule 1 new value", { exact: true })).toHaveValue("0.25");
  await page.evaluate(() => { const original = Storage.prototype.setItem; Storage.prototype.setItem = function(key, value) { if (key === "gestimator.analysis-rules.v1") throw new Error("Storage full"); original.call(this, key, value); }; });
  await dialog.getByLabel("Preset name", { exact: true }).fill("Cannot save");
  await dialog.getByRole("button", { name: "Save preset", exact: true }).click();
  await expect(dialog.getByRole("alert")).toContainText("Preset could not be saved");
  await expect(dialog.getByLabel("Rule 1 new value", { exact: true })).toHaveValue("0.25");
  expect((await call("state")).result).toEqual(before);
  expect(await readFile(path)).toEqual(source);
});

test("MCP controls configure a live authenticated server while ribbon tabs preserve the editor", async ({ page }) => {
  const { execFileSync } = await import("node:child_process");
  const { createServer } = await import("node:net");
  const port = await new Promise<number>((resolve, reject) => {
    const server = createServer();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address() as { port: number };
      server.close(error => error ? reject(error) : resolve(address.port));
    });
  });
  const project = resolve(directory, "mcp.eproj");
  execFileSync(python, ["-m", "modern.e2e.create_fixture", project], { cwd: resolve("..") });
  const original = await readFile(project);
  await openFixture(page, project);
  await applyRecordsIfDirty(page);
  await page.locator("#view-schedule").click();
  const selected = page.locator('.project-main-grid .tabulator-selected [tabulator-field="code"]');
  await page.locator('.project-main-grid [tabulator-field="description"]').filter({ hasText: "Foundation" }).click();
  await expect(selected).toHaveText("A");
  for (const tab of ["databases", "mcp"]) {
    await applyRecordsIfDirty(page);
    await page.locator("#view-" + tab).click();
    await expect(page.locator(".project-view:visible h1")).toHaveText("Schedule of quantities");
    await expect(selected).toHaveText("A");
  }
  const ribbon = page.locator(".ribbon");
  await ribbon.getByRole("button", { name: "Configure MCP server", exact: true }).click();
  const settings = page.getByRole("dialog", { name: "Configure MCP server", exact: true });
  await settings.getByLabel("Port", { exact: true }).fill(String(port));
  await settings.getByLabel("Start automatically when GEstimator opens").check();
  await settings.getByRole("button", { name: "Save settings", exact: true }).click();
  await expect(settings.getByText("MCP settings saved.", { exact: true })).toBeVisible();
  await settings.getByRole("button", { name: "Show token", exact: true }).click();
  await expect(settings.getByLabel("Client configuration", { exact: true })).toHaveValue(/mcpServers/);
  await settings.getByRole("button", { name: "Copy client configuration", exact: true }).click();
  const config = JSON.parse(systemClipboard).mcpServers.gestimator;
  expect(config.url).toBe(`http://127.0.0.1:${port}/mcp`);
  await settings.getByRole("button", { name: "Close MCP settings", exact: true }).click();
  await ribbon.getByRole("button", { name: "Start MCP server", exact: true }).click();
  await expect(ribbon.getByRole("button", { name: "Stop MCP server", exact: true })).toBeEnabled();
  async function rpc(method: string, params = {}) {
    const response = await fetch(config.url, { method: "POST", headers: { ...config.headers, "Content-Type": "application/json", Accept: "application/json, text/event-stream", "MCP-Protocol-Version": "2025-11-25" }, body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }) });
    expect(response.status).toBe(200);
    return response.json();
  }
  expect((await rpc("initialize", { protocolVersion: "2025-11-25", capabilities: {}, clientInfo: { name: "browser-test", version: "1" } })).result.serverInfo.name).toBe("GEstimator");
  expect((await rpc("tools/list")).result.tools.length).toBeGreaterThan(7);
  const result = await rpc("tools/call", { name: "search_items", arguments: { kind: "schedule", query: "Foundation" } });
  expect(result.result.isError).toBe(false);
  expect(result.result.structuredContent.data.items[0].short).toContain("Foundation");
  await expect(selected).toHaveText("A");
  await applyRecordsIfDirty(page);
  await page.locator("#view-schedule").click();
  await ribbon.getByRole("button", { name: "Edit analysis", exact: true }).click();
  await page.locator('.analysis-table .tabulator-row[data-kind="Resource"] [tabulator-field="value"]').dblclick();
  const editor = page.locator('.analysis-table [tabulator-field="value"] input');
  await editor.fill("3");
  await editor.press("Enter");
  await expect(page.locator(".summary-value")).toContainText("30.00");
  const before = (await call("state")).result;
  for (const tab of ["databases", "mcp", "analysis"]) {
    await applyRecordsIfDirty(page);
    await page.locator("#view-" + tab).click();
    await expect(page.getByRole("dialog", { name: /Unsaved/ })).toHaveCount(0);
    await expect(page.locator(".analysis-table:visible")).toBeVisible();
  }
  expect((await call("state")).result).toEqual(before);
  await applyRecordsIfDirty(page);
  await page.locator("#view-mcp").click();
  await ribbon.getByRole("button", { name: "Stop MCP server", exact: true }).click();
  await expect(ribbon.getByRole("button", { name: "Start MCP server", exact: true })).toBeEnabled();
  // Restart the real backend; saved automatic-start settings must restore the endpoint.
  child.stdin.end();
  await new Promise<void>(resolve => child.once("close", () => resolve()));
  startBackend();
  await page.reload();
  await applyRecordsIfDirty(page);
  await page.locator("#view-mcp").click();
  await expect(ribbon.getByRole("button", { name: "Stop MCP server", exact: true })).toBeEnabled();
  expect((await rpc("tools/call", { name: "get_state", arguments: {} })).result.isError).toBe(false);
  await ribbon.getByRole("button", { name: "Configure MCP server", exact: true }).click();
  await expect(settings.getByLabel("Port", { exact: true })).toBeDisabled();
  await settings.getByRole("button", { name: "Stop server", exact: true }).click();
  await settings.getByRole("button", { name: "Rotate token", exact: true }).click();
  await expect(settings.getByRole("status").filter({ hasText: "Connection token changed" })).toBeVisible();
  await settings.getByRole("button", { name: "Start server", exact: true }).click();
  expect((await fetch(config.url, { method: "GET", headers: config.headers })).status).toBe(401);
  await page.screenshot({ path: "test-results/mcp-settings.png", animations: "disabled" });
  await settings.getByRole("button", { name: "Stop server", exact: true }).click();
  await settings.getByRole("button", { name: "Close MCP settings", exact: true }).click();
  expect(await readFile(project)).toEqual(original);
});

test("MCP startup conflicts and invalid saved preferences remain visible and recoverable", async ({ page }) => {
  const { createServer } = await import("node:net");
  const blocker = createServer();
  const port = await new Promise<number>((resolve, reject) => {
    blocker.once("error", reject);
    blocker.listen(0, "127.0.0.1", () => resolve((blocker.address() as { port: number }).port));
  });
  try {
    await page.evaluate(port => localStorage.setItem("gestimator.mcp.v1", JSON.stringify({ version: 1, port, token: "x".repeat(43), autostart: true })), port);
    await page.reload();
    await expect(page.locator(".mcp-error")).toBeVisible();
    await applyRecordsIfDirty(page);
    await expect(page.locator("#view-schedule")).toHaveAttribute("aria-selected", "true");
    expect((await call("mcp.status")).result.running).toBe(false);
    await page.getByRole("button", { name: "Review MCP settings", exact: true }).click();
    const settings = page.getByRole("dialog", { name: "Configure MCP server", exact: true });
    await expect(settings.getByLabel("Port", { exact: true })).toHaveValue(String(port));
    await settings.getByRole("button", { name: "Close MCP settings", exact: true }).click();
    await page.evaluate(() => localStorage.setItem("gestimator.mcp.v1", "invalid JSON"));
    await page.reload();
    await expect(page.locator(".mcp-error")).toContainText("Saved MCP settings could not be read");
    await page.getByRole("button", { name: "Review MCP settings", exact: true }).click();
    await settings.getByLabel("Port", { exact: true }).fill(String(port));
    await settings.getByRole("button", { name: "Save settings", exact: true }).click();
    await expect(settings.getByText("MCP settings saved.", { exact: true })).toBeVisible();
    await new Promise<void>((resolve, reject) => blocker.close(error => error ? reject(error) : resolve()));
    await settings.getByRole("button", { name: "Start server", exact: true }).click();
    await expect(settings.getByRole("button", { name: "Stop server", exact: true })).toBeVisible();
    await settings.getByRole("button", { name: "Stop server", exact: true }).click();
    await settings.getByRole("button", { name: "Close MCP settings", exact: true }).click();
    await expect(page.locator(".mcp-error")).toHaveCount(0);
  } finally {
    if (blocker.listening) await new Promise<void>(resolve => blocker.close(() => resolve()));
  }
});

test("themed template groups and Enter editing retain measurement eval and original Breakup", async ({ page }) => {
  await page.locator(".titlebar").getByRole("button", { name: "New project", exact: true }).click();
  await applyRecordsIfDirty(page);
  await page.locator("#view-measurement").click();
  await page.locator(".ribbon").getByRole("button", { name: "Add measurement", exact: true }).click();
  const add = page.getByRole("dialog", { name: "Add item", exact: true });
  const template = add.getByLabel("Measurement template");
  for (const group of ["General", "Civil", "E&M"]) await expect(template.locator(`optgroup[label="${group}"]`)).toHaveCount(1);
  await template.selectOption({ label: "NLBH (numbers, length, area, volume)" });
  await expect(page.locator(".themed-select-menu")).toHaveCount(0);
  const description = add.getByLabel("Description / remarks");
  await description.fill("Dimensions");
  await description.press("Shift+Enter");
  await description.pressSequentially("Second line");
  await description.press("Control+Enter");
  await description.pressSequentially("Third line");
  await expect(description).toHaveValue("Dimensions\nSecond line\nThird line");
  await description.press("Enter");
  await expect(add).not.toBeVisible();
  await expect(page.locator('.project-main-grid .tabulator-row[data-kind="Resource"] [tabulator-field="description"]')).toHaveText("Dimensions\nSecond line\nThird line");
  await openMeasurementEntry(page);
  await page.getByRole("button", { name: "Add record", exact: true }).click();
  const records = page.locator(".measurement-record-grid");
  const count = records.locator('.tabulator-row [tabulator-field="c2"]');
  await count.dblclick();
  await count.locator("textarea").fill("2*3");
  await count.locator("textarea").press("Enter");
  await expect(count.locator("textarea")).toHaveCount(0);
  await expect(count).toHaveText("6");
  await expect(records.locator('.tabulator-row [tabulator-field="c1"]')).toHaveText("[2*3,,,]");
  await expect(records.locator('.tabulator-row [tabulator-field="c6"]')).toHaveText("6.0");
  await count.dblclick();
  await expect(count.locator("textarea")).toHaveValue("2*3");
  await count.locator("textarea").press("Enter");
  const length = records.locator('.tabulator-row [tabulator-field="c3"]');
  await length.dblclick();
  await length.locator("textarea").fill("2+2");
  await length.locator("textarea").press("Enter");
  await expect(length).toHaveText("4");
  await expect(records.locator('.tabulator-row [tabulator-field="c1"]')).toHaveText("[2*3,2+2,,]");
  await expect(records.locator('.tabulator-row [tabulator-field="c6"]')).toHaveText("24.0");
  await page.screenshot({ path: "test-results/measurement-eval-breakup.png", animations: "disabled" });
});

test("system row clipboard transfers schedule, resources and analysis between independent processes", async ({ page, browser }) => {
  const { execFileSync } = await import("node:child_process");
  const project = resolve(directory, "clipboard.eproj");
  execFileSync(python, ["-m", "modern.e2e.create_fixture", project], { cwd: resolve("..") });
  const original = await readFile(project);
  await openFixture(page, project);
  await applyRecordsIfDirty(page);
  await page.locator("#view-schedule").click();
  await page.locator('.project-main-grid [tabulator-field="description"]').filter({ hasText: "Foundation" }).click();
  await page.keyboard.press("ControlOrMeta+c");
  await expect.poll(() => { try { return JSON.parse(systemClipboard).kind; } catch { return ""; } }).toBe("schedule");

  const other = createBackend();
  const context = await browser.newContext({ baseURL: "http://127.0.0.1:1420", viewport: { width: 1600, height: 1000 } });
  try {
    await other.call("project.new");
    const destination = await context.newPage();
    await connectDesktop(destination, other.call);
    await destination.locator("#view-schedule").click();
    const pasted = destination.locator('.project-main-grid [tabulator-field="description"]').filter({ hasText: "Foundation" });
    await destination.locator(".ribbon").getByRole("button", { name: "Paste", exact: true }).click();
    await expect.poll(async () => JSON.stringify({ state: await other.call("schedule.editor.state"), errors: await destination.getByRole("alert").allTextContents() })).toContain("Foundation");
    await expect(pasted).toHaveCount(1);
    await destination.locator(".titlebar").getByRole("button", { name: "Undo", exact: true }).click();
    await expect(pasted).toHaveCount(0);
    // Native Ctrl+V delivers structured rows through a paste event, not cell TSV.
    await pasteDocument(destination, ".project-main-grid .project-grid", systemClipboard);
    await expect(pasted).toHaveCount(1);

    await applyRecordsIfDirty(page);
    await page.locator("#view-resources").click();
    await page.locator('.project-main-grid [tabulator-field="description"]').filter({ hasText: /^Material$/ }).click();
    await page.locator(".ribbon").getByRole("button", { name: "Copy", exact: true }).click();
    await expect.poll(() => { try { return JSON.parse(systemClipboard).kind; } catch { return ""; } }).toBe("resources");
    await destination.locator("#view-resources").click();
    await destination.locator(".ribbon").getByRole("button", { name: "Paste", exact: true }).click();
    // GTK numbering: the pasted resource gets a new code after the selection.
    await expect(destination.locator('.project-main-grid .tabulator-row [tabulator-field="description"]').filter({ hasText: /^Material$/ })).toHaveCount(2);
    systemClipboard = "ordinary text";
    await destination.locator(".ribbon").getByRole("button", { name: "Paste", exact: true }).click();
    await expect(destination.getByRole("alert")).toContainText("valid GEstimator rows");
    expect((await other.call("resources.editor.state")).result.rows[0]._children).toHaveLength(2);

    for (const editor of [page, destination]) {
      await editor.locator("#view-schedule").click();
      await editor.locator('.project-main-grid [tabulator-field="description"]').filter({ hasText: "Foundation" }).click();
      await editor.locator(".ribbon").getByRole("button", { name: "Edit analysis", exact: true }).click();
    }
    await page.getByRole("grid", { name: "Rate analysis table" }).focus();
    await page.keyboard.press("ControlOrMeta+a");
    await page.keyboard.press("ControlOrMeta+c");
    await expect.poll(() => { try { return JSON.parse(systemClipboard).kind; } catch { return ""; } }).toBe("analysis");
    await destination.locator(".ribbon").getByRole("button", { name: "Paste rows", exact: true }).click();
    await expect(destination.locator(".summary-value")).toContainText("40.00");
    await destination.locator(".titlebar").getByRole("button", { name: "Undo", exact: true }).click();
    await expect(destination.locator(".summary-value")).toContainText("20.00");
    expect(await readFile(project)).toEqual(original);
  } finally {
    await context.close();
    other.child.stdin.end();
    await new Promise<void>(resolve => other.child.once("close", () => resolve()));
  }
});

test("measurement clipboard transfers whole items and template records with explicit local fallback", async ({ page, browser }) => {
  const other = createBackend();
  const context = await browser.newContext({ baseURL: "http://127.0.0.1:1420", viewport: { width: 1600, height: 1000 } });
  async function edit(transport: typeof call, method: string, params: Record<string, unknown> = {}) {
    const revision = (await transport("state")).result.revision;
    const response = await transport(method, { revision, ...params });
    expect(response.error).toBeUndefined();
    return response.result;
  }
  try {
    await call("project.new");
    await edit(call, "measurement.add", { template: "_1_NLBH", description: "Copied dimensions" });
    const id = (await call("measurement.state")).result.rows[0].id;
    await edit(call, "measurement.record_add", { id });
    const record = (await call("measurement.state", { id })).result.detail.rows[0].id;
    await edit(call, "measurement.record_edit_many", { id, edits: [{ id: record, field: "c2", value: "2*3" }, { id: record, field: "c3", value: "4" }] });
    await page.reload();
    await expect(page.getByText("Calculation engine connected")).toBeVisible();
    await applyRecordsIfDirty(page);
    await page.locator("#view-measurement").click();
    await page.locator('.project-main-grid [tabulator-field="description"]').filter({ hasText: "Copied dimensions" }).click();
    await page.locator(".ribbon").getByRole("button", { name: "Copy", exact: true }).click();
    await expect.poll(() => { try { return JSON.parse(systemClipboard).kind; } catch { return ""; } }).toBe("measurement");
    await other.call("project.new");
    const destination = await context.newPage();
    await connectDesktop(destination, other.call);
    await destination.locator("#view-measurement").click();
    await destination.locator(".ribbon").getByRole("button", { name: "Paste", exact: true }).click();
    await destination.locator('.project-main-grid [tabulator-field="description"]').filter({ hasText: "Copied dimensions" }).dblclick();
    await expect(destination.locator('.measurement-record-grid .tabulator-row [tabulator-field="c2"]')).toHaveText("6");
    await openMeasurementEntry(page);
    await page.locator('.measurement-record-grid .tabulator-row [tabulator-field="c2"]').click();
    await page.keyboard.press("ControlOrMeta+c");
    await expect.poll(() => JSON.parse(systemClipboard).kind).toBe("records");
    await pasteDocument(destination, ".measurement-record-grid .project-grid", systemClipboard);
    await expect(destination.locator(".measurement-record-grid .tabulator-row")).toHaveCount(2);
    await destination.locator(".titlebar").getByRole("button", { name: "Undo", exact: true }).click();
    await expect(destination.locator(".measurement-record-grid .tabulator-row")).toHaveCount(1);
    clipboardUnavailable = true;
    await page.getByRole("button", { name: "Copy record", exact: true }).click();
    await expect(page.getByRole("status").filter({ hasText: "within this window only" })).toBeVisible();
    await page.getByRole("button", { name: "Paste record", exact: true }).click();
    await expect(page.locator(".measurement-record-grid .tabulator-row")).toHaveCount(2);
    await destination.getByRole("button", { name: "Paste record", exact: true }).click();
    await expect(destination.getByRole("alert")).toContainText("Unable to read text");
  } finally {
    await context.close();
    other.child.stdin.end();
    await new Promise<void>(resolve => other.child.once("close", () => resolve()));
  }
});

test("GTK insertion shortcuts retain schedule parents and target the active editor", async ({ page }) => {
  const { execFileSync } = await import("node:child_process");
  const project = resolve(directory, "insertion.eproj");
  execFileSync(python, ["-m", "modern.e2e.create_fixture", project], { cwd: resolve("..") });
  await openFixture(page, project);
  await applyRecordsIfDirty(page);
  await page.locator("#view-schedule").click();
  const main = page.locator(".project-view:visible .project-main-grid");
  await main.locator('[tabulator-field="description"]').filter({ hasText: "Foundation" }).click();
  await page.keyboard.press("ControlOrMeta+Shift+i");
  const add = page.getByRole("dialog", { name: "Add item", exact: true });
  await expect(add.getByLabel("Parent code (optional)")).toHaveValue("A");
  await expect(add.getByRole("combobox", { name: "Category", exact: true })).toHaveValue("Work");
  await add.getByLabel("New code", { exact: true }).fill("A.1");
  await add.getByLabel("Description", { exact: true }).fill("Child work");
  await add.getByRole("button", { name: "Add item", exact: true }).click();
  await expect(add).not.toBeVisible();
  await expect(main.locator('.tabulator-tree-level-2 [tabulator-field="description"]')).toContainText("Child work");
  await main.locator('[tabulator-field="description"]').filter({ hasText: "Foundation" }).click();
  await page.keyboard.press("ControlOrMeta+m");
  const colour = page.getByRole("dialog", { name: "Schedule row colour" });
  await expect(colour).toBeVisible();
  await colour.getByRole("button", { name: "Close", exact: true }).click();
  await expect(colour).not.toBeVisible();
  await main.locator('[tabulator-field="description"]').filter({ hasText: "Foundation" }).click();
  await page.keyboard.press("ControlOrMeta+e");
  await applyRecordsIfDirty(page);
  await expect(page.locator("#view-analysis")).toHaveAttribute("aria-selected", "true");
  await page.getByRole("grid", { name: "Rate analysis table" }).focus();
  await page.keyboard.press("ControlOrMeta+i");
  const resource = page.getByRole("dialog", { name: "Add analysis resources from database", exact: true });
  await expect(resource).toBeVisible();
  await resource.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(resource).not.toBeVisible();
  await page.getByRole("grid", { name: "Rate analysis table" }).focus();
  await page.keyboard.press("ControlOrMeta+Shift+i");
  const custom = page.getByRole("dialog", { name: "Add custom resource", exact: true });
  await expect(custom).toBeVisible();
  await custom.getByRole("button", { name: "Close", exact: true }).click();
  await expect(custom).not.toBeVisible();
  await applyRecordsIfDirty(page);
  await page.locator("#view-resources").click();
  await main.locator('[tabulator-field="description"]').filter({ hasText: /^Materials$/ }).click();
  // GTK accelerators also work while focus is in the active ribbon.
  await page.locator(".ribbon").getByRole("button", { name: "Add item", exact: true }).focus();
  await page.keyboard.press("ControlOrMeta+i");
  await expect(add.getByRole("combobox", { name: "Category", exact: true })).toHaveValue("Materials");
  await add.getByRole("button", { name: "Close", exact: true }).click();
  await expect(add).not.toBeVisible();
  await applyRecordsIfDirty(page);
  await page.locator("#view-measurement").click();
  await main.locator(".project-grid").focus();
  await page.keyboard.press("ControlOrMeta+i");
  await add.getByLabel("Measurement template").selectOption("_1_NLBH");
  await add.getByLabel("Description / remarks").fill("Dimensions");
  await add.getByRole("button", { name: "Add item", exact: true }).click();
  await expect(add).not.toBeVisible();
  await main.locator('[tabulator-field="description"]').filter({ hasText: "Dimensions" }).click();
  await openMeasurementEntry(page);
  await page.locator(".measurement-record-grid .project-grid").focus();
  await page.keyboard.press("ControlOrMeta+i");
  await expect(page.locator(".measurement-record-grid .tabulator-row")).toHaveCount(1);
});

test("measurement properties, searchable links and paged batch records keep atomic undo", async ({ page }) => {
  const { execFileSync } = await import("node:child_process");
  const project = resolve(directory, "measurement-parity.eproj");
  execFileSync(python, ["-m", "modern.e2e.create_fixture", project], { cwd: resolve("..") });
  await openFixture(page, project);
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await applyRecordsIfDirty(page);
  await page.locator("#view-measurement").click();
  await page.locator(".ribbon").getByRole("button", { name: "Add measurement", exact: true }).click();
  const add = page.getByRole("dialog", { name: "Add item", exact: true });
  await add.getByLabel("Measurement template").selectOption("civil_steel_table");
  await expect(add).toContainText("mass-per-length");
  await add.getByLabel("Description / remarks").fill("Steel quantities");
  await add.getByRole("button", { name: "Add item", exact: true }).click();
  await expect(add).not.toBeVisible();
  await openMeasurementEntry(page);
  await expect(page.getByRole("button", { name: "Properties…", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Properties…", exact: true }).click();
  const properties = page.getByRole("dialog", { name: "Measurement properties", exact: true });
  await properties.getByLabel("Description / remarks").fill("Discarded change");
  await properties.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(page.locator(".project-view:visible .project-main-grid")).not.toContainText("Discarded change");
  await page.getByRole("button", { name: "Properties…", exact: true }).click();
  await properties.getByLabel("Item 1 constant", { exact: true }).fill("1/0");
  await properties.getByRole("button", { name: "Save properties", exact: true }).click();
  await expect(properties.getByRole("alert")).toContainText("Invalid numeric");
  await properties.getByLabel("Item 1 constant", { exact: true }).fill("2*3");
  await properties.getByLabel("Item 1 Label", { exact: true }).fill("<img src=x onerror=alert(1)>");
  await properties.getByRole("button", { name: "Choose property schedule item 1", exact: true }).click();
  const picker = page.getByRole("dialog", { name: "Choose schedule item", exact: true });
  await picker.getByRole("button", { name: "Search", exact: true }).focus();
  await page.keyboard.press("ControlOrMeta+f");
  await expect(picker.getByLabel("Find linked schedule item")).toBeFocused();
  await picker.getByLabel("Find linked schedule item").fill("Foundation");
  await picker.getByRole("button", { name: "Search", exact: true }).click();
  await picker.locator(".library-item").filter({ hasText: "Foundation" }).click();
  await expect(picker).not.toBeVisible();
  await expect(properties.getByLabel("Property schedule code 1", { exact: true })).toHaveValue("A");
  await properties.getByRole("button", { name: "Save properties", exact: true }).click();
  await expect(properties).not.toBeVisible();
  await expect(page.locator('.measurement-record-grid .tabulator-col[tabulator-field="c10"]')).toContainText("<img src=x onerror=alert(1)>");
  await expect(page.locator(".measurement-record-grid .tabulator-col img")).toHaveCount(0);
  await page.getByRole("button", { name: "Properties…", exact: true }).click();
  await expect(properties.getByLabel("Item 1 constant", { exact: true })).toHaveValue("6.000000");
  await properties.getByLabel("Item 1 Label", { exact: true }).fill("8mm");
  await page.screenshot({ path: "test-results/measurement-properties.png", animations: "disabled" });
  await properties.getByRole("button", { name: "Cancel", exact: true }).click();
  await page.getByRole("button", { name: "Add multiple records", exact: true }).click();
  const insert = page.getByRole("dialog", { name: "Insert measurement records", exact: true });
  await insert.getByLabel("Number of records").fill("120");
  await insert.getByRole("button", { name: "Insert records", exact: true }).click();
  await expect(insert).not.toBeVisible();
  const records = page.locator(".measurement-record-grid .project-grid");
  await expect(page.locator(".project-view:visible .pagination:visible")).toContainText("120 records · Page 1");
  await expect(records.locator('.tabulator-row [tabulator-field="_serial"]').first()).toHaveText("1");
  await page.getByRole("button", { name: "Next records", exact: true }).click();
  await expect(records.locator('.tabulator-row [tabulator-field="_serial"]').first()).toHaveText("101");
  await expect(records.locator(".tabulator-row")).toHaveCount(20);
  await expect(records).toHaveAttribute("aria-busy", "false");
  await expect(page.locator(".measurement-entry-heading")).toContainText("Steel quantities");
  await records.focus();
  await expect(records).toBeFocused();
  await page.keyboard.press("ControlOrMeta+a");
  expect(errors).toEqual([]);
  await expect(records.locator(".tabulator-selected")).toHaveCount(20);
  await expect(page.getByRole("button", { name: "Copy record", exact: true })).toBeEnabled();
  await expect(page.locator(".measurement-entry-heading")).toContainText("Steel quantities");
  await page.keyboard.press("ControlOrMeta+c");
  await expect.poll(() => { try { return JSON.parse(systemClipboard).items.length; } catch { return 0; } }).toBe(20);
  await page.getByRole("button", { name: "Paste record", exact: true }).click();
  await expect(page.locator(".project-view:visible .pagination:visible")).toContainText("140 records");
  await page.locator(".titlebar").getByRole("button", { name: "Undo", exact: true }).click();
  await expect(page.locator(".project-view:visible .pagination:visible")).toContainText("120 records");
  await records.focus();
  await page.keyboard.press("ControlOrMeta+a");
  await page.keyboard.press("Delete");
  await expect(page.locator(".project-view:visible .pagination:visible")).toContainText("100 records");
  await expect(page.getByRole("button", { name: "Next records", exact: true })).toBeDisabled();
  const firstCount = records.locator('.tabulator-row [tabulator-field="c1"]').first();
  await firstCount.click();
  await pasteDocument(page, ".measurement-record-grid .project-grid", "2*3\t4");
  await expect(firstCount).toHaveText("6");
  await firstCount.dblclick();
  await firstCount.locator("textarea").fill("1/0");
  await page.locator(".tabulator-header:visible").click();
  await expect(page.locator(".project-view:visible").getByRole("alert")).toContainText("Invalid numeric");
  await expect(firstCount).toHaveText("6");
  expect(errors).toEqual([]);
});

test("insertion reveals new rows, F2 edits the selection and resource moves preserve links", async ({ page }) => {
  const { execFileSync } = await import("node:child_process");
  const project = resolve(directory, "editor-parity.eproj");
  execFileSync(python, ["-m", "modern.e2e.create_fixture", project], { cwd: resolve("..") });
  const original = await readFile(project);
  await openFixture(page, project);
  await applyRecordsIfDirty(page);
  await page.locator("#view-schedule").click();
  const table = page.locator(".project-main-grid .project-grid");
  await table.locator('[tabulator-field="description"]').filter({ hasText: /^Work$/ }).click();
  await page.keyboard.press("ArrowLeft");
  await page.keyboard.press("ControlOrMeta+i");
  const add = page.getByRole("dialog", { name: "Add item", exact: true });
  await expect(add.getByLabel("New code", { exact: true })).toHaveValue("1.1");
  await add.getByLabel("Description", { exact: true }).fill("Inserted work");
  await add.getByRole("button", { name: "Add item", exact: true }).click();
  await expect(add).not.toBeVisible();
  await expect(table.locator('.tabulator-selected [tabulator-field="description"]')).toContainText("Inserted work");
  await table.focus();
  await page.keyboard.press("F2");
  await table.locator('textarea').fill("Revised work");
  await page.locator(".tabulator-header:visible").click();
  await expect(table.locator('.tabulator-selected [tabulator-field="description"]')).toContainText("Revised work");
  await table.getByRole("gridcell", { name: "Foundation", exact: true }).click({ button: "right" });
  await page.getByText("Open analysis", { exact: true }).click();
  await applyRecordsIfDirty(page);
  await expect(page.locator("#view-analysis")).toHaveAttribute("aria-selected", "true");
  await applyRecordsIfDirty(page);
  await page.locator("#view-resources").click();
  const ribbon = page.locator(".ribbon");
  await ribbon.getByRole("button", { name: "Add category", exact: true }).click();
  const category = page.getByRole("dialog", { name: "Add category", exact: true });
  await category.getByLabel("Category name").fill("Relocated");
  await category.getByRole("button", { name: "Add category", exact: true }).click();
  await expect(category).not.toBeVisible();
  await table.getByRole("gridcell", { name: "Material", exact: true }).click();
  await page.keyboard.press("ControlOrMeta+e");
  const edit = page.getByRole("dialog", { name: "Edit item", exact: true });
  await edit.getByLabel("Rate", { exact: true }).fill("20");
  await edit.getByRole("button", { name: "Save item", exact: true }).click();
  await expect(edit).not.toBeVisible();
  await ribbon.getByRole("button", { name: "Move resources…", exact: true }).click();
  const move = page.getByRole("dialog", { name: "Move resources", exact: true });
  await move.getByLabel("Destination category").selectOption("Relocated");
  await move.getByRole("button", { name: "Move resources", exact: true }).click();
  await expect(move).not.toBeVisible();
  await expect.poll(async () => JSON.stringify((await call("resources.editor.state")).result.rows)).toContain('"category":"Relocated"');
  await page.locator(".titlebar").getByRole("button", { name: "Undo", exact: true }).click();
  await expect.poll(async () => JSON.stringify((await call("resources.editor.state")).result.rows)).toContain('"category":"Materials"');
  expect(await readFile(project)).toEqual(original);
});

test("saved libraries restore across processes, deduplicate and recover from missing paths", async ({ page }) => {
  const { execFileSync } = await import("node:child_process");
  const project = resolve(directory, "library-project.eproj");
  const library = resolve(directory, "saved-library.eproj");
  const moved = resolve(directory, "moved-library.eproj");
  execFileSync(python, ["-m", "modern.e2e.create_fixture", project], { cwd: resolve("..") });
  await copyFile(project, library);
  const original = await readFile(library);
  await openFixture(page, project);
  await attachDatabase(page, library);
  await attachDatabase(page, library);
  const count = async (expected: number) => {
    const manager = await openDatabaseManager(page);
    await expect(manager.locator(".attached-database")).toHaveCount(expected);
    await manager.getByRole("button", { name: "Close database manager", exact: true }).click();
  };
  const restart = async () => {
    child.stdin.end();
    await new Promise<void>(resolve => child.once("close", () => resolve()));
    startBackend();
    await page.reload();
    await expect(page.getByText("Calculation engine connected")).toBeVisible();
    await openFixture(page, project);
  };
  await count(1);
  await page.reload();
  await expect(page.getByText("Calculation engine connected")).toBeVisible();
  await count(1);
  await restart();
  await count(1);
  await rename(library, moved);
  await restart();
  await expect(page.locator(".library-warning")).toContainText("1 saved library is unavailable");
  await count(0);
  let manager = await openDatabaseManager(page);
  await expect(manager.locator(".saved-library")).toContainText("Unavailable:");
  await manager.getByRole("button", { name: "Close database manager", exact: true }).click();
  await attachDatabase(page, moved, "databases");
  manager = await openDatabaseManager(page);
  await manager.locator(".saved-library").filter({ hasText: library }).getByRole("button", { name: /Forget library/ }).click();
  await manager.getByRole("button", { name: "Close database manager", exact: true }).click();
  await expect(page.locator(".library-warning")).not.toBeVisible();
  await restart();
  await count(1);
  expect(await readFile(moved)).toEqual(original);
  const stored = await page.evaluate(() => JSON.parse(localStorage.getItem("gestimator.libraries.v1")!));
  expect(stored.libraries.map((entry: { path: string }) => entry.path)).toEqual([moved]);
});

test("inspector edits are atomic and custom templates persist without changing source files", async ({ page }) => {
  const { execFileSync } = await import("node:child_process");
  const project = resolve(directory, "batch.eproj");
  execFileSync(python, ["-m", "modern.e2e.create_fixture", project], { cwd: resolve("..") });
  const source = await readFile(project);
  await openFixture(page, project);
  const open = page.getByRole("dialog", { name: "Open project", exact: true });
  await expect(open).not.toBeVisible();
  await applyRecordsIfDirty(page);
  await page.locator("#view-schedule").click();
  await page.locator('.project-main-grid [tabulator-field="description"]').filter({ hasText: "Foundation" }).click();
  await page.locator(".ribbon").getByRole("button", { name: "Edit analysis", exact: true }).click();
  await page.locator('.tabulator-row[data-kind="Resource"] [tabulator-field="kind"]').click();
  const rate = page.locator(".inspector").getByLabel("Base rate", { exact: true });
  await rate.fill("1/0");
  await rate.press("Tab");
  await expect(page.getByRole("alert")).toContainText("Invalid numeric");
  await expect(page.locator(".summary-value")).toContainText("20.00");
  await rate.fill("15.555");
  await rate.press("Tab");
  await expect(page.locator(".summary-value")).toContainText("31.12");
  await page.locator(".titlebar").getByRole("button", { name: "Undo", exact: true }).click();
  await expect(page.locator(".summary-value")).toContainText("20.00");
  await page.locator(".ribbon").getByRole("button", { name: "Custom analysis template…" }).click();
  const template = page.getByRole("dialog", { name: "Custom analysis template", exact: true });
  await template.getByLabel("Row 1 description", { exact: true }).fill("CUSTOM MATERIALS");
  await template.getByRole("button", { name: "Save template", exact: true }).click();
  await expect(template.getByRole("status").filter({ hasText: "Template saved" })).toBeVisible();
  await template.getByRole("button", { name: "Apply batch" }).click();
  await expect(template).not.toBeVisible();
  await expect(page.locator(".analysis-content")).toContainText("CUSTOM MATERIALS");
  await page.locator(".titlebar").getByRole("button", { name: "Undo", exact: true }).click();
  await expect(page.locator(".analysis-content")).not.toContainText("CUSTOM MATERIALS");
  await page.reload();
  await expect(page.getByText("Calculation engine connected")).toBeVisible();
  await page.locator("#view-analysis").click();
  await page.locator(".ribbon").getByRole("button", { name: "Custom analysis template…" }).click();
  await expect(template.getByLabel("Row 1 description", { exact: true })).toHaveValue("CUSTOM MATERIALS");
  await expect(template).toHaveCSS("opacity", "1");
  await page.screenshot({ path: "test-results/custom-analysis-template.png", animations: "disabled" });
  expect(await readFile(project)).toEqual(source);
});

test("keyboard table selection opens analysis and wide measurement templates retain their layout", async ({ page }) => {
  // Hold the first measurement response long enough to exercise the loading state.
  measurementDelay = 150;
  const errors: string[] = [];
  page.on("pageerror", error => { errors.push(error.message); });
  const { execFileSync } = await import("node:child_process");
  const project = resolve(directory, "keyboard-layout.eproj");
  execFileSync(python, ["-m", "modern.e2e.create_fixture", project], { cwd: resolve("..") });
  await openFixture(page, project);
  const open = page.getByRole("dialog", { name: "Open project", exact: true });
  await expect(open).not.toBeVisible();
  await applyRecordsIfDirty(page);
  await page.locator("#view-schedule").click();
  const table = page.locator(".project-main-grid .project-grid");
  await table.focus();
  await page.keyboard.press("Home");
  await expect(table.locator(".tabulator-row.tabulator-selected")).toHaveCount(1);
  await page.keyboard.press("Shift+End");
  await expect(table.locator(".tabulator-row.tabulator-selected")).toHaveCount(2);
  await page.keyboard.press("Escape");
  await expect(table.locator(".tabulator-row.tabulator-selected")).toHaveCount(0);
  await page.keyboard.press("End");
  await page.keyboard.press("ControlOrMeta+e");
  await applyRecordsIfDirty(page);
  await expect(page.locator("#view-analysis")).toHaveAttribute("aria-selected", "true");
  const analysis = page.getByRole("grid", { name: "Rate analysis table" });
  await analysis.focus();
  await page.keyboard.press("ControlOrMeta+a");
  await expect(page.locator(".table-toolbar")).toContainText("3 selected");
  await page.keyboard.press("Escape");
  await expect(analysis.locator(".tabulator-row.tabulator-selected")).toHaveCount(0);
  await applyRecordsIfDirty(page);
  await page.locator("#view-measurement").click();
  await applyRecordsIfDirty(page);
  await expect(page.locator("#view-measurement")).toHaveAttribute("aria-selected", "true");
  expect(errors).toEqual([]);
  await expect(page.locator(".project-view:visible h1")).toHaveText("Measurements");
  await page.locator(".ribbon").getByRole("button", { name: "Add measurement", exact: true }).click();
  const add = page.getByRole("dialog", { name: "Add item", exact: true });
  await add.getByLabel("Measurement template").selectOption("civil_steel_table");
  await add.getByLabel("Description / remarks").fill("Steel reinforcement");
  await add.getByRole("button", { name: "Add item", exact: true }).click();
  await expect(add).not.toBeVisible();
  await openMeasurementEntry(page);
  await page.locator(".ribbon").getByRole("button", { name: "Add record", exact: true }).click();
  await page.getByRole("button", { name: "Properties…", exact: true }).click();
  await expect(page.getByLabel("Item 1 constant", { exact: true })).toHaveValue("0.395");
  await expect(page.getByLabel("Item 6 Label", { exact: true })).toHaveValue("25mm");
  await page.getByRole("dialog", { name: "Measurement properties" }).getByRole("button", { name: "Cancel", exact: true }).click();
  const records = page.locator(".measurement-record-grid");
  await expect(records.locator('.tabulator-col[tabulator-field="c1"]')).toHaveCSS("width", "40px");
  await expect(records.locator('.tabulator-col[tabulator-field="c10"]')).toHaveCSS("width", "50px");
  const numeric = records.locator('.tabulator-row [tabulator-field="c1"]');
  await numeric.dblclick();
  await numeric.locator("textarea").fill("2*3");
  await page.locator(".tabulator-header:visible").click();
  await expect(numeric).toHaveText("6");
  const calculated = records.locator('.tabulator-row [tabulator-field="c10"]');
  await calculated.dblclick();
  await expect(calculated.locator("input,textarea")).toHaveCount(0);
  await page.setViewportSize({ width: 1100, height: 1000 });
  await expect.poll(() => page.locator(".measurement-links").evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
  await page.screenshot({ path: "test-results/steel-measurement-layout.png" });
});

test("program settings persist, control Modify & Add, default rows and workbook wrapping", async ({ page }) => {
  const { execFileSync } = await import("node:child_process");
  const library = resolve(directory, "settings-library.eproj");
  execFileSync(python, ["-m", "modern.e2e.create_fixture", library], { cwd: resolve("..") });
  const original = await readFile(library);
  const settings = page.getByRole("dialog", { name: "Program settings", exact: true });
  const openSettings = async () => {
    await page.getByRole("button", { name: "Application menu", exact: true }).click();
    await page.getByRole("menuitem", { name: "Program settings…", exact: true }).click();
    await settings.getByRole("tab", { name: "Library Modify & Add", exact: true }).click();
    await expect(settings.getByLabel("Schedule rate multiplier", { exact: true })).toBeVisible();
  };
  const before = (await call("state")).result;
  await openSettings();
  await settings.getByLabel("Schedule rate multiplier", { exact: true }).fill("1/0");
  await settings.getByRole("button", { name: "Save program settings" }).click();
  await expect(settings.getByRole("alert")).toContainText("Invalid numeric");
  await settings.getByRole("button", { name: "Cancel", exact: true }).click();
  expect((await call("state")).result).toEqual(before);
  await openSettings();
  await settings.getByLabel("Schedule rate multiplier", { exact: true }).fill("2");
  await settings.getByLabel("Trailing analysis rows to replace", { exact: true }).fill("1");
  await settings.getByRole("tab", { name: "General", exact: true }).click();
  await settings.getByRole("checkbox", { name: /Break item descriptions/ }).uncheck();
  await settings.getByRole("tab", { name: "Default analysis template", exact: true }).click();
  await settings.getByLabel("Default row 1 description", { exact: true }).fill("PROGRAM MATERIALS");
  await settings.getByLabel("Default row 1 code", { exact: true }).fill("PM");
  await settings.getByRole("tab", { name: "Library Modify & Add", exact: true }).click();
  await settings.getByRole("button", { name: "Add template row", exact: true }).click();
  await settings.getByLabel("Modify row 1 type", { exact: true }).selectOption("Multiply");
  await settings.getByLabel("Modify row 1 description", { exact: true }).fill("Configured replacement");
  await settings.getByLabel("Modify row 1 value", { exact: true }).fill("3");
  await settings.getByRole("button", { name: "Save program settings" }).click();
  await expect(settings).not.toBeVisible();
  expect((await call("state")).result).toEqual(before);
  await page.reload();
  await expect(page.getByText("Calculation engine connected")).toBeVisible();
  await openSettings();
  await expect(settings.getByLabel("Schedule rate multiplier", { exact: true })).toHaveValue("2.00000");
  await settings.getByRole("tab", { name: "General", exact: true }).click();
  await expect(settings.getByRole("checkbox", { name: /Break item descriptions/ })).not.toBeChecked();
  await settings.getByRole("button", { name: "Cancel", exact: true }).click();
  await page.locator(".titlebar").getByRole("button", { name: "New project", exact: true }).click();
  const ribbon = page.locator(".ribbon");
  await attachDatabase(page, library);
  await ribbon.getByRole("button", { name: "Add item from database", exact: true }).click();
  const picker = page.getByRole("dialog", { name: "Add item from database", exact: true });
  await picker.locator('[tabulator-field="description"]').filter({ hasText: "Foundation" }).click();
  await picker.getByRole("button", { name: "Modify & Add", exact: true }).click();
  await expect(picker).not.toBeVisible();
  const grid = page.locator(".project-view:visible .project-main-grid");
  await expect(grid.locator('.tabulator-row [tabulator-field="rate"]').last()).toHaveText(/^40(\.0+)?$/);
  await page.locator(".titlebar").getByRole("button", { name: "Undo", exact: true }).click();
  await expect(grid).not.toContainText("Foundation");
  await page.locator(".titlebar").getByRole("button", { name: "Redo", exact: true }).click();
  const description = grid.locator('[tabulator-field="description"]').filter({ hasText: "Foundation" });
  await description.dblclick();
  await grid.locator('[tabulator-field="description"] textarea').fill("First line\nSecond line");
  await page.locator(".tabulator-header:visible").click();
  const exportWorkbook = async (name: string) => {
    const output = resolve(directory, name);
    nativeDialogResults.push(output);
    await ribbon.getByRole("button", { name: "Export workbook", exact: true }).click();
    await expect.poll(async () => readFile(output).then(() => true).catch(() => false)).toBe(true);
    return JSON.parse(execFileSync(python, ["-c", "import json,sys;from openpyxl import load_workbook;b=load_workbook(sys.argv[1]);print(json.dumps([c.value for row in b['Schedule'] for c in row if isinstance(c.value,str)]));b.close()", output], { encoding: "utf8" }));
  };
  expect(await exportWorkbook("joined.xlsx")).toContain("First line\nSecond line");
  await openSettings();
  await settings.getByRole("tab", { name: "General", exact: true }).click();
  await settings.getByRole("checkbox", { name: /Break item descriptions/ }).check();
  await settings.getByRole("button", { name: "Save program settings" }).click();
  await expect(settings).not.toBeVisible();
  const split = await exportWorkbook("split.xlsx");
  expect(split).toContain("First line");
  expect(split).toContain("Second line");
  await grid.locator('[tabulator-field="code"]').filter({ hasText: /^A$/ }).click();
  await ribbon.getByRole("button", { name: "Edit analysis", exact: true }).click();
  await expect(page.locator(".summary-value")).toContainText("60");
  await expect(page.locator(".analysis-content")).toContainText("Configured replacement");
  await ribbon.getByRole("button", { name: "Default analysis rows", exact: true }).click();
  await expect(page.locator(".analysis-content")).toContainText("PROGRAM MATERIALS");
  await page.locator(".titlebar").getByRole("button", { name: "Undo", exact: true }).click();
  expect(await readFile(library)).toEqual(original);
  await applyRecordsIfDirty(page);
  await page.locator("#view-schedule").click();
  await ribbon.getByRole("button", { name: "Add item", exact: true }).click();
  const add = page.getByRole("dialog", { name: "Add item", exact: true });
  await add.getByLabel("New code", { exact: true }).fill("BLANK");
  await add.getByLabel("Description", { exact: true }).fill("Blank analysis");
  await add.getByRole("button", { name: "Add item", exact: true }).click();
  await expect(add).not.toBeVisible();
  await grid.locator('[tabulator-field="description"]').filter({ hasText: "Blank analysis" }).click();
  await ribbon.getByRole("button", { name: "Edit analysis", exact: true }).click();
  await expect(page.locator(".analysis-content")).toContainText("PROGRAM MATERIALS");
  expect((await call("state")).result.dirty).toBe(true);
  await page.locator(".titlebar").getByRole("button", { name: "Undo", exact: true }).click();
  expect((await call("state")).result.rows).toHaveLength(0);
  await openSettings();
  await settings.getByRole("button", { name: "Restore shipped defaults", exact: true }).click();
  await expect(settings.getByLabel("Schedule rate multiplier", { exact: true })).toHaveValue("1");
  await settings.getByRole("button", { name: "Cancel", exact: true }).click();
  await openSettings();
  await expect(settings.getByLabel("Schedule rate multiplier", { exact: true })).toHaveValue("2.00000");
  await expect(settings).toHaveCSS("opacity", "1");
  await page.screenshot({ path: "test-results/program-settings.png", animations: "disabled" });
});

test("invalid or unwritable program preferences stay visible and preserve active settings", async ({ page }) => {
  await page.evaluate(() => localStorage.setItem("gestimator.program-settings.v1", JSON.stringify({ version: 1, settings: { sch_rate_mult_factor: "__import__('os')" } })));
  await page.reload();
  await expect(page.getByText("Calculation engine connected")).toBeVisible();
  await expect(page.locator(".program-settings-warning")).toContainText("Shipped defaults are active");
  await page.getByRole("button", { name: "Review program settings", exact: true }).click();
  const settings = page.getByRole("dialog", { name: "Program settings", exact: true });
  await settings.getByRole("tab", { name: "Library Modify & Add", exact: true }).click();
  await expect(settings.getByLabel("Schedule rate multiplier", { exact: true })).toHaveValue("1");
  await settings.getByRole("button", { name: "Save program settings" }).click();
  await expect(settings).not.toBeVisible();
  await expect(page.locator(".program-settings-warning")).not.toBeVisible();
  const saved = await page.evaluate(() => localStorage.getItem("gestimator.program-settings.v1"));
  await page.getByRole("button", { name: "Application menu", exact: true }).click();
  await page.getByRole("menuitem", { name: "Program settings…", exact: true }).click();
  await settings.getByRole("tab", { name: "Library Modify & Add", exact: true }).click();
  await settings.getByLabel("Schedule rate multiplier", { exact: true }).fill("99");
  await page.evaluate(() => { Storage.prototype.setItem = () => { throw new Error("Storage blocked"); }; });
  await settings.getByRole("button", { name: "Save program settings" }).click();
  await expect(settings.getByRole("alert")).toContainText("Storage blocked");
  await settings.getByRole("button", { name: "Cancel", exact: true }).click();
  expect(await page.evaluate(() => localStorage.getItem("gestimator.program-settings.v1"))).toBe(saved);
  await page.getByRole("button", { name: "Application menu", exact: true }).click();
  await page.getByRole("menuitem", { name: "Program settings…", exact: true }).click();
  await settings.getByRole("tab", { name: "Library Modify & Add", exact: true }).click();
  await expect(settings.getByLabel("Schedule rate multiplier", { exact: true })).toHaveValue("1.00000");
});

test("appearance settings persist and library rules preview and import at compact widths", async ({ page }) => {
  const library = await refinementFixture(page);
  const settings = page.getByRole("dialog", { name: "Program settings", exact: true });
  await page.getByRole("button", { name: "Application menu", exact: true }).click();
  await page.getByRole("menuitem", { name: "Program settings…", exact: true }).click();
  await settings.getByRole("tab", { name: "Appearance", exact: true }).click();
  const fonts = (await call("program.fonts")).result;
  expect(fonts.length).toBeGreaterThan(0);
  const fontInput = settings.getByLabel("Interface font face");
  await expect(settings.getByText("Choose an installed font, or Desktop default to follow the system.")).toBeVisible();
  await expect(fontInput).toHaveJSProperty('tagName', 'SELECT');
  await expect(fontInput).toBeEnabled();
  await fontInput.click();
  const fontList = page.getByRole('listbox', { name: 'Interface font face', exact: true });
  await expect(fontList.getByRole('option')).toHaveCount(fonts.length + 1);
  expect(await fontList.getByRole('option').allTextContents()).toEqual(['Desktop default', ...fonts]);
  await page.screenshot({ path: 'test-results/themed-font-selection.png', animations: 'disabled' });
  await fontList.getByRole('option', { name: fonts[0], exact: true }).click();
  await expect(fontInput).toHaveValue(fonts[0]);
  await fontInput.press('ArrowDown');
  await expect(fontList).toBeVisible();
  await fontInput.press('Enter');
  await expect(fontInput).toHaveValue(fonts[0]);
  await expect(fontList).not.toBeVisible();
  await fontInput.press('ArrowDown');
  await fontInput.press('Escape');
  await expect(settings).toBeVisible();
  await settings.getByLabel('Theme').selectOption('light');
  await settings.getByLabel('Interface font face').selectOption(fonts[0]);
  await settings.getByLabel("Interface font size").fill("15");
  await settings.getByLabel("Tables font face").selectOption(fonts[Math.min(1, fonts.length - 1)]);
  await settings.getByLabel("Tables font size").fill("17");
  await settings.getByRole("button", { name: "Save program settings" }).click();
  await expect(settings).not.toBeVisible();
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  expect(await page.locator("html").evaluate(el => getComputedStyle(el).fontFamily)).toContain(fonts[0]);
  await expect(page.locator("html")).toHaveCSS("font-size", "15px");
  await applyRecordsIfDirty(page);
  await page.locator("#view-schedule").click();
  await attachDatabase(page, library);
  await page.setViewportSize({ width: 820, height: 950 });
  await page.getByRole("button", { name: "Add item from database", exact: true }).click();
  const picker = page.getByRole("dialog", { name: "Add item from database", exact: true });
  const table = picker.getByRole("grid");
  await expect(table).toHaveCSS("font-size", "17px");
  expect(await table.evaluate(el => getComputedStyle(el).fontFamily)).toContain(fonts[Math.min(1, fonts.length - 1)]);
  await expect(table.locator('.tabulator-col[tabulator-field="description"]')).toHaveCSS("font-size", "17px");
  // Frozen borders and fractional font metrics can round the extent by two pixels.
  const fits = (scope: ReturnType<Page["locator"]>) =>
    expect.poll(() => scope.locator(".tabulator-tableholder").evaluate(el => el.scrollWidth - el.clientWidth)).toBeLessThanOrEqual(2);
  await fits(table);
  await picker.getByText("Foundation", { exact: true }).click();
  await picker.getByRole("button", { name: "Modify & Add with rules…", exact: true }).click();
  const rules = page.getByRole("dialog", { name: "Modify & Add with analysis rules", exact: true });
  await expect(rules.getByLabel("Preset name")).not.toBeVisible();
  await rules.getByRole("button", { name: "Add rule", exact: true }).click();
  await rules.getByLabel("Rule 1 row type").selectOption("Resource");
  await rules.getByLabel("Rule 1 action").selectOption("multiply");
  await rules.getByLabel("Rule 1 new value").fill("3");
  await rules.getByRole("button", { name: "Preview changes" }).click();
  await expect(rules.getByRole("row").filter({ hasText: "A → A-copy" })).toContainText("60");
  await expect(rules.getByText("Matched row", { exact: true })).not.toBeVisible();
  await rules.getByText("View matched row changes", { exact: true }).click();
  await expect(rules.getByText("Matched row", { exact: true })).toBeVisible();
  await rules.getByRole("button", { name: "Add previewed items" }).click();
  await expect(rules).not.toBeVisible();
  const grid = page.getByRole("grid", { name: "Schedule of quantities", exact: true });
  await expect(grid.getByText("A-copy", { exact: true })).toBeVisible();
  await applyRecordsIfDirty(page);
  await page.locator("#view-resources").click();
  await page.getByRole("button", { name: "Add resources from database", exact: true }).click();
  const resources = page.getByRole("dialog", { name: "Add resources from database", exact: true });
  await fits(resources.getByRole("grid"));
  await resources.getByRole("button", { name: "Cancel", exact: true }).click();
  await page.setViewportSize({ width: 1080, height: 950 });
  await applyRecordsIfDirty(page);
  await page.locator("#view-schedule").click();
  await grid.getByText("A-copy", { exact: true }).click();
  await grid.press("Control+e");
  await expect(page.locator(".analysis-table.fit-table:visible")).toBeVisible();
  await fits(page.locator(".analysis-table.fit-table:visible"));
  await applyRecordsIfDirty(page);
  await page.locator("#view-schedule").click();
  await applyRecordsIfDirty(page);
  await page.locator("#view-analysis").click();
  await fits(page.locator(".analysis-table.fit-table:visible"));
});

test("resource editing, authoritative calculations, undo and workspace presentation", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page
    .getByRole("button", { name: "Add custom resource", exact: true })
    .first()
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Add custom resource",
    exact: true,
  });
  await dialog.getByLabel("Resource code").fill("MAT-001");
  await dialog.getByLabel("Unit", { exact: true }).fill("kg");
  await dialog
    .getByLabel("Description")
    .fill("Concrete constituent\nLong multiline resource description");
  await dialog.getByLabel("Base rate").fill("10.05");
  await dialog.getByLabel("Quantity").fill("2.5");
  await dialog.getByLabel("Tax %").fill("18");
  await dialog.getByLabel("Discount %").fill("5");
  await dialog
    .getByRole("button", { name: "Add resource", exact: true })
    .click();
  await expect(dialog).not.toBeVisible();
  await expect(page.locator(".summary-value")).toContainText("28.18");
  const row = page.locator('.tabulator-row[data-kind="Resource"]');
  await row.locator(".tabulator-cell").nth(2).click();
  await expect(page.locator(".inspector")).toContainText("MAT-001");
  const descriptionCell = row.locator('[tabulator-field="description"]');
  await descriptionCell.dblclick();
  await expect(descriptionCell.locator("textarea")).toHaveCount(0);
  const inspectorDescription = page.locator(".inspector").getByLabel("Description");
  await inspectorDescription.fill("Concrete constituent\nEdited multiline description");
  await inspectorDescription.press("Tab");
  await expect(
    page.locator(".inspector").getByLabel("Description"),
  ).toHaveValue("Concrete constituent\nEdited multiline description");
  await page
    .locator(".inspector")
    .getByLabel("Quantity", { exact: true })
    .fill("3");
  await page
    .locator(".inspector")
    .getByLabel("Quantity", { exact: true })
    .press("Tab");
  await expect(page.locator(".summary-value")).toContainText("33.81");
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(page.locator(".summary-value")).toContainText("28.18");
  await page
    .locator(".ribbon-tabs")
    .getByRole("tab", { name: "Analysis", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Weighted addition", exact: true })
    .click();
  await expect(
    page.locator('.tabulator-row[data-kind="Weight"]'),
  ).toBeVisible();
  const weightedRow = page.locator('.tabulator-row[data-kind="Weight"]');
  const weightedHeight = (await weightedRow.boundingBox())!.height;
  await weightedRow.locator('[tabulator-field="description"]').dblclick();
  expect((await weightedRow.boundingBox())!.height).toBeLessThanOrEqual(weightedHeight + 2);
  await weightedRow.locator('textarea').press("Enter");
  await expect(page.locator(".tabulator-col").first()).toHaveCSS(
    "display",
    "inline-flex",
  );
  await expect(page.locator(".tabulator-header")).toHaveCSS(
    "white-space",
    "nowrap",
  );
  const headers = await page
    .locator(".tabulator-col")
    .evaluateAll((cols) => cols.map((c) => c.getBoundingClientRect().y));
  expect(new Set(headers).size).toBe(1);
  await page.screenshot({ path: "test-results/workspace-dark.png" });
  await page.getByRole("button", { name: "Switch to light theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.screenshot({ path: "test-results/workspace-light.png" });

  const ribbon = page.locator(".ribbon");
  await ribbon
    .getByRole("button", { name: "Hide analysis inspector", exact: true })
    .click();
  await expect(page.locator(".inspector")).not.toBeVisible();
  await ribbon
    .getByRole("button", { name: "Show analysis inspector", exact: true })
    .click();
  await expect(ribbon.getByRole("button", { name: "Compact rows", exact: true })).toHaveCount(0);
  await expect(page.locator(".analysis-table:visible")).toHaveClass(/compact/);
  await expect(ribbon.getByRole("button", { name: /Collapse groups|Expand groups/ })).toHaveCount(0);
  await expect(page.locator(".analysis-table .tabulator-data-tree-control")).toHaveCount(0);
  await page.setViewportSize({ width: 1100, height: 800 });
  await expect
    .poll(() =>
      ribbon.evaluate((element) => element.scrollWidth <= element.clientWidth),
    )
    .toBe(true);
  await page.screenshot({ path: "test-results/workspace-compact.png" });
  expect(errors).toEqual([]);
});

test("real project navigation protects unsaved drafts and save-copy clears dirty state", async ({
  page,
}) => {
  await openFixture(page, resolve("../estimator/database/DSREM2022.eproj"));
  let dialog = page.getByRole("dialog", { name: "Open project", exact: true });
  await expect(dialog).not.toBeVisible();
  const search = page.getByRole("textbox", { name: "Find schedule items" });
  await search.fill("1.1.1");
  await search.press("Enter");
  await expect(page.locator(".item-card").first().locator(".item-code")).toHaveText("1.1.1");
  await page.locator(".item-card").first().click();
  await expect(page.locator(".code-tag")).toBeVisible();
  await page
    .locator('.tabulator-row[data-kind="Resource"]')
    .first()
    .locator('[tabulator-field="kind"]')
    .click();
  await expect(page.locator(".inspector-body")).toBeVisible();
  await page.screenshot({ path: "test-results/workspace-project.png" });
  await page
    .locator(".ribbon-tabs")
    .getByRole("tab", { name: "Analysis", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Resource group", exact: true })
    .click();
  await expect(page.locator(".draft-badge")).toContainText("Unsaved changes");
  await page
    .getByRole("button", { name: "Open project", exact: true })
    .first()
    .click();
  dialog = page.getByRole("dialog", { name: "Open project", exact: true });
  await dialog
    .getByLabel("Project file")
    .fill(resolve("../estimator/database/DSR2021.eproj"));
  await dialog
    .getByRole("button", { name: "Open project", exact: true })
    .click();
  // The other project opens in a new tab; this project and its draft stay open.
  const projectTabs = page.getByRole("navigation", { name: "Open projects" }).getByRole("tab");
  await expect(projectTabs).toHaveCount(2);
  await expect(projectTabs.nth(1)).toHaveAttribute("aria-selected", "true");
  await projectTabs.nth(0).click();
  await expect(page.locator(".draft-badge")).toContainText("Unsaved changes");
  const output = resolve(directory, "review.eproj");
  nativeDialogResults.push(output);
  await page.getByRole("button", { name: "Save copy", exact: true }).click();
  await expect.poll(async () => readFile(output).then(() => true).catch(() => false), { timeout: 45000 }).toBe(true);
  await expect(page.locator(".draft-badge")).toContainText("Up to date");
});

test("native typography and schedule, resource and measurement editing", async ({
  page,
}) => {
  const { execFileSync } = await import("node:child_process");
  const fixture = resolve(directory, "editable.eproj");
  execFileSync(
    python,
    ["-m", "modern.e2e.create_fixture", fixture],
    { cwd: resolve("..") },
  );
  await expect(page.locator("html")).toHaveCSS(
    "font-family",
    "Iosevka, system-ui",
  );
  await expect(page.locator("html")).toHaveCSS("font-size", "14.6667px");
  await openFixture(page, fixture);
  const fileDialog = page.getByRole("dialog", {
    name: "Open project",
    exact: true,
  });
  await expect(fileDialog).not.toBeVisible();
  await page
    .locator(".ribbon-tabs")
    .getByRole("tab", { name: "Schedule", exact: true })
    .click();
  const view = page.locator(".project-view:visible");
  const quantity = view
    .locator('.tabulator-row [tabulator-field="qty"]')
    .last();
  await quantity.dblclick();
  await quantity.locator("textarea,input").fill("2*3");
  await view.locator(".tabulator-header:visible").click();
  await expect(quantity).toHaveText("6");
  await page
    .locator(".titlebar")
    .getByRole("button", { name: "Undo", exact: true })
    .click();
  await expect(quantity).toHaveText("1");
  await quantity.click();
  await view.locator(".project-main-grid .project-grid").evaluate((element) => {
    const data = new DataTransfer();
    data.setData("text/plain", "7");
    element.dispatchEvent(
      new ClipboardEvent("paste", { bubbles: true, clipboardData: data }),
    );
  });
  await expect(quantity).toHaveText("7");
  await page
    .locator(".titlebar")
    .getByRole("button", { name: "Undo", exact: true })
    .click();
  await expect(quantity).toHaveText("1");
  await page.screenshot({ path: "test-results/schedule-desktop.png" });
  await page
    .locator(".ribbon-tabs")
    .getByRole("tab", { name: "Resources", exact: true })
    .click();
  const rate = view.locator('.tabulator-row [tabulator-field="rate"]').last();
  await rate.dblclick();
  await rate.locator("textarea,input").fill("15");
  await view.locator(".tabulator-header:visible").click();
  await expect(rate).toHaveText("15");
  await page.screenshot({ path: "test-results/resources-desktop.png" });
  await page
    .locator(".ribbon-tabs")
    .getByRole("tab", { name: "Measurements", exact: true })
    .click();
  await page
    .locator(".ribbon")
    .getByRole("button", { name: "Add measurement", exact: true })
    .click();
  const add = page.getByRole("dialog", { name: "Add item", exact: true });
  await add.getByLabel("Measurement template").selectOption("_1_NLBH");
  await add.getByLabel("Description / remarks").fill("Foundation dimensions");
  await add.getByRole("button", { name: "Add item", exact: true }).click();
  await expect(add).not.toBeVisible();
  await view
    .locator('.project-main-grid [tabulator-field="description"]')
    .filter({ hasText: "Foundation dimensions" })
    .dblclick();
  await expect(
    page.getByRole("button", { name: "Add record", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Add record", exact: true }).click();
  for (const [field, value] of [
    ["c2", "2"],
    ["c3", "3"],
  ]) {
    const cell = view.locator(
      '.measurement-record-grid .tabulator-row [tabulator-field="' +
        field +
        '"]',
    );
    await cell.dblclick();
    await cell.locator("textarea").fill(value);
    await view.locator(".tabulator-header:visible").click();
  }
  await expect(
    view.locator(
      '.measurement-record-grid .tabulator-row [tabulator-field="c6"]',
    ),
  ).toHaveText("6.0");
  const link = view.getByLabel("Schedule code 1");
  await link.fill("A");
  await link.press("Tab");
  const recordDescriptions = view.locator(
    '.measurement-record-grid .tabulator-row [tabulator-field="c0"]',
  );
  await recordDescriptions.first().dblclick();
  await recordDescriptions.first().locator("textarea").fill("First record");
  await view.locator(".tabulator-header:visible").click();
  await view.locator(".measurement-record-grid .project-grid").focus();
  await page.keyboard.press("ControlOrMeta+d");
  await expect(recordDescriptions).toHaveCount(2);
  await recordDescriptions.last().dblclick();
  await recordDescriptions.last().locator("textarea").fill("Second record");
  await view.locator(".tabulator-header:visible").click();
  await recordDescriptions.last().click();
  await page
    .getByRole("button", { name: "Move record up", exact: true })
    .click();
  await expect(recordDescriptions.first()).toHaveText("Second record");
  await page
    .locator(".titlebar")
    .getByRole("button", { name: "Undo", exact: true })
    .click();
  await expect(recordDescriptions.first()).toHaveText("First record");
  await recordDescriptions.last().click();
  await page
    .getByRole("button", { name: "Delete record", exact: true })
    .click();
  await expect(recordDescriptions).toHaveCount(1);
  await applyRecordsIfDirty(page);
  await finishMeasurementEntry(page);
  await page
    .locator(".ribbon")
    .getByRole("button", { name: "Update schedule quantities", exact: true })
    .click();
  await page.screenshot({ path: "test-results/measurements-desktop.png" });
  await page
    .locator(".ribbon-tabs")
    .getByRole("tab", { name: "Schedule", exact: true })
    .click();
  await expect(
    view.locator('.tabulator-row [tabulator-field="qty"]').last(),
  ).toHaveText("6");
  await page.locator(".titlebar").getByRole("button", { name: "Undo", exact: true }).click();
  await expect(quantity).toHaveText("1");
  await quantity.click();
  await page.locator(".ribbon").getByRole("button", { name: "Quantities from measurements…" }).click();
  const update = page.getByRole("dialog", { name: "Update selected schedule quantities" });
  await update.getByLabel("Quantity rounding").selectOption("Round to 10");
  await update.getByRole("button", { name: "Update quantities" }).click();
  await expect(update).not.toBeVisible();
  await expect(quantity).toHaveText("10");
});

test("new project, settings and mapped Excel import", async ({ page }) => {
  const { execFileSync } = await import("node:child_process");
  const workbook = resolve(directory, "input.xlsx");
  execFileSync(python, [
    "-c",
    "from openpyxl import Workbook; import sys; b=Workbook(); s=b.active; s.append(['Code','Description','Unit','Rate','Qty','Category']); s.append(['NEW','Imported work','m','5','2*3','Work']); b.save(sys.argv[1]); b.close()",
    workbook,
  ]);
  await page.getByRole("button", { name: "New project", exact: true }).click();
  const view = page.locator(".project-view:visible");
  await expect(view.locator("h1")).toHaveText("Schedule of quantities");
  await page
    .locator(".ribbon")
    .getByRole("button", { name: "Import workbook", exact: true })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Import schedule from Excel",
    exact: true,
  });
  await dialog.getByLabel("Workbook", { exact: true }).fill(workbook);
  await dialog.getByLabel("Workbook", { exact: true }).press("Enter");
  // Header detected, columns mapped by name with sample values, and a dry-run count.
  await expect(dialog.getByRole("grid", { name: "Worksheet preview" })).toContainText("Imported work");
  await expect(dialog.getByLabel("Code column", { exact: true })).toHaveValue("0");
  await expect(dialog.getByRole("table", { name: "Column mapping" })).toContainText("Imported work");
  await expect(dialog.getByRole("status")).toHaveText("1 new · 0 updated · 0 skipped");
  await page.screenshot({ path: "test-results/mapped-import.png", animations: "disabled" });
  await dialog
    .getByRole("button", { name: "Import 1 row", exact: true })
    .click();
  await expect(dialog).not.toBeVisible();
  await expect(
    view.locator('.tabulator-row [tabulator-field="qty"]').last(),
  ).toHaveText("6");
  await page
    .getByRole("button", { name: "Application menu", exact: true })
    .click();
  await page
    .getByRole("menuitem", { name: "Project settings…", exact: true })
    .click();
  const settings = page.getByRole("dialog", {
    name: "Project settings",
    exact: true,
  });
  await settings
    .getByLabel("project name", { exact: true })
    .fill("New desktop estimate");
  await settings
    .getByRole("button", { name: "Apply settings", exact: true })
    .click();
  await expect(settings).not.toBeVisible();
  await expect(page.locator(".titlebar-project")).toContainText(
    "New desktop estimate",
  );
});

test("application menu and ribbon views share context-aware header actions", async ({
  page,
}) => {
  const header = page.locator(".titlebar");
  const quickActionNames = [
    "Go back",
    "Go forward",
    "New project",
    "Open project",
    "Save copy",
    "Undo",
    "Redo",
  ];
  for (const name of quickActionNames) {
    const button = header.getByRole("button", { name, exact: true });
    expect((await button.textContent())?.trim()).toBe("");
  }
  expect(
    await header.locator(".quick-actions button").evaluateAll((buttons) =>
      buttons.map((button) => button.getAttribute("aria-label")),
    ),
  ).toEqual(quickActionNames);
  await page.locator(".ribbon").getByRole("button", { name: "Hide explorer", exact: true }).click();
  await expect(page.locator(".explorer")).not.toBeVisible();
  await page.locator(".ribbon").getByRole("button", { name: "Show explorer", exact: true }).click();
  await expect(page.locator(".explorer")).toBeVisible();
  await expect(page.locator(".document-tabs")).toHaveCount(0);
  const menuButton = page.getByRole("button", {
    name: "Application menu",
    exact: true,
  });
  await menuButton.click();
  await expect(menuButton).toHaveAttribute("aria-expanded", "true");
  await expect(
    page.getByRole("menuitem", { name: "Save project copy…", exact: true }),
  ).toHaveAttribute("aria-disabled", "true");
  for (const moved of [
    "Hide explorer",
    "Compact rows",
    "Collapse groups",
    "Hide analysis inspector",
  ])
    await expect(
      page.getByRole("menuitem", { name: moved, exact: true }),
    ).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect(menuButton).toHaveAttribute("aria-expanded", "false");
  await expect(menuButton).toBeFocused();
  await menuButton.click();
  await page
    .getByRole("menuitem", { name: "New project", exact: true })
    .click();
  await expect(
    page
      .locator(".ribbon-tabs")
      .getByRole("tab", { name: "Schedule", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  await page
    .locator(".ribbon")
    .getByRole("button", { name: "Add item", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "Add item", exact: true });
  await dialog.getByLabel("New code", { exact: true }).fill("HEADER-1");
  await dialog
    .getByLabel("Description", { exact: true })
    .fill("Header history test");
  await dialog.getByRole("button", { name: "Add item", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  await expect(page.locator(".project-view:visible")).toContainText(
    "Header history test",
  );
  await header.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(page.locator(".project-view:visible .project-main-grid")).not.toContainText(
    "Header history test",
  );
  await header.getByRole("button", { name: "Redo", exact: true }).click();
  await expect(page.locator(".project-view:visible .project-main-grid")).toContainText(
    "Header history test",
  );
  await page
    .locator(".ribbon-tabs")
    .getByRole("tab", { name: "Resources", exact: true })
    .click();
  await expect(page.locator(".project-view:visible h1")).toHaveText("Resource library");
  await expect(
    page
      .locator(".ribbon")
      .getByRole("button", { name: "Update dependent rates", exact: true }),
  ).toBeVisible();
  await expect(
    page
      .locator(".ribbon")
      .getByRole("button", { name: "Edit analysis", exact: true }),
  ).toHaveCount(0);
  await page
    .locator(".ribbon-tabs")
    .getByRole("tab", { name: "Measurements", exact: true })
    .click();
  await expect(page.locator(".project-view:visible h1")).toHaveText("Measurements");
  await expect(
    page
      .locator(".ribbon")
      .getByRole("button", { name: "Add measurement", exact: true }),
  ).toBeVisible();
  await expect(
    page
      .locator(".ribbon")
      .getByRole("button", { name: "Update dependent rates", exact: true }),
  ).toHaveCount(0);
  const ribbonHeights = new Set<number>();
  for (const tab of ["Schedule", "Analysis", "Resources", "Measurements", "Databases", "MCP"]) {
    await page
      .locator(".ribbon-tabs")
      .getByRole("tab", { name: tab, exact: true })
      .click();
    ribbonHeights.add(
      await page.locator(".ribbon").evaluate((element) => element.clientHeight),
    );
    const positions = await page.locator('.ribbon .ribbon-action:not(.ribbon-icon):not([data-ribbon-mini]) svg').evaluateAll(icons => icons.map(icon => icon.getBoundingClientRect()).filter(rect => rect.height > 0).map(rect => rect.top));
    if (positions.length > 1) expect(Math.max(...positions) - Math.min(...positions), `${tab} full button icons align`).toBeLessThan(1);
    const shortStacks = await page.locator('.ribbon-actions').evaluateAll(groups => groups.filter(group => {
      const buttons = Array.from(group.children).filter(element => element.classList.contains('ribbon-icon'));
      return buttons.length > 0 && buttons.length < 3 && group.getBoundingClientRect().width > 0;
    }).map(group => {
      const button = group.querySelector('.ribbon-icon')!;
      return { top: button.getBoundingClientRect().top - group.getBoundingClientRect().top, height: button.getBoundingClientRect().height, row: parseFloat(getComputedStyle(group).gridTemplateRows) };
    }));
    for (const stack of shortStacks) { expect(Math.abs(stack.top)).toBeLessThan(1); expect(stack.height).toBeCloseTo(stack.row, 0); }
  }
  expect(ribbonHeights.size).toBe(1);
  const scheduleTab = page.getByRole("tab", { name: "Schedule", exact: true }).first();
  await scheduleTab.focus();
  await page.keyboard.press("ArrowRight");
  const analysisTab = page.locator("#view-analysis");
  await expect(analysisTab).toBeFocused();
  // Focusing a tab alone must not switch the editor or discard a draft.
  await applyRecordsIfDirty(page);
  await expect(page.locator("#view-mcp")).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("Enter");
  await expect(analysisTab).toHaveAttribute("aria-selected", "true");
  await expect(page.locator(".draft-headerbar").getByRole("button", { name: "Apply analysis", exact: true }))
    .toHaveAttribute("title", /working copy.*Save the project/);
  for (const width of [1600, 1366, 1280, 1100, 800, 700]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const tab of ["Schedule", "Analysis", "Resources", "Measurements", "Databases", "MCP"]) {
      await page.locator(".ribbon-tabs").getByRole("tab", { name: tab, exact: true }).click();
      await expect.poll(() => page.locator(".ribbon").evaluate(element =>
        element.scrollWidth <= element.clientWidth,
      ), { message: `${tab} ribbon should fit at ${width}px` }).toBe(true);
    }
  }
  const originalFontSize = await page.locator("html").evaluate(element => {
    const previous = element.style.fontSize;
    element.style.fontSize = "20px";
    return previous;
  });
  await page.setViewportSize({ width: 1100, height: 1000 });
  for (const tab of ["Schedule", "Analysis", "Resources", "Measurements", "Databases", "MCP"]) {
    await page.locator(".ribbon-tabs").getByRole("tab", { name: tab, exact: true }).click();
    await expect.poll(() => page.locator(".ribbon").evaluate(element =>
      element.scrollWidth <= element.clientWidth,
    ), { message: `${tab} ribbon should fit with enlarged system text` }).toBe(true);
  }
  await page.locator("html").evaluate((element, size) => { element.style.fontSize = size; }, originalFontSize);
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.screenshot({ path: "test-results/context-ribbon.png" });
});

test("category lifecycle, library category import and used-resource deletion", async ({
  page,
}) => {
  const { execFileSync } = await import("node:child_process");
  const fixture = resolve(directory, "categories.eproj");
  execFileSync(
    python,
    ["-m", "modern.e2e.create_fixture", fixture],
    { cwd: resolve("..") },
  );
  await openFixture(page, fixture);
  const openDialog = page.getByRole("dialog", {
    name: "Open project",
    exact: true,
  });
  await expect(openDialog).not.toBeVisible();
  const tabs = page.locator(".ribbon-tabs");
  const ribbon = page.locator(".ribbon");
  const header = page.locator(".titlebar");
  const grid = page.locator(".project-view:visible .project-main-grid");
  await tabs.getByRole("tab", { name: "Schedule", exact: true }).click();
  await ribbon
    .getByRole("button", { name: "Add category", exact: true })
    .click();
  const addCategory = page.getByRole("dialog", {
    name: "Add category",
    exact: true,
  });
  await addCategory.getByLabel("Category name").fill("Empty category");
  await addCategory
    .getByRole("button", { name: "Add category", exact: true })
    .click();
  await expect(addCategory).not.toBeVisible();
  const emptyCategory = grid
    .locator('.tabulator-row [tabulator-field="description"]')
    .filter({ hasText: "Empty category" });
  await emptyCategory.click();
  await ribbon
    .getByRole("button", { name: "Move item down", exact: true })
    .click();
  await expect(
    grid
      .locator(
        '.tabulator-row[data-kind="Group"] [tabulator-field="description"]',
      )
      .last(),
  ).toHaveText("Empty category");
  await emptyCategory.click();
  await ribbon.getByRole("button", { name: "Delete", exact: true }).click();
  const deletion = page.getByRole("dialog", {
    name: "Delete selected items",
    exact: true,
  });
  await expect(deletion).toContainText("0 items and 1 category");
  await deletion.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(emptyCategory).toBeVisible();
  await ribbon.getByRole("button", { name: "Delete", exact: true }).click();
  await deletion
    .getByRole("button", { name: "Delete selected", exact: true })
    .click();
  await expect(deletion).not.toBeVisible();
  await expect(emptyCategory).toHaveCount(0);
  await header.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(emptyCategory).toBeVisible();

  await attachDatabase(page, fixture);
  await ribbon.getByRole("button", { name: "Add item from database", exact: true }).click();
  const picker = page.getByRole("dialog", { name: "Add item from database", exact: true });
  await picker.locator('.tabulator-row[data-kind="Group"] [tabulator-field="description"]').filter({ hasText: /^Work$/ }).click();
  await picker.getByRole("button", { name: "Add selected items", exact: true }).click();
  await expect(picker).not.toBeVisible();
  await expect(
    grid
      .locator('.tabulator-row [tabulator-field="code"]')
      .filter({ hasText: /^A-copy$/ }),
  ).toBeVisible();

  await tabs.getByRole("tab", { name: "Resources", exact: true }).click();
  await ribbon.getByRole("button", { name: "Add item", exact: true }).click();
  const add = page.getByRole("dialog", { name: "Add item", exact: true });
  await add.getByLabel("New code").fill("UNUSED");
  await add.getByLabel("Description", { exact: true }).fill("Unused resource");
  await add.getByLabel("Category").fill("Materials");
  await add.getByRole("button", { name: "Add item", exact: true }).click();
  await expect(add).not.toBeVisible();
  await expect(grid).toContainText('UNUSED');
  const materials = grid
    .locator(
      '.tabulator-row[data-kind="Group"] [tabulator-field="description"]',
    )
    .filter({ hasText: /^Materials$/ });
  await materials.click();
  await ribbon.getByRole("button", { name: "Delete", exact: true }).click();
  await expect(deletion).toContainText("1 resource is used in analyses");
  await page.screenshot({
    path: "test-results/category-deletion.png",
    animations: "disabled",
  });
  await deletion
    .getByRole("button", { name: "Delete unused", exact: true })
    .click();
  await expect(deletion).not.toBeVisible();
  await expect(grid).not.toContainText("UNUSED");
  await expect(
    grid
      .locator('.tabulator-row [tabulator-field="code"]')
      .filter({ hasText: /^R$/ }),
  ).toBeVisible();
  await header.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(grid).toContainText("UNUSED");
  await materials.click();
  await ribbon.getByRole("button", { name: "Delete", exact: true }).click();
  await deletion
    .getByRole("button", { name: "Delete including used", exact: true })
    .click();
  await expect(deletion).not.toBeVisible();
  await expect(grid.locator(".tabulator-row")).toHaveCount(0);
  await header.getByRole("button", { name: "Undo", exact: true }).click();
  await tabs.getByRole("tab", { name: "Schedule", exact: true }).click();
  await expect(
    grid
      .locator('.tabulator-row [tabulator-field="rate"]')
      .filter({ hasText: /^20$/ }),
  ).toHaveCount(2);
});

test("selected resources can preview and apply library prices", async ({ page }) => {
  const { execFileSync } = await import("node:child_process");
  const project = resolve(directory, "project.eproj");
  const library = resolve(directory, "prices.eproj");
  for (const [file, rate] of [[project, "10"], [library, "25"]]) {
    execFileSync(python, ["-m", "modern.e2e.create_fixture", file, rate], {
      cwd: resolve(".."),
    });
  }
  await openFixture(page, project);
  const open = page.getByRole("dialog", { name: "Open project" });
  await expect(open).not.toBeVisible();

  const tabs = page.locator(".ribbon-tabs");
  const ribbon = page.locator(".ribbon");
  const grid = page.locator(".project-view:visible .project-main-grid");
  await tabs.getByRole("tab", { name: "Resources", exact: true }).click();
  await attachDatabase(page, library, "resources");
  await grid.getByText("Materials", { exact: true }).first().click();
  await ribbon.getByRole("button", { name: "Refresh selected rates from database", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Refresh selected rates from database", exact: true });
  const apply = dialog.getByRole("button", { name: "Apply database rates", exact: true });
  await expect(apply).toBeDisabled();
  await dialog.getByRole("button", { name: "Preview rate changes", exact: true }).click();
  await expect(dialog).toContainText("1 changed · 0 unchanged · 0 unmatched");
  await apply.click();
  await expect(dialog).not.toBeVisible();
  await expect(grid.getByText("25", { exact: true })).toBeVisible();

  await tabs.getByRole("tab", { name: "Schedule", exact: true }).click();
  const rate = grid.getByRole("row", { name: /A Foundation/ }).locator('[tabulator-field="rate"]');
  await expect(rate).toHaveText("50");
  await page.locator(".titlebar").getByRole("button", { name: "Undo", exact: true }).click();
  await expect(rate).toHaveText("20");
});

test("resource usage shows project totals and opens a referencing analysis", async ({ page }) => {
  const { execFileSync } = await import("node:child_process");
  const project = resolve(directory, "usage.eproj");
  execFileSync(python, ["-m", "modern.e2e.create_fixture", project], {
    cwd: resolve(".."),
  });
  await openFixture(page, project);
  const open = page.getByRole("dialog", { name: "Open project" });
  await expect(open).not.toBeVisible();
  await page.locator(".ribbon-tabs").getByRole("tab", { name: "Resources" }).click();
  const ribbon = page.locator(".ribbon");
  await ribbon.getByRole("button", { name: "Resource usage", exact: true }).click();
  const usage = page.getByRole("dialog", { name: "Resource usage" });
  const totals = usage.getByRole("table", { name: "Project resource totals" });
  await expect(totals.getByRole("cell", { name: "20.00", exact: true })).toBeVisible();
  await usage.getByRole("button", { name: "R", exact: true }).click();
  await expect(usage.getByRole("heading", { name: "Analyses using R" })).toBeVisible();
  await usage.getByRole("button", { name: "A Foundation", exact: true }).click();
  await expect(usage).not.toBeVisible();
  await expect(page.getByRole("heading", { name: "Foundation", exact: true })).toBeVisible();
});

test("schedule row colour is visible and undoable", async ({ page }) => {
  const { execFileSync } = await import("node:child_process");
  const project = resolve(directory, "colours.eproj");
  execFileSync(python, ["-m", "modern.e2e.create_fixture", project], { cwd: resolve("..") });
  const header = page.locator(".titlebar");
  await openFixture(page, project);
  const open = page.getByRole("dialog", { name: "Open project" });
  await expect(open).not.toBeVisible();
  await page.locator(".ribbon-tabs").getByRole("tab", { name: "Schedule" }).click();
  const ribbon = page.locator(".ribbon");
  const grid = page.locator(".project-view:visible .project-main-grid");
  const colour = ribbon.getByRole("button", { name: "Row colour…" });
  await grid.getByRole("gridcell", { name: "Work", exact: true }).first().click();
  await expect(colour).toBeDisabled();
  const row = grid.getByRole("row", { name: /A Foundation/ });
  await row.getByRole("gridcell", { name: "Foundation", exact: true }).click();
  await colour.click();
  const dialog = page.getByRole("dialog", { name: "Schedule row colour" });
  await dialog.getByRole("button", { name: "Colour #455a64", exact: true }).click();
  await dialog.getByRole("button", { name: "Apply colour" }).click();
  await expect(dialog).not.toBeVisible();
  // The colour must show without hover (even rows previously lost it to the shell surface).
  await page.mouse.move(1590, 990);
  await expect(row).toHaveCSS("background-color", "rgb(69, 90, 100)");
  await expect(row).toHaveCSS("color", "rgb(255, 255, 255)");
  await header.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(row).not.toHaveAttribute("data-schedule-colour", /./);
  await header.getByRole("button", { name: "Redo", exact: true }).click();
  await expect(row).toHaveAttribute("data-schedule-colour", /^#455a64$/i);
  await colour.click();
  await dialog.getByRole("button", { name: "Clear colour" }).click();
  await expect(row).not.toHaveAttribute("data-schedule-colour", /./);
  await ribbon.getByRole("button", { name: "Renumber schedule…" }).click();
  const renumber = page.getByRole("dialog", { name: "Renumber schedule" });
  await renumber.getByRole("button", { name: "Renumber", exact: true }).click();
  await expect(renumber).not.toBeVisible();
  const code = grid.getByRole("row", { name: /Foundation/ }).locator('[tabulator-field="code"]');
  await expect(code).toHaveText("1");
  await header.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(code).toHaveText("A");
});

test("in-place save keeps a backup and the project appears in recent projects", async ({ page }) => {
  const { execFileSync } = await import("node:child_process");
  const project = resolve(directory, "save.eproj");
  execFileSync(python, ["-m", "modern.e2e.create_fixture", project], { cwd: resolve("..") });
  const original = await readFile(project);
  const header = page.locator(".titlebar");
  await openFixture(page, project);
  const open = page.getByRole("dialog", { name: "Open project" });
  await expect(open).not.toBeVisible();
  await page.locator(".ribbon-tabs").getByRole("tab", { name: "Schedule" }).click();
  const quantity = page.locator('.project-main-grid .tabulator-row [tabulator-field="qty"]').last();
  await expect(quantity).toHaveText("1");
  await quantity.dblclick();
  await quantity.locator("input,textarea").fill("8");
  await page.locator(".tabulator-header:visible").click();
  await expect(quantity).toHaveText("8");
  await expect(page.locator(".statusbar")).toContainText("Unsaved draft");
  await expect(header.getByRole("button", { name: "Save copy" })).toBeEnabled();
  await page.keyboard.press("Control+s");
  await expect(page.locator(".statusbar")).toContainText("Saved");
  expect(await readFile(project + ".bak")).toEqual(original);
  expect(await readFile(project)).not.toEqual(original);
  await header.getByRole("button", { name: "Open project" }).click();
  await open.getByLabel("Recent projects").selectOption({ label: project });
  await expect(open.getByLabel("Project file")).toHaveValue(project);
});

test("Excel analysis import previews a calculated rate and can be undone", async ({ page }) => {
  const { execFileSync } = await import("node:child_process");
  const project = resolve(directory, "analysis-import.eproj");
  const workbook = resolve(directory, "analysis.xlsx");
  execFileSync(python, ["-m", "modern.e2e.create_fixture", project], { cwd: resolve("..") });
  execFileSync(python, ["-c", [
    "import sys",
    "from openpyxl import Workbook",
    "book = Workbook()",
    "for row in [('EXT','Item'), (None,'Cost of concrete'), ('Code','Description','Unit','Qty','Rate','Amount'), (None,'MATERIALS'), ('X','Cement','kg',3,7,21), (None,'TOTAL MATERIALS',None,None,None,21)]:",
    "    book.active.append(row)",
    "book.save(sys.argv[1])",
  ].join("\n"), workbook]);
  const header = page.locator(".titlebar");
  await openFixture(page, project);
  const open = page.getByRole("dialog", { name: "Open project" });
  await expect(open).not.toBeVisible();
  await page.getByRole("navigation", { name: "Schedule items" }).getByRole("button", { name: /A Foundation/ }).click();
  await page.locator(".ribbon").getByRole("button", { name: "Import analysis" }).click();
  const dialog = page.getByRole("dialog", { name: "Import analysis from Excel" });
  await dialog.getByLabel(/Workbook/).fill(workbook);
  await dialog.getByLabel(/Workbook/).press("Enter");
  // The worksheet preview starts at A1 (the item code); the parsed analysis is listed.
  await expect(dialog.getByRole("grid", { name: "Worksheet preview" })).toContainText("Cement");
  await expect(dialog.getByRole("status").filter({ hasText: "rate" })).toContainText("rate 21.00");
  await expect(dialog.getByRole("region", { name: "Import preview" })).toContainText("Cement");
  await page.screenshot({ path: "test-results/analysis-import.png", animations: "disabled" });
  await dialog.getByRole("button", { name: "Replace analysis draft" }).click();
  await expect(dialog).not.toBeVisible();
  await expect(page.locator(".summary-value")).toContainText("21.00");
  await header.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(page.locator(".summary-value")).toContainText("20.00");
});


test("optional enrichment is labelled and clearing it is undoable", async ({ page }) => {
  const { execFileSync } = await import("node:child_process");
  const project = resolve(directory, "enriched.eproj");
  execFileSync(python, ["-m", "modern.e2e.create_fixture", project], { cwd: resolve("..") });
  execFileSync(python, ["-c", "import sys;from estimator.data.schedule import ScheduleDatabase;from estimator.undo import Stack;from modern.backend.metadata import write;d=ScheduleDatabase(Stack());d.open_database(sys.argv[1]);write(d,dict(schema=1,provenance=dict(generator='ai',reviewed=False),database=dict(summary='Sample database overview')));d.close_database()", project], { cwd: resolve("..") });
  const original = await readFile(project);
  await openFixture(page, project);
  await applyRecordsIfDirty(page);
  await page.locator("#view-schedule").click();
  await expect(page.getByText("AI-generated", { exact: true })).toBeVisible();
  await expect(page.getByText("Sample database overview", { exact: true })).toBeVisible();
  await page.screenshot({ path: "test-results/enrichment.png", animations: "disabled" });
  await page.getByRole("button", { name: "Clear enrichment", exact: true }).click();
  await expect(page.getByText("AI-generated", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(page.getByText("AI-generated", { exact: true })).toBeVisible();
  expect(await readFile(project)).toEqual(original);
});

test("feedback: native open, cached navigation, incremental refresh and analysis limits", async ({ page }) => {
  await refinementFixture(page);
  await expect(page.getByRole("dialog", { name: "Open project", exact: true })).toHaveCount(0);
  await expect(page.locator(".explorer")).not.toBeVisible();
  const grid = page.locator(".project-view:visible .project-main-grid");
  const item = grid.locator('[tabulator-field="description"]').filter({ hasText: /^Foundation$/ });
  await item.click();
  await grid.evaluate(element => (element as any).retained = true);
  await page.locator(".ribbon").getByRole("button", { name: "Edit analysis", exact: true }).click();
  await expect(page.locator(".explorer")).toBeVisible();
  const analysis = page.getByRole("grid", { name: "Rate analysis table" });
  await expect(analysis.locator('.tabulator-col[tabulator-field="rate"],.tabulator-col[tabulator-field="vat"],.tabulator-col[tabulator-field="discount"]')).toHaveCount(0);
  await expect(analysis.locator('.tabulator-col[tabulator-field="effective_rate"]')).toContainText("RATE");
  await expect(page.getByRole("button", { name: "Compact rows", exact: true })).toHaveCount(0);
  const resource = analysis.locator('.tabulator-row[data-kind="Resource"]').first();
  await resource.locator('[tabulator-field="description"]').dblclick();
  await expect(resource.locator("textarea")).toHaveCount(0);
  const quantity = resource.locator('[tabulator-field="value"]');
  await quantity.dblclick();
  await quantity.locator("input").fill("3");
  await page.locator(".analysis-heading h1").click();
  frontendCalls = [];
  await page.locator(".draft-headerbar").getByRole("button", { name: "Apply analysis", exact: true }).click();
  await expect(grid.locator('[tabulator-field="rate"]').filter({ hasText: /^30$/ })).toBeVisible();
  await expect(grid).toHaveJSProperty("retained", true);
  await expect(item.locator("..")).toHaveClass(/tabulator-selected/);
  expect(frontendCalls.some(c => c.method === "schedule.editor.state" && typeof c.params.since === "number")).toBe(true);
  await applyRecordsIfDirty(page);
  await page.getByRole("button", { name: "Go back", exact: true }).click();
  await applyRecordsIfDirty(page);
  await expect(page.locator("#view-analysis")).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("Alt+ArrowRight");
  await applyRecordsIfDirty(page);
  await expect(page.locator("#view-schedule")).toHaveAttribute("aria-selected", "true");
  await expect(page.locator(".explorer")).not.toBeVisible();
});

test("feedback: custom resources generate codes and database picker adds multiple", async ({ page }) => {
  await refinementFixture(page);
  const grid = page.locator(".project-view:visible .project-main-grid");
  await grid.locator('[tabulator-field="description"]').filter({ hasText: /^Foundation$/ }).click();
  await page.locator(".ribbon").getByRole("button", { name: "Edit analysis", exact: true }).click();
  await page.getByRole("button", { name: "Add custom resource", exact: true }).click();
  const custom = page.getByRole("dialog", { name: "Add custom resource", exact: true });
  await expect(custom.getByLabel("Description")).toBeFocused();
  await custom.getByLabel("Description").fill("Custom resource without code");
  await custom.getByLabel("Unit", { exact: true }).fill("kg");
  await custom.getByLabel("Base rate").fill("5");
  await custom.getByRole("button", { name: "Add resource", exact: true }).click();
  const analysis = page.getByRole("grid", { name: "Rate analysis table" });
  await expect(analysis).toContainText("MR.1");
  await page.getByRole("button", { name: "Add resources from database", exact: true }).click();
  const picker = page.getByRole("dialog", { name: "Add analysis resources from database", exact: true });
  await expect(picker.getByLabel("Find database items")).toBeFocused();
  const rows = picker.locator('.tabulator-row[data-kind="Resource"]');
  await expect(rows).toHaveCount(2);
  const first = await rows.first().boundingBox(); const last = await rows.last().boundingBox();
  await page.mouse.move(first!.x + 100, first!.y + 10); await page.mouse.down();
  await page.mouse.move(last!.x + 180, last!.y + 10, { steps: 8 }); await page.mouse.up();
  await expect(picker.locator('.tabulator-row.tabulator-selected')).toHaveCount(2);
  await picker.getByRole("button", { name: "Add selected items", exact: true }).click();
  await expect(analysis.locator('.tabulator-row[data-kind="Resource"]')).toHaveCount(4);
  await page.getByRole("tab", { name: "Resources", exact: true }).last().click();
  await page.getByRole("navigation", { name: "Resource library" }).getByRole("button").filter({ hasText: "Material" }).click();
  await expect(analysis.locator('.tabulator-row[data-kind="Resource"]')).toHaveCount(5);
  await expect(page.getByRole("dialog", { name: "Add custom resource", exact: true })).toHaveCount(0);
});

test("feedback: measurements use categories and a separate reusable entry view", async ({ page }) => {
  await refinementFixture(page);
  await applyRecordsIfDirty(page);
  await page.locator("#view-measurement").click();
  const ribbon = page.locator(".ribbon");
  await ribbon.getByRole("button", { name: "Add category", exact: true }).click();
  const category = page.getByRole("dialog", { name: "Add category", exact: true });
  await category.getByLabel("Category name").fill("Ground floor");
  await category.getByRole("button", { name: "Add category", exact: true }).click();
  await ribbon.getByRole("button", { name: "Add measurement", exact: true }).click();
  const add = page.getByRole("dialog", { name: "Add item", exact: true });
  await add.getByLabel("Description / remarks").fill("Room dimensions");
  await add.getByRole("button", { name: "Add item", exact: true }).click();
  const list = page.locator(".project-view:visible .project-main-grid");
  await expect(list).toContainText("Ground floor");
  await expect(list).toContainText("Room dimensions");
  await expect(page.getByLabel("Measurement caption")).toHaveCount(0);
  await expect(page.locator(".measurement-record-grid")).toHaveCount(0);
  await list.getByText("Room dimensions", { exact: true }).dblclick();
  await expect(list).not.toBeVisible();
  await expect(page.getByRole("button", { name: "Discard records", exact: true })).toBeVisible();
  await expect(page.locator(".measurement-record-grid")).toBeVisible();
  await page.getByRole("button", { name: "Add record", exact: true }).click();
  const record = page.locator('.measurement-record-grid .tabulator-row').first();
  const before = (await record.boundingBox())!.height;
  await record.locator('[tabulator-field="c3"]').dblclick();
  await expect(record.locator("textarea")).toBeVisible();
  expect((await record.boundingBox())!.height).toBeLessThanOrEqual(before + 2);
  await record.locator("textarea").fill("3");
  await page.locator(".measurement-entry-heading").click();
  await page.getByRole("button", { name: "Choose schedule item 1", exact: true }).click();
  const picker = page.getByRole("dialog", { name: "Choose schedule item", exact: true });
  await picker.getByLabel("Find linked schedule item").evaluate(el => (el as any).retained = true);
  await picker.getByRole("button", { name: "Close dialog", exact: true }).click();
  await page.getByRole("button", { name: "Choose schedule item 1", exact: true }).click();
  await expect(picker.getByLabel("Find linked schedule item")).toHaveJSProperty("retained", true);
  expect(await picker.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
  await picker.getByRole("button", { name: "Close dialog", exact: true }).click();
  await applyRecordsIfDirty(page);
  await finishMeasurementEntry(page);
  await expect(list).toBeVisible();
  const summaryRow = list.locator('.tabulator-row').filter({ has: page.getByText("Room dimensions", { exact: true }) });
  await expect(summaryRow.locator('[tabulator-field="count"]')).toHaveText("1");
  await applyRecordsIfDirty(page);
  await page.getByRole("button", { name: "Go back", exact: true }).click();
  await expect(page.locator(".measurement-record-grid")).toBeVisible();
  await page.screenshot({ path: "test-results/feedback-measurement-entry.png", animations: "disabled" });
});

test("feedback: scroll position, zero formatting, palette and native save/export", async ({ page }) => {
  const { execFileSync } = await import("node:child_process");
  const path = resolve(directory, "scroll.eproj");
  execFileSync(python, ["-m", "modern.e2e.create_fixture", path], { cwd: resolve("..") });
  execFileSync(python, ["-c", "import sys;from estimator.data.schedule import ScheduleDatabase,ScheduleItemModel;from estimator.undo import Stack;d=ScheduleDatabase(Stack());d.open_database(sys.argv[1]);[d.insert_item_atomic(ScheduleItemModel(str(i),'Item '+str(i),'m',rate=0,qty=0,category='Work')) for i in range(80)];d.close_database()", path], { cwd: resolve("..") });
  await openFixture(page, path);
  await applyRecordsIfDirty(page);
  await page.locator("#view-schedule").click();
  const grid = page.locator(".project-view:visible .project-main-grid");
  const zero = grid.locator('.tabulator-row').filter({ has: page.locator('[tabulator-field="description"]').filter({ hasText: /^Item 0$/ }) });
  await expect(zero.locator('[tabulator-field="rate"]')).toBeEmpty();
  await expect(zero.locator('[tabulator-field="qty"]')).toBeEmpty();
  const nextRow = grid.locator('.tabulator-row').filter({ has: page.locator('[tabulator-field="description"]').filter({ hasText: /^Item 1$/ }) });
  const start = (await zero.locator('[tabulator-field="description"]').boundingBox())!;
  const end = (await nextRow.locator('[tabulator-field="qty"]').boundingBox())!;
  await page.mouse.move(start.x + start.width / 2, start.y + start.height / 2);
  await page.mouse.down();
  await page.mouse.move(end.x + end.width / 2, end.y + end.height / 2, { steps: 6 });
  await page.mouse.up();
  await expect(grid.locator('.tabulator-row.tabulator-selected')).toHaveCount(2);
  await expect(grid.locator('.cell-range-selected')).toHaveCount(8);
  expect(await page.evaluate(() => window.getSelection()?.toString())).toBe("");
  await zero.locator('[tabulator-field="description"]').click();
  await page.getByRole("button", { name: "Row colour…", exact: true }).click();
  const colour = page.getByRole("dialog", { name: "Schedule row colour" });
  await expect(colour.locator('input[type="color"]')).toHaveCount(0);
  await expect(colour.getByRole("group", { name: "Row colour palette" }).getByRole("button")).toHaveCount(16);
  await colour.getByRole("button", { name: "Close", exact: true }).click();
  const holder = grid.locator(".tabulator-tableholder");
  await holder.evaluate(element => element.scrollTop = 700);
  await expect.poll(() => holder.evaluate(element => element.scrollTop)).toBe(700);
  await applyRecordsIfDirty(page);
  await page.locator("#view-resources").click();
  await applyRecordsIfDirty(page);
  await page.locator("#view-schedule").click();
  await expect.poll(() => holder.evaluate(element => element.scrollTop)).toBe(700);
  const copy = resolve(directory, "copied.eproj");
  nativeDialogResults.push(copy);
  await page.locator(".titlebar").getByRole("button", { name: "Save copy", exact: true }).click();
  await expect.poll(async () => readFile(copy).then(() => true).catch(() => false)).toBe(true);
  await expect(page.getByRole("dialog", { name: "Save project copy" })).toHaveCount(0);
  const workbook = resolve(directory, "exported.xlsx");
  nativeDialogResults.push(workbook);
  await page.locator(".ribbon").getByRole("button", { name: "Export workbook", exact: true }).click();
  await expect.poll(async () => readFile(workbook).then(() => true).catch(() => false)).toBe(true);
  await expect(page.getByRole("dialog", { name: "Export project workbook" })).toHaveCount(0);
});

test("feedback: analysis and measurement records share cell-range dragging", async ({ page }) => {
  await refinementFixture(page);
  await page.locator('.project-view:visible [tabulator-field="description"]').filter({ hasText: /^Foundation$/ }).click();
  await page.getByRole("button", { name: "Edit analysis", exact: true }).click();
  const analysis = page.getByRole("grid", { name: "Rate analysis table" });
  const first = analysis.locator('.tabulator-row[data-kind="Resource"] [tabulator-field="description"]').first();
  const last = analysis.locator('.tabulator-row[data-kind="Subtotal"] [tabulator-field="value"]').first();
  const drag = async (from: ReturnType<Page["locator"]>, to: ReturnType<Page["locator"]>) => {
    const start = (await from.boundingBox())!, end = (await to.boundingBox())!;
    await page.mouse.move(start.x + start.width / 2, start.y + start.height / 2);
    await page.mouse.down();
    await page.mouse.move(end.x + end.width / 2, end.y + end.height / 2, { steps: 8 });
    await page.mouse.up();
  };
  await drag(first, last);
  await expect(analysis.locator('.tabulator-row.tabulator-selected')).toHaveCount(2);
  await expect(analysis.locator('.cell-range-selected')).toHaveCount(6);
  expect(await page.evaluate(() => window.getSelection()?.toString())).toBe("");
  await page.screenshot({ path: "test-results/analysis-cell-selection.png", animations: "disabled" });
  await analysis.focus();
  await page.keyboard.press("Escape");
  await expect(analysis.locator('.cell-range-selected')).toHaveCount(0);
  await applyRecordsIfDirty(page);
  await page.locator('#view-measurement').click();
  await page.getByRole("button", { name: "Add measurement", exact: true }).click();
  const add = page.getByRole("dialog", { name: "Add item", exact: true });
  await add.getByLabel("Description / remarks").fill("Drag entry");
  await add.getByRole("button", { name: "Add item", exact: true }).click();
  await openMeasurementEntry(page);
  await page.getByRole("button", { name: "Add record", exact: true }).click();
  await page.getByRole("button", { name: "Add record", exact: true }).click();
  const records = page.locator('.measurement-record-grid');
  await expect(records.locator('.tabulator-row')).toHaveCount(2);
  await drag(records.locator('.tabulator-row [tabulator-field="c0"]').first(), records.locator('.tabulator-row [tabulator-field="c2"]').last());
  await expect(records.locator('.tabulator-row.tabulator-selected')).toHaveCount(2);
  await expect(records.locator('.cell-range-selected')).toHaveCount(6);
  expect(await page.evaluate(() => window.getSelection()?.toString())).toBe("");
  await page.screenshot({ path: "test-results/measurement-cell-selection.png", animations: "disabled" });
  await records.locator('.tabulator-row [tabulator-field="c0"]').first().dblclick();
  await expect(records.locator('textarea')).toBeFocused();
});

test("feedback 2: shared alignment, pane icons, resource actions and dialog focus", async ({ page }) => {
  await refinementFixture(page);
  const ribbon = page.locator('.ribbon');
  for (const view of ['schedule', 'resources']) {
    await applyRecordsIfDirty(page);
    await page.locator('#view-' + view).click();
    const bar = page.locator('.project-view:visible .project-filter-bar').filter({ has: page.getByLabel('Search project table') });
    const search = (await bar.locator('form').boundingBox())!, category = (await bar.getByRole('button', { name: 'Filter categories' }).boundingBox())!;
    expect(Math.abs(search.y - category.y)).toBeLessThan(1);
    expect(Math.abs(search.height - category.height)).toBeLessThan(1);
    const duplicate = (await ribbon.getByRole('button', { name: 'Duplicate', exact: true }).locator('svg').boundingBox())!;
    const add = (await ribbon.getByRole('button', { name: 'Add item', exact: true }).locator('svg').boundingBox())!;
    expect(Math.abs(duplicate.y - add.y)).toBeLessThan(1);
  }
  for (const action of ['Edit resource', 'Move resources…']) {
    const group = ribbon.locator('.ribbon-group').filter({ has: page.getByRole('button', { name: action, exact: true }) });
    await expect(group.locator('small')).toHaveText('EDIT');
  }
  await ribbon.getByRole('button', { name: 'Add item', exact: true }).click();
  const add = page.getByRole('dialog', { name: 'Add item', exact: true });
  await expect(add.getByLabel('Description', { exact: true })).toBeFocused();
  await add.getByRole('button', { name: 'Cancel', exact: true }).click();
  await expect(add).not.toBeVisible();
  for (let attempt = 0; attempt < 2; attempt++) {
    await ribbon.getByRole('button', { name: 'Add category', exact: true }).click();
    const category = page.getByRole('dialog', { name: 'Add category', exact: true });
    await expect(category.getByLabel('Category name')).toBeFocused();
    await category.getByRole('button', { name: 'Close', exact: true }).click();
    await expect(category).not.toBeVisible();
  }
  await applyRecordsIfDirty(page);
  await page.locator('#view-analysis').click();
  await expect(ribbon.getByRole('button', { name: 'Hide explorer', exact: true }).locator('svg')).toHaveAttribute('data-icon', 'panel-left');
  await expect(ribbon.getByRole('button', { name: 'Hide analysis inspector', exact: true })).not.toHaveClass(/ribbon-icon/);
  await expect(ribbon.getByRole('button', { name: 'Delete', exact: true })).toHaveCSS('color', 'rgb(252, 165, 165)');
});

test("feedback 2: contextual measurement ribbon, hierarchy and keyboard return", async ({ page }) => {
  await refinementFixture(page);
  const grid = page.locator('.project-view:visible .project-main-grid .project-grid');
  await grid.getByText('Foundation', { exact: true }).click();
  await page.keyboard.press('ControlOrMeta+e');
  await expect(page.getByRole('grid', { name: 'Rate analysis table' })).toBeFocused();
  await applyRecordsIfDirty(page);
  await page.keyboard.press('Alt+ArrowLeft');
  await expect(grid).toBeFocused();
  await page.keyboard.press('ControlOrMeta+e');
  await expect(page.getByRole('grid', { name: 'Rate analysis table' })).toBeFocused();
  await page.getByRole('button', { name: 'Discard analysis', exact: true }).click();
  await expect(grid).toBeFocused();
  await applyRecordsIfDirty(page);
  await page.locator('#view-measurement').click();
  await page.getByRole('button', { name: 'Add category', exact: true }).click();
  const category = page.getByRole('dialog', { name: 'Add category', exact: true });
  await category.getByLabel('Category name').fill('First floor');
  await category.getByRole('button', { name: 'Add category', exact: true }).click();
  await page.getByRole('button', { name: 'Add measurement', exact: true }).click();
  const add = page.getByRole('dialog', { name: 'Add item', exact: true });
  await expect(add.getByLabel('Description / remarks')).toBeFocused();
  await add.getByLabel('Description / remarks').fill('Room dimensions');
  await add.getByRole('button', { name: 'Add item', exact: true }).click();
  await expect(add).not.toBeVisible();
  await expect(page.locator('.p-dialog-mask')).toHaveCount(0);
  await expect(grid.locator('.tabulator-row[data-kind="Group"] [tabulator-field="type"]')).toBeEmpty();
  await expect(grid.locator('.tabulator-col').first()).toHaveAttribute('tabulator-field', 'description');
  await grid.focus();
  await page.keyboard.press('End');
  await page.keyboard.press('Enter');
  const records = page.locator('.measurement-record-grid .project-grid');
  await expect(records).toBeFocused();
  const ribbon = page.locator('.ribbon');
  await expect(ribbon.getByRole('button', { name: 'Add record', exact: true })).toBeVisible();
  await expect(ribbon.getByRole('button', { name: 'Add category', exact: true })).toHaveCount(0);
  await expect(ribbon.getByRole('button', { name: 'Add measurement', exact: true })).toHaveCount(0);
  await applyRecordsIfDirty(page);
  await expect(page.locator('#view-measurement')).toHaveClass(/record-context/);
  await expect(ribbon.getByRole('button', { name: 'Delete record', exact: true })).toHaveCSS('color', 'rgb(252, 165, 165)');
  await page.keyboard.press('ControlOrMeta+i');
  await expect(records.locator('.tabulator-row')).toHaveCount(1);
  await page.screenshot({ path: 'test-results/contextual-measurement-ribbon.png', animations: 'disabled' });
  await applyRecordsIfDirty(page);
  await finishMeasurementEntry(page);
  await expect(grid).toBeFocused();
  await expect(grid.locator('.tabulator-selected')).toContainText('Room dimensions');
  await page.screenshot({ path: 'test-results/measurement-category-hierarchy.png', animations: 'disabled' });
  await applyRecordsIfDirty(page);
  await expect(page.locator('#view-measurement')).not.toHaveClass(/record-context/);
  await page.keyboard.press('Enter');
  await expect(records).toBeFocused();
});

test("feedback 2: drag selection scrolls past both edges in editors and database pickers", async ({ page }) => {
  const { execFileSync } = await import('node:child_process');
  const path = resolve(directory, 'drag-scroll.eproj');
  execFileSync(python, ['-m', 'modern.e2e.create_fixture', path], { cwd: resolve('..') });
  execFileSync(python, ['-c', "import sys;from estimator.data.schedule import ScheduleDatabase,ScheduleItemModel,ResourceItemModel;from estimator.undo import Stack;d=ScheduleDatabase(Stack());d.open_database(sys.argv[1]);[(d.insert_item_atomic(ScheduleItemModel('Z'+str(i),'Work '+str(i),'m',category='Work')),d.insert_resource(ResourceItemModel('Z'+str(i),'Resource '+str(i),'kg',0,category='Materials'))) for i in range(80)];d.close_database()", path], { cwd: resolve('..') });
  await openFixture(page, path);
  await attachDatabase(page, path);
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  const dragEdges = async (holder: ReturnType<Page['locator']>) => {
    await expect(holder.locator('..')).toHaveAttribute('aria-busy', 'false');
    await expect(holder.locator('.tabulator-row').first()).toBeVisible();
    await holder.evaluate(el => el.scrollTop = 0);
    await expect.poll(() => holder.evaluate(el => el.scrollTop)).toBe(0);
    const bounds = (await holder.boundingBox())!;
    const x = bounds.x + Math.min(310, bounds.width / 2);
    await page.mouse.move(x, bounds.y + 60);
    await page.mouse.down();
    await page.mouse.move(x, bounds.y + bounds.height + 18, { steps: 8 });
    await expect.poll(() => holder.evaluate(el => el.scrollTop)).toBeGreaterThan(350);
    await page.mouse.up();
    await expect(holder.locator('.tabulator-selected').first()).toBeAttached();
    await page.mouse.move(x, bounds.y + 60);
    await page.mouse.down();
    await page.mouse.move(x, bounds.y - 20, { steps: 8 });
    await expect.poll(() => holder.evaluate(el => el.scrollTop)).toBeLessThan(10);
    await page.mouse.up();
  };
  for (const kind of ['schedule', 'resources']) {
    await applyRecordsIfDirty(page);
    await page.locator('#view-' + kind).click();
    await dragEdges(page.locator('.project-view:visible .tabulator-tableholder').first());
    const title = kind === 'schedule' ? 'Add item from database' : 'Add resources from database';
    await page.getByRole('button', { name: title, exact: true }).click();
    const picker = page.getByRole('dialog', { name: title, exact: true });
    await expect(picker.getByLabel('Find database items')).toBeFocused();
    await dragEdges(picker.locator('.tabulator-tableholder'));
    await expect(picker.locator('.cell-range-selected')).toHaveCount(0);
    await picker.getByRole('button', { name: 'Cancel', exact: true }).click();
  }
  expect(errors).toEqual([]);
});


test('feedback 3: measurement category editing, record caption and list actions', async ({ page }) => {
  await refinementFixture(page);
  const scheduleDescription = 'Scope starts. ' + 'Allow for all associated building and civil works. '.repeat(24) + 'Scope ends.';
  const scheduleCell = page.locator('.project-main-grid:visible [tabulator-field="description"]').getByText('Foundation', { exact: true });
  await scheduleCell.dblclick();
  const scheduleEditor = page.locator('.project-main-grid:visible [tabulator-field="description"] textarea');
  await scheduleEditor.fill(scheduleDescription);
  await scheduleEditor.press('Enter');
  await expect(page.locator('.project-main-grid:visible')).toContainText('Scope ends.');
  await applyRecordsIfDirty(page);
  await page.locator('#view-measurement').click();
  const ribbon = page.locator('.ribbon');
  await ribbon.getByRole('button', { name: 'Add category', exact: true }).click();
  const addCategory = page.getByRole('dialog', { name: 'Add category', exact: true });
  await addCategory.getByLabel('Category name').fill('Initial floor');
  await addCategory.getByRole('button', { name: 'Add category', exact: true }).click();
  await expect(addCategory).not.toBeVisible();
  const grid = page.getByRole('grid', { name: 'Measurements', exact: true });
  const categoryCell = grid.locator('.tabulator-row[data-kind="Group"] [tabulator-field="description"]').first();
  await categoryCell.dblclick();
  const category = page.getByRole('dialog', { name: 'Edit measurement category', exact: true });
  await expect(category.getByLabel('Category name')).toBeFocused();
  await category.getByLabel('Category name').fill('Ground floor');
  await category.getByRole('button', { name: 'Save properties', exact: true }).click();
  await expect(category).not.toBeVisible();
  await expect(categoryCell).toContainText('Ground floor');
  await categoryCell.click();
  await grid.focus();
  await page.keyboard.press('Enter');
  await expect(category.getByLabel('Category name')).toBeFocused();
  await category.getByLabel('Category name').fill('First floor');
  await category.getByRole('button', { name: 'Save properties', exact: true }).click();
  await expect(category).not.toBeVisible();
  await expect(categoryCell).toContainText('First floor');
  await ribbon.getByRole('button', { name: 'Add measurement', exact: true }).click();
  const add = page.getByRole('dialog', { name: 'Add item', exact: true });
  await expect(add).not.toContainText('GTK');
  await add.getByLabel('Description / remarks').fill('Room dimensions');
  await add.getByRole('button', { name: 'Add item', exact: true }).click();
  await expect(add).not.toBeVisible();
  await expect(ribbon.getByRole('button', { name: 'Edit records', exact: true })).toBeEnabled();
  await ribbon.getByRole('button', { name: 'Properties…', exact: true }).click();
  const properties = page.getByRole('dialog', { name: 'Measurement properties', exact: true });
  await expect(properties.getByLabel('Description / remarks')).toHaveValue('Room dimensions');
  await properties.getByRole('button', { name: 'Cancel', exact: true }).click();
  await ribbon.getByRole('button', { name: 'Edit records', exact: true }).click();
  const caption = page.getByLabel('Measurement description / remarks', { exact: true });
  const editDescription = page.getByRole('button', { name: 'Edit measurement description / remarks', exact: true });
  const heading = page.locator('.measurement-entry-heading h2');
  await expect(heading).toHaveText('Room dimensions');
  await expect(caption).toHaveCount(0);
  await editDescription.click();
  await expect(caption).toBeFocused();
  await caption.fill('Discarded inline edit');
  await caption.press('Escape');
  await expect(heading).toHaveText('Room dimensions');
  await editDescription.click();
  const description = 'First floor dimensions. ' + 'Include all recesses and openings. '.repeat(22) + 'End of remarks.';
  await caption.fill(description);
  expect(await caption.evaluate(el => el.clientHeight <= parseFloat(getComputedStyle(el).lineHeight) * 5 + 1)).toBe(true);
  await caption.press('Enter');
  await expect(heading).toHaveAttribute('title', description);
  await expect(heading).toHaveText(/^First floor dimensions\..+….+End of remarks\.$/);
  const wideTitle = await heading.textContent();
  await page.setViewportSize({ width: 820, height: 1000 });
  await expect.poll(async () => (await heading.textContent())!.length).toBeLessThan(wideTitle!.length);
  expect(await heading.evaluate(el => el.scrollHeight <= el.clientHeight && el.clientHeight <= parseFloat(getComputedStyle(el).lineHeight) * 5 + 1)).toBe(true);
  const link = page.getByLabel('Schedule code 1', { exact: true });
  await link.fill('A');
  await link.press('Tab');
  const linkedDescription = page.locator('.measurement-links .five-line-description').first();
  await expect(linkedDescription).toHaveText(/^Scope starts\..+….+Scope ends\. \(m3\)$/);
  await expect(linkedDescription).toHaveAttribute('title', scheduleDescription);
  expect(await linkedDescription.evaluate(el => el.scrollHeight <= el.clientHeight && el.clientHeight <= parseFloat(getComputedStyle(el).lineHeight) * 5 + 1)).toBe(true);
  await applyRecordsIfDirty(page);
  await finishMeasurementEntry(page);
  await expect(grid).toContainText(description.trim());
  await ribbon.getByRole('button', { name: 'Properties…', exact: true }).click();
  await expect(properties.getByLabel('Description / remarks')).toHaveValue(description);
  const code = properties.getByLabel('Property schedule code 1', { exact: true });
  const remark = properties.getByLabel('Property item remark 1', { exact: true });
  const codeBox = (await code.boundingBox())!, remarkBox = (await remark.boundingBox())!;
  expect(remarkBox.y - codeBox.y - codeBox.height).toBeGreaterThanOrEqual(10);
  await code.focus();
  await page.screenshot({ path: 'test-results/measurement-properties-spacing.png', animations: 'disabled' });
});

test('feedback 3: text editor preserves indentation typography and row geometry', async ({ page }) => {
  await refinementFixture(page);
  const checkEditor = async (cell: ReturnType<Page['locator']>, tree: boolean) => {
    const before = await cell.evaluate(el => {
      const row = el.closest('.tabulator-row')!, style = getComputedStyle(el), r = el.getBoundingClientRect();
      const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
      let text: Node | null = null;
      while (walker.nextNode()) if (walker.currentNode.textContent?.trim()) { text = walker.currentNode; break; }
      const range = document.createRange();
      if (text) range.selectNodeContents(text);
      const box = text ? range.getBoundingClientRect() : undefined;
      return { height: row.getBoundingClientRect().height, font: style.fontFamily, weight: style.fontWeight, x: box?.x ?? r.x + parseFloat(style.paddingLeft), y: box?.y ?? r.y + parseFloat(style.paddingTop), weights: Array.from(row.querySelectorAll('.tabulator-cell')).map(e => getComputedStyle(e).fontWeight) };
    });
    await cell.dblclick();
    const input = cell.locator('textarea,input');
    await expect(input).toBeFocused();
    await expect(input).toHaveCSS('font-weight', before.weight);
    if (tree) await expect(cell.locator('.table-text-editor-shell .tabulator-data-tree-branch')).toBeVisible();
    const bounds = (await input.boundingBox())!;
    expect(Math.abs(bounds.x - before.x)).toBeLessThanOrEqual(2);
    expect(Math.abs(bounds.y - before.y)).toBeLessThanOrEqual(2);
    expect(await cell.evaluate(el => Array.from(el.closest('.tabulator-row')!.querySelectorAll('.tabulator-cell')).map(e => getComputedStyle(e).fontWeight))).toEqual(before.weights);
    await input.press('End');
    await page.keyboard.insertText('x');
    expect(Math.abs((await cell.locator('..').boundingBox())!.height - before.height)).toBeLessThanOrEqual(1);
    await input.press('Escape');
    await expect(cell).toBeFocused();
    await page.keyboard.press('F2');
    await expect(input).toBeFocused();
    await input.press('Escape');
    await expect(cell).toBeFocused();
    if (tree) {
      const branch = cell.locator(':scope > .tabulator-data-tree-branch');
      await expect(branch).toBeVisible();
      await cell.dblclick();
      await input.press('Enter');
      await expect(branch).toBeVisible();
      await cell.dblclick();
      await input.fill('Revised description\nSecond description line');
      await input.press('Enter');
      await expect(cell).toHaveText('Revised description\nSecond description line');
      const committedHeight = (await cell.boundingBox())!.height;
      await cell.dblclick();
      expect(Math.abs((await cell.boundingBox())!.height - committedHeight)).toBeLessThanOrEqual(1);
      await input.press('Escape');
      await expect(branch).toBeVisible();
    }
  };
  for (const view of ['schedule', 'resources']) {
    await applyRecordsIfDirty(page);
    await page.locator('#view-' + view).click();
    const code = view === 'schedule' ? 'A' : 'R';
    const cell = page.locator('.project-view:visible .tabulator-row').filter({ has: page.locator('[tabulator-field="code"]').filter({ hasText: code === 'A' ? /^A$/ : /^R$/ }) }).locator('[tabulator-field="description"]');
    await checkEditor(cell, true);
  }
  await applyRecordsIfDirty(page);
  await page.locator('#view-measurement').click();
  await page.getByRole('button', { name: 'Add measurement', exact: true }).click();
  const add = page.getByRole('dialog', { name: 'Add item', exact: true });
  await add.getByLabel('Measurement template').selectOption('_2_LLLLL');
  await add.getByLabel('Description / remarks').fill('Quantities');
  await add.getByRole('button', { name: 'Add item', exact: true }).click();
  await expect(add).not.toBeVisible();
  await page.getByRole('button', { name: 'Edit records', exact: true }).click();
  await page.getByRole('button', { name: 'Add record', exact: true }).click();
  const row = page.locator('.measurement-record-grid .tabulator-row').first();
  await expect(row).toBeVisible();
  await expect(row.locator('[tabulator-field="_serial"]')).toHaveText('1');
  const blankHeight = (await row.boundingBox())!.height;
  expect(blankHeight).toBeGreaterThanOrEqual(32);
  const cell = row.locator('[tabulator-field="c0"]');
  await checkEditor(cell, false);
  await cell.dblclick();
  await cell.locator('textarea').fill('Measured room');
  await page.locator('.measurement-entry-heading').click();
  await expect(cell).toHaveText('Measured room');
  expect(Math.abs((await row.boundingBox())!.height - blankHeight)).toBeLessThanOrEqual(1);
  await cell.dblclick();
  await cell.locator('textarea').press('End');
  await cell.locator('textarea').press('Shift+Enter');
  await page.keyboard.insertText('Additional line');
  expect((await row.boundingBox())!.height).toBeGreaterThan(blankHeight + 10);
  await page.screenshot({ path: 'test-results/stable-measurement-editor.png', animations: 'disabled' });
  const editingHeight = (await row.boundingBox())!.height;
  await cell.locator('textarea').press('Enter');
  await expect(cell).toHaveText('Measured room\nAdditional line');
  await expect.poll(async () => (await row.boundingBox())!.height).toBe(editingHeight);
  await page.screenshot({ path: 'test-results/committed-measurement-text.png', animations: 'disabled' });
  await cell.dblclick();
  expect(Math.abs((await row.boundingBox())!.height - editingHeight)).toBeLessThanOrEqual(1);
  await cell.locator('textarea').press('Escape');
});

test('feedback 3: tax labels and four-place precision', async ({ page }) => {
  await refinementFixture(page);
  await applyRecordsIfDirty(page);
  await page.locator('#view-resources').click();
  const row = page.locator('.project-view:visible .tabulator-row').filter({ has: page.locator('[tabulator-field="code"]').filter({ hasText: /^R$/ }) });
  await expect(page.locator('.project-view:visible .tabulator-col[tabulator-field="vat"]')).toHaveText('TAX %');
  const tax = row.locator('[tabulator-field="vat"]');
  await expect(tax).toHaveText('0');
  await tax.dblclick();
  await tax.locator('input').fill('1.2345');
  await tax.locator('input').press('Tab');
  await expect(tax).toHaveText('1.2345');
  await applyRecordsIfDirty(page);
  await page.locator('#view-schedule').click();
  await page.locator('.project-view:visible').getByText('Foundation', { exact: true }).click();
  await page.getByRole('button', { name: 'Edit analysis', exact: true }).click();
  await page.getByRole('grid', { name: 'Rate analysis table' }).locator('.tabulator-row[data-kind="Resource"] [tabulator-field="kind"]').click();
  await expect(page.locator('.inspector').getByLabel('Tax %', { exact: true })).toHaveValue('1.2345');
  await page.getByRole('button', { name: 'Add custom resource', exact: true }).click();
  const custom = page.getByRole('dialog', { name: 'Add custom resource', exact: true });
  await expect(custom.getByLabel('Tax %', { exact: true })).toHaveValue('0');
  await expect(custom).not.toContainText('VAT');
});

test('feedback 4: persistent tree geometry and focus rings in editable fields', async ({ page }) => {
  await refinementFixture(page);
  const grid = page.locator('.project-view:visible .project-main-grid');
  const cell = grid.locator('.tabulator-row').filter({ has: page.locator('[tabulator-field="code"]').filter({ hasText: /^A$/ }) }).locator('[tabulator-field="description"]');
  const branches = () => grid.locator('.tabulator-data-tree-branch');
  const positions = await branches().evaluateAll(nodes => nodes.map(node => { const b=node.getBoundingClientRect(); return {x:b.x,y:b.y,width:b.width,height:b.height}; }));
  await cell.dblclick();
  const editor = cell.locator('textarea');
  const editingBranch = cell.locator('.table-text-editor-shell .tabulator-data-tree-branch');
  const first = await editingBranch.boundingBox();
  expect(Math.abs(first!.x-positions[0].x)).toBeLessThan(1);
  expect(Math.abs(first!.y-positions[0].y)).toBeLessThan(1);
  await editor.press('End');
  await editor.press('Shift+Enter');
  await page.keyboard.insertText('Additional description line');
  const multiline = (await editingBranch.boundingBox())!;
  expect(Math.abs(multiline.x-first!.x)).toBeLessThan(1);
  expect(Math.abs(multiline.y-first!.y)).toBeLessThan(1);
  await expect(branches()).toHaveCount(positions.length);
  await editor.press('Escape');
  const audit = async (scope: ReturnType<Page['locator']>) => {
    await expect(scope).toBeVisible();
    const fields = scope.locator('input:visible:not([type="checkbox"]):not([type="radio"]):not(:disabled):not([readonly]),textarea:visible:not(:disabled):not([readonly]),select:visible:not(:disabled)');
    expect(await fields.count()).toBeGreaterThan(0);
    await page.keyboard.press('Tab');
    for (const field of await fields.all()) {
      await field.scrollIntoViewIfNeeded();
      await field.focus();
      const result = await field.evaluate(el => {
        const target=getComputedStyle(el).outlineStyle==='none' ? el.closest('.search-field') || el : el;
        const style=getComputedStyle(target), box=target.getBoundingClientRect();
        const ringWidth=parseFloat(style.outlineWidth)||0, offset=parseFloat(style.outlineOffset)||0;
        const outset=style.outlineStyle==='none'?0:Math.max(0,ringWidth+offset);
        const clipped: string[]=[];
        for(let parent=el.parentElement;parent;parent=parent.parentElement){
          const s=getComputedStyle(parent), r=parent.getBoundingClientRect();
          if (['auto','scroll','hidden','clip'].includes(s.overflowX) && (box.left-outset<r.left-1 || box.right+outset>r.right+1)) clipped.push(parent.className+':x');
          if (['auto','scroll','hidden','clip'].includes(s.overflowY) && (box.top-outset<r.top-1 || box.bottom+outset>r.bottom+1)) clipped.push(parent.className+':y');
        }
        return {name:el.getAttribute('aria-label')||el.closest('label')?.textContent,clipped,style:style.outlineStyle,width:ringWidth,offset};
      });
      expect(result.clipped,result.name || 'field').toEqual([]);
      expect(result.width,result.name || 'field').toBe(2);
      expect(result.offset,result.name || 'field').toBeLessThanOrEqual(-2);
    }
  };
  for(const view of ['schedule','resources']){
    await applyRecordsIfDirty(page);
    await page.locator('#view-'+view).click();
    const firstRow=page.locator('.project-view:visible .tabulator-row[data-kind="Resource"]').first();
    const tree=firstRow.locator('[tabulator-field="description"] .tabulator-data-tree-branch');
    const original=(await tree.boundingBox())!;
    for(const field of view==='schedule'?['code','description','unit','rate','qty','remarks']:['code','description','unit','rate','vat','discount','reference']){
      await firstRow.locator(`[tabulator-field="${field}"]`).dblclick();
      const input=firstRow.locator('input,textarea');
      await expect(input).toBeFocused();
      await page.keyboard.insertText('x');
      const during=(await tree.boundingBox())!;
      expect(Math.abs(during.x-original.x),view+':'+field).toBeLessThan(1);
      expect(Math.abs(during.y-original.y),view+':'+field).toBeLessThan(1);
      await input.press('Escape');
    }
    await audit(page.locator('.project-view:visible'));
    await page.getByRole('button',{name:'Add item',exact:true}).click();
    const dialog=page.getByRole('dialog',{name:'Add item',exact:true});
    await audit(dialog);
    await dialog.getByRole('button',{name:'Cancel',exact:true}).click();
  }
  await applyRecordsIfDirty(page);
  await page.locator('#view-schedule').click();
  await page.locator('.project-view:visible').getByText('Foundation',{exact:true}).click();
  await page.getByRole('button',{name:'Edit analysis',exact:true}).click();
  await page.getByRole('grid',{name:'Rate analysis table'}).locator('.tabulator-row[data-kind="Resource"] [tabulator-field="kind"]').click();
  await audit(page.locator('.inspector'));
  await page.getByRole('button',{name:'Add custom resource',exact:true}).click();
  const custom=page.getByRole('dialog',{name:'Add custom resource',exact:true});
  await audit(custom);
  await custom.getByRole('button',{name:'Cancel',exact:true}).click();
  await applyRecordsIfDirty(page);
  await page.locator('#view-measurement').click();
  await page.getByRole('button',{name:'Add measurement',exact:true}).click();
  const add=page.getByRole('dialog',{name:'Add item',exact:true});
  await audit(add);
  await add.getByLabel('Measurement template').selectOption('civil_steel_table');
  await add.getByLabel('Description / remarks').fill('Steel work');
  await add.getByRole('button',{name:'Add item',exact:true}).click();
  await expect(add).not.toBeVisible();
  await page.setViewportSize({width:700,height:900});
  const properties=page.locator('.ribbon').getByRole('button',{name:'Properties…',exact:true});
  await expect(properties.locator('.ribbon-label')).toBeVisible();
  await expect(properties).not.toHaveAttribute('data-ribbon-mini','true');
  await properties.click();
  const dialog=page.getByRole('dialog',{name:'Measurement properties',exact:true});
  await audit(dialog);
  await dialog.getByRole('button',{name:'Cancel',exact:true}).click();
  await page.getByRole('button',{name:'Edit records',exact:true}).click();
  await page.getByRole('button',{name:'Edit measurement description / remarks',exact:true}).click();
  await expect(page.getByLabel('Measurement description / remarks',{exact:true})).toBeFocused();
  await audit(page.locator('.project-view:visible'));
  await page.screenshot({path:'test-results/measurement-editable-caption.png',animations:'disabled'});
});

test('multiline analysis cells retain padding when editing and accepting', async ({ page }) => {
  await refinementFixture(page);
  await page.locator('.project-view:visible').getByText('Foundation', { exact: true }).click();
  await page.getByRole('button', { name: 'Edit analysis', exact: true }).click();
  const cell = page.getByRole('grid', { name: 'Rate analysis table' }).locator('.tabulator-row[data-kind="Group"] [tabulator-field="description"]').first();
  await cell.dblclick();
  await cell.locator('textarea').fill('Materials\nAdditional line');
  await cell.locator('textarea').press('Enter');
  await expect(cell).toHaveText('Materials\nAdditional line');
  const before = await cell.evaluate(el => { const style = getComputedStyle(el); const range = document.createRange(); range.selectNodeContents(el); const b = range.getBoundingClientRect(); return { y: b.y, x: b.x, height: el.getBoundingClientRect().height, padding: style.padding }; });
  await cell.dblclick();
  const editor = cell.locator('textarea');
  const bounds = (await editor.boundingBox())!;
  await page.screenshot({ path: 'test-results/analysis-text-editing.png', animations: 'disabled' });
  expect(Math.abs(bounds.x - before.x)).toBeLessThanOrEqual(2);
  expect(Math.abs(bounds.y - before.y)).toBeLessThanOrEqual(2);
  await editor.press('End');
  await page.keyboard.insertText(' edited');
  await editor.press('Enter');
  await expect(cell).toHaveText('Materials\nAdditional line edited');
  await expect(cell).toHaveCSS('padding', before.padding);
  await page.screenshot({ path: 'test-results/analysis-text-accepted.png', animations: 'disabled' });
  expect(Math.abs((await cell.boundingBox())!.height - before.height)).toBeLessThanOrEqual(1);
});


test('Escape retains cell focus and search shortcuts follow active views and dialogs', async ({ page }) => {
  await refinementFixture(page);
  for (const view of ['schedule', 'resources']) {
    await applyRecordsIfDirty(page);
    await page.locator('#view-' + view).click();
    const search = page.locator('.project-view:visible').getByLabel('Search project table');
    const cell = page.locator('.project-view:visible .tabulator-row[data-kind="Resource"] [tabulator-field="description"]').first();
    await cell.dblclick();
    await cell.locator('textarea').fill('Discard this edit');
    await cell.locator('textarea').press('Escape');
    await expect(cell).toBeFocused();
    await expect(cell).not.toContainText('Discard this edit');
    await page.keyboard.press('F2');
    await expect(cell.locator('textarea')).toBeFocused();
    await cell.locator('textarea').press('Escape');
    await page.keyboard.press('ArrowRight');
    await expect(page.locator('.project-view:visible .cell-focused')).toHaveAttribute('tabulator-field', 'unit');
    await page.keyboard.press('ControlOrMeta+f');
    await expect(search).toBeFocused();
    await page.keyboard.press('ControlOrMeta+k');
    await applyRecordsIfDirty(page);
    await expect(page.locator('#view-' + view)).toHaveAttribute('aria-selected', 'true');
    await expect(search).toBeFocused();
  }
  await applyRecordsIfDirty(page);
  await page.locator('#view-schedule').click();
  await page.locator('.project-view:visible').getByText('Foundation', { exact: true }).click();
  await page.getByRole('button', { name: 'Edit analysis', exact: true }).click();
  const cell = page.getByRole('grid', { name: 'Rate analysis table' }).locator('.tabulator-row[data-kind="Group"] [tabulator-field="description"]').first();
  await cell.dblclick();
  await cell.locator('textarea').fill('Discard analysis edit');
  await cell.locator('textarea').press('Escape');
  await expect(cell).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(cell.locator('textarea')).toBeFocused();
  await cell.locator('textarea').press('Escape');
  await page.getByRole('button', { name: 'Hide explorer', exact: true }).click();
  await page.keyboard.press('ControlOrMeta+f');
  await expect(page.getByLabel('Find schedule items', { exact: true })).toBeFocused();
  await page.locator('.explorer').getByRole('tab', { name: 'Resources', exact: true }).click();
  await cell.click();
  await page.keyboard.press('ControlOrMeta+f');
  await expect(page.getByLabel('Find resources', { exact: true })).toBeFocused();
  await page.getByRole('button', { name: 'Add resources from database', exact: true }).click();
  const picker = page.getByRole('dialog', { name: 'Add analysis resources from database', exact: true });
  const pickerSearch = picker.locator('.search-field input').first();
  await picker.getByRole('grid').focus();
  await page.keyboard.press('ControlOrMeta+f');
  await expect(pickerSearch).toBeFocused();
  await picker.getByRole('button', { name: 'Cancel', exact: true }).click();
  await page.getByRole('button', { name: 'Keyboard shortcuts', exact: true }).click();
  const help = page.getByRole('dialog', { name: 'Keyboard shortcuts', exact: true });
  await expect(help).toContainText('Focus search in current view or selection dialog');
  await expect(help).toContainText('Ctrl / ⌘ + F');
  await expect(help).not.toContainText('Ctrl / ⌘ + K');
  await expect(page.locator('.statusbar')).toContainText('Ctrl / ⌘ + F to find');
});

test('opening an analysis populates newly added schedule items in explorer', async ({ page }) => {
  await refinementFixture(page);
  await page.getByRole('button', { name: 'Add item', exact: true }).click();
  const add = page.getByRole('dialog', { name: 'Add item', exact: true });
  await add.getByLabel('New code', { exact: true }).fill('NEW');
  await add.getByLabel('Description', { exact: true }).fill('New schedule item');
  await add.getByRole('button', { name: 'Add item', exact: true }).click();
  await expect(add).not.toBeVisible();
  await page.locator('.project-view:visible').getByText('Foundation', { exact: true }).click();
  await page.getByRole('button', { name: 'Edit analysis', exact: true }).click();
  await expect(page.locator('.explorer')).toContainText('New schedule item');
  await expect(page.getByLabel('Find schedule items', { exact: true })).toHaveValue('');
});


test('schedule overall estimate total stays visible across search edits and undo', async ({ page }) => {
  await refinementFixture(page);
  const total = page.getByRole('status', { name: 'Overall estimate total', exact: true });
  await expect(total).toContainText('25.00');
  const search = page.locator('.project-view:visible').getByLabel('Search project table');
  await search.fill('Foundation');
  await search.press('Enter');
  await expect(total).toContainText('25.00');
  const quantity = page.locator('.project-view:visible .tabulator-row').filter({ has: page.locator('[tabulator-field="code"]').filter({ hasText: /^A$/ }) }).locator('[tabulator-field="qty"]');
  await quantity.dblclick();
  await quantity.locator('input').fill('2');
  await quantity.locator('input').press('Enter');
  await expect(total).toContainText('45.00');
  await page.locator('.titlebar').getByRole('button', { name: 'Undo', exact: true }).click();
  await expect(total).toContainText('25.00');
  await page.screenshot({ path: 'test-results/schedule-estimate-total.png', animations: 'disabled' });
  await applyRecordsIfDirty(page);
  await page.locator('#view-resources').click();
  await expect(total).not.toBeVisible();
});

test('keyboard shortcut help groups commands into accessible categories', async ({ page }) => {
  await page.getByRole('button', { name: 'Keyboard shortcuts', exact: true }).click();
  const help = page.getByRole('dialog', { name: 'Keyboard shortcuts', exact: true });
  for (const [category, command] of [
    ['Project and search', 'Focus search in current view or selection dialog'],
    ['Rows and clipboard', 'Copy / Paste rows'],
    ['Cell editing and selection', 'Cancel cell edit and retain focus'],
    ['Editor actions', 'Open selected schedule analysis'],
    ['Ribbon navigation', 'Activate focused ribbon tab'],
  ]) {
    const group = help.getByRole('region', { name: category, exact: true });
    await expect(group.getByRole('heading', { name: category, exact: true })).toBeVisible();
    await expect(group).toContainText(command);
  }
  await page.screenshot({ path: 'test-results/grouped-shortcuts.png', animations: 'disabled' });
});


test('native window is revealed after startup theme typography and UI are ready', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('gestimator.program-settings.v1', JSON.stringify({ version: 1, appearance: { theme: 'light', uiFamily: 'Arial', uiSize: 16, tableFamily: 'Arial', tableSize: 17 } }));
    (window as any).startupFontGate = new Promise(resolve => {
      (window as any).releaseStartupFont = () => resolve({ family: 'Iosevka', size: '11pt' });
    });
  });
  let releaseState!: () => void;
  const stateGate = new Promise<void>(resolve => { releaseState = resolve; });
  let requestedState = false;
  await page.exposeBinding('delayedStartupTransport', async (_source, request) => {
    if (request.method === 'state') { requestedState = true; await stateGate; }
    return call(request.method, request.params);
  });
  await page.addInitScript(() => { (window as any).backendTransport = (window as any).delayedStartupTransport; });
  await page.reload();
  await expect.poll(() => page.evaluate(() => typeof (window as any).releaseStartupFont)).toBe('function');
  expect(await page.evaluate(() => (window as any).windowCommands || [])).not.toContain('plugin:window|show');
  await page.evaluate(() => (window as any).releaseStartupFont());
  await expect.poll(() => requestedState).toBe(true);
  expect(await page.evaluate(() => (window as any).windowCommands || [])).not.toContain('plugin:window|show');
  releaseState();
  await expect.poll(() => page.evaluate(() => (window as any).startupAtShow)).toEqual({
    theme: 'light', family: 'Arial, system-ui', size: '16px', fonts: 'loaded', landing: true, ribbonSized: false,
  });
  expect((await page.evaluate(() => (window as any).windowCommands)).filter((command: string) => command === 'plugin:window|show')).toHaveLength(1);
});

test('native startup errors reveal the initialized window with an error message', async ({ page }) => {
  await page.exposeBinding('failedStartupTransport', async (_source, request) => request.method === 'program.settings'
    ? { error: { code: 'backend_error', message: 'Startup backend unavailable' } }
    : call(request.method, request.params));
  await page.addInitScript(() => { (window as any).backendTransport = (window as any).failedStartupTransport; });
  await page.reload();
  await expect.poll(() => page.evaluate(() => (window as any).windowCommands || [])).toContain('plugin:window|show');
  await expect(page.getByRole('alert')).toContainText('Startup backend unavailable');
});


test('long first-level items retain typography and indentation through Enter and library attachment', async ({ page }) => {
  const { execFileSync } = await import('node:child_process');
  const path = resolve(directory, 'long-first-level.eproj');
  execFileSync(python, ['-m', 'modern.e2e.create_fixture', path], { cwd: resolve('..') });
  execFileSync(python, ['-c', "import sys;from estimator.data.schedule import ScheduleDatabase,ScheduleItemModel;from estimator.undo import Stack;d=ScheduleDatabase(Stack());d.open_database(sys.argv[1]);desc='Long wiring description with conductors, switches, conduits and accessories. '*5;d.insert_item_atomic(ScheduleItemModel('1.1',desc,'',category='Work'));d.insert_item_atomic(ScheduleItemModel('1.1.1','Group A','Point',rate=2,qty=1,parent='1.1',category='Work'));d.insert_item_atomic(ScheduleItemModel('1.2',desc,'Point',rate=3,qty=1,category='Work'));d.close_database()", path], { cwd: resolve('..') });
  const original = await readFile(path);
  await openFixture(page, path);
  await applyRecordsIfDirty(page);
  await page.locator('#view-schedule').click();
  const grid = page.locator('.project-view:visible .project-main-grid');
  const metrics = async (cell: ReturnType<Page['locator']>) => cell.evaluate(el => {
    const style = getComputedStyle(el), walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let textX = 0;
    while (walker.nextNode()) if (walker.currentNode.textContent?.trim()) { const range = document.createRange(); range.selectNodeContents(walker.currentNode); textX = range.getBoundingClientRect().x; break; }
    return { padding: style.padding, weight: style.fontWeight, height: el.getBoundingClientRect().height, textX };
  });
  for (const code of ['1.1', '1.2']) {
    const cell = grid.locator('.tabulator-row').filter({ has: page.locator('[tabulator-field="code"]').filter({ hasText: code === '1.1' ? /^1\.1$/ : /^1\.2$/ }) }).locator('[tabulator-field="description"]');
    const before = await metrics(cell);
    expect(before.weight).toBe('400');
    for (const changed of [false, true]) {
      await cell.dblclick();
      const input = cell.locator('textarea');
      await expect(input).toHaveCSS('font-weight', before.weight);
      expect(Math.abs((await input.boundingBox())!.x - before.textX)).toBeLessThanOrEqual(1);
      expect((await cell.locator('.tabulator-data-tree-branch').boundingBox())!.width).toBe(7);
      if (changed) { await input.press('End'); await page.keyboard.insertText(' revised'); }
      await input.press('Enter');
      await expect(input).toHaveCount(0);
      await expect(cell).toHaveCSS('padding', before.padding);
      await expect(cell).toHaveCSS('font-weight', before.weight);
      const after = await metrics(cell);
      expect(Math.abs(after.textX - before.textX)).toBeLessThanOrEqual(1);
      if (!changed) expect(after.height).toBe(before.height);
    }
  }
  await page.screenshot({ path: 'test-results/long-first-level-items.png', animations: 'disabled' });
  const manager = await openDatabaseManager(page);
  const labels = [manager.locator('.dialog-intro'), manager.getByLabel('Library project', { exact: true }), manager.locator('.library-remember')];
  const weights = await Promise.all(labels.map(label => label.evaluate(el => getComputedStyle(el).fontWeight)));
  await manager.getByLabel('Library project', { exact: true }).fill(path);
  await manager.getByRole('button', { name: 'Attach library', exact: true }).click();
  await expect(manager.locator('.attached-database')).toHaveCount(1);
  for (const [index, label] of labels.entries()) await expect(label).toHaveCSS('font-weight', weights[index]!);
  await page.screenshot({ path: 'test-results/attached-library-typography.png', animations: 'disabled' });
  expect(await readFile(path)).toEqual(original);
});

test('arrows edit text within a cell and toolbar SVGs use two-tone engineering icons', async ({ page }) => {
  await refinementFixture(page);
  const checkCaret = async (cell: ReturnType<Page['locator']>) => {
    const original = await cell.textContent();
    await cell.dblclick();
    const input = cell.locator('textarea');
    await input.fill('Alpha beta\nGamma delta');
    await input.evaluate(el => (el as HTMLTextAreaElement).setSelectionRange(5, 5));
    await input.press('ArrowLeft');
    await expect(input).toBeFocused();
    expect(await input.evaluate(el => (el as HTMLTextAreaElement).selectionStart)).toBe(4);
    await input.press('ArrowRight');
    await input.press('Shift+ArrowRight');
    expect(await input.evaluate(el => [(el as HTMLTextAreaElement).selectionStart, (el as HTMLTextAreaElement).selectionEnd])).toEqual([5, 6]);
    await input.press('ArrowDown');
    await expect(input).toBeFocused();
    expect(await input.evaluate(el => (el as HTMLTextAreaElement).selectionStart)).toBeGreaterThan(10);
    await input.press('ArrowUp');
    expect(await input.evaluate(el => (el as HTMLTextAreaElement).selectionStart)).toBeLessThan(11);
    await input.press('Escape');
    await expect(cell).toBeFocused();
    await expect(cell).toHaveText(original || '');
  };
  for (const view of ['schedule', 'resources']) {
    await applyRecordsIfDirty(page);
    await page.locator('#view-' + view).click();
    await checkCaret(page.locator('.project-view:visible .tabulator-row[data-kind="Resource"] [tabulator-field="description"]').first());
  }
  await applyRecordsIfDirty(page);
  await page.locator('#view-schedule').click();
  const icon = page.getByRole('button', { name: 'Add item', exact: true }).locator('svg');
  for (const [theme, color] of [['dark', 'rgb(190, 189, 189)'], ['light', 'rgb(95, 95, 101)']]) {
    if (await page.locator('html').getAttribute('data-theme') !== theme) await page.getByRole('button', { name: /Switch to .* theme/ }).click();
    await expect(icon).toHaveCSS('color', color!);
    await expect(icon).toHaveCSS('stroke-linecap', 'round');
    await expect(icon).toHaveCSS('stroke-linejoin', 'round');
    // B2-style line weight: 1.25–1.75 rendered px at toolbar sizes.
    const renderedStroke = await icon.evaluate(el => parseFloat(getComputedStyle(el).strokeWidth) * el.getBoundingClientRect().width / 24);
    expect(renderedStroke).toBeGreaterThanOrEqual(1.2);
    expect(renderedStroke).toBeLessThanOrEqual(1.8);
    await expect(icon.locator('.icon-accent')).toHaveCount(0);
    await page.screenshot({ path: `test-results/monochrome-toolbar-${theme}.png`, animations: 'disabled' });
  }
  await page.locator('.project-view:visible').getByText('Foundation', { exact: true }).click();
  await page.getByRole('button', { name: 'Edit analysis', exact: true }).click();
  await checkCaret(page.getByRole('grid', { name: 'Rate analysis table' }).locator('.tabulator-row[data-kind="Group"] [tabulator-field="description"]').first());
  await applyRecordsIfDirty(page);
  await page.locator('#view-measurement').click();
  await page.getByRole('button', { name: 'Add measurement', exact: true }).click();
  const add = page.getByRole('dialog', { name: 'Add item', exact: true });
  await add.getByRole('button', { name: 'Add item', exact: true }).click();
  await expect(add).not.toBeVisible();
  await openMeasurementEntry(page);
  await page.getByRole('button', { name: 'Add record', exact: true }).click();
  await checkCaret(page.locator('.measurement-record-grid .tabulator-row [tabulator-field="c0"]').first());
});


test('markup characters in descriptions categories and attached library names stay literal', async ({ page }) => {
  const { execFileSync } = await import('node:child_process');
  const path = resolve(directory, 'literal-markup.eproj');
  const literal = '<b>Wiring & "quoted"</b><style>body{font-weight:900}</style>';
  const category = '<strong>Category & accessories</strong>';
  execFileSync(python, ['-m', 'modern.e2e.create_fixture', path], { cwd: resolve('..') });
  execFileSync(python, ['-c', "import sys;from estimator.data.schedule import ScheduleDatabase,ScheduleItemModel;from estimator.undo import Stack;d=ScheduleDatabase(Stack());d.open_database(sys.argv[1]);settings=d.get_project_settings();settings['project_name']=sys.argv[2];d.set_project_settings(settings);d.insert_item_atomic(ScheduleItemModel('1.1',sys.argv[2],'Point',rate=1,qty=1,category=sys.argv[3]));d.close_database()", path, literal, category], { cwd: resolve('..') });
  const original = await readFile(path);
  const bodyWeight = await page.locator('body').evaluate(el => getComputedStyle(el).fontWeight);
  await openFixture(page, path);
  await applyRecordsIfDirty(page);
  await page.locator('#view-schedule').click();
  const grid = page.locator('.project-view:visible .project-main-grid');
  const cell = grid.locator('.tabulator-row').filter({ has: page.locator('[tabulator-field="code"]').filter({ hasText: /^1\.1$/ }) }).locator('[tabulator-field="description"]');
  await expect(cell).toHaveText(literal);
  await expect(grid.getByText(category, { exact: true })).toBeVisible();
  await expect(cell.locator('b,strong,style')).toHaveCount(0);
  await cell.dblclick();
  await expect(cell.locator('textarea')).toHaveValue(literal);
  await expect(cell.locator('textarea')).toHaveCSS('font-weight', '400');
  await cell.locator('textarea').press('Enter');
  await expect(cell).toHaveText(literal);
  await expect(cell).toHaveCSS('font-weight', '400');
  const manager = await openDatabaseManager(page);
  const introWeight = await manager.locator('.dialog-intro').evaluate(el => getComputedStyle(el).fontWeight);
  await manager.getByLabel('Library project', { exact: true }).fill(path);
  await manager.getByRole('button', { name: 'Attach library', exact: true }).click();
  await expect(manager.locator('.attached-database span')).toHaveText(literal);
  await expect(manager.locator('.saved-library strong')).toHaveText(literal);
  await expect(manager.locator('.attached-database b,.attached-database style,.saved-library strong b,.saved-library strong style')).toHaveCount(0);
  await expect(manager.locator('.dialog-intro')).toHaveCSS('font-weight', introWeight);
  await expect(page.locator('body')).toHaveCSS('font-weight', bodyWeight);
  expect(await readFile(path)).toEqual(original);
});


test('repeated bundled database attachment keeps regular weight and stable smoothing when content overflows', async ({ page }) => {
  await refinementFixture(page);
  await page.setViewportSize({ width: 1280, height: 900 });
  const catalog = (await call('program.libraries')).result.rows.filter((entry: any) => entry.bundled);
  expect(catalog.length).toBeGreaterThanOrEqual(2);
  const sourceBytes = await Promise.all(['DSR2021.eproj', 'DSREM2022.eproj'].map(name => readFile(resolve('../estimator/database', name))));
  const manager = await openDatabaseManager(page);
  const fields = [manager.locator('.dialog-intro'), manager.getByLabel('Library project', { exact: true }), manager.locator('.library-remember')];
  const selected = manager.getByLabel('Available databases');
  const seen = new Set<string>();
  for (const [index, entry] of [catalog[0], catalog[1], catalog[0], catalog[1]].entries()) {
    if (index === 2) await page.locator('body').evaluate(el => { el.style.fontWeight = '700'; });
    await selected.locator(`option[value="${entry.path}"]`).waitFor({ state: 'attached' });
    await selected.selectOption(entry.path);
    await expect(manager.getByLabel('Library project', { exact: true })).toHaveValue(entry.path);
    await manager.getByRole('button', { name: 'Attach library', exact: true }).click();
    seen.add(entry.path);
    await expect(manager.locator('.attached-database')).toHaveCount(seen.size);
    await expect(manager.getByRole('button', { name: 'Attach library', exact: true })).toBeEnabled();
    for (const field of fields) await expect(field).toHaveCSS('font-weight', '400');
    await expect(manager).toHaveCSS('font-weight', '400');
    await expect(manager.locator('.p-dialog-content')).toHaveCSS('-webkit-font-smoothing', 'antialiased');
    await expect(manager.locator('.dialog-intro')).toHaveCSS('-webkit-font-smoothing', 'antialiased');
    if (index >= 1) {
      expect(await manager.locator('.p-dialog-content').evaluate(el => el.scrollHeight > el.clientHeight)).toBe(true);
      await expect(manager.locator('.saved-libraries p')).toHaveCSS('-webkit-font-smoothing', 'antialiased');
    }
  }
  await expect(manager.locator('h3').first()).toHaveCSS('font-weight', '700');
  await expect(manager.locator('.saved-library strong').first()).toHaveCSS('font-weight', '700');
  await page.screenshot({ path: 'test-results/repeated-bundled-attachment.png', animations: 'disabled' });
  await page.locator('body').evaluate(el => { el.style.removeProperty('font-weight'); });
  expect(await readFile(resolve('../estimator/database/DSR2021.eproj'))).toEqual(sourceBytes[0]);
  expect(await readFile(resolve('../estimator/database/DSREM2022.eproj'))).toEqual(sourceBytes[1]);
});

test('clipboard icons and toolbar hover outlines remain sharp without changing button size', async ({ page }) => {
  await refinementFixture(page);
  await page.locator('.project-view:visible').getByText('Foundation', { exact: true }).click();
  const ribbon = page.locator('.ribbon');
  for (const [theme, color] of [['dark', 'rgb(190, 189, 189)'], ['light', 'rgb(95, 95, 101)']]) {
    if (await page.locator('html').getAttribute('data-theme') !== theme) await page.getByRole('button', { name: /Switch to .* theme/ }).click();
    await page.mouse.move(1590, 990);
    const copy = ribbon.getByRole('button', { name: 'Copy', exact: true });
    for (const name of ['Copy', 'Paste']) {
      const icon = ribbon.getByRole('button', { name, exact: true }).locator('svg');
      await expect(icon).toHaveAttribute('fill', 'none');
      await expect(icon).toHaveAttribute('stroke', 'currentColor');
      await expect(icon.locator('.icon-accent')).toHaveCount(1);
      await expect(icon).toHaveCSS('color', color!);
    }
    for (const button of [copy, ribbon.getByRole('button', { name: 'Add item', exact: true }), page.locator('.titlebar').getByRole('button', { name: 'Save copy', exact: true })]) {
      const before = (await button.boundingBox())!;
      await button.hover();
      await expect(button).toHaveCSS('border-radius', '0px');
      expect(await button.evaluate(el => getComputedStyle(el).boxShadow)).toContain('inset');
      const after = (await button.boundingBox())!;
      expect(after.width).toBe(before.width);
      expect(after.height).toBe(before.height);
      expect(after.x).toBe(before.x);
      expect(after.y).toBe(before.y);
    }
    await copy.hover();
    await page.screenshot({ path: `test-results/sharp-clipboard-hover-${theme}.png`, animations: 'disabled' });
  }
});


test('feedback 5: schedule returns from analysis with fitting desktop columns', async ({ page }) => {
  await refinementFixture(page);
  const item = page.locator('.project-view:visible .project-main-grid .tabulator-row').filter({ has: page.getByText('Foundation', { exact: true }) });
  for (const width of [1280, 1366, 1600, 1920]) {
    await page.setViewportSize({ width, height: 900 });
    await item.locator('[tabulator-field="description"]').click();
    await page.getByRole('button', { name: 'Edit analysis', exact: true }).click();
    const table = page.getByRole('grid', { name: 'Rate analysis table' });
    const holder = table.locator('.tabulator-tableholder');
    await expect.poll(() => holder.evaluate(el => getComputedStyle(el).overflowX)).toBe('hidden');
    const amount = table.locator('.tabulator-row').first().locator('[tabulator-field="amount"]');
    const edge = await holder.boundingBox(), cell = await amount.boundingBox();
    expect(cell!.x + cell!.width).toBeLessThanOrEqual(edge!.x + edge!.width + 1);
    await page.getByRole('button', { name: 'Discard analysis', exact: true }).click();
    await expect(item).toBeVisible();
    await expect.poll(() => item.evaluate(el => {
      const viewport = el.closest('.tabulator')!.querySelector('.tabulator-tableholder')!.getBoundingClientRect();
      const row = el.getBoundingClientRect();
      return row.height > 0 && row.top < viewport.bottom && row.bottom > viewport.top;
    })).toBe(true);
  }
  await page.setViewportSize({ width: 820, height: 900 });
  await item.locator('[tabulator-field="description"]').click();
  await page.getByRole('button', { name: 'Edit analysis', exact: true }).click();
  const narrow = page.getByRole('grid', { name: 'Rate analysis table' }).locator('.tabulator-tableholder');
  await expect.poll(() => narrow.evaluate(el => getComputedStyle(el).overflowX)).toBe('auto');
  await expect.poll(() => narrow.evaluate(el => el.scrollWidth > el.clientWidth)).toBe(true);
});

test('records import picks a range in the worksheet preview and lists template columns', async ({ page }) => {
  await refinementFixture(page);
  const workbook = resolve(directory, 'records.xlsx');
  const { execFileSync } = await import('node:child_process');
  execFileSync(python, ['-c', `import sys
from openpyxl import Workbook
b=Workbook()
for row in [['Room schedule'],[],['Kitchen',1,3,4,2.5],['Hall',2,5,4,3]]:
 b.active.append(row)
b.save(sys.argv[1])`, workbook], { cwd: resolve('..') });
  const state = (await call('state')).result;
  await call('measurement.add', { revision: state.revision, template: '_1_NLBH', description: 'Imported rooms' });
  await page.locator('#view-measurement').click();
  await page.getByRole('grid', { name: 'Measurements', exact: true }).getByText('Imported rooms', { exact: true }).dblclick();
  await page.locator('.ribbon').getByRole('button', { name: 'Import records…', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Import measurement records', exact: true });
  await dialog.getByLabel('Workbook', { exact: true }).fill(workbook);
  await dialog.getByLabel('Workbook', { exact: true }).press('Enter');
  const sheet = dialog.getByRole('grid', { name: 'Worksheet preview' });
  // Clicking the first record cell sets the range; template columns label the worksheet.
  await sheet.getByRole('cell', { name: 'Kitchen', exact: true }).click();
  await expect(dialog.getByLabel('First row')).toHaveValue('3');
  await expect(dialog.getByRole('status').filter({ hasText: 'records will be inserted' })).toContainText('2 records');
  await expect(dialog.getByRole('region', { name: 'Import preview' })).toContainText('Hall');
  await page.screenshot({ path: 'test-results/records-import.png', animations: 'disabled' });
  await dialog.getByRole('button', { name: 'Import 2 records', exact: true }).click();
  await expect(dialog).not.toBeVisible();
  await expect(page.locator('.measurement-record-grid .tabulator-row')).toHaveCount(2);
});

test('feedback 5: records drafts apply discard guard navigation and save', async ({ page }) => {
  await refinementFixture(page);
  const state = (await call('state')).result;
  const added = (await call('measurement.add', { revision: state.revision, template: '_1_NLBH', description: 'Draft room' })).result;
  await page.locator('#view-measurement').click();
  await page.getByRole('grid', { name: 'Measurements', exact: true }).getByText('Draft room', { exact: true }).dblclick();
  const ribbon = page.locator('.ribbon');
  await ribbon.getByRole('button', { name: 'Add record', exact: true }).click();
  await expect(page.getByText('Unsaved records', { exact: true })).toBeVisible();
  await page.locator('#view-schedule').click();
  const guard = page.getByRole('dialog', { name: 'Keep your measurement records?' });
  await expect(guard).toBeVisible();
  await guard.getByRole('button', { name: 'Keep editing', exact: true }).click();
  await expect(page.locator('.measurement-record-grid .tabulator-row')).toHaveCount(1);
  await page.locator('.draft-headerbar').getByRole('button', { name: 'Apply records', exact: true }).click();
  await expect(page.getByRole('grid', { name: 'Measurements', exact: true })).toBeVisible();
  await openMeasurementEntry(page);
  await ribbon.getByRole('button', { name: 'Add record', exact: true }).click();
  await page.locator('#view-schedule').click();
  await expect(guard).toBeVisible();
  await guard.getByRole('button', { name: 'Discard changes', exact: true }).click();
  await expect(page.locator('#view-schedule')).toHaveAttribute('aria-selected', 'true');
  await page.locator('#view-measurement').click();
  await expect(page.locator('.measurement-record-grid .tabulator-row')).toHaveCount(1);
  await ribbon.getByRole('button', { name: 'Add record', exact: true }).click();
  const copy = resolve(directory, 'draft-records.eproj');
  nativeDialogResults.push(copy);
  await page.locator('.titlebar').getByRole('button', { name: 'Save copy', exact: true }).click();
  await expect(page.getByText('Unsaved records', { exact: true })).toHaveCount(0);
  await expect.poll(async () => readFile(copy).then(() => true).catch(() => false)).toBe(true);
  expect((await call('measurement.detail', { id: added.selected[0] })).result.detail.total_records).toBe(2);
  await page.screenshot({ path: 'test-results/records-draft.png' });
});

test('feedback 5: regional money formatting updates views and preserves raw numeric editing', async ({ page }) => {
  await refinementFixture(page);
  const state = (await call('state')).result;
  const schedule = (await call('schedule.editor.state')).result;
  const identity = schedule.rows.flatMap((row: any) => row._children || []).find((row: any) => row.code === 'A').id;
  await call('schedule.editor.edit', { revision: state.revision, id: identity, field: 'rate', value: '1234567.89' });
  await page.locator('#view-resources').click();
  await page.locator('#view-schedule').click();
  await page.getByRole('button', { name: 'Application menu', exact: true }).click();
  await page.getByRole('menuitem', { name: 'Program settings…', exact: true }).click();
  const settings = page.getByRole('dialog', { name: 'Program settings', exact: true });
  await settings.getByLabel('Regional format').selectOption('en-IN');
  await settings.getByLabel('Show currency symbol').check();
  await expect(settings.getByLabel('Regional amount preview')).toHaveText('₹12,34,567.89');
  await settings.getByRole('button', { name: 'Save program settings', exact: true }).click();
  const row = page.locator('.project-view:visible .project-main-grid .tabulator-row').filter({ has: page.getByText('Foundation', { exact: true }) });
  const rate = row.locator('[tabulator-field="rate"]');
  await expect(rate).toHaveText('₹12,34,567.89');
  await rate.dblclick();
  await expect(rate.locator('input')).toHaveValue('1234567.89');
  await page.keyboard.press('Escape');
  await expect(page.getByLabel('Overall estimate total')).toContainText('₹');
  await row.locator('[tabulator-field="description"]').click();
  await page.getByRole('button', { name: 'Edit analysis', exact: true }).click();
  await expect(page.locator('.summary-value')).toContainText('₹');
  await expect(page.getByRole('grid', { name: 'Rate analysis table' }).locator('.tabulator-row').first().locator('[tabulator-field="amount"]')).toContainText('₹');
  await page.getByRole('button', { name: 'Application menu', exact: true }).click();
  await page.getByRole('menuitem', { name: 'Program settings…', exact: true }).click();
  await settings.getByLabel('Regional format').selectOption('de-DE');
  await settings.getByLabel('Show currency symbol').uncheck();
  await settings.getByRole('button', { name: 'Save program settings', exact: true }).click();
  await page.getByRole('button', { name: 'Discard analysis', exact: true }).click();
  await expect(rate).toHaveText('1.234.567,89');
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem('gestimator.program-settings.v1')!).settings.number_locale)).toBe('de-DE');
  const exact = await page.evaluate(async () => { const module = await import('/src/numberFormatting.ts'); return module.formatMoney('9007199254740993.23'); });
  expect(exact).toBe('9.007.199.254.740.993,23');
});


test('feedback 5: interface and table fonts independently default to the OS', async ({ page }) => {
  const table = page.getByRole('grid', { name: 'Rate analysis table' });
  await expect(page.locator('html')).toHaveCSS('font-size', '14.6667px');
  await expect(table).toHaveCSS('font-size', '14.6667px');
  await expect(table).toHaveCSS('font-family', /Iosevka/);
  await page.getByRole('button', { name: 'Application menu', exact: true }).click();
  await page.getByRole('menuitem', { name: 'Program settings…', exact: true }).click();
  const settings = page.getByRole('dialog', { name: 'Program settings', exact: true });
  await settings.getByRole('tab', { name: 'Appearance', exact: true }).click();
  await expect(settings.getByLabel('Interface font size (px)')).toHaveValue('');
  await expect(settings.getByLabel('Tables font size (px)')).toHaveValue('');
  await settings.getByLabel('Interface font size (px)').fill('19');
  await settings.getByRole('button', { name: 'Save program settings', exact: true }).click();
  await expect(page.locator('html')).toHaveCSS('font-size', '19px');
  await expect(table).toHaveCSS('font-size', '14.6667px');
  await page.reload();
  await expect(page.getByText('Calculation engine connected')).toBeVisible();
  await page.locator('#view-analysis').click();
  await expect(page.locator('html')).toHaveCSS('font-size', '19px');
  await expect(table).toHaveCSS('font-size', '14.6667px');
});


test('feedback 5: records drafts close on list return and switch between measurement items', async ({ page }) => {
  await refinementFixture(page);
  const create = async (description: string) => {
    const state = (await call('state')).result;
    return (await call('measurement.add', { revision: state.revision, template: '_1_NLBH', description })).result.selected[0];
  };
  const first = await create('First measured room');
  const second = await create('Second measured room');
  await page.locator('#view-measurement').click();
  const list = page.getByRole('grid', { name: 'Measurements', exact: true });
  await list.getByText('First measured room', { exact: true }).dblclick();
  await page.getByRole('button', { name: 'Add record', exact: true }).click();
  await page.getByRole('button', { name: 'Apply records', exact: true }).click();
  await expect(list).toBeVisible();
  await expect.poll(async () => (await call('state')).result.measurement_draft).toBeNull();
  await page.getByRole('button', { name: 'Properties…', exact: true }).click();
  const properties = page.getByRole('dialog', { name: 'Measurement properties', exact: true });
  await properties.getByLabel('Description / remarks').fill('Main properties committed');
  await properties.getByRole('button', { name: 'Save properties', exact: true }).click();
  await expect(properties).not.toBeVisible();
  expect((await call('state')).result.measurement_draft).toBeNull();
  expect((await call('measurement.detail', { id: first })).result.detail.description).toBe('Main properties committed');
  await list.getByText('Second measured room', { exact: true }).dblclick();
  await page.getByRole('button', { name: 'Add record', exact: true }).click();
  const state = (await call('state')).result;
  expect(state.measurement_draft.id).toBe(second);
  expect(state.measurement_draft.dirty).toBe(true);
  const stored = (await call('mcp.read', { name: 'get_measurements', arguments: { id: second } })).result;
  expect(stored.data.total_records).toBe(0);
  await page.getByRole('button', { name: 'Apply records', exact: true }).click();
  await expect.poll(async () => (await call('state')).result.measurement_draft).toBeNull();
});

test('draft headerbars use dropdowns and manual and About stay available offline', async ({ page }) => {
  await refinementFixture(page);
  await page.locator('.project-main-grid [tabulator-field="description"]').filter({ hasText: 'Foundation' }).click();
  await page.getByRole('button', { name: 'Edit analysis', exact: true }).click();
  const header = page.getByRole('region', { name: 'Analysis draft', exact: true });
  await expect(header.getByRole('button', { name: 'Apply analysis', exact: true })).toBeVisible();
  await expect(header.getByRole('button', { name: 'Discard analysis', exact: true })).toBeEnabled();
  await expect(page.locator('.ribbon').getByRole('button', { name: 'Apply analysis', exact: true })).toHaveCount(0);
  const qty = page.locator('.analysis-table .tabulator-row[data-kind="Resource"] [tabulator-field="value"]');
  await qty.dblclick();
  await qty.locator('input').fill('3');
  await qty.locator('input').press('Enter');
  await header.getByRole('button', { name: 'Discard analysis', exact: true }).click();
  await expect(page.locator('#view-schedule')).toHaveAttribute('aria-selected', 'true');
  expect((await call('state')).result.dirty).toBe(false);
  await page.getByRole('button', { name: 'Application menu', exact: true }).click();
  await page.getByRole('menuitem', { name: 'Application manual', exact: true }).click();
  const manual = page.getByRole('dialog', { name: 'Application manual', exact: true });
  await expect(manual).toContainText('Measurements');
  await expect(manual).toContainText('Save project copy');
  await manual.getByRole('button', { name: 'Close', exact: true }).click();
  await page.getByRole('button', { name: 'Application menu', exact: true }).click();
  await page.getByRole('menuitem', { name: 'About GEstimator', exact: true }).click();
  const about = page.getByRole('dialog', { name: 'About GEstimator', exact: true });
  await expect(about).toContainText('Modern workspace version 0.1.0');
  await about.getByText('GNU General Public License', { exact: true }).click();
  await expect(about.locator('pre')).toContainText('Version 3, 29 June 2007');
});

test('OS project requests serialize through the unsaved guard and reject invalid files', async ({ page }) => {
  const project = await refinementFixture(page);
  async function emitOs(paths: string[], drop = false) {
    await page.evaluate(({ paths, drop }) => {
      const w = window as any;
      if (!drop) w.osOpenRequests = paths;
      const event = drop ? 'tauri://drag-drop' : 'project-open-available';
      const callback = w.tauriCallbacks[w.tauriListeners[event]];
      callback({ event, payload: drop ? { paths, position: { x: 1, y: 1 } } : null });
    }, { paths, drop });
  }
  await page.locator('.project-main-grid [tabulator-field="description"]').filter({ hasText: 'Foundation' }).click();
  await page.getByRole('button', { name: 'Edit analysis', exact: true }).click();
  const qty = page.locator('.analysis-table .tabulator-row[data-kind="Resource"] [tabulator-field="value"]');
  await qty.dblclick();
  await qty.locator('input').fill('3');
  await qty.locator('input').press('Enter');
  const before = frontendCalls.filter(call => call.method === 'project.open').length;
  const tabs = page.getByRole('navigation', { name: 'Open projects' }).getByRole('tab');
  // The already open project keeps its tab and its unapplied analysis.
  await emitOs([project]);
  await expect(page.locator('.summary-value')).toContainText('30.00');
  expect(frontendCalls.filter(call => call.method === 'project.open')).toHaveLength(before);
  await expect(tabs).toHaveCount(1);
  // Another project opens in a new tab without discarding this draft.
  const second = resolve(directory, 'second.eproj');
  await copyFile(project, second);
  await emitOs([second], true);
  await expect.poll(() => frontendCalls.filter(call => call.method === 'project.open').length).toBe(before + 1);
  await expect(tabs).toHaveCount(2);
  await tabs.nth(0).click();
  await expect(page.locator('.summary-value')).toContainText('30.00');
  // The remounted tab registers its drop listener after connecting; retry until it does.
  await expect(async () => {
    await emitOs(['/tmp/not-a-project.txt'], true);
    await expect(page.getByRole('alert').filter({ hasText: 'Not a GEstimator project' })).toBeVisible({ timeout: 500 });
  }).toPass();
  await emitOs([resolve(directory, 'missing file.eproj')]);
  await expect(page.getByRole('alert')).toContainText(/not found|does not exist|No such|Cannot|exist/i);
});

test('remaining parity commands highlight rates renumber exclusions and synchronize selected resources', async ({ page }) => {
  await refinementFixture(page);
  const ribbon = page.locator('.ribbon');
  await ribbon.getByRole('button', { name: 'Show rate discrepancies', exact: true }).click();
  const rates = page.locator('.project-view:visible').getByRole('status').filter({ hasText: 'Missing analysis:' });
  await expect(rates).toContainText('mismatches');
  await rates.getByText('Stored / calculated rates', { exact: true }).click();
  await expect(rates).toContainText('A:');
  await rates.getByRole('button', { name: 'Clear highlighting', exact: true }).click();
  await expect(rates).toHaveCount(0);
  const state = (await call('state')).result;
  await call('resources.editor.add', { revision: state.revision, data: { code: 'LIB:KEEP', description: 'Excluded library resource', rate: '1', category: 'Materials' } });
  await page.locator('#view-resources').click();
  await ribbon.getByRole('button', { name: 'Renumber resources', exact: true }).click();
  const renumber = page.getByRole('dialog', { name: 'Renumber resources', exact: true });
  await expect(renumber.getByRole('switch', { name: 'Renumber LIB resources', exact: true })).toHaveAttribute('aria-checked', 'false');
  await renumber.getByRole('button', { name: 'Renumber resources', exact: true }).click();
  await expect(renumber).not.toBeVisible();
  await expect(page.locator('.project-view:visible .project-main-grid')).toContainText('LIB:KEEP');
  await page.locator('.titlebar').getByRole('button', { name: 'Undo', exact: true }).click();
  const revision = (await call('state')).result.revision;
  await call('resources.editor.add', { revision, data: { code: 'A', description: 'Same-code repair', rate: '1', category: 'Materials' } });
  // Reload resources through an ordinary view return after this external fixture edit.
  await page.locator('#view-schedule').click();
  await page.locator('#view-resources').click();
  const resource = page.locator('.project-view:visible .project-main-grid .tabulator-row').filter({ has: page.getByText('Same-code repair', { exact: true }) });
  await resource.locator('[tabulator-field="description"]').click();
  await ribbon.getByRole('button', { name: 'Rates from schedule', exact: true }).click();
  await expect(resource.locator('[tabulator-field="rate"]')).toHaveText('20');
  await page.locator('.titlebar').getByRole('button', { name: 'Undo', exact: true }).click();
  await expect(resource.locator('[tabulator-field="rate"]')).toHaveText('1');
});

test('multiple analysis workbook import previews matches and preserves metadata with one undo', async ({ page }) => {
  await refinementFixture(page);
  const workbook = resolve(directory, 'matched analyses.xlsx');
  const { execFileSync } = await import('node:child_process');
  execFileSync(python, ['-c', `import sys
from openpyxl import Workbook
b=Workbook()
for code in ['A','B','UNMATCHED']:
 for row in [[code,'Workbook description'],['','Description','Unit','Qty','Rate','Amount'],['','MATERIALS'],['X','Imported material','kg',2,10,20],['','Total','',0,0,20]]:
  b.active.append(row)
b.save(sys.argv[1])`, workbook], { cwd: resolve('..') });
  await page.getByRole('button', { name: 'Import multiple analyses', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Import analyses from Excel', exact: true });
  await dialog.getByLabel('Workbook', { exact: true }).fill(workbook);
  await dialog.getByLabel('Workbook', { exact: true }).press('Enter');
  await dialog.getByLabel('Resource comments').selectOption('0');
  await dialog.getByLabel('Rounding', { exact: true }).selectOption('2');
  await expect(dialog.getByRole("status").filter({ hasText: "not in this project" })).toHaveText("2 matched · 1 not in this project");
  await expect(dialog.getByRole('region', { name: 'Import preview' })).toContainText('Not in project – skipped');
  await dialog.getByRole('button', { name: 'Import 2 analyses', exact: true }).click();
  await expect(dialog).not.toBeVisible();
  const grid = page.locator('.project-view:visible .project-main-grid');
  await expect(grid).toContainText('Foundation');
  await expect(grid).toContainText('Masonry');
  const masonry = grid.locator('.tabulator-row').filter({ has: page.getByText('Masonry', { exact: true }) });
  await expect(masonry.locator('[tabulator-field="rate"]')).toHaveText('20');
  await masonry.locator('[tabulator-field="description"]').click();
  await page.getByRole('button', { name: 'Edit analysis', exact: true }).click();
  await expect(page.locator('.analysis-table .tabulator-row[data-kind="Resource"] [tabulator-field="kind"]')).toContainText('X');
  await page.getByRole('button', { name: 'Discard analysis', exact: true }).click();
  await page.locator('.titlebar').getByRole('button', { name: 'Undo', exact: true }).click();
  await expect(masonry.locator('[tabulator-field="rate"]')).toHaveText('5');
});

test('measurement total footer includes off-page records', async ({ page }) => {
  await refinementFixture(page);
  async function edit(method: string, params = {}) {
    return (await call(method, { revision: (await call('state')).result.revision, ...params })).result;
  }
  const added = await edit('measurement.add', { template: '_1_NLBH', description: 'All-page total' });
  const id = added.selected[0];
  await edit('measurement.draft.open', { id });
  await edit('measurement.record_add', { id, count: 101 });
  const first = (await call('measurement.detail', { id })).result.detail.rows[0].id;
  const last = (await call('measurement.detail', { id, record_offset: 100 })).result.detail.rows[0].id;
  await edit('measurement.record_edit', { id, record_id: first, field: 'c3', value: '2' });
  await edit('measurement.record_edit', { id, record_id: last, field: 'c3', value: '3' });
  await edit('measurement.draft.apply');
  await page.locator('#view-measurement').click();
  await page.getByRole('grid', { name: 'Measurements', exact: true }).getByText('All-page total', { exact: true }).dblclick();
  const footer = page.getByRole('status', { name: 'All measurement records total', exact: true });
  await expect(footer).toContainText(/5(?:\.0+)?/);
  await expect(page.getByText('101 records · Page 1', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Next records', exact: true }).click();
  await expect(page.locator('.measurement-record-grid .tabulator-row')).toHaveCount(1);
  await expect(footer).toContainText(/5(?:\.0+)?/);
  const header = page.getByRole('region', { name: 'Measurement records draft', exact: true });
  await expect(header.getByRole('button', { name: 'Apply records', exact: true })).toBeVisible();
  await expect(page.locator('.ribbon').getByRole('button', { name: 'Apply records', exact: true })).toHaveCount(0);
  await page.screenshot({ path: 'test-results/measurement-headerbar-total.png', animations: 'disabled' });
});

test('themed dropdowns use anchored listboxes with groups keyboard and theme colours', async ({ page }) => {
  await refinementFixture(page);
  await page.locator('#view-measurement').click();
  await page.getByRole('button', { name: 'Add measurement', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Add item', exact: true });
  const select = dialog.getByLabel('Measurement template');
  await select.click();
  const list = page.getByRole('listbox', { name: 'Choose option' });
  await expect(list).toBeVisible();
  for (const theme of ['light', 'dark']) {
    await page.evaluate(value => { document.documentElement.dataset.theme = value; }, theme);
    await expect(list).toHaveCSS('background-color', theme === 'light' ? 'rgb(255, 255, 255)' : 'rgb(51, 51, 60)');
    await page.screenshot({ path: `test-results/themed-dropdown-${theme}.png`, animations: 'disabled' });
  }
  for (const group of ['General', 'Civil', 'E&M']) await expect(list.getByText(group, { exact: true })).toBeVisible();
  const field = await select.boundingBox(), bounds = await list.boundingBox();
  expect(Math.abs(field!.width - bounds!.width)).toBeLessThan(2);
  await list.getByRole('option', { name: 'NLBH (numbers, length, area, volume)', exact: true }).click();
  await expect(select).toHaveValue('_1_NLBH');
  await expect(select).toBeFocused();
  await select.press('ArrowDown');
  await select.press('End');
  await select.press('Home');
  await select.press('Enter');
  await expect(list).not.toBeVisible();
  await select.click();
  await select.press('Escape');
  await expect(dialog).toBeVisible();
  await expect(list).not.toBeVisible();
  await select.click();
  await select.press('Tab');
  await expect(list).not.toBeVisible();
  await dialog.getByRole('button', { name: 'Cancel', exact: true }).click();
});

test('Apply and Discard finish analysis and record editors and preserve only applied changes', async ({ page }) => {
  await refinementFixture(page);
  const item = page.locator('.project-view:visible .project-main-grid').getByText('Foundation', { exact: true });
  async function editQuantity(value: string) {
    await item.click();
    await page.getByRole('button', { name: 'Edit analysis', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Back to schedule', exact: true })).toHaveCount(0);
    const cell = page.locator('.analysis-table .tabulator-row[data-kind="Resource"] [tabulator-field="value"]');
    await cell.dblclick(); await cell.locator('input').fill(value); await cell.locator('input').press('Enter');
  }
  await editQuantity('3');
  await page.getByRole('button', { name: 'Apply analysis', exact: true }).click();
  await expect(page.locator('#view-schedule')).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator('.project-view:visible .project-main-grid')).toContainText('30');
  await editQuantity('4');
  await page.getByRole('button', { name: 'Discard analysis', exact: true }).click();
  await expect(page.locator('#view-schedule')).toHaveAttribute('aria-selected', 'true');
  expect((await call('state')).result.rate).toBe('30.00');
  const state = (await call('state')).result;
  await call('measurement.add', { revision: state.revision, template: '_1_NLBH', description: 'Finish records' });
  await page.locator('#view-measurement').click();
  const list = page.getByRole('grid', { name: 'Measurements', exact: true });
  await list.getByText('Finish records', { exact: true }).dblclick();
  await expect(page.getByRole('button', { name: 'Back to measurements', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Add record', exact: true }).click();
  await page.getByRole('button', { name: 'Apply records', exact: true }).click();
  await expect(list).toBeVisible();
  await list.getByText('Finish records', { exact: true }).dblclick();
  await page.getByRole('button', { name: 'Add record', exact: true }).click();
  await page.getByRole('button', { name: 'Discard records', exact: true }).click();
  await expect(list).toBeVisible();
  await list.getByText('Finish records', { exact: true }).dblclick();
  await expect(page.locator('.measurement-record-grid .tabulator-row')).toHaveCount(1);
  await page.getByRole('button', { name: 'Discard records', exact: true }).click();
  await expect(list).toBeVisible();
  await expect(page.getByRole('alert')).toHaveCount(0);
});

test('database enable switches have separate rows and checkbox labels align in settings', async ({ page }) => {
  await refinementFixture(page);
  for (const code of ['FIRST:R', 'SECOND:R']) await call('resources.editor.add', { revision: (await call('state')).result.revision, data: { code, rate: '1', category: 'Materials' } });
  await page.locator('#view-resources').click();
  await page.getByRole('button', { name: 'Renumber resources', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Renumber resources', exact: true });
  const first = dialog.getByRole('switch', { name: 'Renumber FIRST resources', exact: true });
  const second = dialog.getByRole('switch', { name: 'Renumber SECOND resources', exact: true });
  expect((await second.boundingBox())!.y).toBeGreaterThan((await first.boundingBox())!.y + (await first.boundingBox())!.height);
  await first.click(); await expect(first).toHaveAttribute('aria-checked', 'true');
  await dialog.getByRole('button', { name: 'Cancel', exact: true }).click();
  await page.getByRole('button', { name: 'Application menu', exact: true }).click();
  await page.getByRole('menuitem', { name: 'Program settings…', exact: true }).click();
  const settings = page.getByRole('dialog', { name: 'Program settings', exact: true });
  for (const checkbox of await settings.getByRole('checkbox').all()) {
    await expect(checkbox).toHaveCSS('width', '16px'); await expect(checkbox).toHaveCSS('height', '16px');
    const geometry = await checkbox.evaluate(el => { const input = el.getBoundingClientRect(), label = el.parentElement!.getBoundingClientRect(); return { left: input.left - label.left, top: input.top - label.top }; });
    expect(geometry.left).toBeGreaterThanOrEqual(0); expect(geometry.top).toBeLessThan(8);
  }
  await page.screenshot({ path: 'test-results/shared-checkbox-alignment.png', animations: 'disabled' });
});

test('locale choices are selection-only while category suggestions retain custom entry', async ({ page }) => {
  await refinementFixture(page);
  await page.getByRole('button', { name: 'Application menu', exact: true }).click();
  await page.getByRole('menuitem', { name: 'Program settings…', exact: true }).click();
  const settings = page.getByRole('dialog', { name: 'Program settings', exact: true });
  const locale = settings.getByLabel('Regional format', { exact: true });
  await expect(locale).toHaveJSProperty('tagName', 'SELECT');
  await locale.click();
  const formats = page.getByRole('listbox', { name: 'Regional format', exact: true });
  await formats.getByRole('option', { name: 'German (Germany) · de-DE', exact: true }).click();
  await expect(locale).toHaveValue('de-DE');
  await locale.selectOption('es-ES');
  await expect(locale).toHaveValue('es-ES');
  const suggestions = page.locator('.themed-autocomplete-options');
  await settings.getByRole('button', { name: 'Cancel', exact: true }).click();
  await page.getByRole('button', { name: 'Add item', exact: true }).click();
  const add = page.getByRole('dialog', { name: 'Add item', exact: true });
  const category = add.getByLabel('Category', { exact: true });
  await category.fill('Wor');
  await suggestions.getByRole('option', { name: 'Work', exact: true }).click();
  await expect(category).toHaveValue('Work');
  await category.fill('New typed category');
  await add.getByLabel('Description', { exact: true }).click();
  await expect(category).toHaveValue('New typed category');
  await category.fill('Wor');
  await expect(suggestions).toBeVisible();
  await category.press('Escape');
  await expect(add).toBeVisible();
  await expect(suggestions).not.toBeVisible();
  await expect(page.locator('input[list]')).toHaveCount(0);
});

test('measurement draft puts type and ordered actions on the first row in both themes', async ({ page }) => {
  await refinementFixture(page);
  const added = (await call('measurement.add', { revision: (await call('state')).result.revision, template: '_1_NLBH', description: 'Header layout room' })).result;
  await page.locator('#view-measurement').click();
  await page.getByRole('grid', { name: 'Measurements', exact: true }).getByText('Header layout room', { exact: true }).dblclick();
  const header = page.getByRole('region', { name: 'Measurement records draft', exact: true });
  await expect(header.locator('strong')).toHaveText('NLBH (numbers, length, area, volume)');
  await expect(page.locator('.measurement-summary')).toHaveCount(0);
  const discard = header.getByRole('button', { name: 'Discard records', exact: true });
  const apply = header.getByRole('button', { name: 'Apply records', exact: true });
  for (const width of [1280, 700]) {
    await page.setViewportSize({ width, height: 900 });
    const first = (await discard.boundingBox())!, second = (await apply.boundingBox())!;
    expect(first.x + first.width).toBeLessThanOrEqual(second.x);
    expect(Math.abs(first.y - second.y)).toBeLessThan(1);
    expect((await page.locator('.measurement-entry-heading').boundingBox())!.y).toBeGreaterThanOrEqual((await header.boundingBox())!.y + (await header.boundingBox())!.height);
  }
  await page.setViewportSize({ width: 1280, height: 900 });
  for (const theme of ['dark', 'light']) {
    if (await page.locator('html').getAttribute('data-theme') !== theme) await page.getByRole('button', { name: /Switch to .* theme/ }).click();
    await expect(page.locator('.titlebar')).toHaveCSS('background-color', theme === 'dark' ? 'rgb(42, 42, 50)' : 'rgb(244, 244, 245)');
    await expect(page.locator('.ribbon')).toHaveCSS('background-color', theme === 'dark' ? 'rgb(51, 51, 60)' : 'rgb(255, 255, 255)');
    const icon = page.getByRole('button', { name: 'Import records…', exact: true }).locator('svg');
    await expect(icon.locator('.icon-accent')).toHaveCSS('stroke', theme === 'dark' ? 'rgb(217, 119, 6)' : 'rgb(180, 83, 9)');
    await expect(icon).toHaveCSS('color', theme === 'dark' ? 'rgb(190, 189, 189)' : 'rgb(95, 95, 101)');
    await page.screenshot({ path: `test-results/measurement-type-header-${theme}.png`, animations: 'disabled' });
  }
  await apply.click();
  await expect(page.getByRole('grid', { name: 'Measurements', exact: true })).toBeVisible();
  expect((await call('measurement.detail', { id: added.selected[0] })).result.detail.total_records).toBe(0);
});

test('analysis header save applies without leaving and failed saves retain the draft', async ({ page }) => {
  const path = await refinementFixture(page);
  const original = await readFile(path);
  await page.locator('.project-view:visible .project-main-grid').getByText('Foundation', { exact: true }).click();
  await page.getByRole('button', { name: 'Edit analysis', exact: true }).click();
  const header = page.getByRole('region', { name: 'Analysis draft', exact: true });
  const save = header.getByRole('button', { name: 'Save analysis without leaving', exact: true });
  await expect(header.getByRole('button')).toHaveText(['Discard analysis', 'Save analysis', 'Apply analysis']);
  const actions = await header.getByRole('button').evaluateAll(buttons => buttons.map(button => button.getBoundingClientRect()));
  expect(new Set(actions.map(rect => Math.round(rect.height))).size).toBe(1);
  expect(actions[0]!.x + actions[0]!.width).toBeLessThanOrEqual(actions[1]!.x);
  expect(actions[1]!.x + actions[1]!.width).toBeLessThanOrEqual(actions[2]!.x);
  await expect(save.locator('svg')).toHaveAttribute('data-icon', 'save');
  const quantity = page.locator('.analysis-table .tabulator-row[data-kind="Resource"] [tabulator-field="value"]');
  await quantity.dblclick(); await quantity.locator('input').fill('3'); await quantity.locator('input').press('Enter');
  await expect(page.locator('.summary-value')).toContainText('30.00');
  await page.evaluate(() => {
    const w = window as any;
    const invoke = w.__TAURI_INTERNALS__.invoke;
    let rejectOnce = true;
    w.__TAURI_INTERNALS__.invoke = (method: string, args: any) => {
      if (rejectOnce && method === 'backend_request' && args.request.method === 'analysis.apply') {
        rejectOnce = false;
        return Promise.resolve({ error: { code: 'test_failure', message: 'Injected analysis save failure' } });
      }
      return invoke(method, args);
    };
  });
  await save.click();
  await expect(page.getByRole('alert')).toContainText('Injected analysis save failure');
  await expect(page.locator('#view-analysis')).toHaveAttribute('aria-selected', 'true');
  expect((await call('state')).result.dirty).toBe(true);
  await save.click();
  await expect(page.getByRole('alert')).toHaveCount(0);
  await expect(page.locator('#view-analysis')).toHaveAttribute('aria-selected', 'true');
  const saved = (await call('state')).result;
  expect(saved.dirty).toBe(false);
  expect(saved.workspace_dirty).toBe(true);
  expect(saved.rate).toBe('30.00');
  expect(await readFile(path)).toEqual(original);
  await quantity.dblclick(); await quantity.locator('input').fill('4'); await quantity.locator('input').press('Enter');
  await header.getByRole('button', { name: 'Discard analysis', exact: true }).click();
  await expect(page.locator('#view-schedule')).toHaveAttribute('aria-selected', 'true');
  const row = page.locator('.project-view:visible .project-main-grid .tabulator-row').filter({ has: page.getByText('Foundation', { exact: true }) });
  await expect(row.locator('[tabulator-field="rate"]')).toHaveText('30');
});


// Performance profile on a large real database: GESTIMATOR_PERF=1 npx playwright test -g "perf:"
test("perf: everyday operations on a large project", async ({ page }) => {
  test.skip(!process.env.GESTIMATOR_PERF, "Set GESTIMATOR_PERF=1 to profile");
  test.setTimeout(300000);
  const project = resolve(directory, "large.eproj");
  await copyFile(resolve("../Other databases/DSR2021_12GST.eproj"), project);
  await page.locator("#view-schedule").click();
  await openFixture(page, project);
  const grid = page.locator(".project-view:visible .project-main-grid");
  await expect(grid.locator(".tabulator-row").first()).toBeVisible();
  const ribbon = page.locator(".ribbon");
  const results: string[] = [];
  async function settle() {
    await expect.poll(() => requestTimings.some(timing => !timing.end), { intervals: [20] }).toBe(false);
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    await expect.poll(() => requestTimings.some(timing => !timing.end), { intervals: [20] }).toBe(false);
  }
  async function measure(label: string, action: () => Promise<void>) {
    await settle();
    const first = requestTimings.length;
    await page.evaluate(() => {
      const w = window as any;
      w.perfStart = performance.now(); w.perfLast = w.perfStart;
      w.perfObserver?.disconnect();
      w.perfObserver = new MutationObserver(() => { w.perfLast = performance.now(); });
      w.perfObserver.observe(document.body, { subtree: true, childList: true, attributes: true, characterData: true });
    });
    const started = performance.now();
    await action();
    await settle();
    await page.waitForTimeout(300);
    const visual = await page.evaluate(() => { const w = window as any; w.perfObserver.disconnect(); return w.perfLast - w.perfStart; });
    const total = performance.now() - started;
    const calls = requestTimings.slice(first);
    const backendMs = calls.reduce((sum, call) => sum + (call.end - call.start), 0);
    results.push(`${label.padEnd(34)} visual ${visual.toFixed(0).padStart(5)} ms  harness ${total.toFixed(0).padStart(5)} ms  backend ${backendMs.toFixed(0).padStart(5)} ms  requests ${calls.length}: ${calls.map(call => `${call.method}@${(call.start - started).toFixed(0)}+${(call.end - call.start).toFixed(0)}`).join(" ")}`);
    console.log(results[results.length - 1]);
  }
  const row = (n: number) => grid.locator('.tabulator-row[data-kind="Resource"] [tabulator-field="description"]').nth(n);
  async function dialogSubmit() {
    const dialog = page.getByRole("dialog").last();
    await dialog.locator(".button.primary").last().click();
    await expect(dialog).not.toBeVisible();
  }
  await row(3).click();
  await measure("open analysis (Ctrl+E)", async () => { await grid.press("Control+e"); await expect(page.locator("#view-analysis")).toHaveAttribute("aria-selected", "true"); });
  await measure("analysis -> schedule (no edit)", async () => { await page.locator("#view-schedule").click(); await expect(grid).toBeVisible(); });
  await row(3).click();
  await measure("add item", async () => { await ribbon.getByRole("button", { name: "Add item", exact: true }).click(); await dialogSubmit(); });
  await row(3).click();
  await measure("add subitem", async () => { await ribbon.getByRole("button", { name: "Add subitem", exact: true }).click(); await dialogSubmit(); });
  await measure("add category", async () => { await ribbon.getByRole("button", { name: "Add category", exact: true }).click(); const dialog = page.getByRole("dialog").last(); await dialog.getByRole("textbox").first().fill("Perf category"); await dialog.getByRole("textbox").first().press("Enter"); await expect(dialog).not.toBeVisible(); });
  await row(5).click();
  await measure("duplicate", async () => { await ribbon.getByRole("button", { name: "Duplicate", exact: true }).click(); await dialogSubmit(); });
  await row(5).click();
  await row(14).click({ modifiers: ["Shift"] });
  await measure("copy 10 rows", async () => { await ribbon.getByRole("button", { name: "Copy", exact: true }).click(); });
  await row(20).click();
  await measure("paste 10 rows", async () => { await ribbon.getByRole("button", { name: "Paste", exact: true }).click(); });
  await measure("undo", async () => { await page.locator(".titlebar").getByRole("button", { name: "Undo", exact: true }).click(); });
  await measure("renumber schedule", async () => { await ribbon.getByRole("button", { name: "Renumber schedule…", exact: true }).click(); await dialogSubmit(); });
  await measure("edit cell (remarks)", async () => {
    const cell = grid.locator('.tabulator-row[data-kind="Resource"] [tabulator-field="remarks"]').nth(2);
    await cell.dblclick(); await page.keyboard.type("perf"); await page.keyboard.press("Enter");
  });
  await attachDatabase(page, resolve("../estimator/database/DSR2021.eproj"));
  await row(8).click();
  await measure("open database picker", async () => { await ribbon.getByRole("button", { name: "Add item from database", exact: true }).click(); await expect(page.getByRole("dialog", { name: "Add item from database" }).locator(".tabulator-row").first()).toBeVisible(); });
  const picker = page.getByRole("dialog", { name: "Add item from database" });
  const pick = picker.locator('.tabulator-row[data-kind="Resource"] [tabulator-field="code"]');
  await pick.nth(2).click();
  await pick.nth(12).click({ modifiers: ["Shift"] });
  await measure("add 11 from database", async () => { await picker.getByRole("button", { name: "Add selected items", exact: true }).click(); await expect(picker).not.toBeVisible(); });
  await measure("search schedule", async () => {
    const search = page.locator(".project-view:visible").getByPlaceholder(/Search codes/);
    await search.fill("cement concrete"); await search.press("Enter");
  });
  await measure("switch to resources", async () => { await page.locator("#view-resources").click(); });
  const rrow = (n: number) => page.locator(".project-view:visible .project-main-grid").locator('.tabulator-row[data-kind="Resource"] [tabulator-field="description"]').nth(n);
  await rrow(3).click();
  await measure("add resource", async () => { await ribbon.getByRole("button", { name: "Add item", exact: true }).click(); await dialogSubmit(); });
  await rrow(4).click();
  await measure("edit resource rate", async () => {
    const cell = page.locator(".project-view:visible .project-main-grid").locator('.tabulator-row[data-kind="Resource"] [tabulator-field="rate"]').nth(4);
    await cell.dblclick(); await page.keyboard.type("123"); await page.keyboard.press("Enter");
  });
  await measure("switch to schedule", async () => { await page.locator("#view-schedule").click(); });
  console.log("PERF\n" + results.join("\n"));
});
