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
    await page.locator(".ribbon").getByRole("button", { name: title, exact: true }).click();
    const picker = page.getByRole("dialog", { name: title, exact: true });
    const grid = picker.getByRole("grid", { name: gridLabel, exact: true });
    await expect(grid.locator('.tabulator-row[data-kind="Resource"]')).toHaveCount(2);

    // Extend the keyboard selection across both items and their category rows.
    await grid.press("Home");
    await grid.press("Shift+End");
    await expect(grid.locator('.tabulator-selected[data-kind="Resource"]')).toHaveCount(2);
    await expect(grid.locator('.tabulator-selected[data-kind="Group"]').first()).toBeVisible();
    await grid.press(key);
    await expect(picker).not.toBeVisible();

    const command = frontendCalls.findLast(({ method }) => method === kind + ".editor.add_from_library");
    expect(command?.params).toMatchObject({ modify, ids: [expect.any(String), expect.any(String)] });
    const projectCodes = page.locator('.project-view:visible .project-main-grid [tabulator-field="code"]');
    for (const code of codes) await expect(projectCodes.getByText(code, { exact: true })).toBeVisible();
  });
}
