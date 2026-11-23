import { ref } from "vue";
import { request, type RowKind } from "./backend";
import { appearance, programSettingsKey, validateAppearance, type Appearance } from "./appearance";

export interface TemplateRow {
  kind: Exclude<RowKind, "Resource">;
  description: string;
  value: string;
  code?: string;
}
export interface ProgramSettings {
  number_locale: string;
  currency_code: string;
  show_currency_symbol: boolean;
  export_break_items: boolean;
  live_search: boolean;
  enter_edits_next_cell: boolean;
  mcp_enabled: boolean;
  sch_rate_mult_factor: string;
  ana_copy_delete_rows: number;
  ana_default_rows: TemplateRow[];
  ana_copy_rows: TemplateRow[];
}
export const programSettings = ref<ProgramSettings>();
export const programSettingsWarning = ref("");
export const customDatabaseDirectory = ref("");
export async function shippedProgramSettings() {
  const result = await request<{ settings: ProgramSettings; library_directory: string }>("program.settings");
  customDatabaseDirectory.value = result.library_directory;
  return result.settings;
}
export async function initializeProgramSettings() {
  if (programSettings.value) return;
  const defaults = await shippedProgramSettings();
  try {
    const raw = localStorage.getItem(programSettingsKey);
    let candidate = defaults;
    if (raw) {
      const stored = JSON.parse(raw);
      if (stored?.version !== 1) throw new Error("Unsupported saved settings version");
      if ("settings" in stored) candidate = stored.settings;
    }
    if (candidate === defaults) {
      const previous = JSON.parse(localStorage.getItem("gestimator.analysis-template.v1") || "null");
      if (previous?.version === 1) candidate = { ...defaults, ana_default_rows: previous.rows };
    }
    programSettings.value = await request<ProgramSettings>("program.settings.validate", { settings: candidate });
  } catch {
    programSettings.value = defaults;
    programSettingsWarning.value =
      "Saved program settings could not be read or validated. Shipped defaults are active; save settings to replace the invalid preferences.";
  }
}
export async function saveProgramSettings(settings: ProgramSettings, appearanceDraft: Appearance = appearance.value) {
  const nextAppearance = validateAppearance(appearanceDraft);
  const validated = await request<ProgramSettings>("program.settings.validate", { settings });
  localStorage.setItem(
    programSettingsKey,
    JSON.stringify({ version: 1, settings: validated, appearance: nextAppearance }),
  );
  programSettings.value = validated;
  appearance.value = nextAppearance;
  programSettingsWarning.value = "";
}
