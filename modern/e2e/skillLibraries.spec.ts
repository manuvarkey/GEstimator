import { expect, test } from "@playwright/test";
import { mkdir, rm, writeFile } from "node:fs/promises";
import { createServer, type AddressInfo } from "node:net";
import { resolve } from "node:path";
import { call, directory, useWorkspaceHarness } from "./workspaceHarness";

useWorkspaceHarness({ isolateSkillLibraries: true });

test("MCP user skill libraries become selectable after refresh and fall back after removal", async ({ page }) => {
  const settings = page.getByRole("dialog", { name: "Program settings", exact: true });
  const skillset = settings.getByRole("combobox", { name: "Estimation skillset", exact: true });
  const ribbonSkillset = page.locator(".ribbon").getByRole("combobox", { name: "Estimation skillset", exact: true });
  const save = settings.getByRole("button", { name: "Save program settings", exact: true });
  const configure = page.getByRole("dialog", { name: "Configure MCP server" });
  const refresh = page.getByRole("button", { name: "Refresh skills", exact: true });
  async function openSettings() {
    await page.getByRole("button", { name: "Application menu", exact: true }).click();
    await page.getByRole("menuitem", { name: "Program settings…", exact: true }).click();
    await expect(skillset).toBeVisible();
  }
  async function activeSkills() {
    const response = await call("mcp.read", { name: "describe_source", arguments: { section: "skills" } });
    return response.result.data;
  }

  await openSettings();
  await expect(skillset).toHaveValue("generic");
  await skillset.selectOption({ label: "IN" });
  await save.click();
  await expect(settings).not.toBeVisible();
  expect(await activeSkills()).toMatchObject({
    library: "in",
    skills: expect.arrayContaining([expect.objectContaining({ skill: "preliminary-lighting-design", library: "in" })]),
  });

  await page.locator("#view-mcp").click();
  await expect(ribbonSkillset).toHaveValue("in");
  await page.getByRole("button", { name: "Open user skill folder", exact: true }).click();
  const root = resolve(directory, "skill-libraries");
  await expect.poll(() => page.evaluate(() => Reflect.get(window, "openedLibraryDirectory"))).toBe(root);

  const library = resolve(root, "office-library");
  const skill = resolve(library, "office-takeoff");
  await mkdir(skill, { recursive: true });
  await writeFile(
    resolve(library, "library.json"),
    JSON.stringify({
      schema_version: 1,
      id: "office",
      name: "Office estimating",
      description: "Office measuring rules.",
    }),
  );
  await writeFile(
    resolve(skill, "SKILL.md"),
    "---\nname: office-takeoff\ndescription: An office-specific takeoff guide.\n---\n# Office takeoff\n",
  );
  await mkdir(resolve(root, "broken"));
  await writeFile(resolve(root, "broken/library.json"), "{}");

  await refresh.click();
  await expect(page.getByText(/Skill libraries refreshed/)).toBeVisible();
  await page.getByRole("button", { name: "Configure MCP server", exact: true }).click();
  await expect(configure.getByText(/broken: .*schema_version 1/)).toBeVisible();
  await configure.getByRole("button", { name: "Close MCP settings", exact: true }).click();

  const port = await new Promise<number>((done, reject) => {
    const listener = createServer();
    listener.once("error", reject);
    listener.listen(0, "127.0.0.1", () => {
      const { port } = listener.address() as AddressInfo;
      listener.close((error) => (error ? reject(error) : done(port)));
    });
  });
  expect((await call("mcp.configure", { port })).result).toMatchObject({ port });
  const started = (await call("mcp.start")).result;
  expect(started).toMatchObject({ port, running: true });

  await ribbonSkillset.press("Enter");
  await expect(page.getByRole("listbox").getByRole("option", { name: "Office estimating" })).toBeVisible();
  await ribbonSkillset.press("End");
  await ribbonSkillset.press("Enter");
  await expect(ribbonSkillset).toHaveValue("office");
  await expect(ribbonSkillset).toBeFocused();
  await openSettings();
  await expect(skillset).toHaveValue("office");
  await expect(settings.getByText("Office measuring rules.", { exact: true })).toBeVisible();
  await settings.getByRole("button", { name: "Cancel", exact: true }).click();
  expect((await call("mcp.status")).result).toMatchObject({ port, running: true, token: started.token });
  expect(await activeSkills()).toMatchObject({
    library: "office",
    skills: [
      expect.objectContaining({ skill: "office-takeoff", library: "office" }),
      expect.objectContaining({ skill: "rate-analysis", library: "shared" }),
    ],
  });
  await page.reload();
  await page.locator("#view-mcp").click();
  await expect(ribbonSkillset).toHaveValue("office");
  await openSettings();
  await expect(skillset).toHaveValue("office");
  await settings.getByRole("button", { name: "Cancel", exact: true }).click();

  await rm(library, { recursive: true });
  await page.locator("#view-mcp").click();
  await refresh.click();
  await expect.poll(async () => (await activeSkills()).library).toBe("generic");
  await expect(ribbonSkillset).toHaveValue("generic");
  await openSettings();
  await expect(skillset).toHaveValue("generic");
  await expect(settings.getByText(/office.*is unavailable/)).toBeVisible();
});
