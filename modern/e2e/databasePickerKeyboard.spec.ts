import { expect, test } from "@playwright/test";
import { attachDatabase, frontendCalls, refinementFixture, useWorkspaceHarness } from "./workspaceHarness";

useWorkspaceHarness();

for (const { kind, title, gridLabel, codes, key, modify } of [
  {
    kind: "schedule",
    title: "Add item from database",
    gridLabel: "Database schedule items",
    codes: ["A", "B"],
    key: "Enter",
    modify: true,
  },
  {
    kind: "schedule",
    title: "Add item from database",
    gridLabel: "Database schedule items",
    codes: ["A", "B"],
    key: "Control+Enter",
    modify: false,
  },
  {
    kind: "resources",
    title: "Add resources from database",
    gridLabel: "Database resource rates",
    codes: ["L", "R"],
    key: "Enter",
    modify: false,
  },
]) {
  test(`${kind} picker imports the keyboard-selected range with ${key}`, async ({ page }) => {
    const source = await refinementFixture(page);
    await page.locator(".titlebar").getByRole("button", { name: "New project", exact: true }).click();
    await attachDatabase(page, source, kind);
    await page.keyboard.press("Control+l");
    const picker = page.getByRole("dialog", { name: title, exact: true });
    const search = picker.getByRole("textbox", { name: "Find database items" });
    const grid = picker.getByRole("grid", { name: gridLabel, exact: true });
    await expect(grid.locator('.tabulator-row[data-kind="Resource"]')).toHaveCount(2);
    await expect(search).toBeFocused();

    // Enter searches from the field. An arrow into the results starts row navigation.
    const searches = () =>
      frontendCalls.filter(({ method, params }) => method === kind + ".editor.state" && params.source).length;
    const beforeSearch = searches();
    await page.keyboard.press("Enter");
    await expect.poll(searches).toBe(beforeSearch + 1);
    await expect(picker.getByRole("button", { name: "Search", exact: true })).toBeEnabled();
    await expect(picker).toBeVisible();
    await expect(grid.locator(".tabulator-selected")).toHaveCount(0);
    await page.keyboard.press("ArrowDown");
    await expect(grid).toBeFocused();
    await expect(grid.locator(".tabulator-selected")).toHaveCount(1);
    await page.keyboard.press("Shift+End");
    await expect(grid.locator('.tabulator-selected[data-kind="Resource"]')).toHaveCount(2);
    await expect(grid.locator('.tabulator-selected[data-kind="Group"]').first()).toBeVisible();
    await page.keyboard.press(key);
    await expect(picker).not.toBeVisible();

    const command = frontendCalls.findLast(({ method }) => method === kind + ".editor.add_from_library");
    expect(command?.params).toMatchObject({ modify, ids: [expect.any(String), expect.any(String)] });
    const projectCodes = page.locator('.project-view:visible .project-main-grid [tabulator-field="code"]');
    for (const code of codes) await expect(projectCodes.getByText(code, { exact: true })).toBeVisible();
  });
}
