import { expect, test } from "@playwright/test";
import { frontendCalls, holdNextRequest, refinementFixture, useWorkspaceHarness } from "./workspaceHarness";

useWorkspaceHarness();

test("Analysis explorer honours live search and arrows focus schedule and resource results", async ({ page }) => {
  await refinementFixture(page);
  await page.clock.install();
  await page.locator("#view-analysis").click();
  const explorer = page.locator(".explorer");
  const schedule = explorer.getByRole("navigation", { name: "Schedule items" });
  const scheduleSearch = explorer.getByRole("textbox", { name: "Find schedule items" });
  await expect(schedule.getByRole("button")).toHaveCount(2);
  await scheduleSearch.fill("Foundation");
  await page.clock.runFor(400);
  await expect(schedule.getByRole("button")).toHaveCount(2);
  await scheduleSearch.press("Enter");
  await expect(schedule.getByRole("button")).toHaveCount(1);

  await page.getByRole("button", { name: "Application menu", exact: true }).click();
  await page.getByRole("menuitem", { name: "Program settings…", exact: true }).click();
  const settings = page.getByRole("dialog", { name: "Program settings", exact: true });
  await settings.getByRole("checkbox", { name: "Search as you type", exact: true }).check();
  await settings.getByRole("button", { name: "Save program settings" }).click();
  await expect(settings).not.toBeVisible();
  await scheduleSearch.fill("");
  await expect(schedule.getByRole("button")).toHaveCount(2);
  await scheduleSearch.fill("Foundation");
  await expect(schedule.getByRole("button")).toHaveCount(1);
  const foundation = schedule.getByRole("button", { name: /Foundation/ });
  await expect(foundation).toBeVisible();

  // A query can return to the previous text while a different request is in flight.
  const release = await holdNextRequest(page, "schedule.list");
  await scheduleSearch.fill("Masonry");
  await expect(explorer.getByRole("button", { name: "Search explorer" })).toBeDisabled();
  const foundationSearches = () =>
    frontendCalls.filter(({ method, params }) => method === "schedule.list" && params.query === "Foundation").length;
  const before = foundationSearches();
  await scheduleSearch.fill("Foundation");
  await page.clock.runFor(400);
  await release();
  await expect.poll(foundationSearches).toBe(before + 1);
  await expect(foundation).toBeVisible();
  await page.keyboard.press("ArrowDown");
  await expect(foundation).toBeFocused();
  await expect(foundation).toHaveCSS("outline-style", "solid");
  await page.keyboard.press("Enter");
  const analysis = page.getByRole("grid", { name: "Rate analysis table" });
  await expect(analysis).toContainText("Material");

  await explorer.getByRole("tab", { name: "Resources", exact: true }).click();
  const resources = explorer.getByRole("navigation", { name: "Resource library" });
  await expect(resources.getByRole("button")).toHaveCount(2);
  await explorer.getByRole("textbox", { name: "Find resources" }).fill("Worker");
  await expect(resources.getByRole("button")).toHaveCount(1);
  const worker = resources.getByRole("button", { name: /Worker/ });
  await expect(worker).toBeVisible();
  await page.keyboard.press("ArrowDown");
  await expect(worker).toBeFocused();
  await expect(worker).toHaveCSS("outline-style", "solid");
  await page.keyboard.press("Enter");
  await expect(analysis).toContainText("Worker");
});

for (const kind of ["schedule", "resources"] as const) {
  test(`${kind} search arrows hand focus to the project grid`, async ({ page }) => {
    await refinementFixture(page);
    await page.locator(`#view-${kind}`).click();
    const view = page.locator(".project-view:visible");
    const grid = view.locator(".project-main-grid").getByRole("grid");
    const search = view.getByRole("textbox", { name: "Search project table" });
    await expect(grid.locator(".tabulator-row").first()).toBeVisible();
    await search.click();
    await page.keyboard.press("ControlOrMeta+f");
    await expect(search).toBeFocused();
    await page.keyboard.press("ArrowDown");
    await expect(grid).toBeFocused();
    await expect(grid).toHaveCSS("outline-style", "solid");
    await page.keyboard.press("Shift+End");
    await expect(grid.locator('.tabulator-selected[data-kind="Resource"]')).toHaveCount(2);
  });
}
