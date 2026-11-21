// Screenshots for the user manual (docs/manual). Not part of the test suite.
// Run: npx playwright test -c playwright.manual.config.ts
// The desktop shell is replaced by the same transport the browser tests use;
// every command runs in the real Python backend on a sample DSR 2023 estimate.
import { test, expect, type Page } from "@playwright/test";
import { spawn, execFileSync, type ChildProcessWithoutNullStreams } from "node:child_process";
import { createInterface } from "node:readline";
import { resolve } from "node:path";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";

const python = resolve(process.platform === "win32" ? "../.venv/Scripts/python.exe" : "../.venv/bin/python");
const images = resolve("../docs/manual/images");
let child: ChildProcessWithoutNullStreams;
let directory: string;
let dialogResults: (string | null)[] = [];

function startBackend() {
  const pending = new Map<string, (value: any) => void>();
  let sequence = 0;
  child = spawn(python, ["-m", "modern.backend"], { cwd: resolve(".."), env: { ...process.env, GESTIMATOR_RECOVERY_DIR: resolve(directory, "recovery"), XDG_DATA_HOME: resolve(directory, "data"), XDG_CONFIG_HOME: resolve(directory, "config"), XDG_CACHE_HOME: resolve(directory, "cache") } });
  createInterface({ input: child.stdout }).on("line", line => {
    const message = JSON.parse(line);
    if (message.event) return;
    pending.get(message.id)?.(message);
    pending.delete(message.id);
  });
  return (method: string, params: unknown, session?: string) => new Promise<any>(resolveCall => {
    const id = String(++sequence);
    pending.set(id, resolveCall);
    child.stdin.write(JSON.stringify({ id, method, params, session }) + "\n");
  });
}

async function connect(page: Page, theme: "light" | "dark" = "light") {
  const call = startBackend();
  await page.exposeBinding("backendTransport", (_source, request) => call(request.method, request.params, request.session));
  await page.exposeBinding("nativeDialogTransport", () => dialogResults.shift() ?? null);
  await page.addInitScript(theme => {
    localStorage.setItem("gestimator.program-settings.v1", JSON.stringify({ version: 1, settings: { mcp_enabled: true }, appearance: { theme } }));
    (window as any).isTauri = true;
    let callbackId = 0;
    (window as any).__TAURI_EVENT_PLUGIN_INTERNALS__ = { unregisterListener: () => {} };
    (window as any).__TAURI_INTERNALS__ = {
      metadata: { currentWindow: { label: "main" }, currentWebview: { label: "main" } },
      transformCallback: () => ++callbackId,
      invoke: (method: string, args: any) => {
        if (method === "desktop_font") return Promise.resolve({ family: "Iosevka", size: "11pt" });
        if (method === "take_project_open_requests") return Promise.resolve([]);
        if (method.startsWith("plugin:event|")) return Promise.resolve(1);
        if (method === "backend_request") return (window as any).backendTransport(args.request);
        if (method.startsWith("plugin:clipboard-manager|")) return Promise.resolve("");
        if (method.startsWith("plugin:dialog|")) return (window as any).nativeDialogTransport();
        if (method.startsWith("plugin:window|")) return Promise.resolve();
        throw new Error("Unexpected desktop command: " + method);
      },
    };
  }, theme);
  await page.goto("/");
  await expect(page.getByText("Calculation engine connected")).toBeVisible();
}

/** The window is shown on a transparent canvas with a soft drop shadow, as a desktop window would be. */
async function shot(page: Page, name: string) {
  await page.mouse.move(1, 1);
  await page.waitForTimeout(400);
  const window = await page.screenshot({ animations: "disabled" });
  const frame = await page.context().newPage();
  const size = page.viewportSize()!;
  const margin = 48;
  await frame.setViewportSize({ width: size.width + margin * 2, height: size.height + margin * 2 });
  await frame.setContent(`<body style="margin:0;background:transparent"><img src="data:image/png;base64,${window.toString("base64")}" style="position:absolute;left:${margin}px;top:${margin}px;width:${size.width}px;height:${size.height}px;border-radius:12px;box-shadow:0 2px 6px rgba(0,0,0,.25),0 12px 40px rgba(0,0,0,.35)"></body>`);
  await frame.waitForFunction(() => (document.images[0] as HTMLImageElement).complete);
  await frame.screenshot({ path: resolve(images, name + ".png"), omitBackground: true });
  await frame.close();
}

async function openSample(page: Page) {
  const project = resolve(directory, "Staff Quarters.eproj");
  execFileSync(python, ["-m", "modern.e2e.create_sample_project", project], { cwd: resolve("..") });
  dialogResults.push(project);
  await page.getByRole("region", { name: "Start an estimate" }).getByRole("button", { name: /Open project/ }).click();
  await expect(page.locator(".project-view:visible .project-main-grid")).toContainText("EARTH WORK");
}

test.beforeEach(async () => {
  directory = await mkdtemp(resolve(tmpdir(), "gestimator-manual-"));
  dialogResults = [];
});
test.afterEach(async () => {
  child.stdin.end();
  await new Promise(done => child.once("close", done));
  await rm(directory, { recursive: true, force: true });
});

test("manual screenshots", async ({ page }) => {
  page.setDefaultTimeout(15000);
  await connect(page);
  await shot(page, "start");
  await openSample(page);
  const grid = page.locator(".project-view:visible .project-main-grid");
  await grid.locator(".tabulator-row", { hasText: "2.6.1" }).first().locator('[tabulator-field="code"]').click();
  await shot(page, "schedule");

  // Attach the bundled DSR 2023 database.
  await page.locator("#view-databases").click();
  await page.locator(".ribbon").getByRole("button", { name: "Attach database…", exact: true }).click();
  const manager = page.getByRole("dialog", { name: "Attach resource / schedule library", exact: true });
  // Bundled databases attach themselves.
  await expect(manager.locator(".attached-database").first()).toBeVisible();
  await shot(page, "attach-database");
  await manager.getByRole("button", { name: "Close database manager", exact: true }).click();
  await expect(manager).not.toBeVisible();
  await page.locator("#view-schedule").click();

  // Add from database.
  await page.locator(".ribbon").getByRole("button", { name: "Add item from database", exact: true }).click();
  const picker = page.getByRole("dialog", { name: "Add item from database", exact: true });
  await picker.getByLabel("Database", { exact: true }).selectOption({ label: await picker.locator("option", { hasText: /DSR.*2023/ }).first().innerText() });
  await expect(picker.locator(".tabulator-row", { hasText: "1.1.1" }).first()).toBeVisible();
  await picker.getByLabel("Find database items").fill("cement plaster");
  await picker.getByRole("button", { name: "Search", exact: true }).click();
  await picker.locator(".tabulator-row", { hasText: "13.1.1" }).first().locator('[tabulator-field="code"]').click();
  await shot(page, "add-from-database");
  await picker.getByText("Database notes", { exact: true }).click();
  await shot(page, "database-notes");
  await picker.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(picker).not.toBeVisible();

  // Rate analysis of 5.3.
  await grid.locator(".tabulator-row", { hasText: "Reinforced cement concrete work in beams" }).first().locator('[tabulator-field="code"]').click();
  await page.locator(".ribbon").getByRole("button", { name: /^Edit analysis/ }).first().click();
  await expect(page.locator("#view-analysis")).toHaveAttribute("aria-selected", "true");
  await shot(page, "analysis");

  // Resources.
  await page.locator("#view-resources").click();
  await expect(page.locator(".project-view:visible .project-main-grid .tabulator-row").first()).toBeVisible();
  await shot(page, "resources");

  // Measurements: list, then the records of one measurement.
  await page.locator("#view-measurement").click();
  const list = page.getByRole("grid", { name: "Measurements", exact: true });
  await expect(list.locator(".tabulator-row").first()).toBeVisible();
  await shot(page, "measurements");
  await list.locator('.tabulator-row[data-kind="Resource"]', { hasText: "Plaster on external walls" }).first().locator('[tabulator-field="description"]').dblclick();
  await expect(page.locator(".measurement-record-grid")).toBeVisible();
  await shot(page, "measurement-records");
  await page.getByRole("button", { name: "Discard records", exact: true }).click();
  await expect(page.locator(".measurement-record-grid")).not.toBeVisible();

  // MCP server.
  await page.locator("#view-mcp").click();
  await page.locator(".ribbon").getByRole("button", { name: "Configure MCP server", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Configure MCP server" })).toBeVisible();
  await shot(page, "mcp");
});

test("dark theme screenshot", async ({ page }) => {
  await connect(page, "dark");
  await openSample(page);
  await shot(page, "schedule-dark");
});
