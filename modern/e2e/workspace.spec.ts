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
async function attachDatabase(page: Page, path: string, returnView = "schedule") {
  await page.locator("#view-databases").click();
  await page.locator(".ribbon").getByRole("button", { name: "Attach database…", exact: true }).click();
  const manager = page.getByRole("dialog", { name: "Attach resource / schedule library", exact: true });
  await manager.getByLabel("Library project", { exact: true }).fill(path);
  await manager.getByRole("button", { name: "Attach library", exact: true }).click();
  await expect(manager.locator(".attached-database").first()).toBeVisible();
  await expect(manager).toBeVisible();
  await manager.getByRole("button", { name: "Close database manager", exact: true }).click();
  await expect(manager).not.toBeVisible();
  await page.locator("#view-" + returnView).click();
}

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
  await expect(page.locator(".database-view .attached-database")).toHaveCount(2);
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
  await expect(grid.locator('.tabulator-row [tabulator-field="rate"]').last()).toHaveText("60");
  await page.locator(".titlebar").getByRole("button", { name: "Undo", exact: true }).click();
  await expect(grid.locator('.tabulator-row [tabulator-field="rate"]').last()).toHaveText("50");
  await page.locator("#view-resources").click();
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
    await expect.poll(() => JSON.parse(systemClipboard).kind).toBe("analysis");
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
  await page.locator(".project-view h1").click();
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
  await page.locator(".project-view h1").click();
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
  await expect(table.locator('.tabulator-selected [tabulator-field="category"]')).toHaveText("Relocated");
  await page.locator(".titlebar").getByRole("button", { name: "Undo", exact: true }).click();
  await expect(table.locator('.tabulator-selected [tabulator-field="category"]')).toHaveText("Materials");
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
    await page.locator("#view-databases").click();
    await expect(page.locator(".database-view .attached-database")).toHaveCount(expected);
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
  await expect(page.locator(".database-view .saved-library")).toContainText("Unavailable:");
  await attachDatabase(page, moved, "databases");
  await page.locator(".database-view .saved-library").filter({ hasText: library }).getByRole("button", { name: /Forget library/ }).click();
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
  await page.locator(".ribbon").getByRole("button", { name: "Bulk edit analysis…" }).click();
  const bulk = page.getByRole("dialog", { name: "Bulk edit analysis", exact: true });
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
  await page.keyboard.press("Enter");
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
  await page.locator(".project-view h1").click();
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
  await page.locator(".project-view h1").click();
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
  await ribbon
    .getByRole("button", { name: "Collapse groups", exact: true })
    .click();
  await expect(
    ribbon.getByRole("button", { name: "Expand groups", exact: true }),
  ).toBeVisible();
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
  await view.locator("h1").click();
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
  await view.locator("h1").click();
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
    await view.locator("h1").click();
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
  await view.locator("h1").click();
  await view.locator(".measurement-record-grid .project-grid").focus();
  await page.keyboard.press("ControlOrMeta+d");
  await expect(recordDescriptions).toHaveCount(2);
  await recordDescriptions.last().dblclick();
  await recordDescriptions.last().locator("textarea").fill("Second record");
  await view.locator("h1").click();
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
  for (const tab of ["Schedule", "Analysis", "Resources", "Measurements", "Databases"]) {
    await page
      .locator(".ribbon-tabs")
      .getByRole("tab", { name: tab, exact: true })
      .click();
    ribbonHeights.add(
      await page.locator(".ribbon").evaluate((element) => element.clientHeight),
    );
  }
  expect(ribbonHeights.size).toBe(1);
  const scheduleTab = page.getByRole("tab", { name: "Schedule", exact: true }).first();
  await scheduleTab.focus();
  await page.keyboard.press("ArrowRight");
  const analysisTab = page.locator("#view-analysis");
  await expect(analysisTab).toBeFocused();
  // Focusing a tab alone must not switch the editor or discard a draft.
  await expect(page.locator("#view-databases")).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("Enter");
  await expect(analysisTab).toHaveAttribute("aria-selected", "true");
  await expect(page.locator(".ribbon").getByRole("button", { name: "Apply analysis", exact: true }))
    .toHaveAttribute("title", /working copy.*Save the project/);
  for (const width of [1600, 1366, 1280, 1100, 800, 700]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const tab of ["Schedule", "Analysis", "Resources", "Measurements", "Databases"]) {
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
  for (const tab of ["Schedule", "Analysis", "Resources", "Measurements", "Databases"]) {
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
  await page.getByRole("heading", { name: "Schedule of quantities" }).click();
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
