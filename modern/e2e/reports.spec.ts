/** Compose and export reports through the real Python backend and native chooser adapter. */
import { test, expect, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import {
  directory,
  python,
  openFixture,
  useWorkspaceHarness,
  nativeDialogResults,
  frontendCalls,
  holdNextRequest,
} from "./workspaceHarness";

useWorkspaceHarness();

async function openReport(page: Page) {
  const path = resolve(directory, "report.eproj");
  execFileSync(python, ["-m", "modern.e2e.create_fixture", path], { cwd: resolve("..") });
  await openFixture(page, path);
  await page.locator("#view-reports").click();
  return page.getByRole("region", { name: "Report workspace" });
}

test("reports compose ordered sections and export matching HTML, Excel and available PDF", async ({ page }) => {
  const report = await openReport(page);
  await report.getByLabel("Report title", { exact: true }).fill("<Project report>");
  await report.getByLabel("Organization", { exact: true }).fill("Engineering office");
  await report.getByLabel("Include signoff", { exact: true }).uncheck();
  await report.getByRole("button", { name: "Move schedule up", exact: true }).focus();
  await page.keyboard.press("Enter");
  await report.getByRole("button", { name: "Generate preview", exact: true }).click();
  const preview = page.frameLocator('iframe[title="Report preview"]');
  await expect(preview.getByRole("heading", { name: "<Project report>" })).toBeVisible();
  await expect(preview.locator("section h1")).toHaveText(["Schedule", "Abstract of estimate"]);
  await expect(preview.locator("section").first()).toContainText("20.00");
  await expect(report.getByRole("button", { name: "Export report…", exact: true })).toBeEnabled();
  const htmlPath = resolve(directory, "report.html");
  nativeDialogResults.push(htmlPath);
  await report.getByRole("button", { name: "Export report…", exact: true }).click();
  await expect(page.getByText(`Report exported: ${htmlPath}`, { exact: true })).toBeVisible();
  const html = await readFile(htmlPath, "utf8");
  expect(html).toContain("&lt;Project report&gt;");
  expect(html).toContain("20.00");
  expect(html).not.toContain('id="signoff"');
  await report.getByLabel("Output format").selectOption("xlsx");
  const excelPath = resolve(directory, "report.xlsx");
  nativeDialogResults.push(excelPath);
  await report.getByRole("button", { name: "Export report…", exact: true }).click();
  await expect(page.getByText(`Report exported: ${excelPath}`, { exact: true })).toBeVisible();
  expect((await readFile(excelPath)).subarray(0, 2).toString()).toBe("PK");
  const pdfOption = report.getByLabel("Output format").locator('option[value="pdf"]');
  if (!(await pdfOption.isDisabled())) {
    await report.getByLabel("Output format").selectOption("pdf");
    const pdfPath = resolve(directory, "report.pdf");
    nativeDialogResults.push(pdfPath);
    await report.getByRole("button", { name: "Export report…", exact: true }).click();
    await expect(page.getByText(`Report exported: ${pdfPath}`, { exact: true })).toBeVisible();
    expect((await readFile(pdfPath)).subarray(0, 5).toString()).toBe("%PDF-");
  }
  await page.screenshot({ path: "test-results/report-workspace-light.png", animations: "disabled" });
  await page.getByRole("button", { name: "Switch to dark theme" }).click();
  await page.setViewportSize({ width: 700, height: 900 });
  await expect(report.getByLabel("Report title", { exact: true })).toBeVisible();
  await expect(report.getByRole("button", { name: "Export report…", exact: true })).toBeVisible();
  await page.screenshot({ path: "test-results/report-workspace-dark-narrow.png", animations: "disabled" });
});

test("reports preserve settings across views, reject stale previews and retain failed exports", async ({ page }) => {
  const report = await openReport(page);
  const generate = report.getByRole("button", { name: "Generate preview", exact: true });
  const exportButton = report.getByRole("button", { name: "Export report…", exact: true });
  await generate.click();
  await expect(exportButton).toBeEnabled();
  await report.getByLabel("Reference", { exact: true }).fill("REF-1");
  await expect(report.getByRole("status")).toContainText("out of date");
  await expect(exportButton).toBeDisabled();
  await generate.click();
  await expect(exportButton).toBeEnabled();
  await page.locator("#view-schedule").click();
  const quantity = page
    .locator('.project-view:visible .project-main-grid .tabulator-row [tabulator-field="qty"]')
    .last();
  await quantity.dblclick();
  await quantity.locator("input").fill("3");
  await quantity.locator("input").press("Enter");
  await expect(quantity).toHaveText("3");
  await page.locator("#view-reports").click();
  await expect(report.getByLabel("Reference", { exact: true })).toHaveValue("REF-1");
  await expect(report.getByRole("status")).toContainText("out of date");
  await expect(exportButton).toBeDisabled();
  await generate.click();
  await expect(report.locator(".report-summary")).toContainText("60.00");
  const path = resolve(directory, "existing.html");
  await writeFile(path, "original");
  nativeDialogResults.push(path);
  await exportButton.click();
  await expect(report.getByRole("alert")).toBeVisible();
  expect(await readFile(path, "utf8")).toBe("original");
  await expect(report.getByLabel("Reference", { exact: true })).toHaveValue("REF-1");
  const before = frontendCalls.filter((entry) => entry.method === "report.export").length;
  nativeDialogResults.push(null);
  await exportButton.click();
  await expect(exportButton).toBeEnabled();
  expect(frontendCalls.filter((entry) => entry.method === "report.export")).toHaveLength(before);
});

test("reports handle busy previews and keep composition local to a project tab", async ({ page }) => {
  const report = await openReport(page);
  await report.getByLabel("Report title", { exact: true }).fill("First project report");
  const resume = await holdNextRequest(page, "report.preview");
  await report.getByRole("button", { name: "Generate preview", exact: true }).click();
  await expect(report.getByLabel("Report title", { exact: true })).toBeDisabled();
  await expect(report.getByRole("button", { name: "Generate preview", exact: true })).toBeDisabled();
  await resume();
  await expect(report.getByRole("button", { name: "Export report…", exact: true })).toBeEnabled();
  const rail = page.getByRole("navigation", { name: "Open projects" });
  await rail.getByRole("button", { name: "New project tab", exact: true }).click();
  await expect(page.getByRole("region", { name: "Start an estimate" })).toBeVisible();
  await rail.getByRole("tab").first().click();
  await expect(report.getByLabel("Report title", { exact: true })).toHaveValue("First project report");
  await expect(report.getByRole("button", { name: "Export report…", exact: true })).toBeEnabled();
});
