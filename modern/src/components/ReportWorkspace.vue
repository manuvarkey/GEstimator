<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { save } from "@tauri-apps/plugin-dialog";
import AppIcon from "./AppIcon.vue";
import ReportLogoEditor from "./ReportLogoEditor.vue";
import ReportAppearance from "./ReportAppearance.vue";
import ReportSections from "./ReportSections.vue";
import { initializeProgramSettings, programSettings } from "../programSettings";
import { currentBackendSession, request } from "../backend";
import { activeDocument } from "../documents";
import { recallTabState, rememberTabState } from "../tabMemory";
import { formatMoney } from "../numberFormatting";
import { renderReportExport, reportExporting, reportExportMessage, reportNumberFormat } from "../reportExport";
import { notify } from "../statusNotice";
import type { ReportFormat, ReportPreview, ReportSettings, ReportSpecification } from "../reportTypes";

const props = defineProps<{ revision: number; externalBusy: boolean }>();
const emit = defineEmits<{ busy: [value: boolean]; changed: [] }>();
const documentId = activeDocument.value;
type ReportMemory = {
  specification: ReportSpecification;
  preview?: ReportPreview;
  previewSpec: string;
  format: ReportFormat;
  defaults?: ReportSpecification;
};
const memory = recallTabState<ReportMemory>("report");
const defaultSpecification = (): ReportSpecification => ({
  schema_version: 1,
  title: "Detailed estimate",
  organization: "",
  reference: "",
  issue_date: "",
  office: "",
  logo: "",
  font_family: "",
  font_scale: 1,
  sections: [],
});
const specification = ref<ReportSpecification>(memory?.specification ?? defaultSpecification());
const preview = ref<ReportPreview | undefined>(memory?.preview);
const previewSpec = ref(memory?.previewSpec ?? "");
const format = ref<ReportFormat>(memory?.format ?? "html");
const busy = ref(false);
const error = ref("");
const defaults = ref<ReportSpecification | undefined>(memory?.defaults);
const locked = computed(() => busy.value || props.externalBusy);
const stale = computed(
  () =>
    !!preview.value &&
    (preview.value.document.revision !== props.revision || previewSpec.value !== JSON.stringify(specification.value)),
);
const canExport = computed(
  () =>
    !!preview.value &&
    !stale.value &&
    !locked.value &&
    !reportExporting.value &&
    (format.value !== "pdf" || preview.value.pdf_available),
);
let generation = 0;

async function loadSettings() {
  const token = ++generation;
  busy.value = true;
  emit("busy", true);
  error.value = "";
  try {
    await initializeProgramSettings();
    const result = await request<ReportSettings>("report.settings", {
      revision: props.revision,
      estimate_defaults: programSettings.value?.estimate_defaults,
    });
    if (token !== generation) return;
    defaults.value = result.defaults;
    specification.value = result.specification ?? structuredClone(result.defaults);
    error.value = result.warning;
  } catch (reason) {
    if (token === generation) error.value = String(reason);
  } finally {
    if (token === generation) {
      busy.value = false;
      emit("busy", false);
    }
  }
}

async function applySettings() {
  if (locked.value) return;
  busy.value = true;
  emit("busy", true);
  error.value = "";
  try {
    await request<ReportSettings>("report.settings.apply", {
      revision: props.revision,
      specification: JSON.parse(JSON.stringify(specification.value)),
    });
    emit("changed");
    notify("Report settings applied. Save project to keep them.");
  } catch (reason) {
    error.value = String(reason);
  } finally {
    busy.value = false;
    emit("busy", false);
  }
}

onMounted(() => {
  if (!memory) void loadSettings();
});

async function generate() {
  if (locked.value) return;
  const token = ++generation;
  const snapshot = JSON.stringify(specification.value);
  busy.value = true;
  emit("busy", true);
  error.value = "";
  try {
    const result = await request<ReportPreview>("report.preview", {
      revision: props.revision,
      specification: JSON.parse(snapshot),
      number_format: reportNumberFormat(programSettings.value?.number_locale ?? ""),
    });
    if (token !== generation) return;
    preview.value = result;
    previewSpec.value = snapshot;
  } catch (reason) {
    if (token === generation) error.value = String(reason);
  } finally {
    if (token === generation) {
      busy.value = false;
      emit("busy", false);
    }
  }
}

async function exportReport() {
  if (!canExport.value || !preview.value) return;
  reportExporting.value = true;
  reportExportMessage.value = "";
  const session = currentBackendSession();
  try {
    const numberFormat = reportNumberFormat(programSettings.value?.number_locale ?? "");
    // Keep the preview's exact definition/revision across the native chooser.
    const captured = preview.value.document;
    const selectedFormat = format.value;
    const labels = { html: "HTML document", xlsx: "Excel workbook", pdf: "PDF document" };
    const path = await save({
      defaultPath: `estimate-report.${selectedFormat}`,
      filters: [{ name: labels[selectedFormat], extensions: [selectedFormat] }],
    });
    if (typeof path !== "string") return;
    await renderReportExport(
      {
        revision: captured.revision,
        specification: captured.specification,
        format: selectedFormat,
        path,
        replace_selected: true,
        number_format: numberFormat,
      },
      session,
    );
  } catch (reason) {
    reportExportMessage.value = String(reason);
    notify("Report export failed: " + String(reason));
  } finally {
    reportExporting.value = false;
  }
}

onBeforeUnmount(() => {
  generation++;
  emit("busy", false);
  rememberTabState(documentId, "report", {
    specification: specification.value,
    preview: preview.value,
    previewSpec: previewSpec.value,
    format: format.value,
    defaults: defaults.value,
  } satisfies ReportMemory);
});
defineExpose({ exportWorkbook: exportReport, canExport });
</script>

<template>
  <section class="report-workspace" aria-label="Report workspace" :aria-busy="busy">
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="stale" class="report-status" role="status">
      Preview is out of date. Generate a new preview before exporting.
    </p>
    <p v-if="preview && !preview.pdf_available" class="report-status">
      PDF export requires an installed WeasyPrint 70 or newer renderer. HTML and Excel are available.
    </p>
    <div class="report-body">
      <aside class="report-settings" aria-label="Report settings">
        <div class="panel-heading">Report settings</div>
        <div class="report-scroll">
          <fieldset class="report-composition-fields" :disabled="locked" aria-label="Report composition">
            <details class="settings-group" name="report-settings" open>
              <summary>
                <span
                  >Report details<small>{{ specification.title || "Title, organization and reference" }}</small></span
                >
                <AppIcon class="settings-chevron" name="chevron" />
              </summary>
              <div class="settings-group-body">
                <label>Report title<input v-model="specification.title" maxlength="10000" /></label>
                <label>Organization<input v-model="specification.organization" maxlength="10000" /></label>
                <label>Reference<input v-model="specification.reference" maxlength="10000" /></label>
                <label
                  >Issue date<input
                    v-model="specification.issue_date"
                    maxlength="10000"
                    placeholder="e.g. 26 November 2026"
                /></label>
                <label
                  >Office<textarea v-model="specification.office" rows="3" maxlength="10000" data-multiline />
                </label>
                <ReportLogoEditor v-model="specification.logo" />
              </div>
            </details>
            <details class="settings-group" name="report-settings">
              <summary>
                <span
                  >Page and typography<small
                    >20 mm margins · {{ Math.round((specification.font_scale ?? 1) * 100) }}% font scale</small
                  ></span
                >
                <AppIcon class="settings-chevron" name="chevron" />
              </summary>
              <div class="settings-group-body"><ReportAppearance v-model="specification" /></div>
            </details>
            <ReportSections
              v-model="specification.sections"
              :locked="locked"
              :default-sections="defaults?.sections ?? []"
              :signoff-defaults="
                specification.sections.find((section) => section.kind === 'signoff')?.signoff_blocks ??
                programSettings?.estimate_defaults.signoff_blocks ??
                []
              "
            />
            <div class="report-settings-actions">
              <button :disabled="locked" @click="applySettings">Apply report settings</button>
              <button :disabled="locked" @click="loadSettings">Reload report settings</button>
            </div>
            <p class="report-hint">
              Apply report settings to the working project, then Save project to keep them in the file. Unapplied
              changes stay with this open tab.
            </p>
          </fieldset>
        </div>
        <div class="report-controls">
          <button :disabled="locked" @click="generate"><AppIcon name="refresh" />Generate preview</button>
          <label
            >Output format
            <select v-model="format" :disabled="locked">
              <option value="html">HTML</option>
              <option value="xlsx">Excel</option>
              <option value="pdf" :disabled="!preview?.pdf_available">PDF</option>
            </select>
          </label>
          <button :disabled="!canExport" @click="exportReport"><AppIcon name="file" />Export report…</button>
          <div v-if="reportExporting" class="export-progress" role="status">
            <progress aria-label="Exporting report" />Exporting report…
          </div>
          <p v-if="reportExportMessage" class="error" role="alert">{{ reportExportMessage }}</p>
        </div>
      </aside>
      <div class="report-preview">
        <template v-if="preview">
          <div class="report-summary">
            Estimate total: <strong>{{ formatMoney(preview.document.total) }}</strong
            ><span>Continuous preview · PDF provides final pagination</span>
          </div>
          <iframe title="Report preview" :srcdoc="preview.html" sandbox="" />
        </template>
        <p v-else class="report-empty">Choose sections and generate a preview to prepare your report.</p>
      </div>
    </div>
  </section>
</template>

<style scoped>
.report-workspace {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  padding: 12px;
  gap: 10px;
}
.report-controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-block-start: 1px solid var(--line);
}
.report-controls > button:first-child,
.export-progress,
.report-controls > p {
  flex-basis: 100%;
}
.report-controls label,
.export-progress {
  display: flex;
  align-items: center;
  gap: 8px;
}
.export-progress progress {
  inline-size: 54px;
}
.report-status {
  margin: 0;
  color: var(--muted);
}
.report-body {
  display: grid;
  grid-template-columns: minmax(280px, 340px) minmax(0, 1fr);
  gap: 16px;
  min-height: 0;
  flex: 1;
}
.report-settings {
  min-width: 0;
  min-height: 0;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  overflow: hidden;
  background: var(--panel);
  border: 1px solid var(--line);
}
.report-scroll {
  overflow: auto;
  min-width: 0;
  min-height: 0;
}
.report-composition-fields {
  margin: 0;
  padding: 0 12px 12px;
  min-width: 0;
  border: 0;
}
.settings-group-body > label {
  display: grid;
  gap: 4px;
  margin-bottom: 12px;
}
.settings-group {
  border: 1px solid transparent;
  border-block-end-color: var(--line);
  padding-inline: 6px;
}
.settings-group[open] {
  border-color: var(--line);
  border-radius: 6px;
  background: var(--bg);
}
.settings-group summary {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-block: 10px;
  cursor: pointer;
}
summary .settings-chevron {
  margin-inline-start: auto;
  flex-shrink: 0;
  color: var(--muted);
}
details[open] > summary .settings-chevron {
  transform: rotate(90deg);
}
summary:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
summary small {
  display: block;
  font-weight: normal;
  color: var(--muted);
  margin-block-start: 3px;
}
.settings-group-body {
  padding-block: 6px;
}

.report-settings-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-block: 12px;
}
.report-hint {
  font-size: var(--text-size-small);
  color: var(--muted);
}
.report-preview {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  border: 1px solid var(--line);
  background: var(--panel);
}
.report-preview iframe {
  border: 0;
  flex: 1;
  min-height: 300px;
  width: 100%;
  background: white;
}
.report-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px;
  border-bottom: 1px solid var(--line);
}
.report-summary span {
  flex-basis: 100%;
  color: var(--muted);
  font-size: var(--text-size-small);
}
.report-empty {
  padding: 24px;
  color: var(--muted);
}
@media (max-width: 800px) {
  .report-body {
    display: flex;
    flex-direction: column;
    overflow: auto;
  }
  .report-settings {
    block-size: min(65vh, 520px);
    flex-shrink: 0;
  }
  .report-preview {
    min-height: 500px;
    flex-shrink: 0;
  }
}
</style>
