import { ref, watch } from "vue";

export interface Appearance {
  theme: "system" | "light" | "dark";
  uiFamily: string;
  uiSize: number | null;
  tableFamily: string;
  tableSize: number | null;
}

export const programSettingsKey = "gestimator.program-settings.v1";
export const defaultAppearance: Appearance = {
  theme: "dark", uiFamily: "", uiSize: null, tableFamily: "", tableSize: null,
};

function normalizeAppearance(value: Partial<Appearance> | undefined): Appearance {
  const family = (name: unknown) => typeof name === "string" && !/[\u0000-\u001f\u007f]/.test(name) ? name.trim().slice(0, 120) : "";
  const size = (px: unknown) => typeof px === "number" && Number.isFinite(px) && px >= 10 && px <= 30 ? px : null;
  return {
    theme: value?.theme === "system" || value?.theme === "light" || value?.theme === "dark" ? value.theme : defaultAppearance.theme,
    uiFamily: family(value?.uiFamily), uiSize: size(value?.uiSize),
    tableFamily: family(value?.tableFamily), tableSize: size(value?.tableSize),
  };
}

function storedAppearance() {
  try {
    const stored = JSON.parse(localStorage.getItem(programSettingsKey) || "null");
    if (stored?.version === 1 && stored.appearance) return normalizeAppearance(stored.appearance);
    return normalizeAppearance({ theme: localStorage.getItem("gestimator-theme") as Appearance["theme"] });
  } catch {
    return { ...defaultAppearance };
  }
}

export const appearance = ref(storedAppearance());
const platformFont = ref<{ family?: string; size?: string }>({});
export function setPlatformFont(font: typeof platformFont.value) { platformFont.value = font; }
const systemDark = matchMedia("(prefers-color-scheme: dark)");
export const activeTheme = ref<"dark" | "light">("dark");
function applyTheme() {
  const theme = appearance.value.theme;
  activeTheme.value = theme === "system" ? systemDark.matches ? "dark" : "light" : theme;
  document.documentElement.dataset.theme = activeTheme.value;
}
systemDark.addEventListener("change", applyTheme);
watch(() => appearance.value.theme, applyTheme, { immediate: true });

watch([appearance, platformFont], ([prefs, native]) => {
  const root = document.documentElement.style;
  const uiFamily = prefs.uiFamily || native.family;
  // Empty custom properties expose the shared defaults from theme.css.
  root.setProperty("--ui-font-family", uiFamily ? JSON.stringify(uiFamily) + ", system-ui" : "");
  root.setProperty("--ui-font-size", prefs.uiSize ? `${prefs.uiSize}px` : native.size || "");
  root.setProperty("--table-font-family", prefs.tableFamily ? JSON.stringify(prefs.tableFamily) + ", var(--ui-font-family)" : "");
  root.setProperty("--table-font-size", prefs.tableSize ? `${prefs.tableSize}px` : "");
}, { immediate: true });

export function toggleTheme() {
  const next = { ...appearance.value, theme: activeTheme.value === "dark" ? "light" : "dark" } as Appearance;
  try {
    const stored = JSON.parse(localStorage.getItem(programSettingsKey) || "null");
    if (stored?.version === 1 || stored === null)
      localStorage.setItem(programSettingsKey, JSON.stringify({ ...stored, version: 1, appearance: next }));
  } catch {
    // The quick toggle still works for the session if preferences cannot be written.
  }
  appearance.value = next;
}

export function validateAppearance(prefs: Appearance): Appearance {
  const result = normalizeAppearance(prefs);
  for (const size of ["uiSize", "tableSize"] as const) {
    if (prefs[size] !== null && result[size] === null) throw new Error("Font sizes must be between 10 and 30 px, or left blank.");
  }
  return result;
}
