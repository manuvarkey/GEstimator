<script setup lang="ts">
/** Reorder stable section instances by handle, or Alt+Arrow on a focused handle. */
import { computed, ref } from "vue";
import AppIcon from "./AppIcon.vue";
import ReportSectionLayout from "./ReportSectionLayout.vue";
import SignoffEditor from "./SignoffEditor.vue";
import ReportNotesEditor from "./ReportNotesEditor.vue";
import type { ReportSection, ReportSectionKind, SignoffBlock } from "../reportTypes";
const sections = defineModel<ReportSection[]>({ required: true });
const props = defineProps<{ locked: boolean; defaultSections: ReportSection[]; signoffDefaults: SignoffBlock[] }>();
const dragging = ref<string>();
const nextKind = ref<ReportSectionKind>("narrative");
const titles: Record<ReportSectionKind, string> = {
  narrative: "Notes",
  abstract: "Abstract of estimate",
  schedule: "Schedule",
  signoff: "Signoff",
  analyses: "Analyses of rates",
  resources: "Resources",
  resource_usage: "Resource usage",
  measurement_abstract: "Measurement abstract",
  measurements: "Measurements",
};
const defaultByKind = computed(() => new Map(props.defaultSections.map((section) => [section.kind, section])));
function label(kind: string) {
  return kind.replaceAll("_", " ");
}
function move(index: number, target: number) {
  if (props.locked || target < 0 || target >= sections.value.length) return;
  const next = [...sections.value];
  const [section] = next.splice(index, 1);
  next.splice(target, 0, section!);
  sections.value = next;
}
function drop(target: number) {
  const source = sections.value.findIndex((section) => section.id === dragging.value);
  if (source >= 0) move(source, target);
  dragging.value = undefined;
}
function structuredSignoff() {
  const blocks = defaultByKind.value.get("signoff")?.signoff_blocks ?? props.signoffDefaults;
  return blocks.length ? blocks.map((block) => ({ ...block })) : [{ caption: "Signature", body: "" }];
}
function add() {
  if (props.locked || sections.value.length >= 20) return;
  const kind = nextKind.value;
  const defaults = defaultByKind.value.get(kind);
  sections.value = [
    ...sections.value,
    {
      id: `${kind}-${crypto.randomUUID()}`,
      kind,
      title: defaults?.title ?? titles[kind],
      enabled: true,
      new_page: kind !== "signoff",
      each_item_page: false,
      show_name_of_work: false,
      ...(kind === "narrative" ? { body: "" } : {}),
      ...(kind === "signoff"
        ? { signoff_blocks: structuredSignoff(), signoff_intro: defaults?.signoff_intro ?? "" }
        : {}),
    },
  ];
}
</script>
<template>
  <div class="report-composition">
    <h2>Report sections</h2>
    <p class="field-hint">
      Toggle a numbered badge to include a section. Drag its handle to reorder, or focus the handle and press Alt+↑/↓.
    </p>
    <ol class="report-sections" aria-label="Report sections">
      <li v-for="(section, index) in sections" :key="section.id" @dragover.prevent @drop.prevent="drop(index)">
        <details class="section-settings" name="report-settings">
          <summary>
            <button
              type="button"
              class="section-badge"
              :class="{ included: section.enabled }"
              :aria-label="`Include ${label(section.kind)}`"
              :aria-pressed="section.enabled"
              :disabled="locked"
              @click.stop.prevent="section.enabled = !section.enabled"
            >
              {{ index + 1 }}
            </button>
            <button
              type="button"
              class="icon-button drag-handle"
              :draggable="!locked"
              :disabled="locked"
              :aria-label="`Reorder ${label(section.kind)}`"
              title="Drag to reorder; Alt+Up/Down to move"
              @dragstart="
                dragging = section.id;
                $event.dataTransfer?.setData('text/plain', section.id);
              "
              @dragend="dragging = undefined"
              @click.stop.prevent
              @keydown.alt.up.prevent="move(index, index - 1)"
              @keydown.alt.down.prevent="move(index, index + 1)"
            >
              <AppIcon name="grip" />
            </button>
            <span
              >{{ section.title || label(section.kind)
              }}<small
                >{{ section.enabled ? "Included" : "Excluded" }} · {{ section.orientation || "auto" }} pages</small
              ></span
            ><AppIcon class="chevron" name="chevron" />
          </summary>
          <div class="section-body">
            <label
              >Section title<input
                v-model="section.title"
                :aria-label="`${label(section.kind)} title`"
                maxlength="10000"
            /></label>
            <ReportNotesEditor v-if="section.kind === 'narrative'" v-model="section.body" />
            <SignoffEditor
              v-if="section.kind === 'signoff' && section.signoff_blocks"
              v-model="section.signoff_blocks"
              :label="`${section.title} signature`"
            />
            <label v-if="section.kind === 'signoff'"
              ><input v-model="section.new_page" type="checkbox" />Start signoff on a separate page</label
            >
            <label v-if="section.kind === 'analyses' || section.kind === 'measurements'"
              ><input
                v-model="section.each_item_page"
                type="checkbox"
                :aria-label="`${label(section.kind)} separate item pages`"
              />Print each item on a separate page</label
            >
            <label v-if="section.kind === 'abstract' || section.kind === 'schedule'"
              ><input
                v-model="section.show_name_of_work"
                type="checkbox"
                :aria-label="`${label(section.kind)} show name of work`"
              />Show name of work</label
            >
            <label v-if="section.kind === 'signoff'"
              >Text before signature blocks (Jinja2)
              <textarea v-model="section.signoff_intro" rows="3" maxlength="10000" data-multiline />
            </label>
            <template v-if="section.kind === 'measurement_abstract'">
              <label
                >Maximum description lines (0 for all)
                <input
                  type="number"
                  min="0"
                  max="50"
                  step="1"
                  :value="section.description_lines || 0"
                  @input="section.description_lines = Number(($event.target as HTMLInputElement).value)"
                />
              </label>
              <label
                >Maximum description words (0 for all)
                <input
                  type="number"
                  min="0"
                  max="500"
                  step="1"
                  :value="section.description_words || 0"
                  @input="section.description_words = Number(($event.target as HTMLInputElement).value)"
                />
              </label>
            </template>
            <ReportSectionLayout
              :kind="section.kind"
              :inline="section.kind === 'signoff' && !section.new_page"
              v-model:columns="section.columns"
              v-model:orientation="section.orientation"
            />
            <button
              type="button"
              :disabled="locked"
              @click="sections = sections.filter((value) => value.id !== section.id)"
            >
              Remove section
            </button>
          </div>
        </details>
      </li>
    </ol>
    <div class="add-section">
      <label
        >Add page or section<select v-model="nextKind">
          <option v-for="(title, kind) in titles" :key="kind" :value="kind">
            {{ defaultByKind.get(kind)?.title || title }}
          </option>
        </select></label
      ><button type="button" :disabled="locked || sections.length >= 20" @click="add">Add section</button>
    </div>
  </div>
</template>
<style scoped>
h2 {
  font-size: var(--text-size-heading);
}
.report-sections {
  list-style: none;
  padding: 0;
  margin: 0;
}
li {
  position: relative;
}
.section-settings {
  border: 1px solid transparent;
  border-block-end-color: var(--line);
  padding-inline: 6px;
}
.section-settings[open] {
  border-color: var(--line);
  border-radius: 6px;
  background: var(--bg);
}
.section-badge {
  min-width: 28px;
  flex-shrink: 0;
  height: 28px;
  padding: 0;
  color: var(--muted);
  border: 1px solid var(--line);
  border-radius: 6px;
}
.section-badge.included {
  color: var(--text);
  border-color: var(--accent);
  background: var(--panel);
}
.drag-handle {
  cursor: grab;
}
.drag-handle:active {
  cursor: grabbing;
}
summary {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 8px 0;
}
summary small {
  display: block;
  color: var(--muted);
  font-weight: normal;
  margin-block-start: 3px;
}
.chevron {
  margin-inline-start: auto;
  flex-shrink: 0;
}
details[open] > summary .chevron {
  transform: rotate(90deg);
}
.section-body > label {
  display: grid;
  gap: 4px;
  margin-block: 12px;
}
.section-body > label:has(input[type="checkbox"]) {
  display: flex;
  align-items: start;
  gap: 6px;
}
.add-section label {
  display: grid;
  gap: 4px;
  margin-block: 8px;
}
.field-hint {
  color: var(--muted);
  font-size: var(--text-size-small);
}
</style>
