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
let backend: ReturnType<typeof createBackend>;
function call(method: string, params: Record<string, unknown> = {}) {
  return backend.call(method, params);
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
    call(method: string, params: Record<string, unknown> = {}) {
      const id = String(++sequence);
      return new Promise<any>((resolve, reject) => {
        pending.set(id, { resolve, reject });
        process.stdin.write(JSON.stringify({ id, method, params }) + "\n");
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
    frontendRequests.push(request.method + (request.params?.source ? ":library" : ""));
    if (request.method === "measurement.state" && measurementDelay)
      await new Promise(resolve => setTimeout(resolve, measurementDelay));
    return transport(request.method, request.params);
  });
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
      metadata: { currentWindow: { label: "main" } },
      transformCallback: () => ++callbackId,
      invoke: (method: string, args: any) => {
        if (method === "desktop_font")
          return Promise.resolve({ family: "Iosevka", size: "11pt" });
        if (method.startsWith("plugin:event|")) return Promise.resolve(1);
        if (method === "backend_request")
          return (window as any).backendTransport(args.request);
        if (method.startsWith("plugin:clipboard-manager|"))
          return (window as any).clipboardTransport(method.split("|")[1], args?.text);
        if (method.startsWith("plugin:dialog|")) return Promise.resolve(null);
        if (method.startsWith("plugin:window|")) {
          ((window as any).windowCommands ||= []).push(method);
          return Promise.resolve();
        }
        throw new Error("Unexpected desktop command: " + method);
      },
    };
  });
  await page.goto("/");
  await expect(page.getByText("Calculation engine connected")).toBeVisible();
}
test.beforeEach(async ({ page }) => {
  directory = await mkdtemp(resolve(tmpdir(), "gestimator-ui-"));
  measurementDelay = 0;
  systemClipboard = "";
  clipboardUnavailable = false;
  frontendRequests = [];
  startBackend();
  await connectDesktop(page);
});
test.afterEach(async () => {
  child.stdin.end();
  await new Promise<void>((resolve) => child.once("close", () => resolve()));
  await rm(directory, { recursive: true, force: true });
});

async function openFixture(page: Page, path: string) {
  await page.locator(".titlebar").getByRole("button", { name: "Open project", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Open project", exact: true });
  await dialog.getByLabel("Project file").fill(path);
  await dialog.getByRole("button", { name: "Open project", exact: true }).click();
  await expect(dialog).not.toBeVisible();
}
async function pasteDocument(page: Page, selector: string, data: string) {
  await page.locator(selector).evaluate((table, text) => {
    const clipboardData = new DataTransfer();
    clipboardData.setData("text/plain", text);
    table.dispatchEvent(new ClipboardEvent("paste", { bubbles: true, cancelable: true, clipboardData }));
  }, data);
}
async function openDatabaseManager(page: Page) {
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
  await page.locator("#view-" + returnView).click();
}

async function refinementFixture(page: Page) {
  const { execFileSync } = await import("node:child_process");
  const path = resolve(directory, "refinements.eproj");
  execFileSync(python, ["-m", "modern.e2e.create_fixture", path], { cwd: resolve("..") });
  execFileSync(python, ["-c", "import sys;from estimator.data.schedule import ScheduleDatabase,ScheduleItemModel,ResourceItemModel;from estimator.undo import Stack;d=ScheduleDatabase(Stack());d.open_database(sys.argv[1]);d.insert_item_atomic(ScheduleItemModel('B','Masonry','m2',rate=5,qty=1,category='Other'));d.insert_schedule_category_atomic('Empty');d.insert_resource(ResourceItemModel('L','Worker','day',5,category='Labour'));d.close_database()", path], { cwd: resolve("..") });
  await openFixture(page, path);
  await page.locator("#view-schedule").click();
  return path;
}

test("compact contrast, category filters, expanded trees and client window controls", async ({ page }) => {
  await refinementFixture(page);
  const grid = page.locator(".project-main-grid");
  await expect(grid.locator('.tabulator-col[tabulator-field="category"],.tabulator-col[tabulator-field="parent"]')).toHaveCount(0);
  await expect(grid.locator(".tabulator-data-tree-control")).toHaveCount(0);
  await expect(grid.locator('.tabulator-row[data-kind="Group"] [tabulator-field="description"]').first()).toHaveCSS("font-weight", "700");
  await page.getByRole("button", { name: "Switch to light theme", exact: true }).click();
  await expect(grid.locator('.tabulator-row [tabulator-field="code"]').filter({ hasText: /^A$/ })).toHaveCSS("color", "rgb(17, 24, 39)");
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
  const buttons = await minor.locator(".ribbon-action").evaluateAll(elements => elements.map(element => element.getBoundingClientRect()));
  expect(new Set(buttons.map(button => Math.round(button.top))).size).toBe(3);
  expect(Math.max(...buttons.map(button => button.left)) - Math.min(...buttons.map(button => button.left))).toBeLessThan(1);
  const full = page.locator('.ribbon-action').filter({ has: page.locator('.ribbon-label').filter({ hasText: /^Add from database$/ }) });
  expect((await full.boundingBox())!.width).toBeLessThan(80);
  expect(await full.locator(".ribbon-label").evaluate(element => element.scrollHeight <= element.clientHeight + 1)).toBe(true);
  await expect(page.locator(".titlebar-project")).toHaveAttribute("data-tauri-drag-region", "");
  for (const name of ["Minimize window", "Maximize or restore window", "Close window"]) await page.locator(".window-controls").getByRole("button", { name, exact: true }).click();
  expect(await page.evaluate(() => (window as any).windowCommands)).toEqual(expect.arrayContaining(["plugin:window|minimize", "plugin:window|toggle_maximize", "plugin:window|close"]));
  await page.screenshot({ path: "test-results/compact-light-categories.png", animations: "disabled" });
});

test("cell navigation commits and continues editing across schedule resources measurements and analysis", async ({ page }) => {
  await refinementFixture(page);
  const main = page.locator(".project-main-grid");
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
  await active().press("ArrowRight");
  await field("remarks");
  await expect(row("A").locator('[tabulator-field="amount"]')).toHaveText("12.00");
  await active().fill("Accepted remark");
  await active().press("Shift+Tab");
  await field("qty");
  await active().press("ArrowDown");
  await expect(row("B").locator('[tabulator-field="qty"] input')).toBeFocused();
  await active().fill("4");
  await active().press("ArrowUp");
  await expect(row("A").locator('[tabulator-field="qty"] input')).toBeFocused();
  await active().press("ArrowLeft");
  await field("rate");
  await active().fill("1/0");
  await active().press("Tab");
  await field("rate");
  await expect(active()).toHaveValue("1/0");
  await active().fill("8");
  await active().press("Tab");
  await field("qty");
  await active().press("Escape");
  await page.locator("#view-resources").click();
  await row("R").locator('[tabulator-field="rate"]').click();
  await page.keyboard.press("Enter");
  await active().fill("2*3");
  await active().press("ArrowRight");
  await field("vat");
  await active().fill("5");
  await active().press("Shift+Tab");
  await field("rate");
  await active().press("ArrowDown");
  await expect(row("L").locator('[tabulator-field="rate"] input')).toBeFocused();
  await active().press("Escape");
  await page.locator("#view-measurement").click();
  await page.getByRole("button", { name: "Add measurement", exact: true }).click();
  const add = page.getByRole("dialog", { name: "Add item", exact: true });
  await add.getByLabel("Measurement template").selectOption("_1_NLBH");
  await add.getByLabel("Description / remarks").fill("Dimensions");
  await add.getByRole("button", { name: "Add item", exact: true }).click();
  await expect(add).not.toBeVisible();
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
  await active(records).press("ArrowDown");
  await field("c3", records);
  await active(records).fill("2");
  await active(records).press("ArrowLeft");
  await field("c2", records);
  await active(records).press("ArrowUp");
  await expect(active(records)).toHaveValue("2*3");
  await active(records).press("Shift+Tab");
  await field("c0", records);
  await active(records).fill("Record");
  await active(records).press("Shift+Enter");
  await active(records).pressSequentially("Second line");
  await active(records).press("ArrowDown");
  await field("c0", records);
  await expect(records.locator('.tabulator-row [tabulator-field="c0"]').first()).toHaveText("Record\nSecond line");
  await active(records).press("Escape");
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
  await field("rate", analysis);
  await active(analysis).fill("5");
  await active(analysis).press("ArrowRight");
  await field("vat", analysis);
  await active(analysis).fill("10");
  await active(analysis).press("Shift+Tab");
  await field("rate", analysis);
  await expect(page.locator(".summary-value")).toContainText("33.00");
  await active(analysis).press("ArrowLeft");
  await field("value", analysis);
  await active(analysis).press("Enter");
  await expect(analysis.locator('.tabulator-row[data-kind="Round"] [tabulator-field="value"] input')).toBeFocused();
  await active(analysis).press("ArrowUp");
  await expect(analysis.locator('.tabulator-row[data-kind="Resource"] [tabulator-field="value"] input')).toBeFocused();
  await active(analysis).press("Escape");
  await expect(analysis.locator(".tabulator-data-tree-control")).toHaveCount(0);
  await page.setViewportSize({ width: 1100, height: 1000 });
  await analysis.focus();
  await page.keyboard.press("Enter");
  await active(analysis).press("Tab");
  await field("rate", analysis);
  await active(analysis).press("ArrowRight");
  await field("vat", analysis);
  const editorBounds = (await active(analysis).boundingBox())!;
  const fixedHeader = analysis.locator('.tabulator-col[tabulator-field="amount"]');
  await expect(fixedHeader).toHaveCSS("background-color", "rgb(29, 34, 43)");
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
  await page.locator("#view-mcp").click();
  await page.getByRole("button", { name: "Configure MCP server", exact: true }).click();
  const config = page.getByRole("dialog", { name: "Configure MCP server", exact: true });
  await config.getByLabel("Port", { exact: true }).fill(String(port));
  await config.getByLabel("Access mode", { exact: true }).click();
  await page.locator(".themed-select-menu").getByRole("menuitem", { name: "Read and write", exact: true }).click();
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
  await page.locator("#view-schedule").click();
  await agent("upsert_items", { kind: "schedule", items: [{ code: item.code, description: "Edited by agent" }] }, true);
  await page.clock.runFor(1600);
  const grid = page.locator(".project-main-grid");
  await expect(grid.getByText("Edited by agent", { exact: true })).toBeVisible();
  const qty = grid.locator('.tabulator-row').filter({ has: page.locator('[tabulator-field="code"]').filter({ hasText: /^A$/ }) }).locator('[tabulator-field="qty"]');
  await qty.click();
  await page.keyboard.press("Enter");
  await qty.locator("input").fill("13");
  await agent("upsert_items", { kind: "schedule", items: [{ code: item.code, description: "Agent changed another field" }] }, true);
  await page.clock.runFor(1700);
  await expect(qty.locator("input")).toHaveValue("13");
  await qty.locator("input").press("Tab");
  await expect(page.locator(".project-view").getByRole("alert")).toContainText("Stale");
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
  await expect(page.locator(".project-view h1")).toHaveText("Schedule of quantities");
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
  const grid = page.locator(".project-main-grid");
  await expect(grid.locator('.tabulator-selected [tabulator-field="code"]')).toHaveText("A");
  await expect(grid.locator('.tabulator-row [tabulator-field="rate"]').last()).toHaveText("50");
  await expect(ribbon.getByRole("button", { name: "Refresh selected rates from database", exact: true })).toHaveCount(0);
  await page.locator("#view-resources").click();
  await grid.locator('.tabulator-row [tabulator-field="code"]').filter({ hasText: /^R$/ }).click();
  await ribbon.getByRole("button", { name: "Refresh selected rates from database", exact: true }).click();
  const rates = page.getByRole("dialog", { name: "Refresh selected rates from database", exact: true });
  await rates.getByLabel("Database", { exact: true }).click();
  const menu = page.locator(".themed-select-menu");
  await expect(menu).toBeVisible();
  await menu.getByRole("menuitem", { name: "picker-second", exact: true }).click();
  await expect(menu).not.toBeVisible();
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
  expect(await page.evaluate(() => window.getSelection()?.toString())).toBe("");
  await page.screenshot({ path: `test-results/database-${kind}-row-selection.png`, animations: "disabled" });
  await picker.getByRole("button", { name: "Add selected items", exact: true }).click();
  await expect(picker).not.toBeVisible();
  const project = page.locator(".project-main-grid");
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
    await page.locator("#view-analysis").click();
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
  await page.locator("#view-schedule").click();
  const ribbon = page.locator(".ribbon"), grid = page.locator(".project-main-grid");
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
  await expect(ribbon.getByRole("button", { name: "Bulk edit analysis…", exact: true }).locator(".ribbon-label")).toHaveText("Bulk edit analysis");
  await expect(ribbon.getByRole("button", { name: "Duplicate", exact: true })).not.toHaveClass(/ribbon-icon/);
  await ribbon.getByRole("button", { name: "Bulk edit analysis…", exact: true }).click();
  await expect(dialog.getByLabel("Schedule scope")).toHaveValue("selected");
  await expect(dialog.getByLabel("Schedule scope")).toContainText("Current schedule item A");
  await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
  await page.getByRole("button", { name: "Back to schedule", exact: true }).click();
  await expect(grid).toBeVisible();
  await ribbon.getByRole("button", { name: "Bulk edit analysis…", exact: true }).click();
  await expect(dialog.getByLabel("Schedule scope")).toHaveValue("all");
  await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
  await grid.locator('.tabulator-row [tabulator-field="code"]').filter({ hasText: /^A$/ }).click();
  await ribbon.getByRole("button", { name: "Edit analysis", exact: true }).click();
  await page.locator('.analysis-table .tabulator-row[data-kind="Weight"] [tabulator-field="value"]').dblclick();
  await page.locator('.analysis-table [tabulator-field="value"] input').fill("0.3");
  await page.locator('.analysis-table [tabulator-field="value"] input').press("Enter");
  await expect(page.locator(".draft-badge")).toContainText("Unsaved changes");
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
  await page.locator("#view-schedule").click();
  const selected = page.locator('.project-main-grid .tabulator-selected [tabulator-field="code"]');
  await page.locator('.project-main-grid [tabulator-field="description"]').filter({ hasText: "Foundation" }).click();
  await expect(selected).toHaveText("A");
  for (const tab of ["databases", "mcp"]) {
    await page.locator("#view-" + tab).click();
    await expect(page.locator(".project-view h1")).toHaveText("Schedule of quantities");
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
  await page.locator("#view-schedule").click();
  await ribbon.getByRole("button", { name: "Edit analysis", exact: true }).click();
  await page.locator('.analysis-table .tabulator-row[data-kind="Resource"] [tabulator-field="value"]').dblclick();
  const editor = page.locator('.analysis-table [tabulator-field="value"] input');
  await editor.fill("3");
  await editor.press("Enter");
  await expect(page.locator(".summary-value")).toContainText("30.00");
  const before = (await call("state")).result;
  for (const tab of ["databases", "mcp", "analysis"]) {
    await page.locator("#view-" + tab).click();
    await expect(page.getByRole("dialog", { name: /Unsaved/ })).toHaveCount(0);
    await expect(page.locator(".analysis-table")).toBeVisible();
  }
  expect((await call("state")).result).toEqual(before);
  await page.locator("#view-mcp").click();
  await ribbon.getByRole("button", { name: "Stop MCP server", exact: true }).click();
  await expect(ribbon.getByRole("button", { name: "Start MCP server", exact: true })).toBeEnabled();
  // Restart the real backend; saved automatic-start settings must restore the endpoint.
  child.stdin.end();
  await new Promise<void>(resolve => child.once("close", () => resolve()));
  startBackend();
  await page.reload();
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
    await expect(page.locator("#view-analysis")).toHaveAttribute("aria-selected", "true");
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
  await page.locator("#view-measurement").click();
  await page.locator(".ribbon").getByRole("button", { name: "Add measurement", exact: true }).click();
  const add = page.getByRole("dialog", { name: "Add item", exact: true });
  await add.getByLabel("Measurement template").click();
  const menu = page.locator(".themed-select-menu");
  for (const group of ["General", "Civil", "E&M"]) await expect(menu.getByText(group, { exact: true })).toBeVisible();
  await menu.getByRole("menuitem", { name: "NLBH (numbers, length, area, volume)", exact: true }).click();
  const description = add.getByLabel("Description / remarks");
  await description.fill("Dimensions");
  await description.press("Shift+Enter");
  await description.pressSequentially("Second line");
  await description.press("Control+Enter");
  await description.pressSequentially("Third line");
  await expect(description).toHaveValue("Dimensions\nSecond line\nThird line");
  await description.press("Enter");
  await expect(add).not.toBeVisible();
  await expect(page.locator('.project-main-grid .tabulator-row [tabulator-field="description"]')).toHaveText("Dimensions\nSecond line\nThird line");
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

    await page.locator("#view-resources").click();
    await page.locator('.project-main-grid [tabulator-field="description"]').filter({ hasText: /^Material$/ }).click();
    await page.locator(".ribbon").getByRole("button", { name: "Copy", exact: true }).click();
    await expect.poll(() => { try { return JSON.parse(systemClipboard).kind; } catch { return ""; } }).toBe("resources");
    await destination.locator("#view-resources").click();
    await destination.locator(".ribbon").getByRole("button", { name: "Paste", exact: true }).click();
    await expect(destination.locator('.project-main-grid .tabulator-row [tabulator-field="code"]').filter({ hasText: /^R-copy$/ })).toHaveCount(1);
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
    await page.locator("#view-measurement").click();
    await page.locator('.project-main-grid [tabulator-field="description"]').filter({ hasText: "Copied dimensions" }).click();
    await page.locator(".ribbon").getByRole("button", { name: "Copy", exact: true }).click();
    await expect.poll(() => { try { return JSON.parse(systemClipboard).kind; } catch { return ""; } }).toBe("measurement");
    await other.call("project.new");
    const destination = await context.newPage();
    await connectDesktop(destination, other.call);
    await destination.locator("#view-measurement").click();
    await destination.locator(".ribbon").getByRole("button", { name: "Paste", exact: true }).click();
    await destination.locator('.project-main-grid [tabulator-field="description"]').filter({ hasText: "Copied dimensions" }).click();
    await expect(destination.locator('.measurement-record-grid .tabulator-row [tabulator-field="c2"]')).toHaveText("6");
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
  await page.locator("#view-schedule").click();
  const main = page.locator(".project-main-grid");
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
  await expect(page.locator("#view-analysis")).toHaveAttribute("aria-selected", "true");
  await page.getByRole("grid", { name: "Rate analysis table" }).focus();
  await page.keyboard.press("ControlOrMeta+i");
  const resource = page.getByRole("dialog", { name: "Add resource", exact: true });
  await expect(resource.getByRole("tab", { name: "From library" })).toHaveAttribute("aria-selected", "true");
  await resource.getByRole("button", { name: "Close", exact: true }).click();
  await expect(resource).not.toBeVisible();
  await page.getByRole("grid", { name: "Rate analysis table" }).focus();
  await page.keyboard.press("ControlOrMeta+Shift+i");
  await expect(resource.getByRole("tab", { name: "Custom resource" })).toHaveAttribute("aria-selected", "true");
  await resource.getByRole("button", { name: "Close", exact: true }).click();
  await expect(resource).not.toBeVisible();
  await page.locator("#view-resources").click();
  await main.locator('[tabulator-field="description"]').filter({ hasText: /^Materials$/ }).click();
  // GTK accelerators also work while focus is in the active ribbon.
  await page.locator(".ribbon").getByRole("button", { name: "Add item", exact: true }).focus();
  await page.keyboard.press("ControlOrMeta+i");
  await expect(add.getByRole("combobox", { name: "Category", exact: true })).toHaveValue("Materials");
  await add.getByRole("button", { name: "Close", exact: true }).click();
  await expect(add).not.toBeVisible();
  await page.locator("#view-measurement").click();
  await main.locator(".project-grid").focus();
  await page.keyboard.press("ControlOrMeta+i");
  await add.getByLabel("Measurement template").selectOption("_1_NLBH");
  await add.getByLabel("Description / remarks").fill("Dimensions");
  await add.getByRole("button", { name: "Add item", exact: true }).click();
  await expect(add).not.toBeVisible();
  await main.locator('[tabulator-field="description"]').filter({ hasText: "Dimensions" }).click();
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
  await page.locator("#view-measurement").click();
  await page.locator(".ribbon").getByRole("button", { name: "Add measurement", exact: true }).click();
  const add = page.getByRole("dialog", { name: "Add item", exact: true });
  await add.getByLabel("Measurement template").selectOption("civil_steel_table");
  await expect(add).toContainText("mass-per-length");
  await add.getByLabel("Description / remarks").fill("Steel quantities");
  await add.getByRole("button", { name: "Add item", exact: true }).click();
  await expect(add).not.toBeVisible();
  await expect(page.getByRole("button", { name: "Properties…", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Properties…", exact: true }).click();
  const properties = page.getByRole("dialog", { name: "Measurement properties", exact: true });
  await properties.getByLabel("Description / remarks").fill("Discarded change");
  await properties.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(page.locator(".project-main-grid")).not.toContainText("Discarded change");
  await page.getByRole("button", { name: "Properties…", exact: true }).click();
  await properties.getByLabel("Item 1 constant", { exact: true }).fill("1/0");
  await properties.getByRole("button", { name: "Save properties", exact: true }).click();
  await expect(properties.getByRole("alert")).toContainText("Invalid numeric");
  await properties.getByLabel("Item 1 constant", { exact: true }).fill("2*3");
  await properties.getByLabel("Item 1 Label", { exact: true }).fill("<img src=x onerror=alert(1)>");
  await properties.getByRole("button", { name: "Choose property schedule item 1", exact: true }).click();
  const picker = page.getByRole("dialog", { name: "Choose schedule item", exact: true });
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
  await expect(page.locator(".project-view .pagination")).toContainText("120 records · Page 1");
  await page.getByRole("button", { name: "Next records", exact: true }).click();
  await expect(records.locator(".tabulator-row")).toHaveCount(20);
  await expect(records).toHaveAttribute("aria-busy", "false");
  await expect(page.locator(".project-main-grid .tabulator-selected")).toHaveCount(1);
  await records.focus();
  await expect(records).toBeFocused();
  await page.keyboard.press("ControlOrMeta+a");
  expect(errors).toEqual([]);
  await expect(records.locator(".tabulator-selected")).toHaveCount(20);
  await expect(page.getByRole("button", { name: "Copy record", exact: true })).toBeEnabled();
  await expect(page.locator(".project-main-grid .tabulator-selected")).toHaveCount(1);
  await page.keyboard.press("ControlOrMeta+c");
  await expect.poll(() => { try { return JSON.parse(systemClipboard).items.length; } catch { return 0; } }).toBe(20);
  await page.getByRole("button", { name: "Paste record", exact: true }).click();
  await expect(page.locator(".project-view .pagination")).toContainText("140 records");
  await page.locator(".titlebar").getByRole("button", { name: "Undo", exact: true }).click();
  await expect(page.locator(".project-view .pagination")).toContainText("120 records");
  await records.focus();
  await page.keyboard.press("ControlOrMeta+a");
  await page.keyboard.press("Delete");
  await expect(page.locator(".project-view .pagination")).toContainText("100 records");
  await expect(page.getByRole("button", { name: "Next records", exact: true })).toBeDisabled();
  const firstCount = records.locator('.tabulator-row [tabulator-field="c1"]').first();
  await firstCount.click();
  await pasteDocument(page, ".measurement-record-grid .project-grid", "2*3\t4");
  await expect(firstCount).toHaveText("6");
  await firstCount.dblclick();
  await firstCount.locator("textarea").fill("1/0");
  await page.locator(".project-main-grid .tabulator-header").click();
  await expect(page.locator(".project-view").getByRole("alert")).toContainText("Invalid numeric");
  await expect(firstCount).toHaveText("6");
  expect(errors).toEqual([]);
});

test("insertion reveals new rows, F2 edits the selection and resource moves preserve links", async ({ page }) => {
  const { execFileSync } = await import("node:child_process");
  const project = resolve(directory, "editor-parity.eproj");
  execFileSync(python, ["-m", "modern.e2e.create_fixture", project], { cwd: resolve("..") });
  const original = await readFile(project);
  await openFixture(page, project);
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
  await page.locator(".project-main-grid .tabulator-header").click();
  await expect(table.locator('.tabulator-selected [tabulator-field="description"]')).toContainText("Revised work");
  await table.getByRole("gridcell", { name: "Foundation", exact: true }).click({ button: "right" });
  await page.getByText("Open analysis", { exact: true }).click();
  await expect(page.locator("#view-analysis")).toHaveAttribute("aria-selected", "true");
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

test("bulk analysis preview is atomic and custom templates persist without changing source files", async ({ page }) => {
  const { execFileSync } = await import("node:child_process");
  const project = resolve(directory, "batch.eproj");
  execFileSync(python, ["-m", "modern.e2e.create_fixture", project], { cwd: resolve("..") });
  const source = await readFile(project);
  await page.locator(".titlebar").getByRole("button", { name: "Open project", exact: true }).click();
  const open = page.getByRole("dialog", { name: "Open project", exact: true });
  await open.getByLabel("Project file").fill(project);
  await open.getByRole("button", { name: "Open project", exact: true }).click();
  await expect(open).not.toBeVisible();
  await page.locator("#view-schedule").click();
  await page.locator('.project-main-grid [tabulator-field="description"]').filter({ hasText: "Foundation" }).click();
  await page.locator(".ribbon").getByRole("button", { name: "Edit analysis", exact: true }).click();
  await page.locator('.tabulator-row[data-kind="Resource"] [tabulator-field="kind"]').click();
  await page.locator(".ribbon").getByRole("button", { name: "Edit selected analysis rows…" }).click();
  const bulk = page.getByRole("dialog", { name: "Edit selected analysis rows", exact: true });
  await bulk.getByLabel("Field to change").selectOption("rate");
  await bulk.getByLabel("New value").fill("1/0");
  await bulk.getByRole("button", { name: "Preview changes" }).click();
  await expect(bulk.getByRole("alert")).toContainText("Invalid numeric");
  await expect(bulk.getByRole("button", { name: "Apply batch" })).toBeDisabled();
  await bulk.getByLabel("New value").fill("15.555");
  await bulk.getByRole("button", { name: "Preview changes" }).click();
  await expect(bulk.locator(".batch-preview")).toContainText("31.12");
  await expect(page.locator(".summary-value")).toContainText("20.00");
  await bulk.getByRole("button", { name: "Apply batch" }).click();
  await expect(bulk).not.toBeVisible();
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
  await page.locator(".titlebar").getByRole("button", { name: "Open project", exact: true }).click();
  const open = page.getByRole("dialog", { name: "Open project", exact: true });
  await open.getByLabel("Project file").fill(project);
  await open.getByRole("button", { name: "Open project", exact: true }).click();
  await expect(open).not.toBeVisible();
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
  await expect(page.locator("#view-analysis")).toHaveAttribute("aria-selected", "true");
  const analysis = page.getByRole("grid", { name: "Rate analysis table" });
  await analysis.focus();
  await page.keyboard.press("ControlOrMeta+a");
  await expect(page.locator(".table-toolbar")).toContainText("3 selected");
  await page.keyboard.press("Escape");
  await expect(analysis.locator(".tabulator-row.tabulator-selected")).toHaveCount(0);
  await page.locator("#view-measurement").click();
  await expect(page.locator("#view-measurement")).toHaveAttribute("aria-selected", "true");
  expect(errors).toEqual([]);
  await expect(page.locator(".project-view h1")).toHaveText("Measurements");
  await page.locator(".ribbon").getByRole("button", { name: "Add measurement", exact: true }).click();
  const add = page.getByRole("dialog", { name: "Add item", exact: true });
  await add.getByLabel("Measurement template").selectOption("civil_steel_table");
  await add.getByLabel("Description / remarks").fill("Steel reinforcement");
  await add.getByRole("button", { name: "Add item", exact: true }).click();
  await expect(add).not.toBeVisible();
  await page.locator('.project-main-grid [tabulator-field="description"]').filter({ hasText: "Steel reinforcement" }).click();
  await page.locator(".project-view").getByRole("button", { name: "Add record", exact: true }).click();
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
  await page.locator(".project-main-grid .tabulator-header").click();
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
  const grid = page.locator(".project-main-grid");
  await expect(grid.locator('.tabulator-row [tabulator-field="rate"]').last()).toHaveText(/^40(\.0+)?$/);
  await page.locator(".titlebar").getByRole("button", { name: "Undo", exact: true }).click();
  await expect(grid).not.toContainText("Foundation");
  await page.locator(".titlebar").getByRole("button", { name: "Redo", exact: true }).click();
  const description = grid.locator('[tabulator-field="description"]').filter({ hasText: "Foundation" });
  await description.dblclick();
  await grid.locator('[tabulator-field="description"] textarea').fill("First line\nSecond line");
  await page.locator(".project-main-grid .tabulator-header").click();
  const exportWorkbook = async (name: string) => {
    await ribbon.getByRole("button", { name: "Export workbook", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "Export project workbook", exact: true });
    const output = resolve(directory, name);
    await dialog.getByLabel(/New Excel file/).fill(output);
    await dialog.getByRole("button", { name: "Export workbook", exact: true }).click();
    await expect(dialog).not.toBeVisible();
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

test("resource editing, authoritative calculations, undo and workspace presentation", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page
    .getByRole("button", { name: "Add resource", exact: true })
    .first()
    .click();
  await page.getByRole("tab", { name: "Custom resource" }).click();
  const dialog = page.getByRole("dialog", {
    name: "Add resource",
    exact: true,
  });
  await dialog.getByLabel("Resource code").fill("MAT-001");
  await dialog.getByLabel("Unit", { exact: true }).fill("kg");
  await dialog
    .getByLabel("Description")
    .fill("Concrete constituent\nLong multiline resource description");
  await dialog.getByLabel("Base rate").fill("10.05");
  await dialog.getByLabel("Quantity").fill("2.5");
  await dialog.getByLabel("VAT %").fill("18");
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
  await descriptionCell
    .locator("textarea")
    .fill("Concrete constituent\nEdited multiline description");
  await page.locator(".analysis-heading h1").click();
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
  await ribbon
    .getByRole("button", { name: "Compact rows", exact: true })
    .click();
  await expect(page.locator(".analysis-table")).toHaveClass(/compact/);
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
  await page
    .getByRole("button", { name: "Open project", exact: true })
    .first()
    .click();
  let dialog = page.getByRole("dialog", { name: "Open project", exact: true });
  await dialog
    .getByLabel("Project file")
    .fill(resolve("../estimator/database/DSREM2022.eproj"));
  await dialog
    .getByRole("button", { name: "Open project", exact: true })
    .click();
  await expect(dialog).not.toBeVisible();
  const search = page.getByRole("textbox", { name: "Find schedule items" });
  await search.fill("1.1.1");
  await search.press("Enter");
  await expect(page.locator(".item-card").first()).toBeVisible();
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
  await expect(
    page.getByRole("dialog", { name: "Keep your analysis changes?" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Keep editing" }).click();
  await expect(page.locator(".draft-badge")).toContainText("Unsaved changes");
  await page.getByRole("button", { name: "Save copy", exact: true }).click();
  dialog = page.getByRole("dialog", { name: "Save project copy" });
  await dialog
    .getByLabel("Project file")
    .fill(resolve(directory, "review.eproj"));
  await dialog.getByRole("button", { name: "Save copy", exact: true }).click();
  await expect(dialog).not.toBeVisible({ timeout: 45000 });
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
  await page
    .getByRole("button", { name: "Open project", exact: true })
    .first()
    .click();
  const fileDialog = page.getByRole("dialog", {
    name: "Open project",
    exact: true,
  });
  await fileDialog.getByLabel("Project file").fill(fixture);
  await fileDialog
    .getByRole("button", { name: "Open project", exact: true })
    .click();
  await expect(fileDialog).not.toBeVisible();
  await page
    .locator(".ribbon-tabs")
    .getByRole("tab", { name: "Schedule", exact: true })
    .click();
  const view = page.locator(".project-view");
  const quantity = view
    .locator('.tabulator-row [tabulator-field="qty"]')
    .last();
  await quantity.dblclick();
  await quantity.locator("textarea,input").fill("2*3");
  await view.locator(".project-main-grid .tabulator-header").click();
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
  await view.locator(".project-main-grid .tabulator-header").click();
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
    .click();
  await expect(
    view.getByRole("button", { name: "Add record", exact: true }),
  ).toBeVisible();
  await view.getByRole("button", { name: "Add record", exact: true }).click();
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
    await view.locator(".project-main-grid .tabulator-header").click();
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
  await view.locator(".project-main-grid .tabulator-header").click();
  await view.locator(".measurement-record-grid .project-grid").focus();
  await page.keyboard.press("ControlOrMeta+d");
  await expect(recordDescriptions).toHaveCount(2);
  await recordDescriptions.last().dblclick();
  await recordDescriptions.last().locator("textarea").fill("Second record");
  await view.locator(".project-main-grid .tabulator-header").click();
  await recordDescriptions.last().click();
  await view
    .getByRole("button", { name: "Move record up", exact: true })
    .click();
  await expect(recordDescriptions.first()).toHaveText("Second record");
  await page
    .locator(".titlebar")
    .getByRole("button", { name: "Undo", exact: true })
    .click();
  await expect(recordDescriptions.first()).toHaveText("First record");
  await recordDescriptions.last().click();
  await view
    .getByRole("button", { name: "Delete record", exact: true })
    .click();
  await expect(recordDescriptions).toHaveCount(1);
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
  const view = page.locator(".project-view");
  await expect(view.locator("h1")).toHaveText("Schedule of quantities");
  await page
    .locator(".ribbon")
    .getByRole("button", { name: "Import workbook", exact: true })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Import spreadsheet",
    exact: true,
  });
  await dialog.getByLabel("Workbook", { exact: true }).fill(workbook);
  await dialog.getByRole("button", { name: "Preview", exact: true }).click();
  await expect(
    dialog.getByRole("button", { name: "Import rows", exact: true }),
  ).toBeEnabled();
  await dialog
    .getByRole("button", { name: "Import rows", exact: true })
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
    "New project",
    "Open project",
    "Save copy",
    "Undo",
    "Redo",
    "Hide explorer",
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
  await header.getByRole("button", { name: "Hide explorer", exact: true }).click();
  await expect(page.locator(".explorer")).not.toBeVisible();
  await header.getByRole("button", { name: "Show explorer", exact: true }).click();
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
  await expect(page.locator(".project-view")).toContainText(
    "Header history test",
  );
  await header.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(page.locator(".project-main-grid")).not.toContainText(
    "Header history test",
  );
  await header.getByRole("button", { name: "Redo", exact: true }).click();
  await expect(page.locator(".project-main-grid")).toContainText(
    "Header history test",
  );
  await page
    .locator(".ribbon-tabs")
    .getByRole("tab", { name: "Resources", exact: true })
    .click();
  await expect(page.locator(".project-view h1")).toHaveText("Resource library");
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
  await expect(page.locator(".project-view h1")).toHaveText("Measurements");
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
  await expect(page.locator("#view-mcp")).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("Enter");
  await expect(analysisTab).toHaveAttribute("aria-selected", "true");
  await expect(page.locator(".ribbon").getByRole("button", { name: "Apply analysis", exact: true }))
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
  await page
    .locator(".titlebar")
    .getByRole("button", { name: "Open project", exact: true })
    .click();
  const openDialog = page.getByRole("dialog", {
    name: "Open project",
    exact: true,
  });
  await openDialog.getByLabel("Project file").fill(fixture);
  await openDialog
    .getByRole("button", { name: "Open project", exact: true })
    .click();
  await expect(openDialog).not.toBeVisible();
  const tabs = page.locator(".ribbon-tabs");
  const ribbon = page.locator(".ribbon");
  const header = page.locator(".titlebar");
  const grid = page.locator(".project-main-grid");
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
  await page.locator(".titlebar").getByRole("button", { name: "Open project" }).click();
  const open = page.getByRole("dialog", { name: "Open project" });
  await open.getByLabel("Project file").fill(project);
  await open.getByRole("button", { name: "Open project", exact: true }).click();
  await expect(open).not.toBeVisible();

  const tabs = page.locator(".ribbon-tabs");
  const ribbon = page.locator(".ribbon");
  const grid = page.locator(".project-main-grid");
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
  await page.locator(".titlebar").getByRole("button", { name: "Open project" }).click();
  const open = page.getByRole("dialog", { name: "Open project" });
  await open.getByLabel("Project file").fill(project);
  await open.getByRole("button", { name: "Open project", exact: true }).click();
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
  await header.getByRole("button", { name: "Open project" }).click();
  const open = page.getByRole("dialog", { name: "Open project" });
  await open.getByLabel("Project file").fill(project);
  await open.getByRole("button", { name: "Open project", exact: true }).click();
  await expect(open).not.toBeVisible();
  await page.locator(".ribbon-tabs").getByRole("tab", { name: "Schedule" }).click();
  const ribbon = page.locator(".ribbon");
  const grid = page.locator(".project-main-grid");
  const colour = ribbon.getByRole("button", { name: "Row colour…" });
  await grid.getByRole("gridcell", { name: "Work", exact: true }).first().click();
  await expect(colour).toBeDisabled();
  const row = grid.getByRole("row", { name: /A Foundation/ });
  await row.getByRole("gridcell", { name: "Foundation", exact: true }).click();
  await colour.click();
  const dialog = page.getByRole("dialog", { name: "Schedule row colour" });
  await dialog.getByLabel("Row colour").fill("#253657");
  await dialog.getByRole("button", { name: "Apply colour" }).click();
  await expect(dialog).not.toBeVisible();
  await expect(row).toHaveCSS("background-color", "rgb(37, 54, 87)");
  await expect(row).toHaveCSS("color", "rgb(255, 255, 255)");
  await header.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(row).not.toHaveAttribute("data-schedule-colour", /./);
  await header.getByRole("button", { name: "Redo", exact: true }).click();
  await expect(row).toHaveAttribute("data-schedule-colour", "#253657");
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
  await header.getByRole("button", { name: "Open project" }).click();
  const open = page.getByRole("dialog", { name: "Open project" });
  await open.getByLabel("Project file").fill(project);
  await open.getByRole("button", { name: "Open project", exact: true }).click();
  await expect(open).not.toBeVisible();
  await page.locator(".ribbon-tabs").getByRole("tab", { name: "Schedule" }).click();
  const quantity = page.locator('.project-main-grid .tabulator-row [tabulator-field="qty"]').last();
  await expect(quantity).toHaveText("1");
  await quantity.dblclick();
  await quantity.locator("input,textarea").fill("8");
  await page.locator(".project-main-grid .tabulator-header").click();
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
  await header.getByRole("button", { name: "Open project" }).click();
  const open = page.getByRole("dialog", { name: "Open project" });
  await open.getByLabel("Project file").fill(project);
  await open.getByRole("button", { name: "Open project", exact: true }).click();
  await expect(open).not.toBeVisible();
  await page.getByRole("navigation", { name: "Schedule items" }).getByRole("button", { name: /A Foundation/ }).click();
  await page.locator(".ribbon").getByRole("button", { name: "Import analysis" }).click();
  const dialog = page.getByRole("dialog", { name: "Import analysis from Excel" });
  await dialog.getByLabel(/Workbook/).fill(workbook);
  await dialog.getByRole("button", { name: "Preview analysis" }).click();
  await expect(dialog.getByRole("status")).toContainText("parsed rate 21.00");
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
