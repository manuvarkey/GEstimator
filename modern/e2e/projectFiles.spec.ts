import { test, expect, type Page } from "@playwright/test";
import { readFile, copyFile, mkdir, symlink, unlink } from "node:fs/promises";
import { resolve } from "node:path";
import {
  python,
  child,
  directory,
  frontendCalls,
  nativeDialogResults,
  requestTimings,
  call,
  startBackend,
  openFixture,
  refinementFixture,
  useWorkspaceHarness,
} from "./workspaceHarness";

useWorkspaceHarness();

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
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem("gestimator.recent-projects") || "[]"))).toContain(
    project,
  );
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
  // Search text and the selected row of a tab survive switching tabs.
  const search = page.locator(".project-view:visible").getByLabel("Search project table");
  await search.fill("Foundation");
  await search.press("Enter");
  await grid.locator(".tabulator-row", { hasText: "Foundation" }).first().click();
  await expect(grid.locator(".tabulator-row.tabulator-selected")).toContainText("Foundation");
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
  await expect(search).toHaveValue("Foundation");
  await expect(grid.locator(".tabulator-row.tabulator-selected")).toContainText("Foundation");
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
  const selected = await tabs.evaluateAll((items) =>
    items.findIndex((item) => item.getAttribute("aria-selected") === "true"),
  );
  await page.keyboard.press("Control+Tab");
  await expect(tabs.nth(1 - selected)).toHaveAttribute("aria-selected", "true");
  // Shortcuts wait until the remounted tab finished connecting.
  await expect(async () => {
    await page.keyboard.press("Control+o");
    await expect(page.getByRole("dialog", { name: /Open project/ })).toBeVisible({ timeout: 500 });
  }).toPass();
});

test("landing page creates a new project", async ({ page }) => {
  const landing = page.getByRole("region", { name: "Start an estimate" });
  await page.locator("#view-measurement").click();
  await expect(landing).toBeVisible();
  await page.screenshot({ path: "test-results/project-landing.png", animations: "disabled" });
  await landing.getByRole("button", { name: /New project/ }).click();
  await expect(landing).not.toBeVisible();
  await expect(page.locator(".project-view:visible .project-main-grid")).toBeVisible();
  const project = resolve(directory, "first-save.eproj");
  nativeDialogResults.push(project);
  await page.locator(".titlebar").getByRole("button", { name: "Save project", exact: true }).click();
  await expect.poll(async () => (await call("state")).result.source_path).toBe(project);
  expect((await readFile(project)).subarray(0, 15).toString()).toBe("SQLite format 3");

  // Close project from the application menu returns to the landing page.
  await page.getByRole("button", { name: "Application menu", exact: true }).click();
  await page.getByRole("menuitem", { name: "Close project", exact: true }).click();
  const guard = page.getByRole("dialog").filter({ hasText: "Discard changes" });
  if (await guard.isVisible().catch(() => false))
    await guard.getByRole("button", { name: "Discard changes", exact: true }).click();
  await expect(landing).toBeVisible();
  await page.getByRole("button", { name: "Application menu", exact: true }).click();
  await expect(page.getByRole("menuitem", { name: "Close project", exact: true })).toHaveAttribute(
    "aria-disabled",
    "true",
  );
});

test("real project navigation protects unsaved drafts and save-copy clears dirty state", async ({ page }) => {
  await openFixture(page, resolve("../Other databases/DSREM2022.eproj"));
  let dialog = page.getByRole("dialog", { name: "Open project", exact: true });
  await expect(dialog).not.toBeVisible();
  const search = page.getByRole("textbox", { name: "Find schedule items" });
  await search.fill("1.1.1");
  await search.press("Enter");
  await expect(page.locator(".item-card").first().locator(".item-code")).toHaveText("1.1.1");
  await page.locator(".item-card").first().click();
  await expect(page.locator(".code-tag")).toBeVisible();
  await page.locator('.tabulator-row[data-kind="Resource"]').first().locator('[tabulator-field="kind"]').click();
  await expect(page.locator(".inspector-body")).toBeVisible();
  await page.screenshot({ path: "test-results/workspace-project.png" });
  await page.locator(".ribbon-tabs").getByRole("tab", { name: "Analysis", exact: true }).click();
  await page.getByRole("button", { name: "Resource group", exact: true }).click();
  await expect(page.locator(".draft-badge")).toContainText("Unsaved changes");
  await page.getByRole("button", { name: "Open project", exact: true }).first().click();
  dialog = page.getByRole("dialog", { name: "Open project", exact: true });
  await dialog.getByLabel("Project file").fill(resolve("../Other databases/DSR2021.eproj"));
  await dialog.getByRole("button", { name: "Open project", exact: true }).click();
  // The other project opens in a new tab; this project and its draft stay open.
  const projectTabs = page.getByRole("navigation", { name: "Open projects" }).getByRole("tab");
  await expect(projectTabs).toHaveCount(2);
  await expect(projectTabs.nth(1)).toHaveAttribute("aria-selected", "true");
  await projectTabs.nth(0).click();
  await expect(page.locator(".draft-badge")).toContainText("Unsaved changes");
  const output = resolve(directory, "review.eproj");
  nativeDialogResults.push(output);
  await page.getByRole("button", { name: "Application menu", exact: true }).click();
  await page.getByRole("menuitem", { name: "Save project copy…", exact: true }).click();
  await expect
    .poll(
      async () =>
        readFile(output)
          .then(() => true)
          .catch(() => false),
      { timeout: 45000 },
    )
    .toBe(true);
  await expect(page.locator(".draft-badge")).toContainText("Up to date");
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
  await header.getByRole("button", { name: "Save project", exact: true }).click();
  await expect(page.locator(".statusbar")).toContainText("Saved");
  expect(await readFile(project + ".bak")).toEqual(original);
  expect(await readFile(project)).not.toEqual(original);
  await header.getByRole("button", { name: "Open project" }).click();
  await open.getByLabel("Recent projects").selectOption({ label: project });
  await expect(open.getByLabel("Project file")).toHaveValue(project);
});

test("native window is revealed after startup theme typography and UI are ready", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem(
      "gestimator.program-settings.v1",
      JSON.stringify({
        version: 1,
        appearance: { theme: "light", uiFamily: "Arial", uiSize: 16, tableFamily: "Arial", tableSize: 17 },
      }),
    );
    (window as any).startupFontGate = new Promise((resolve) => {
      (window as any).releaseStartupFont = () => resolve({ family: "Iosevka", size: "11pt" });
    });
  });
  let releaseState!: () => void;
  const stateGate = new Promise<void>((resolve) => {
    releaseState = resolve;
  });
  let requestedState = false;
  await page.exposeBinding("delayedStartupTransport", async (_source, request) => {
    if (request.method === "state") {
      requestedState = true;
      await stateGate;
    }
    return call(request.method, request.params);
  });
  await page.addInitScript(() => {
    (window as any).backendTransport = (window as any).delayedStartupTransport;
  });
  await page.reload();
  await expect.poll(() => page.evaluate(() => typeof (window as any).releaseStartupFont)).toBe("function");
  expect(await page.evaluate(() => (window as any).windowCommands || [])).not.toContain("plugin:window|show");
  await page.evaluate(() => (window as any).releaseStartupFont());
  await expect.poll(() => requestedState).toBe(true);
  expect(await page.evaluate(() => (window as any).windowCommands || [])).not.toContain("plugin:window|show");
  releaseState();
  await expect
    .poll(() => page.evaluate(() => (window as any).startupAtShow))
    .toEqual({
      theme: "light",
      family: "Arial, system-ui",
      size: "16px",
      fonts: "loaded",
      landing: true,
      ribbonSized: false,
    });
  expect(
    (await page.evaluate(() => (window as any).windowCommands)).filter(
      (command: string) => command === "plugin:window|show",
    ),
  ).toHaveLength(1);
});

test("native startup errors reveal the initialized window with an error message", async ({ page }) => {
  await page.exposeBinding("failedStartupTransport", async (_source, request) =>
    request.method === "program.settings"
      ? { error: { code: "backend_error", message: "Startup backend unavailable" } }
      : call(request.method, request.params),
  );
  await page.addInitScript(() => {
    (window as any).backendTransport = (window as any).failedStartupTransport;
  });
  await page.reload();
  await expect.poll(() => page.evaluate(() => (window as any).windowCommands || [])).toContain("plugin:window|show");
  await expect(page.getByRole("alert")).toContainText("Startup backend unavailable");
});

async function emitOsOpen(page: Page, paths: string[], drop = false) {
  await page.evaluate(
    ({ paths, drop }) => {
      const w = window as any;
      if (!drop) w.osOpenRequests = paths;
      const event = drop ? "tauri://drag-drop" : "project-open-available";
      const callback = w.tauriCallbacks[w.tauriListeners[event]];
      callback({ event, payload: drop ? { paths, position: { x: 1, y: 1 } } : null });
    },
    { paths, drop },
  );
}

test("OS project requests serialize through the unsaved guard and reject invalid files", async ({ page }) => {
  const project = await refinementFixture(page);
  await page.locator('.project-main-grid [tabulator-field="description"]').filter({ hasText: "Foundation" }).click();
  await page.getByRole("button", { name: "Edit analysis", exact: true }).click();
  const qty = page.locator('.analysis-table .tabulator-row[data-kind="Resource"] [tabulator-field="value"]');
  await qty.dblclick();
  await qty.locator("input").fill("3");
  await qty.locator("input").press("Enter");
  const before = frontendCalls.filter((call) => call.method === "project.open").length;
  const tabs = page.getByRole("navigation", { name: "Open projects" }).getByRole("tab");
  // The already open project keeps its tab and its unapplied analysis.
  await emitOsOpen(page, [project]);
  await expect(page.locator(".summary-value")).toContainText("30.00");
  expect(frontendCalls.filter((call) => call.method === "project.open")).toHaveLength(before);
  await expect(tabs).toHaveCount(1);
  // Another project opens in a new tab without discarding this draft.
  const second = resolve(directory, "second.eproj");
  await copyFile(project, second);
  await emitOsOpen(page, [second], true);
  await expect.poll(() => frontendCalls.filter((call) => call.method === "project.open").length).toBe(before + 1);
  await expect(tabs).toHaveCount(2);
  await tabs.nth(0).click();
  await expect(page.locator(".summary-value")).toContainText("30.00");
  // The remounted tab registers its drop listener after connecting; retry until it does.
  await expect(async () => {
    await emitOsOpen(page, ["/tmp/not-a-project.txt"], true);
    await expect(page.getByRole("alert").filter({ hasText: "Not a GEstimator project" })).toBeVisible({ timeout: 500 });
  }).toPass();
  await emitOsOpen(page, [resolve(directory, "missing file.eproj")]);
  await expect(page.getByRole("alert")).toContainText(/not found|does not exist|No such|Cannot|exist/i);
});

test("opening the active project keeps its session and a closed project can reopen from the OS", async ({ page }) => {
  const project = await refinementFixture(page);
  const opens = () => frontendCalls.filter((request) => request.method === "project.open").length;
  const before = opens();
  await page.locator(".titlebar").getByRole("button", { name: "Open project", exact: true }).click();
  const chooser = page.getByRole("dialog", { name: "Open project", exact: true });
  const lookupCount = requestTimings.filter(({ method, end }) => method === "path.canonical" && end).length;
  await chooser.getByLabel("Project file").fill(project);
  await chooser.getByLabel("Project file").press("Enter");
  await expect
    .poll(() => requestTimings.filter(({ method, end }) => method === "path.canonical" && end).length)
    .toBe(lookupCount + 1);
  await expect(chooser).not.toBeVisible();
  expect(opens()).toBe(before);
  await page.getByRole("button", { name: "Application menu", exact: true }).click();
  await page.getByRole("menuitem", { name: "Close project", exact: true }).click();
  const landing = page.getByRole("region", { name: "Start an estimate" });
  await expect(landing).toBeVisible();
  await emitOsOpen(page, [project]);
  await expect(landing).not.toBeVisible();
  expect(opens()).toBe(before + 1);
  await expect(page.getByRole("navigation", { name: "Open projects" }).getByRole("tab")).toHaveCount(1);
});

test("OS project opens resolve a directory alias again after it moves", async ({ page }) => {
  const project = await refinementFixture(page);
  const first = resolve(directory, "first");
  const second = resolve(directory, "second");
  const alias = resolve(directory, "alias");
  await mkdir(first);
  await mkdir(second);
  await copyFile(project, resolve(first, "linked.eproj"));
  await copyFile(project, resolve(second, "linked.eproj"));
  // Junctions let the Windows runner exercise alias resolution without symlink privileges.
  await symlink(first, alias, process.platform === "win32" ? "junction" : "dir");
  const aliasFile = resolve(alias, "linked.eproj");
  const tabs = page.getByRole("navigation", { name: "Open projects" }).getByRole("tab");
  await emitOsOpen(page, [aliasFile]);
  await expect(tabs.nth(1)).toHaveAttribute("aria-selected", "true");
  await expect(page.locator(".project-main-grid:visible")).toContainText("Foundation");
  await unlink(alias);
  await symlink(second, alias, process.platform === "win32" ? "junction" : "dir");

  // Wait for the newly mounted workspace to finish installing the native callback.
  await expect.poll(() => page.evaluate(() => (window as any).openedProjectPath)).toBe(aliasFile);
  await emitOsOpen(page, [aliasFile]);
  await expect(tabs.nth(2)).toHaveAttribute("aria-selected", "true");
  await expect(page.locator(".project-main-grid:visible")).toContainText("Foundation");
  const opened = await call(
    "state",
    {},
    frontendCalls.filter(({ method }) => method === "session.activate").at(-1)?.params.session as string,
  );
  const canonical = await call("path.canonical", { path: resolve(second, "linked.eproj") });
  expect(opened.result.source_path).toBe(canonical.result.canonical);
});

test("project tabs keep the analysis inspector and measurement record view", async ({ page }) => {
  const rail = page.getByRole("navigation", { name: "Open projects" });
  const tabs = rail.getByRole("tab");
  await refinementFixture(page);
  async function edit(method: string, params = {}) {
    return (await call(method, { revision: (await call("state")).result.revision, ...params })).result;
  }
  // Analysis: a hidden inspector stays hidden after switching tabs.
  await page.locator('.project-main-grid [tabulator-field="description"]').filter({ hasText: "Foundation" }).click();
  await page.locator(".ribbon").getByRole("button", { name: "Edit analysis", exact: true }).click();
  await expect(page.locator(".inspector")).toBeVisible();
  await page.locator(".ribbon").getByRole("button", { name: "Hide analysis inspector", exact: true }).click();
  await expect(page.locator(".inspector")).toBeHidden();
  await page.locator(".titlebar").getByRole("button", { name: "New project", exact: true }).click();
  await expect(tabs).toHaveCount(2);
  await tabs.nth(0).click();
  await expect(page.locator("#view-analysis")).toHaveAttribute("aria-selected", "true");
  await expect(
    page.locator(".ribbon").getByRole("button", { name: "Show analysis inspector", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".inspector")).toBeHidden();
  // Measurement records: page, selected record and scroll come back.
  const added = await edit("measurement.add", { template: "_1_NLBH", description: "Tab memory" });
  const id = added.selected[0];
  await edit("measurement.draft.open", { id });
  await edit("measurement.record_add", { id, count: 160 });
  await edit("measurement.draft.apply");
  await page.locator("#view-measurement").click();
  await page
    .getByRole("grid", { name: "Measurements", exact: true })
    .getByText("Tab memory", { exact: true })
    .dblclick();
  await page.getByRole("button", { name: "Next records", exact: true }).click();
  await expect(page.getByText("160 records · Page 2", { exact: true })).toBeVisible();
  const records = page.locator(".measurement-record-grid");
  const holder = records.locator(".tabulator-tableholder");
  await holder.evaluate((element) => {
    element.scrollTop = element.scrollHeight;
  });
  const row = records.locator(".tabulator-row").last();
  await row.locator('[tabulator-field="c2"]').click();
  await expect(records.locator(".tabulator-row.tabulator-selected")).toHaveCount(1);
  const selectedText = await records.locator(".tabulator-row.tabulator-selected").innerText();
  const top = await holder.evaluate((element) => element.scrollTop);
  expect(top).toBeGreaterThan(0);
  await tabs.nth(1).click();
  await expect(records).toBeHidden();
  await tabs.nth(0).click();
  await expect(page.getByText("160 records · Page 2", { exact: true })).toBeVisible();
  await expect(records.locator(".tabulator-row.tabulator-selected")).toHaveCount(1);
  await expect.poll(() => records.locator(".tabulator-row.tabulator-selected").innerText()).toBe(selectedText);
  await expect.poll(() => holder.evaluate((element) => element.scrollTop)).toBeGreaterThan(top - 40);
});

test("in-place save waits for folder selection and keeps edits on cancellation", async ({ page }) => {
  const project = await refinementFixture(page);
  await page.evaluate(() => {
    const internals = (window as any).__TAURI_INTERNALS__;
    const invoke = internals.invoke;
    internals.invoke = async (command: string, params: { options?: { defaultPath?: string } }) => {
      if (command === "plugin:dialog|save") internals.saveDefaultPath = params.options?.defaultPath;
      const reply = await invoke(command, params);
      if (command === "backend_request" && reply?.result?.source_path && "source_requires_folder" in reply.result) {
        reply.result.source_path = "/run/flatpak/doc/grant/estimate.eproj";
        reply.result.source_requires_folder = true;
      }
      return reply;
    };
  });

  const quantity = page
    .locator(".project-view:visible .tabulator-row")
    .filter({ has: page.locator('[tabulator-field="code"]').filter({ hasText: /^A$/ }) })
    .locator('[tabulator-field="qty"]');
  await quantity.dblclick();
  await quantity.locator("input").fill("2");
  await quantity.locator("input").press("Enter");
  await expect(page.getByRole("status", { name: "Overall estimate total", exact: true })).toContainText("45.00");

  nativeDialogResults.push(null);
  await page.getByRole("button", { name: "Application menu", exact: true }).click();
  await page.getByRole("menuitem", { name: "Save project copy…", exact: true }).click();
  await expect.poll(() => nativeDialogResults.length).toBe(0);
  expect(await page.evaluate(() => (window as any).__TAURI_INTERNALS__.saveDefaultPath)).toBe("estimate-edited.eproj");

  async function saveProject() {
    await page.locator(".titlebar").getByRole("button", { name: "Save project", exact: true }).click();
    await expect.poll(() => nativeDialogResults.length).toBe(0);
  }

  nativeDialogResults.push(null);
  await saveProject();
  expect(frontendCalls.some(({ method }) => method === "project.save")).toBe(false);
  expect((await call("state")).result.workspace_dirty).toBe(true);

  nativeDialogResults.push(directory);
  await saveProject();
  await expect.poll(() => frontendCalls.find(({ method }) => method === "project.save")?.params).toEqual({ directory });
  await expect.poll(async () => (await call("state")).result.workspace_dirty).toBe(false);
  expect(await readFile(project + ".bak")).not.toEqual(await readFile(project));
});
