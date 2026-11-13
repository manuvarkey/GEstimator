import { test, expect } from "@playwright/test";
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { createInterface } from "node:readline";
import { resolve } from "node:path";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";

const python = resolve(
  process.platform === "win32"
    ? "../.venv/Scripts/python.exe"
    : "../.venv/bin/python",
);

// Only the Tauri transport is replaced. Every analysis command runs in real Python.
let child: ChildProcessWithoutNullStreams;
let directory: string;
const pending = new Map<
  string,
  { resolve: (value: unknown) => void; reject: (error: Error) => void }
>();
let sequence = 0;
function call(method: string, params: Record<string, unknown> = {}) {
  const id = String(++sequence);
  return new Promise<any>((resolve, reject) => {
    pending.set(id, { resolve, reject });
    child.stdin.write(JSON.stringify({ id, method, params }) + "\n");
  });
}
test.beforeEach(async ({ page }) => {
  directory = await mkdtemp(resolve(tmpdir(), "gestimator-ui-"));
  child = spawn(python, ["-m", "modern.backend"], {
    cwd: resolve(".."),
  });
  createInterface({ input: child.stdout }).on("line", (line) => {
    const message = JSON.parse(line);
    if (message.event) return;
    pending.get(message.id)?.resolve(message);
    pending.delete(message.id);
  });
  child.stderr.on("data", (data) => process.stderr.write(data));
  await page.exposeBinding("backendTransport", (_source, request) =>
    call(request.method, request.params),
  );
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
        if (method.startsWith("plugin:dialog|")) return Promise.resolve(null);
        throw new Error("Unexpected desktop command: " + method);
      },
    };
  });
  await page.goto("/");
  await expect(page.getByText("Calculation engine connected")).toBeVisible();
});
test.afterEach(async () => {
  child.stdin.end();
  await new Promise<void>((resolve) => child.once("close", () => resolve()));
  await rm(directory, { recursive: true, force: true });
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

  await page
    .getByRole("button", { name: "Application menu", exact: true })
    .click();
  await page
    .getByRole("menuitem", { name: "Hide analysis inspector", exact: true })
    .click();
  await expect(page.locator(".inspector")).not.toBeVisible();
  await page
    .getByRole("button", { name: "Application menu", exact: true })
    .click();
  await page
    .getByRole("menuitem", { name: "Show analysis inspector", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Application menu", exact: true })
    .click();
  await page
    .getByRole("menuitem", { name: "Compact rows", exact: true })
    .click();
  await expect(page.locator(".analysis-table")).toHaveClass(/compact/);
  await page.setViewportSize({ width: 1100, height: 800 });
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
  await view
    .getByRole("button", { name: "Duplicate record", exact: true })
    .click();
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
  for (const name of [
    "New project",
    "Open project",
    "Save copy",
    "Undo",
    "Redo",
  ]) {
    const button = header.getByRole("button", { name, exact: true });
    expect((await button.textContent())?.trim()).toBe("");
  }
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

  await ribbon
    .getByRole("button", { name: "Attach library…", exact: true })
    .click();
  const attach = page.getByRole("dialog", {
    name: "Attach resource / schedule library",
    exact: true,
  });
  await attach.getByLabel(/Library project/).fill(fixture);
  await attach
    .getByRole("button", { name: "Attach library", exact: true })
    .click();
  await expect(attach).not.toBeVisible();
  await ribbon.getByLabel("Data source").selectOption({ index: 1 });
  await grid
    .locator(
      '.tabulator-row[data-kind="Group"] [tabulator-field="description"]',
    )
    .filter({ hasText: /^Work$/ })
    .click();
  await ribbon
    .getByRole("button", { name: "Import selected into project", exact: true })
    .click();
  await ribbon.getByLabel("Data source").selectOption("");
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
  await ribbon.getByRole("button", { name: "Attach library…" }).click();
  const attach = page.getByRole("dialog", { name: "Attach resource / schedule library" });
  await attach.getByLabel(/Library project/).fill(library);
  await attach.getByRole("button", { name: "Attach library", exact: true }).click();
  await expect(attach).not.toBeVisible();
  await grid.getByText("Materials", { exact: true }).first().click();
  await ribbon.getByRole("button", { name: "Update prices from library…" }).click();
  const dialog = page.getByRole("dialog", { name: "Update resource prices from library" });
  const apply = dialog.getByRole("button", { name: "Update prices", exact: true });
  await expect(apply).toBeDisabled();
  await dialog.getByRole("button", { name: "Preview updates" }).click();
  await expect(dialog).toContainText("1 to update, 0 already current, 0 without a matching code.");
  await apply.click();
  await expect(dialog).not.toBeVisible();
  await expect(page.getByText("Updated prices for 1 resource.")).toBeVisible();
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
