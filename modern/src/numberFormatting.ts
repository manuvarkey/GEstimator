import { computed } from "vue";
import type { CellComponent } from "tabulator-tables";
import { programSettings } from "./programSettings";

export interface MoneySettings { number_locale: string; currency_code: string; show_currency_symbol: boolean }
export function moneyFormatter(settings: MoneySettings, places = 2) {
  return new Intl.NumberFormat(settings.number_locale || undefined, {
    style: settings.show_currency_symbol ? "currency" : "decimal",
    currency: settings.currency_code, currencyDisplay: "symbol",
    minimumFractionDigits: places, maximumFractionDigits: places,
  });
}
const settings = computed(() => programSettings.value || {
  number_locale: "", currency_code: "INR", show_currency_symbol: false,
});
const formatters = new Map<string, Intl.NumberFormat>();
export const moneyFormatKey = computed(() => {
  const settings = programSettings.value;
  return [settings?.number_locale, settings?.currency_code, settings?.show_currency_symbol].join("|");
});
export function formatMoney(value: unknown) {
  if (value === null || value === undefined || value === "") return "";
  const raw = String(value);
  if (!/^-?\d+(?:\.\d+)?$/.test(raw)) return raw;
  // Modern Intl accepts decimal strings without first losing precision to Number.
  const places = Math.min(20, raw.split(".")[1]?.length || 0);
  const key = moneyFormatKey.value + ":" + places;
  let formatter = formatters.get(key);
  if (!formatter) {
    if (formatters.size > 100) formatters.clear();
    formatter = moneyFormatter(settings.value, places);
    formatters.set(key, formatter);
  }
  return formatter.format(raw as unknown as number);
}
export function moneyCell(cell: CellComponent) { return formatMoney(cell.getValue()); }
