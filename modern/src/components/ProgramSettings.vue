<script setup lang="ts">
import { computed, ref, onMounted, watch } from "vue";
import { moneyFormatter } from "../numberFormatting";
import Dialog from "primevue/dialog";
import AnalysisRowEditor from "./AnalysisRowEditor.vue";
import {
  programSettings,
  programSettingsWarning,
  initializeProgramSettings,
  saveProgramSettings,
  shippedProgramSettings,
  type ProgramSettings,
} from "../programSettings";
import { applyMCPEnabled } from "../mcp";
import { appearance, defaultAppearance } from "../appearance";
import { request } from "../backend";
const visible = defineModel<boolean>({ required: true });
const draft = ref<ProgramSettings>();
const appearanceDraft = ref({ ...appearance.value });
const tab = ref("general");
const busy = ref(false);
const error = ref("");
const moneyPreview = computed(() => {
  try {
    return draft.value ? moneyFormatter(draft.value).format(1234567.89) : "";
  } catch {
    return "Choose a valid locale and currency.";
  }
});
const fontFamilies = ref<string[]>();
const fontsLoading = ref(false);
const localeOptions = [
  { value: "en-IN", label: "English (India)" },
  { value: "en-US", label: "English (United States)" },
  { value: "en-GB", label: "English (United Kingdom)" },
  { value: "de-DE", label: "German (Germany)" },
  { value: "fr-FR", label: "French (France)" },
  { value: "es-ES", label: "Spanish (Spain)" },
];
const savedLocale = computed(() =>
  draft.value?.number_locale && !localeOptions.some((option) => option.value === draft.value!.number_locale)
    ? draft.value.number_locale
    : "",
);
function fontOptions(selected: string) {
  const available = fontFamilies.value || [];
  return selected && !available.includes(selected) ? [selected, ...available] : available;
}
const sections = [
  { key: "general", label: "General" },
  { key: "appearance", label: "Appearance" },
  { key: "default", label: "Default analysis template" },
  { key: "modify", label: "Library Modify & Add" },
];
const fontGroups = [
  { label: "Interface", family: "uiFamily", size: "uiSize", placeholder: "Desktop default" },
  { label: "Tables", family: "tableFamily", size: "tableSize", placeholder: "Desktop default" },
] as const;
function navigate(event: KeyboardEvent, index: number) {
  const last = sections.length - 1;
  const next =
    event.key === "ArrowRight"
      ? (index + 1) % sections.length
      : event.key === "ArrowLeft"
        ? (index + last) % sections.length
        : event.key === "Home"
          ? 0
          : event.key === "End"
            ? last
            : -1;
  if (next < 0) return;
  event.preventDefault();
  document.getElementById("settings-tab-" + sections[next]!.key)?.focus();
}
onMounted(async () => {
  try {
    await initializeProgramSettings();
    draft.value = programSettings.value
      ? JSON.parse(JSON.stringify(programSettings.value))
      : await shippedProgramSettings();
  } catch (failure) {
    error.value = String(failure);
  }
});
watch(tab, async (section) => {
  if (section !== "appearance" || fontFamilies.value || fontsLoading.value) return;
  fontsLoading.value = true;
  try {
    fontFamilies.value = await request<string[]>("program.fonts");
  } catch {
    fontFamilies.value = [];
  } finally {
    fontsLoading.value = false;
  }
});
async function save() {
  if (!draft.value || busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    moneyFormatter(draft.value);
    await saveProgramSettings(draft.value, appearanceDraft.value);
    await applyMCPEnabled(draft.value.mcp_enabled);
    visible.value = false;
  } catch (failure) {
    error.value = String(failure);
  } finally {
    busy.value = false;
  }
}
async function reset() {
  busy.value = true;
  error.value = "";
  try {
    draft.value = await shippedProgramSettings();
    appearanceDraft.value = { ...defaultAppearance };
  } catch (failure) {
    error.value = String(failure);
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <Dialog
    v-model:visible="visible"
    modal
    header="Program settings"
    class="workspace-dialog program-settings-dialog"
    :closable="!busy"
    :close-on-escape="!busy"
  >
    <p class="dialog-intro">
      Application preferences apply to future operations and are saved separately from projects. Cancel keeps the
      current settings.
    </p>
    <p v-if="programSettingsWarning" class="dialog-error" role="status">{{ programSettingsWarning }}</p>
    <div class="settings-tabs" role="tablist" aria-label="Program settings sections">
      <button
        v-for="(section, index) in sections"
        :id="'settings-tab-' + section.key"
        :key="section.key"
        role="tab"
        :tabindex="tab === section.key ? 0 : -1"
        :aria-selected="tab === section.key"
        :aria-controls="'settings-panel-' + section.key"
        :disabled="busy"
        @click="tab = section.key"
        @keydown="navigate($event, index)"
      >
        {{ section.label }}
      </button>
    </div>
    <section v-if="draft" :id="'settings-panel-' + tab" role="tabpanel" :aria-labelledby="'settings-tab-' + tab">
      <template v-if="tab === 'general'">
        <h3>Rates and amounts</h3>
        <label class="field"
          >Regional format<select v-model="draft.number_locale" aria-label="Regional format" :disabled="busy">
            <option value="">System default</option>
            <option v-if="savedLocale" :value="savedLocale">{{ savedLocale }} (saved format)</option>
            <option v-for="option in localeOptions" :key="option.value" :value="option.value">
              {{ option.label }} · {{ option.value }}
            </option>
          </select></label
        >
        <label class="field"
          >Currency code<input
            v-model="draft.currency_code"
            maxlength="3"
            aria-describedby="currency-code-help"
            :disabled="busy"
            @input="draft.currency_code = draft.currency_code.toUpperCase()"
        /></label>
        <p id="currency-code-help" class="field-hint">
          Three-letter currency code (for example INR, USD or EUR). Selects the symbol for displayed rates, amounts and
          monetary totals when enabled below. It does not convert prices or change calculations or workbook numeric
          values.
        </p>
        <label class="library-remember"
          ><input v-model="draft.show_currency_symbol" type="checkbox" :disabled="busy" />Show currency symbol</label
        >
        <p class="field-hint">
          Preview: <output aria-label="Regional amount preview">{{ moneyPreview }}</output
          >. Leave the region blank to follow your system. Numeric editing uses the original values and arithmetic
          expressions.
        </p>
        <h3>Search</h3>
        <label class="library-remember"
          ><input v-model="draft.live_search" type="checkbox" :disabled="busy" />Search as you type</label
        >
        <p class="field-hint">
          Schedule, Resources and the database picker update their results shortly after you stop typing. When off,
          press Enter or Search.
        </p>
        <h3>Cell editing</h3>
        <label class="library-remember"
          ><input v-model="draft.enter_edits_next_cell" type="checkbox" :disabled="busy" />Edit the cell below after
          pressing Enter</label
        >
        <h3>AI assistants (MCP)</h3>
        <label class="library-remember"
          ><input v-model="draft.mcp_enabled" type="checkbox" :disabled="busy" />Enable the MCP server for AI
          assistants</label
        >
        <p class="field-hint">
          Off by default. When on, the MCP tab lets you start a local server (127.0.0.1 only, with a connection token)
          that AI assistants on this computer can use to read and, if you allow it, edit the open project. Turning this
          off stops a running server.
        </p>
        <h3>Export options</h3>
        <label class="library-remember"
          ><input v-model="draft.export_break_items" type="checkbox" :disabled="busy" />Break item descriptions across
          multiple rows in exported workbooks</label
        >
      </template>
      <template v-else-if="tab === 'appearance'">
        <label class="field"
          >Theme<select v-model="appearanceDraft.theme" :disabled="busy">
            <option value="system">Follow system</option>
            <option value="light">Light</option>
            <option value="dark">Dark</option>
          </select></label
        >
        <div v-for="group in fontGroups" :key="group.family" class="field-pair">
          <label class="field"
            >{{ group.label }} font face<select
              v-model="appearanceDraft[group.family]"
              :aria-label="group.label + ' font face'"
              :disabled="busy || fontsLoading"
            >
              <option value="">Desktop default</option>
              <option v-for="font in fontOptions(appearanceDraft[group.family])" :key="font" :value="font">
                {{ font }}{{ fontFamilies && !fontFamilies.includes(font) ? " (saved font unavailable)" : "" }}
              </option>
            </select></label
          >
          <label class="field"
            >{{ group.label }} font size (px)<input
              type="number"
              min="10"
              max="30"
              step="any"
              :value="appearanceDraft[group.size] ?? ''"
              :placeholder="group.placeholder"
              :disabled="busy"
              @input="
                appearanceDraft[group.size] =
                  ($event.target as HTMLInputElement).value === ''
                    ? null
                    : ($event.target as HTMLInputElement).valueAsNumber
              "
          /></label>
        </div>
        <p v-if="fontsLoading" role="status" class="field-hint">Loading installed fonts…</p>
        <p v-else-if="!fontFamilies?.length" class="field-hint">
          The system font list is unavailable. Desktop default and any saved font remain available.
        </p>
        <p v-else class="field-hint">Choose an installed font, or Desktop default to follow the system.</p>
      </template>
      <template v-else-if="tab === 'default'">
        <p class="field-hint">
          Used by Analysis → Default rows and when opening an analysis with no calculation rows. An empty template
          leaves blank analyses empty.
        </p>
        <AnalysisRowEditor v-model="draft.ana_default_rows" prefix="Default row" :disabled="busy" />
      </template>
      <template v-else>
        <div class="settings-import-options">
          <section>
            <h3>Stored schedule rate</h3>
            <label class="field"
              >Schedule rate multiplier<input v-model="draft.sch_rate_mult_factor" :disabled="busy"
            /></label>
            <p class="field-hint">Multiply the source rate. Use 1 to keep the source rate.</p>
          </section>
          <section>
            <h3>Replace trailing analysis rows</h3>
            <label class="field"
              >Trailing analysis rows to replace<input
                v-model.number="draft.ana_copy_delete_rows"
                type="number"
                min="0"
                max="5"
                step="1"
                :disabled="busy"
            /></label>
            <p v-if="!draft.ana_copy_delete_rows" class="field-hint">
              Use a count above 0 to configure replacement rows.
            </p>
            <template v-else>
              <p class="field-hint">
                Add replacement rows below. This applies to source analyses with more rows than the count.
              </p>
              <AnalysisRowEditor v-model="draft.ana_copy_rows" prefix="Modify row" :disabled="busy" />
            </template>
          </section>
        </div>
      </template>
    </section>
    <p v-if="error" role="alert" class="dialog-error">{{ error }}</p>
    <div class="dialog-footer">
      <button class="button secondary" :disabled="busy || !draft" @click="reset">Restore shipped defaults</button
      ><button class="button secondary" :disabled="busy" @click="visible = false">Cancel</button
      ><button class="button primary" :disabled="busy || !draft" @click="save">Save program settings</button>
    </div>
  </Dialog>
</template>
