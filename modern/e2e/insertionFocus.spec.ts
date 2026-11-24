import { expect, test } from "@playwright/test";
import { holdNextRequest, refinementFixture, requestTimings, useWorkspaceHarness } from "./workspaceHarness";

useWorkspaceHarness();

for (const view of ["schedule", "resources", "measurement"] as const) {
  test(`${view} restores list focus after item and category insertion`, async ({ page }) => {
    await refinementFixture(page);
    if (view !== "schedule") await page.locator("#view-" + view).click();
    const ribbon = page.locator(".ribbon");
    const grid = page.locator(".project-view:visible .project-main-grid").getByRole("grid");
    if (view === "measurement") await expect(grid).toBeFocused();
    else await expect(grid.locator(".tabulator-row").first()).toBeVisible();

    const categoryButton = ribbon.getByRole("button", { name: "Add category", exact: true });
    await expect(categoryButton).toBeEnabled();
    await categoryButton.press("Enter");
    const category = page.getByRole("dialog", { name: "Add category", exact: true });
    await category.getByRole("textbox", { name: "Category name" }).fill("Focus test category");
    await category.getByRole("button", { name: "Add category", exact: true }).click();
    await expect(category).not.toBeVisible();
    await expect(grid).toContainText("Focus test category");
    await expect(grid).toBeFocused();

    await ribbon
      .getByRole("button", { name: view === "measurement" ? "Add measurement" : "Add item", exact: true })
      .click();
    const item = page.getByRole("dialog", { name: "Add item", exact: true });
    await item.getByRole("textbox", { name: /Description/ }).fill("Focus test item");
    await item.getByRole("button", { name: "Add item", exact: true }).click();
    await expect(item).not.toBeVisible();
    await expect(grid).toContainText("Focus test item");
    await expect(grid).toBeFocused();

    if (view === "schedule") {
      await grid.getByText("Focus test item", { exact: true }).click();
      await ribbon.getByRole("button", { name: "Add subitem", exact: true }).click();
      await item.getByRole("textbox", { name: "Description" }).fill("Focus test subitem");
      await item.getByRole("button", { name: "Add item", exact: true }).click();
      await expect(item).not.toBeVisible();
      await expect(grid).toContainText("Focus test subitem");
      await expect(grid).toBeFocused();
    }
    if (view === "measurement") {
      await grid.getByText("Focus test item", { exact: true }).dblclick();
      const records = page.locator(".measurement-record-grid").getByRole("grid");
      await ribbon.getByRole("button", { name: "Add record", exact: true }).click();
      await expect(records.locator(".tabulator-row")).toHaveCount(1);
      await expect(records).toBeFocused();
      await ribbon.getByRole("button", { name: "Add multiple records", exact: true }).click();
      const batch = page.getByRole("dialog", { name: "Insert measurement records" });
      await batch.getByRole("spinbutton", { name: "Number of records" }).fill("2");
      await batch.getByRole("button", { name: "Insert records", exact: true }).click();
      await expect(batch).not.toBeVisible();
      await expect(records.locator(".tabulator-row")).toHaveCount(3);
      await expect(records).toBeFocused();
    }
  });
}

test("Analysis returns focus to its grid after inserting rows and Explorer resources", async ({ page }) => {
  await refinementFixture(page);
  await page.locator("#view-analysis").click();
  const explorer = page.locator(".explorer");
  await explorer.getByRole("button", { name: /Foundation/ }).click();
  const grid = page.getByRole("grid", { name: "Rate analysis table" });
  await expect(grid).toBeFocused();
  const ribbon = page.locator(".ribbon");
  const add = ribbon.getByRole("button", { name: "Resource group", exact: true });
  await add.focus();
  await page.keyboard.press("Enter");
  await expect(grid.locator('.tabulator-row[data-kind="Group"]')).toHaveCount(2);
  await expect(grid).toBeFocused();

  await explorer.getByRole("tab", { name: "Resources", exact: true }).click();
  const worker = explorer.getByRole("button", { name: /Worker/ });
  await worker.focus();
  await worker.press("Enter");
  await expect(grid).toContainText("Worker");
  await expect(grid).toBeFocused();

  await ribbon.getByRole("button", { name: "Add resources from database", exact: true }).click();
  const picker = page.getByRole("dialog", { name: "Add analysis resources from database" });
  const libraryWorker = picker.getByRole("gridcell", { name: "Worker", exact: true });
  await libraryWorker.click();
  await page.keyboard.press("Enter");
  await expect(picker).not.toBeVisible();
  await expect(grid.getByRole("gridcell", { name: "Worker", exact: true })).toHaveCount(2);
  await expect(grid).toBeFocused();
});

test("Analysis Explorer initially lists schedule items created in a new project", async ({ page }) => {
  await page.locator(".titlebar").getByRole("button", { name: "New project", exact: true }).click();
  await page.locator(".ribbon").getByRole("button", { name: "Add item", exact: true }).click();
  const item = page.getByRole("dialog", { name: "Add item", exact: true });
  await item.getByRole("textbox", { name: "Description" }).fill("New project schedule row");
  await item.getByRole("button", { name: "Add item", exact: true }).click();
  await expect(item).not.toBeVisible();
  await page.locator("#view-analysis").click();
  const schedule = page.getByRole("navigation", { name: "Schedule items" });
  await expect(schedule.getByRole("button", { name: /New project schedule row/ })).toBeVisible();
});

test("Analysis Explorer accepts search during its initial Schedule load", async ({ page }) => {
  await refinementFixture(page);
  const release = await holdNextRequest(page, "schedule.list");
  await page.locator("#view-analysis").click();
  await expect.poll(() => page.evaluate(() => typeof Reflect.get(window, "resumeHeldRequest"))).toBe("function");
  const explorer = page.locator(".explorer");
  const search = explorer.getByRole("textbox", { name: "Find schedule items" });
  const results = explorer.getByRole("navigation", { name: "Schedule items" }).getByRole("button");
  await search.fill("Masonry");
  await search.press("Enter");
  await expect(results).toHaveCount(1);
  await expect(results).toContainText("Masonry");
  const completed = () => requestTimings.filter(({ method, end }) => method === "schedule.list" && end).length;
  const before = completed();
  await release();
  await expect.poll(completed).toBe(before + 1);
  await page.evaluate(
    () => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))),
  );
  await expect(results).toHaveCount(1);
  await expect(results).toContainText("Masonry");
});
