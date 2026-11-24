import { test, expect } from "@playwright/test";
import { resolve } from "node:path";
import { call, directory, openFixture, useWorkspaceHarness } from "./workspaceHarness";

useWorkspaceHarness();

test("wrapped schedule descriptions keep their padding when returning to Schedule", async ({ page }) => {
  const { result } = await call("project.new");
  const path = resolve(directory, "wrapped-schedule.eproj");
  const description = [
    "Remove each floor slab in sections and transport the debris to the designated site.",
    "Include handling of materials, temporary protection, watering and disposal.",
    "Record quantities separately for each building wing and retain the existing services.",
  ]
    .join(" ")
    .repeat(3);
  const added = await call("schedule.editor.add", {
    revision: result.revision,
    data: { code: "D1", description, category: "Demolition", unit: "m²" },
  });
  expect(added.error).toBeUndefined();
  expect((await call("project.save_copy", { path })).error).toBeUndefined();
  await openFixture(page, path);
  await page.locator("#view-schedule").click();

  const cell = page.locator(
    '.project-view:visible .project-main-grid .tabulator-row[data-kind="Resource"] [tabulator-field="description"]',
  );
  const dimensions = () =>
    cell.evaluate((element) => {
      const range = document.createRange();
      range.selectNodeContents(element);
      const bounds = element.getBoundingClientRect();
      const lines = [...range.getClientRects()];
      return {
        height: bounds.height,
        top: Math.min(...lines.map((line) => line.top)) - bounds.top,
        bottom: bounds.bottom - Math.max(...lines.map((line) => line.bottom)),
      };
    });
  await expect(cell).toHaveText(description);
  await expect.poll(async () => (await dimensions()).height).toBeGreaterThan(100);
  const initial = await dimensions();
  expect(initial.top).toBeGreaterThan(0);
  expect(initial.bottom).toBeGreaterThan(0);

  for (const view of ["analysis", "resources", "measurement"]) {
    await page.locator("#view-" + view).click();
    await page.locator("#view-schedule").click();
    await expect(cell).toBeVisible();
    // Wait for the scheduled reveal redraw before measuring the final layout.
    await page.evaluate(
      () => new Promise<void>((done) => requestAnimationFrame(() => requestAnimationFrame(() => done()))),
    );
    const restored = await dimensions();
    expect(restored.height).toBeCloseTo(initial.height, 0);
    expect(restored.top).toBeGreaterThan(0);
    expect(restored.bottom).toBeGreaterThan(0);
  }
});
