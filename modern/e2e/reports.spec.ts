/** Compose and export reports through the real Python backend and native chooser adapter. */
import { test, expect, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import {
  directory,
  call,
  python,
  openFixture,
  useWorkspaceHarness,
  nativeDialogResults,
  frontendCalls,
  holdNextRequest,
} from "./workspaceHarness";

useWorkspaceHarness();

async function openReport(page: Page, measurements = false) {
  const path = resolve(directory, "report.eproj");
  execFileSync(python, ["-m", "modern.e2e.create_fixture", path], { cwd: resolve("..") });
  if (measurements) {
    execFileSync(
      python,
      [
        "-c",
        `
import sys
from estimator.data.schedule import ScheduleDatabase
from estimator.data.measurement import MeasurementItemCustom, RecordCustom
from estimator.undo import Stack
s = ScheduleDatabase(Stack())
s.open_database(sys.argv[1])
m = s.get_measurement()
i = MeasurementItemCustom(plugin="_1_NLBH")
i.remark = "Measured foundation"
i.itemnos[0] = s.ScheduleTable.get(code="A").id
i.append_record(RecordCustom(["Foundation", "", "1", "2", "3", "4", ""], i.cust_funcs, i.total_func_item, i.columntypes))
m.append_item(i)
s.set_measurement(m)
s.close_database()
`,
        path,
      ],
      { cwd: resolve("..") },
    );
  }
  await openFixture(page, path);
  await page.locator("#view-reports").click();
  return page.getByRole("region", { name: "Report workspace" });
}

test("reports compose ordered sections and export matching HTML, Excel and available PDF", async ({ page }) => {
  test.setTimeout(90000);
  const report = await openReport(page);
  await report.getByLabel("Report title", { exact: true }).fill("<Project report>");
  await report.getByLabel("Organization", { exact: true }).fill("Engineering office");
  await report.getByLabel("Include signoff", { exact: true }).click();
  await report.getByRole("button", { name: "Reorder schedule", exact: true }).focus();
  await page.keyboard.press("Alt+ArrowUp");
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
    await expect(page.getByText(`Report exported: ${pdfPath}`, { exact: true })).toBeVisible({ timeout: 60000 });
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

test("reports include analyses, resources and usage with shared engine values", async ({ page }) => {
  const report = await openReport(page);
  for (const label of ["Include analyses", "Include resources", "Include resource usage"]) {
    await report.getByLabel(label, { exact: true }).click();
  }
  await report.getByRole("button", { name: "Generate preview", exact: true }).click();
  const preview = page.frameLocator('iframe[title="Report preview"]');
  await expect(preview.locator("section > h1")).toHaveText([
    "Abstract of estimate",
    "Schedule",
    "Signoff",
    "Analyses of rates",
    "Resources",
    "Resource usage",
  ]);
  const analyses = preview.locator("#analyses");
  await expect(analyses).toContainText("Stored schedule rate: 20");
  await expect(analyses).toContainText("Calculated analysis rate: 20.00");
  await expect(analyses.getByRole("cell", { name: "Material", exact: true })).toBeVisible();
  await expect(preview.locator("#resources")).toContainText("Materials");
  await expect(preview.locator("#resource_usage")).toContainText("2.0000");
  await expect(preview.locator("#resource_usage")).toContainText("20.00");
  const exportButton = report.getByRole("button", { name: "Export report…", exact: true });
  await expect(exportButton).toBeEnabled();
  const htmlPath = resolve(directory, "complete.html");
  nativeDialogResults.push(htmlPath);
  await exportButton.click();
  await expect(page.getByText(`Report exported: ${htmlPath}`, { exact: true })).toBeVisible();
  const html = await readFile(htmlPath, "utf8");
  expect(html).toContain('href="#analyses:analysis:0"');
  expect(html).toContain('class="section wide" id="resources"');
  await report.getByLabel("Output format").selectOption("xlsx");
  const excelPath = resolve(directory, "complete.xlsx");
  nativeDialogResults.push(excelPath);
  await exportButton.click();
  await expect(page.getByText(`Report exported: ${excelPath}`, { exact: true })).toBeVisible();
  const titles = execFileSync(
    python,
    [
      "-c",
      "import sys,json;from openpyxl import load_workbook;w=load_workbook(sys.argv[1]);print(json.dumps([s['A1'].value for s in list(w)[2:]]));w.close()",
      excelPath,
    ],
    { cwd: resolve(".."), encoding: "utf8" },
  );
  expect(JSON.parse(titles)).toEqual([
    "Abstract of estimate",
    "Schedule",
    "Analyses of rates",
    "Resources",
    "Resource usage",
  ]);
  await analyses.getByRole("heading", { name: "Analyses of rates", exact: true }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: "test-results/report-analyses.png", animations: "disabled" });
});

test("reports render measurement templates and editable plain-text notes", async ({ page }) => {
  const report = await openReport(page, true);
  await report.getByLabel("Include measurements", { exact: true }).click();
  await report.getByLabel("Include narrative", { exact: true }).click();
  await report
    .locator(".report-sections > li")
    .filter({ has: page.getByLabel("Include narrative", { exact: true }) })
    .locator("summary")
    .click();
  const notes = report.getByLabel("Notes text", { exact: true });
  await notes.fill("<Notes>\n=Office reference");
  await notes.press("Enter");
  await expect(notes).toHaveValue("<Notes>\n=Office reference\n");
  await report.getByRole("button", { name: "Generate preview", exact: true }).click();
  const preview = page.frameLocator('iframe[title="Report preview"]');
  await expect(preview.locator("#narrative")).toContainText("<Notes>");
  await expect(preview.locator("#narrative script")).toHaveCount(0);
  await expect(preview.locator("#measurements")).toContainText("Complete measurement sheets");
  await expect(preview.locator("#measurements")).toContainText("Measured foundation");
  await expect(preview.locator("#measurements")).toContainText("24.0");
  await notes.fill("Updated notes");
  await expect(report.getByRole("button", { name: "Export report…", exact: true })).toBeDisabled();
  await page.locator("#view-schedule").click();
  await page.locator("#view-reports").click();
  await expect(notes).toHaveValue("Updated notes");
  await report.getByRole("button", { name: "Generate preview", exact: true }).click();
  await expect(preview.locator("#narrative")).toContainText("Updated notes");
  await report.getByLabel("Output format").selectOption("xlsx");
  const path = resolve(directory, "notes.xlsx");
  nativeDialogResults.push(path);
  await report.getByRole("button", { name: "Export report…", exact: true }).click();
  await expect(page.getByText(`Report exported: ${path}`, { exact: true })).toBeVisible();
  await page.screenshot({ path: "test-results/report-notes-light.png", animations: "disabled" });
  await page.getByRole("button", { name: "Switch to dark theme" }).click();
  await page.setViewportSize({ width: 700, height: 900 });
  await notes.scrollIntoViewIfNeeded();
  await expect(notes).toBeVisible();
  await page.screenshot({ path: "test-results/report-notes-dark-narrow.png", animations: "disabled" });
});

test("reports customize column order and page orientation without changing totals", async ({ page }) => {
  const report = await openReport(page);
  const schedule = report
    .locator(".report-sections > li")
    .filter({ has: page.getByLabel("Include schedule", { exact: true }) });
  await schedule.locator("summary").click();
  await schedule.getByLabel("schedule custom columns", { exact: true }).check();
  for (const name of ["Code", "Unit", "Rate"]) {
    await schedule.getByLabel(`Include schedule ${name} column`, { exact: true }).uncheck();
  }
  await schedule.getByLabel("Include schedule Remarks column", { exact: true }).check();
  const move = schedule.getByRole("button", { name: "Move schedule Amount column up", exact: true });
  await move.focus();
  await page.keyboard.press("Enter");
  await move.click();
  await schedule.getByLabel("schedule page orientation", { exact: true }).selectOption("landscape");
  await report.getByRole("button", { name: "Generate preview", exact: true }).click();
  const preview = page.frameLocator('iframe[title="Report preview"]');
  await expect(preview.locator("#schedule th")).toHaveText(["Amount", "Description", "Quantity", "Remarks"]);
  await expect(preview.locator("#schedule")).toHaveClass("section wide");
  await expect(report.locator(".report-summary")).toContainText("20.00");
  await report.getByLabel("Output format").selectOption("xlsx");
  const path = resolve(directory, "layout.xlsx");
  nativeDialogResults.push(path);
  await report.getByRole("button", { name: "Export report…", exact: true }).click();
  await expect(page.getByText(`Report exported: ${path}`, { exact: true })).toBeVisible();
  const exported = execFileSync(
    python,
    [
      "-c",
      "import sys,json;from openpyxl import load_workbook;w=load_workbook(sys.argv[1]);s=w['Section 2'];print(json.dumps([[c.value for c in s[3]],s.page_setup.orientation,s['A4'].value]));w.close()",
      path,
    ],
    { cwd: resolve(".."), encoding: "utf8" },
  );
  expect(JSON.parse(exported)).toEqual([["Amount", "Description", "Quantity", "Remarks"], "landscape", 20]);
  await schedule.getByLabel("schedule page orientation", { exact: true }).selectOption("portrait");
  await expect(report.getByRole("button", { name: "Export report…", exact: true })).toBeDisabled();
  await page.locator("#view-schedule").click();
  await page.locator("#view-reports").click();
  await expect(schedule.getByLabel("schedule page orientation", { exact: true })).toHaveValue("portrait");
  await report.getByRole("button", { name: "Generate preview", exact: true }).click();
  await expect(preview.locator("#schedule")).toHaveClass("section portrait");
  await expect(preview.locator("#schedule th")).toHaveText(["Amount", "Description", "Quantity", "Remarks"]);
  await schedule.scrollIntoViewIfNeeded();
  await page.screenshot({ path: "test-results/report-layout-light.png", animations: "disabled" });
  await page.getByRole("button", { name: "Switch to dark theme" }).click();
  await page.setViewportSize({ width: 700, height: 900 });
  await schedule.scrollIntoViewIfNeeded();
  await page.screenshot({ path: "test-results/report-layout-dark-narrow.png", animations: "disabled" });
  await schedule.getByLabel("schedule custom columns", { exact: true }).uncheck();
  await report.getByRole("button", { name: "Generate preview", exact: true }).click();
  await expect(preview.locator("#schedule th")).toHaveText([
    "Code",
    "Description",
    "Unit",
    "Quantity",
    "Rate",
    "Amount",
  ]);
});

test("reports apply settings to the working project and restore them after save and reopen", async ({ page }) => {
  const report = await openReport(page);
  const path = resolve(directory, "report.eproj");
  const original = await readFile(path);
  await report.getByLabel("Report title", { exact: true }).fill("Saved office report");
  await report.getByLabel("Include narrative", { exact: true }).click();
  await report
    .locator(".report-sections > li")
    .filter({ has: page.getByLabel("Include narrative", { exact: true }) })
    .locator("summary")
    .click();
  await report.getByLabel("Notes text", { exact: true }).fill("Saved notes\n<Literal>");
  const schedule = report
    .locator(".report-sections > li")
    .filter({ has: page.getByLabel("Include schedule", { exact: true }) });
  await schedule.locator("summary").click();
  await schedule.getByLabel("schedule page orientation", { exact: true }).selectOption("landscape");
  await schedule.getByLabel("schedule custom columns", { exact: true }).check();
  await schedule.getByLabel("Include schedule Rate column", { exact: true }).uncheck();
  await report.getByRole("button", { name: "Generate preview", exact: true }).click();
  await expect(report.getByRole("button", { name: "Export report…", exact: true })).toBeEnabled();
  const resume = await holdNextRequest(page, "report.settings.apply");
  await report.getByRole("button", { name: "Apply report settings", exact: true }).click();
  await expect(report.getByLabel("Report title", { exact: true })).toBeDisabled();
  await resume();
  await expect(page.getByText("Report settings applied. Save project to keep them.", { exact: true })).toBeVisible();
  await expect(report.getByRole("button", { name: "Export report…", exact: true })).toBeDisabled();
  expect(await readFile(path)).toEqual(original);
  await expect.poll(async () => (await call("state")).result.workspace_dirty).toBe(true);
  await page.locator(".titlebar").getByRole("button", { name: "Save project", exact: true }).click();
  await expect.poll(async () => (await call("state")).result.workspace_dirty).toBe(false);
  expect(await readFile(path)).not.toEqual(original);
  await report.getByLabel("Report title", { exact: true }).fill("Unapplied change");
  await report.getByRole("button", { name: "Reload report settings", exact: true }).click();
  await expect(report.getByLabel("Report title", { exact: true })).toHaveValue("Saved office report");
  await page.getByRole("button", { name: "Application menu", exact: true }).click();
  await page.getByRole("menuitem", { name: "Close project", exact: true }).click();
  await expect(page.getByRole("region", { name: "Start an estimate" })).toBeVisible();
  await openFixture(page, path);
  await page.locator("#view-reports").click();
  await expect(report.getByLabel("Report title", { exact: true })).toHaveValue("Saved office report");
  await report
    .locator(".report-sections > li")
    .filter({ has: page.getByLabel("Include narrative", { exact: true }) })
    .locator("summary")
    .click();
  await expect(report.getByLabel("Notes text", { exact: true })).toHaveValue("Saved notes\n<Literal>");
  await schedule.locator("summary").click();
  await expect(schedule.getByLabel("schedule page orientation", { exact: true })).toHaveValue("landscape");
  await expect(schedule.getByLabel("Include schedule Rate column", { exact: true })).not.toBeChecked();
  await report.getByRole("button", { name: "Generate preview", exact: true }).click();
  await expect(page.frameLocator('iframe[title="Report preview"]').locator("#narrative")).toContainText("<Literal>");
  await page.screenshot({ path: "test-results/report-saved-settings.png", animations: "disabled" });
});

test("reports preserve unreadable future settings until explicitly replaced", async ({ page }) => {
  const path = resolve(directory, "future-report.eproj");
  execFileSync(python, ["-m", "modern.e2e.create_fixture", path], { cwd: resolve("..") });
  execFileSync(
    python,
    [
      "-c",
      "import sqlite3,sys;c=sqlite3.connect(sys.argv[1]);c.execute('INSERT INTO projecttable (key,value) VALUES (?,?)',('project_report_specification','{\"schema_version\":99}'));c.commit();c.close()",
      path,
    ],
    { cwd: resolve("..") },
  );
  const original = await readFile(path);
  await openFixture(page, path);
  await page.locator("#view-reports").click();
  const report = page.getByRole("region", { name: "Report workspace" });
  await expect(report.getByRole("alert")).toContainText("remain unchanged");
  await report.getByRole("button", { name: "Generate preview", exact: true }).click();
  await expect(report.getByRole("button", { name: "Export report…", exact: true })).toBeEnabled();
  expect(await readFile(path)).toEqual(original);
  await report.getByLabel("Report title", { exact: true }).fill("Replacement");
  await report.getByRole("button", { name: "Apply report settings", exact: true }).click();
  await expect(page.getByText("Report settings applied. Save project to keep them.", { exact: true })).toBeVisible();
  await report.getByRole("button", { name: "Reload report settings", exact: true }).click();
  await expect(report.getByRole("alert")).not.toBeVisible();
  await expect(report.getByLabel("Report title", { exact: true })).toHaveValue("Replacement");
  expect(await readFile(path)).toEqual(original);
});

test("report typography uses installed fonts, persists and invalidates previews", async ({ page }) => {
  const report = await openReport(page);
  const typography = report.locator(".settings-group").filter({ hasText: "Page and typography" });
  await typography.locator("summary").focus();
  await page.keyboard.press("Enter");
  const font = typography.getByLabel("Report font", { exact: true });
  await expect(font).toBeEnabled();
  const fonts = await font
    .locator("option")
    .evaluateAll((options) => options.map((option) => (option as HTMLOptionElement).value));
  expect(fonts.length).toBeGreaterThan(1);
  const selected = fonts.find((value) => value === "DejaVu Serif") ?? fonts[1]!;
  await font.selectOption(selected);
  await typography.getByLabel("Font scale (%)", { exact: true }).fill("125");
  await report.getByRole("button", { name: "Generate preview", exact: true }).click();
  const preview = page.frameLocator('iframe[title="Report preview"]');
  await expect(preview.locator("body")).toHaveCSS("font-size", "16.6667px");
  await expect(preview.locator("body")).toHaveCSS("font-family", new RegExp(selected));
  const current = frontendCalls.filter((entry) => entry.method === "report.preview").at(-1)!;
  expect(current.params.specification).toMatchObject({ font_family: selected, font_scale: 1.25 });
  await typography.getByLabel("Font scale (%)", { exact: true }).fill("110");
  await expect(report.getByRole("button", { name: "Export report…", exact: true })).toBeDisabled();
  await report.getByRole("button", { name: "Apply report settings", exact: true }).click();
  await expect(page.getByText("Report settings applied. Save project to keep them.", { exact: true })).toBeVisible();
  await report.getByRole("button", { name: "Reload report settings", exact: true }).click();
  await expect(font).toHaveValue(selected);
  await expect(typography.getByLabel("Font scale (%)", { exact: true })).toHaveValue("110");
  const schedule = report
    .locator(".report-sections > li")
    .filter({ has: page.getByLabel("Include schedule", { exact: true }) });
  const abstract = report
    .locator(".report-sections > li")
    .filter({ has: page.getByLabel("Include abstract", { exact: true }) });
  await schedule.locator("summary").click();
  await expect(schedule.getByLabel("schedule title", { exact: true })).toBeVisible();
  await abstract.locator("summary").click();
  await expect(schedule.getByLabel("schedule title", { exact: true })).not.toBeVisible();
  await expect(abstract.getByLabel("abstract title", { exact: true })).toBeVisible();
  await typography.scrollIntoViewIfNeeded();
  await page.screenshot({ path: "test-results/report-typography-light.png", animations: "disabled" });
  await page.getByRole("button", { name: "Switch to dark theme" }).click();
  await page.setViewportSize({ width: 700, height: 900 });
  await typography.scrollIntoViewIfNeeded();
  await expect(font).toBeVisible();
  await page.screenshot({ path: "test-results/report-typography-dark-narrow.png", animations: "disabled" });
});

test("reports edit templated pages, repeat signoffs, group items and reorder by drag handle", async ({ page }) => {
  const report = await openReport(page, true);
  const item = (kind: string) =>
    report
      .locator(".report-sections > li")
      .filter({ has: page.getByRole("button", { name: `Include ${kind}`, exact: true }) });
  await report.getByLabel("Organization", { exact: true }).fill("Office reference");
  await report.getByRole("button", { name: "Include narrative", exact: true }).click();
  await item("narrative").locator("summary").click();
  await report
    .getByLabel("Notes text", { exact: true })
    .fill("Office: {{ organization | upper }}\nTotal: {{ estimate_total }}");
  await report.getByRole("button", { name: "Add notes page", exact: true }).click();
  await report
    .getByLabel("Notes text page 2", { exact: true })
    .fill("Reference: {{ reference | default('Not issued', true) }}");
  // Bounded Jinja supports positional default arguments, without arbitrary calls.
  await report.getByLabel("Notes text page 2", { exact: true }).fill("Second page: {{ title }}");
  for (const kind of ["analyses", "measurements"]) {
    await report.getByRole("button", { name: `Include ${kind}`, exact: true }).click();
    await item(kind).locator("summary").click();
    await item(kind).getByLabel(`${kind} separate item pages`, { exact: true }).check();
  }
  await item("schedule").locator("summary").click();
  await item("schedule").getByLabel("schedule show name of work", { exact: true }).check();
  await item("signoff").locator("summary").click();
  await expect(item("signoff").getByLabel("signoff page orientation", { exact: true })).toBeDisabled();
  await item("signoff").getByLabel("Signoff signature block 1 caption", { exact: true }).fill("Designed by");
  await item("signoff").getByLabel("Signoff signature block 1 text", { exact: true }).fill("Engineer\nDepartment");
  await report.getByLabel("Add page or section").selectOption("signoff");
  await report.getByRole("button", { name: "Add section", exact: true }).click();
  const extra = item("signoff").last();
  await extra.locator("summary").click();
  await extra.getByLabel("signoff title", { exact: true }).fill("Approval page");
  await extra.getByLabel("Start signoff on a separate page").check();
  await expect(extra.getByLabel("signoff page orientation", { exact: true })).toBeEnabled();
  const notes = item("narrative");
  const abstract = item("abstract");
  await notes.getByRole("button", { name: "Reorder narrative", exact: true }).dragTo(abstract);
  await expect(
    report.locator(".report-sections > li").first().getByRole("button", { name: "Include abstract", exact: true }),
  ).toBeVisible();
  await report.getByRole("button", { name: "Generate preview", exact: true }).click();
  const preview = page.frameLocator('iframe[title="Report preview"]');
  await expect(preview.locator("#narrative")).toContainText("OFFICE REFERENCE");
  await expect(preview.locator("#narrative .note-page")).toHaveCount(2);
  await expect(preview.locator("#signoff")).toHaveClass("section inline");
  await expect(preview.locator("#signoff")).toContainText("Designed by");
  await expect(preview.locator('.toc a[href="#measurements:measurement:0"]')).toContainText("Measured foundation");
  await expect(preview.locator(".item-heading").first()).toHaveCSS("font-size", "13.3333px");
  await expect(preview.getByRole("heading", { name: "Approval page", exact: true })).toBeVisible();
  await page.screenshot({ path: "test-results/report-composition-pages.png", animations: "disabled" });
});

test("program estimate defaults populate project fields and the report", async ({ page }) => {
  await openReport(page);
  await page.getByRole("button", { name: "Application menu", exact: true }).click();
  await page.getByRole("menuitem", { name: "Program settings…", exact: true }).click();
  const program = page.getByRole("dialog", { name: "Program settings", exact: true });
  await program.getByRole("tab", { name: "Estimate defaults", exact: true }).click();
  await program.getByLabel("Program default Organization", { exact: true }).fill("Default office");
  await program.locator("summary").filter({ hasText: "Signoff blocks" }).click();
  await program.getByLabel("Program default signoff block 1 caption", { exact: true }).fill("Office engineer");
  await program.getByRole("button", { name: "Save program settings", exact: true }).click();
  await expect(program).not.toBeVisible();
  await page.getByRole("button", { name: "Application menu", exact: true }).click();
  await page.getByRole("menuitem", { name: "Project settings…", exact: true }).click();
  const project = page.getByRole("dialog", { name: "Project settings", exact: true });
  await expect(project.getByLabel("Project Organization", { exact: true })).toHaveValue("Default office");
  await project.getByLabel("Project Organization", { exact: true }).fill("Override");
  await project.getByRole("button", { name: "Use program default for organization", exact: true }).click();
  await expect(project.getByLabel("Project Organization", { exact: true })).toHaveValue("Default office");
  await project.getByRole("button", { name: "Apply settings", exact: true }).click();
  await expect(project).not.toBeVisible();
  const report = page.getByRole("region", { name: "Report workspace" });
  await report.getByRole("button", { name: "Reload report settings", exact: true }).click();
  await expect(report.getByLabel("Organization", { exact: true })).toHaveValue("Default office");
  const signoff = report
    .locator(".report-sections > li")
    .filter({ has: page.getByRole("button", { name: "Include signoff", exact: true }) });
  await signoff.locator("summary").click();
  await expect(signoff.getByLabel("Signoff signature block 1 caption", { exact: true })).toHaveValue("Office engineer");
});
