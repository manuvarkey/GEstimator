<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import Dialog from "primevue/dialog";
import AppIcon from "./AppIcon.vue";
import AnalysisRowEditor from "./AnalysisRowEditor.vue";
import AnalysisConditionGroup from "./AnalysisConditionGroup.vue";
import { request } from "../backend";
import { analysisFields as fields, conditionCount, type AnalysisRule as Rule } from "../analysisRules";
const visible = defineModel<boolean>({ required: true });
const props = defineProps<{ revision: number; ids: string[]; code: string; dirty: boolean; apply: (params: Record<string, unknown>) => Promise<boolean> }>();
interface Preview { selected: number; changed: number; unmatched: number; rule_matches: number[]; affected: number; truncated: boolean; items: { code: string; description: string; before: string; after: string; dependent: boolean }[]; changes: { code: string; rule: number; kind: string; row: string; action: string; field: string; before: string; after: string }[] }
const kinds = ["Any", "Group", "Resource", "Subtotal", "Weight", "Multiply", "Round"];
const actions = [{ value: "set", label: "Set field" }, { value: "multiply", label: "Multiply quantity / factor" }, { value: "add", label: "Add to quantity / factor" }, { value: "replace_text", label: "Replace literal text" }, { value: "delete", label: "Delete matched rows" }, { value: "insert_before", label: "Insert rows before match" }, { value: "insert_after", label: "Insert rows after match" }, { value: "replace", label: "Replace matched rows" }, { value: "append", label: "Append to each analysis" }, { value: "prepend", label: "Prepend to each analysis" }];
const scope = ref(props.ids.length || props.code ? "selected" : "all");
const rules = ref<Rule[]>([]);
const busy = ref(false);
const error = ref("");
const preview = ref<Preview>();
const prepared = ref<Record<string, unknown>>();
const previewElement = ref<HTMLElement>();
interface Preset { id: string; name: string; rules: Rule[] }
const presetKey = "gestimator.analysis-rules.v1";
const presets = ref<Preset[]>([]);
const presetId = ref("");
const presetName = ref("");
const presetStatus = ref("");
function readPresets(): Preset[] {
  const raw = localStorage.getItem(presetKey);
  if (!raw) return [];
  if (raw.length > 2_000_000) throw new Error("Saved presets are too large");
  const stored = JSON.parse(raw);
  if (stored?.version !== 1 || !Array.isArray(stored.presets) || stored.presets.length > 50 || stored.presets.some((preset: Preset) => !preset || typeof preset.id !== "string" || typeof preset.name !== "string" || !preset.name.trim() || preset.name.length > 120 || !Array.isArray(preset.rules))) throw new Error("Invalid saved preset format");
  return stored.presets;
}
onMounted(() => { try { presets.value = readPresets(); } catch { error.value = "Saved bulk-edit presets could not be read. The current rules remain available; no stored preferences were changed."; } });
async function loadPreset() {
  invalidate();
  if (!presetId.value) { presetName.value = ""; return; }
  busy.value = true; error.value = ""; presetStatus.value = "";
  try {
    const preset = readPresets().find(item => item.id === presetId.value);
    if (!preset) throw new Error("This preset no longer exists; reopen the dialog to refresh the list.");
    const validated = await request<Rule[]>("analysis.rules.validate", { rules: preset.rules });
    rules.value = validated;
    presetName.value = preset.name;
    await nextTick();
    presetStatus.value = "Preset loaded. Choose the scope and preview before applying.";
  } catch (failure) { error.value = String(failure); }
  finally { busy.value = false; }
}
async function savePreset() {
  if (!presetName.value.trim() || busy.value) return;
  busy.value = true; error.value = ""; presetStatus.value = "";
  try {
    const validated = await request<Rule[]>("analysis.rules.validate", { rules: rules.value });
    const current = readPresets();
    const name = presetName.value.trim();
    const existing = current.find(item => item.id === presetId.value && item.name === name);
    if (!existing && current.length >= 50) throw new Error("Keep at most 50 saved rule presets.");
    const preset = { id: existing?.id || crypto.randomUUID(), name, rules: validated };
    const next = existing ? current.map(item => item.id === existing.id ? preset : item) : [...current, preset];
    const encoded = JSON.stringify({ version: 1, presets: next });
    if (encoded.length > 2_000_000) throw new Error("Saved presets are too large; remove unused presets or shorten template text.");
    localStorage.setItem(presetKey, encoded);
    presets.value = next; presetId.value = preset.id;
    presetStatus.value = "Rule preset saved. No project data changed.";
  } catch (failure) { error.value = "Preset could not be saved: " + String(failure); }
  finally { busy.value = false; }
}
function deletePreset() {
  error.value = ""; presetStatus.value = "";
  try {
    const next = readPresets().filter(item => item.id !== presetId.value);
    localStorage.setItem(presetKey, JSON.stringify({ version: 1, presets: next }));
    presets.value = next; presetId.value = ""; presetName.value = "";
    presetStatus.value = "Preset deleted. The current rules remain in the editor.";
  } catch { error.value = "The preset could not be deleted; stored preferences were not changed."; }
}
function addRule() { rules.value.push({ match: { kind: "Weight", mode: "all", occurrence: "all", case_sensitive: false, conditions: [{ field: "description", operator: "contains", value: "" }] }, action: "set", field: "value", value: "", find: "", rows: [] }); }
addRule();
function move(index: number, delta: number) { const next = index + delta; if (next >= 0 && next < rules.value.length) [rules.value[index], rules.value[next]] = [rules.value[next]!, rules.value[index]!]; }
function inserting(rule: Rule) { return ["insert_before", "insert_after", "replace", "append", "prepend"].includes(rule.action); }
function whole(rule: Rule) { return ["append", "prepend"].includes(rule.action); }
function actionLabel(action: string) { return actions.find(item => item.value === action)?.label || action; }
function fieldLabel(field: string) { return fields.find(item => item.value === field)?.label || ""; }
function changeFields(rule: Rule) { return fields.filter(field => rule.match.kind === "Resource" ? field.value !== "description" : field.value !== "remarks" && (field.value !== "code" || rule.match.kind === "Group") && (field.value !== "value" || ["Weight", "Multiply", "Round", "Any"].includes(rule.match.kind))); }
function actionChanged(rule: Rule) { if (["multiply", "add"].includes(rule.action)) rule.field = "value"; }
function kindChanged(rule: Rule) { if (!changeFields(rule).some(field => field.value === rule.field)) rule.field = changeFields(rule)[0]!.value; }
function invalidate() { preview.value = undefined; prepared.value = undefined; error.value = ""; presetStatus.value = ""; }
watch([rules, scope], invalidate, { deep: true });
watch(() => props.revision, invalidate);
const selectionLabel = computed(() => props.ids.length ? `${props.ids.length} selected schedule rows/categories, including children` : props.code ? `Current schedule item ${props.code}, including children` : "No schedule selection");
async function calculate() {
  busy.value = true; error.value = ""; preview.value = undefined; prepared.value = undefined;
  try {
    const params = JSON.parse(JSON.stringify({ revision: props.revision, scope: scope.value, ids: props.ids, code: props.code, rules: rules.value }));
    preview.value = await request<Preview>("schedule.editor.analysis_rules.preview", params);
    prepared.value = params;
    await nextTick();
    previewElement.value?.scrollIntoView({ block: "nearest" });
  } catch (failure) { error.value = String(failure); }
  finally { busy.value = false; }
}
async function apply() {
  if (!prepared.value || busy.value) return;
  busy.value = true;
  try { if (await props.apply(prepared.value)) visible.value = false; else { invalidate(); error.value = "The batch could not be applied. Refresh the project and preview again."; } }
  finally { busy.value = false; }
}
</script>
<template>
  <Dialog v-model:visible="visible" modal header="Bulk edit analysis" class="workspace-dialog analysis-rules-dialog" :closable="!busy" :close-on-escape="!busy">
    <p class="field-hint">Rules run in order across the chosen schedule items. Each rule matches the result of previous rules. Preview leaves the project unchanged; Apply creates one project undo step.</p>
    <p v-if="dirty" class="dialog-error" role="alert">Apply or discard the open analysis draft before editing project analyses.</p>
    <div class="analysis-rule-presets"><label class="field">Saved rule preset<select v-model="presetId" aria-label="Saved rule preset" :disabled="busy" @change="loadPreset"><option value="">Current unsaved rules</option><option v-for="preset in presets" :key="preset.id" :value="preset.id">{{ preset.name }}</option></select></label><button class="icon-button danger" aria-label="Delete saved rule preset" title="Delete this saved preset while retaining its rules in the editor." :disabled="busy || !presetId" @click="deletePreset"><AppIcon name="trash" /></button><label class="field">Preset name<input v-model="presetName" aria-label="Preset name" :disabled="busy" maxlength="120" placeholder="Name for reuse in other projects" /></label><button class="button small secondary" :disabled="busy || !presetName.trim()" title="Save matching conditions and actions only. The scope and schedule item selection are chosen each time. Change the name to save a new preset." @click="savePreset">Save preset</button></div>
    <p v-if="presetStatus" role="status">{{ presetStatus }}</p>
    <label class="field">Schedule scope<select v-model="scope" aria-label="Schedule scope" :disabled="busy"><option value="selected" :disabled="!ids.length && !code">{{ selectionLabel }}</option><option value="all">Whole schedule</option></select></label>
    <div class="analysis-rules">
      <fieldset v-for="(rule, index) in rules" :key="index" class="analysis-rule" :disabled="busy">
        <legend>Rule {{ index + 1 }}</legend>
        <div class="project-tools rule-order"><button class="icon-button" :aria-label="`Move rule ${index + 1} up`" :disabled="index === 0" @click="move(index, -1)"><AppIcon name="up" /></button><button class="icon-button" :aria-label="`Move rule ${index + 1} down`" :disabled="index === rules.length - 1" @click="move(index, 1)"><AppIcon name="down" /></button><button class="icon-button" :aria-label="`Remove rule ${index + 1}`" :disabled="rules.length === 1" @click="rules.splice(index, 1)"><AppIcon name="trash" /></button></div>
        <div class="field-pair"><label class="field">Action<select v-model="rule.action" :aria-label="`Rule ${index + 1} action`" @change="actionChanged(rule)"><option v-for="action in actions" :key="action.value" :value="action.value">{{ action.label }}</option></select></label><label v-if="!whole(rule)" class="field">Row type<select v-model="rule.match.kind" :aria-label="`Rule ${index + 1} row type`" @change="kindChanged(rule)"><option v-for="kind in kinds" :key="kind">{{ kind }}</option></select></label></div>
        <template v-if="!whole(rule)">
          <div class="field-pair"><label class="field">Occurrence<select v-model="rule.match.occurrence" :aria-label="`Rule ${index + 1} occurrence`"><option value="all">Every match per analysis</option><option value="first">First match per analysis</option><option value="last">Last match per analysis</option></select></label><label class="library-remember"><input v-model="rule.match.case_sensitive" type="checkbox" />Case sensitive</label></div>
          <AnalysisConditionGroup :group="rule.match" :label="`Rule ${index + 1}`" :remaining="32 - conditionCount(rule.match)" @change="Object.assign(rule.match, $event)" />
        </template>
        <template v-if="['set', 'multiply', 'add', 'replace_text'].includes(rule.action)">
          <div class="field-pair"><label class="field">Field to change<select v-model="rule.field" :aria-label="`Rule ${index + 1} field to change`" :disabled="['multiply', 'add'].includes(rule.action)"><option v-for="field in changeFields(rule)" :key="field.value" :value="field.value">{{ field.label }}</option></select></label><label v-if="rule.action === 'replace_text'" class="field">Find literal text<input v-model="rule.find" :aria-label="`Rule ${index + 1} find text`" /></label><label class="field">{{ rule.action === 'multiply' ? 'Multiplier' : rule.action === 'add' ? 'Offset' : 'New value' }}<input v-model="rule.value" :aria-label="`Rule ${index + 1} new value`" /></label></div>
        </template>
        <AnalysisRowEditor v-if="inserting(rule)" v-model="rule.rows" :prefix="`Rule ${index + 1} row`" :disabled="busy" />
        <p v-if="rule.match.kind === 'Resource' && !whole(rule)" class="field-hint">Resource matches edit entry quantity, remarks or an existing project resource code. Shared resource definitions remain controlled by the Resources editor. Deleting a group also deletes its entries.</p>
      </fieldset>
    </div>
    <button class="button small secondary" :disabled="busy || rules.length >= 50" @click="addRule"><AppIcon name="plus" :size="16" />Add rule</button>
    <p v-if="error" class="dialog-error" role="alert">{{ error }}</p>
    <div v-if="preview" ref="previewElement" class="batch-preview">
      <p role="status">{{ preview.changed }} of {{ preview.selected }} scoped analyses change · {{ preview.affected }} items affected · {{ preview.unmatched }} unmatched analyses</p>
      <p class="field-hint">{{ preview.rule_matches.map((count, i) => `Rule ${i + 1}: ${count} matches`).join(' · ') }}{{ preview.truncated ? ' · Preview details are limited; counts cover the full scope.' : '' }}</p>
      <div class="import-sample"><table><thead><tr><th>Schedule item</th><th>Rate before</th><th>Rate after</th><th>Effect</th></tr></thead><tbody><tr v-for="item in preview.items" :key="item.code"><td>{{ item.code }} · {{ item.description }}</td><td>{{ item.before }}</td><td>{{ item.after }}</td><td>{{ item.dependent ? 'Dependent rate' : 'Analysis edited' }}</td></tr></tbody></table></div>
      <div class="import-sample"><table><thead><tr><th>Item / rule</th><th>Matched row</th><th>Action / field</th><th>Before</th><th>After</th></tr></thead><tbody><tr v-for="(change, i) in preview.changes" :key="i"><td>{{ change.code }} / {{ change.rule }}</td><td>{{ change.kind }} · {{ change.row }}</td><td>{{ actionLabel(change.action) }} {{ fieldLabel(change.field) }}</td><td>{{ change.before }}</td><td>{{ change.after }}</td></tr></tbody></table></div>
    </div>
    <template #footer><div class="dialog-footer"><button class="button secondary" :disabled="busy" @click="visible = false">Cancel</button><button class="button secondary" :disabled="busy || dirty" @click="calculate">Preview changes</button><button class="button primary" :disabled="busy || dirty || !prepared || !preview?.changed" @click="apply">Apply rules</button></div></template>
  </Dialog>
</template>
