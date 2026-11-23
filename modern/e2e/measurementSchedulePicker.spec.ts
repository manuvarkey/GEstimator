import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import { directory, openFixture, openMeasurementEntry, python, useWorkspaceHarness } from "./workspaceHarness";

useWorkspaceHarness();

test("measurement schedule picker scrolls and selects a link from both entry points", async ({ page }) => {
  const path = resolve(directory, "measurement-links.eproj");
  execFileSync(python, ["-m", "modern.e2e.create_fixture", path], { cwd: resolve("..") });
  const populate = `
import sys
from estimator.data.schedule import ScheduleDatabase, ScheduleItemModel
from estimator.undo import Stack
db = ScheduleDatabase(Stack())
db.open_database(sys.argv[1])
for i in range(30):
    db.insert_item_atomic(ScheduleItemModel(f'L{i:02}', f'Link candidate {i:02}', 'm', category='Links'))
db.close_database()
`;
  execFileSync(python, ["-c", populate, path], { cwd: resolve("..") });
  await page.setViewportSize({ width: 850, height: 600 });
  await openFixture(page, path);
  await page.locator("#view-measurement").click();
  await page.getByRole("button", { name: "Add measurement", exact: true }).click();
  const add = page.getByRole("dialog", { name: "Add item", exact: true });
  await add.getByLabel("Description / remarks").fill("Linked measurement");
  await add.getByRole("button", { name: "Add item", exact: true }).click();
  await openMeasurementEntry(page);

  const picker = page.getByRole("dialog", { name: "Choose schedule item", exact: true });
  const results = picker.locator(".library-results");
  const last = results.getByRole("button", { name: /Link candidate 29/ });
  await page.getByRole("button", { name: "Choose schedule item 1", exact: true }).click();
  await expect(last).not.toBeInViewport();
  await results.hover();
  await page.mouse.wheel(0, 4000);
  await expect(last).toBeInViewport();
  await last.click();
  await expect(picker).not.toBeVisible();

  await page.getByRole("button", { name: "Properties…", exact: true }).click();
  const properties = page.getByRole("dialog", { name: "Measurement properties", exact: true });
  const code = properties.getByLabel("Property schedule code 1", { exact: true });
  await expect(code).toHaveValue("L29");
  await properties.getByRole("button", { name: "Choose property schedule item 1", exact: true }).click();
  const search = picker.getByRole("textbox", { name: "Find linked schedule item" });
  await expect(search).toBeFocused();
  await page.keyboard.press("ArrowDown");
  await expect(results.getByRole("button").first()).toBeFocused();
  await page.keyboard.press("End");
  await expect(last).toBeFocused();
  await page.keyboard.press("ArrowUp");
  await page.keyboard.press("Enter");
  await expect(picker).not.toBeVisible();
  await expect(code).toHaveValue("L28");
});
