/** Native chooser shared by project and analysis workbook exports. */
import { save } from "@tauri-apps/plugin-dialog";

type WorkbookExportDestination = {
  path: string;
  replace_selected: true;
};

/** Run the caller's export only after the native chooser returns a destination. */
export async function exportWithWorkbookChooser(
  defaultPath: string,
  exportWorkbook: (destination: WorkbookExportDestination) => Promise<boolean>,
  reportError: (message: string) => void,
): Promise<void> {
  try {
    const path = await save({
      filters: [{ name: "Excel workbook", extensions: ["xlsx"] }],
      defaultPath,
    });
    if (typeof path === "string") {
      // Python can replace a portal file after the chooser has confirmed it.
      await exportWorkbook({ path, replace_selected: true });
    }
  } catch (reason) {
    reportError(String(reason));
  }
}
