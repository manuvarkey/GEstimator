/** Keep a report export visible while the desktop switches views or documents. */
import { ref } from "vue";
import { request } from "./backend";
import { notify } from "./statusNotice";
import type { ReportExportResult, ReportFormat, ReportSpecification } from "./reportTypes";

export const reportExporting = ref(false);
export const reportExportMessage = ref("");

type ReportExportRequest = {
  revision: number;
  specification: ReportSpecification;
  format: ReportFormat;
  path: string;
  replace_selected: boolean;
  number_format: ReturnType<typeof reportNumberFormat>;
};

export async function renderReportExport(params: ReportExportRequest, session: string) {
  const { token } = await request<{ token: string }>("report.export.start", params, session);
  for (;;) {
    await new Promise((resolve) => setTimeout(resolve, 300));
    const { result } = await request<{ result: ReportExportResult | null }>("report.export.status", { token });
    if (!result) continue;
    notify("Report exported: " + result.saved);
    reportExportMessage.value = result.warnings.join("\n");
    return;
  }
}

export function reportNumberFormat(locale: string) {
  const integer = new Intl.NumberFormat(locale || undefined);
  const sample = integer.formatToParts(1234567890123.5);
  const groups = sample.filter((part) => part.type === "integer");
  const minimum = [4, 5, 6, 7].find((length) =>
    integer.formatToParts(10 ** (length - 1)).some((part) => part.type === "group"),
  );
  const ungrouped = new Intl.NumberFormat(locale || undefined, { useGrouping: false });
  return {
    group: sample.find((part) => part.type === "group")?.value ?? ",",
    decimal: sample.find((part) => part.type === "decimal")?.value ?? ".",
    primary: Array.from(groups.at(-1)?.value ?? "000").length,
    secondary: Array.from(groups.at(-2)?.value ?? "000").length,
    minimum: minimum ?? 16,
    digits: Array.from({ length: 10 }, (_, index) => ungrouped.format(index)).join(""),
  };
}
