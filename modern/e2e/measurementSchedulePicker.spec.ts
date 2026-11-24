import { expect, test, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import { directory, openFixture, openMeasurementEntry, python, useWorkspaceHarness } from "./workspaceHarness";

useWorkspaceHarness();

/** Hold one lookup at the bridge so the test can send input before the results arrive. */
async function holdScheduleLookup(page: Page) {
  await page.evaluate(() => {
    const bridge = window as Window & {
      backendTransport: (request: { method: string }) => Promise<unknown>;
      finishScheduleLookup?: () => void;
    };
    const send = bridge.backendTransport;
    bridge.backendTransport = async (request) => {
      if (request.method === "schedule.list") {
        bridge.backendTransport = send;
        await new Promise<void>((resolve) => (bridge.finishScheduleLookup = resolve));
      }
      return send(request);
    };
  });
  return () =>
    page.evaluate(() => {
      const finish = Reflect.get(window, "finishScheduleLookup");
      Reflect.deleteProperty(window, "finishScheduleLookup");
      finish();
    });
}

async function openMeasurementFixture(page: Page) {
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
}

test("measurement schedule picker scrolls and selects a link from both entry points", async ({ page }) => {
  await openMeasurementFixture(page);
  const picker = page.getByRole("dialog", { name: "Choose schedule item", exact: true });
  const results = picker.locator(".library-results");
  const first = results.getByRole("button").first();
  const last = results.getByRole("button", { name: /Link candidate 29/ });
  const find = page.getByRole("button", { name: "Choose schedule item 1", exact: true });
  const releaseFirst = await holdScheduleLookup(page);
  await find.click();
  const search = picker.getByRole("textbox", { name: "Find linked schedule item" });
  const searchButton = picker.getByRole("button", { name: "Search", exact: true });
  await expect(search).toBeFocused();
  await expect(searchButton).toBeDisabled();
  await page.keyboard.press("ArrowDown");
  await releaseFirst();
  await expect(first).toBeFocused();
  await expect(first).toHaveCSS("outline-style", "solid");
  await page.keyboard.press("ArrowDown");
  const second = results.getByRole("button").nth(1);
  await expect(second).toBeFocused();
  await expect(second).toHaveCSS("outline-style", "solid");

  const insets = await second.evaluate((button) => {
    const item = button.getBoundingClientRect();
    const pane = button.parentElement!.getBoundingClientRect();
    const style = getComputedStyle(button);
    return {
      gaps: [item.left - pane.left, pane.right - item.right],
      outline: parseFloat(style.outlineWidth) + parseFloat(style.outlineOffset),
    };
  });
  expect(Math.min(...insets.gaps)).toBeGreaterThanOrEqual(insets.outline);

  // Incremental wheel movement must keep advancing, even with a result focused.
  await expect(last).not.toBeInViewport();
  await results.hover();
  let top = 0;
  for (let step = 0; step < 4; step++) {
    await page.mouse.wheel(0, 180);
    await expect.poll(() => results.evaluate((list) => list.scrollTop)).toBeGreaterThan(top);
    top = await results.evaluate((list) => list.scrollTop);
  }
  await page.mouse.wheel(0, 4000);
  await expect(last).toBeInViewport();
  await last.click();
  await expect(picker).not.toBeVisible();

  await page.getByRole("button", { name: "Properties…", exact: true }).click();
  const properties = page.getByRole("dialog", { name: "Measurement properties", exact: true });
  const code = properties.getByLabel("Property schedule code 1", { exact: true });
  await expect(code).toHaveValue("L29");
  const releaseReopen = await holdScheduleLookup(page);
  await properties.getByRole("button", { name: "Choose property schedule item 1", exact: true }).press("Enter");
  await expect(searchButton).toBeDisabled();
  await expect(results.getByRole("button")).toHaveCount(0);
  await expect(results).toHaveJSProperty("scrollTop", 0);
  await releaseReopen();
  await expect(searchButton).toBeEnabled();
  await expect(search).toBeFocused();
  await page.keyboard.press("ArrowDown");
  await expect(first).toBeFocused();
  await page.keyboard.press("End");
  await expect(last).toBeFocused();
  await page.keyboard.press("ArrowUp");
  const previous = results.getByRole("button", { name: /Link candidate 28/ });
  await expect(previous).toBeFocused();
  await expect(previous).toHaveCSS("outline-style", "solid");
  await page.keyboard.press("Enter");
  await expect(picker).not.toBeVisible();
  await expect(code).toHaveValue("L28");
});

test("measurement schedule picker honours Search as you type and retries a query while busy", async ({ page }) => {
  await openMeasurementFixture(page);
  await page.clock.install();
  const find = page.getByRole("button", { name: "Choose schedule item 1", exact: true });
  const picker = page.getByRole("dialog", { name: "Choose schedule item", exact: true });
  const search = picker.getByRole("textbox", { name: "Find linked schedule item" });
  const searchButton = picker.getByRole("button", { name: "Search", exact: true });
  const results = picker.locator(".library-results");
  const foundation = results.getByRole("button", { name: /Foundation/ });
  const candidate = results.getByRole("button", { name: /Link candidate 20/ });
  await find.click();
  await expect(foundation).toBeVisible();
  await search.fill("L20");
  await page.clock.runFor(400);
  await expect(foundation).toBeVisible();
  await search.press("Enter");
  await expect(results.getByRole("button")).toHaveCount(1);
  await expect(candidate).toBeVisible();
  await picker.getByRole("button", { name: "Close dialog", exact: true }).click();

  await page.getByRole("button", { name: "Application menu", exact: true }).click();
  await page.getByRole("menuitem", { name: "Program settings…", exact: true }).click();
  const settings = page.getByRole("dialog", { name: "Program settings", exact: true });
  await settings.getByRole("checkbox", { name: "Search as you type", exact: true }).check();
  await settings.getByRole("button", { name: "Save program settings" }).click();
  await expect(settings).not.toBeVisible();

  await find.click();
  await expect(foundation).toBeVisible();
  const release = await holdScheduleLookup(page);
  await search.fill("Foundation");
  await expect(searchButton).toBeDisabled();
  await search.fill("L20");
  await page.clock.runFor(400);
  await release();
  await expect(results.getByRole("button")).toHaveCount(1);
  await expect(candidate).toBeVisible();
  await expect(search).toBeFocused();
});
