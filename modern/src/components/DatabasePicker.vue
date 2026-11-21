<script setup lang="ts">
import { computed, nextTick, ref } from "vue";
import PersistentDialog from "./PersistentDialog.vue";
import DataTable from "./DataTable.vue";
import AnalysisRulesDialog from "./AnalysisRulesDialog.vue";
import AppIcon from "./AppIcon.vue";
import CategoryFilter from "./CategoryFilter.vue";
import DatabaseNotes from "./DatabaseNotes.vue";
import type { ColumnDefinition } from "tabulator-tables";
import { request } from "../backend";
import { useLiveSearch } from "../liveSearch";
import { overflowTooltip } from "../cellTooltip";
const visible = defineModel<boolean>({ required: true });
const props = defineProps<{
  analysis?: boolean;
  kind: "schedule" | "resources";
  mode: "add" | "rates";
  revision: number;
  targetIds: string[];
  apply: (params: Record<string, unknown>) => Promise<boolean>;
  parentError: string;
}>();
const emit = defineEmits<{ manage: [] }>();
const libraries = ref<{ id: string; name: string; notes?: boolean }[]>([]);
const current = computed(() => libraries.value.find(item => item.id === source.value));
const source = ref("");
const query = ref("");
const categories = ref<string[]>([]);
const categoryFilters = ref<string[]>([]);
const pickerTable = ref<InstanceType<typeof DataTable>>();
let loadRequest = 0;
let loaded = false;
const page = ref(0);
const rows = ref<{ id: string; [key: string]: any }[]>([]);
const total = ref(0);
const enrichment = ref<{ summary: string } | null>(null);
const selected = ref<{ id: string; [key: string]: any }[]>([]);
const busy = ref(false);
const error = ref("");
const rulesOpen = ref(false);
const pickerVisible = computed({
  get: () => visible.value && !rulesOpen.value,
  set: value => { visible.value = value; },
});
const selectedIds = computed(() => selected.value.map(row => row.id));
const preview = ref<{ changed: number; unchanged: number; unmatched: number }>();
const title = computed(() => props.analysis ? "Add analysis resources from database" : props.mode === "rates" ? "Refresh selected rates from database" : props.kind === "schedule" ? "Add item from database" : "Add resources from database");
const columns: ColumnDefinition[] = [
  { title: "CODE", field: "code", width: 126, minWidth: 78, widthShrink: 1, tooltip: overflowTooltip() },
  { title: "DESCRIPTION", field: "description", minWidth: 116, formatter: "textarea", variableHeight: true },
  { title: "UNIT", field: "unit", width: 64, minWidth: 45, widthShrink: 1, tooltip: overflowTooltip() },
  { title: "RATE", field: "rate", width: 104, minWidth: 72, widthShrink: 1, hozAlign: "right", tooltip: overflowTooltip() },
];
let searchedQuery = "";
const liveSearch = useLiveSearch(query, () => searchedQuery, () => search());
/** Load the first page of results for the current search and filters. */
async function search() {
  liveSearch.cancel();
  return goToPage(0);
}
async function goToPage(index: number) {
  page.value = index;
  await pickerTable.value?.scrollToTop();
  return load();
}
async function load() {
  const token = ++loadRequest;
  searchedQuery = query.value;
  preview.value = undefined;
  selected.value = [];
  if (!source.value || props.mode === "rates") return;
  busy.value = true; error.value = "";
  try {
    await pickerTable.value?.clearSelection();
    if (token !== loadRequest) return;
    const result = await request<{ rows: typeof rows.value; total: number; categories: string[]; enrichment: typeof enrichment.value }>(props.kind + ".editor.state", { source: source.value === "project" ? undefined : source.value, query: query.value, categories: categoryFilters.value, offset: page.value * 100 });
    if (token === loadRequest) { rows.value = result.rows; total.value = result.total; categories.value = result.categories; enrichment.value = result.enrichment; loaded = true; }
  } catch (failure) { if (token === loadRequest) { error.value = String(failure); rows.value = []; total.value = 0; } }
  finally { if (token === loadRequest) busy.value = false; }
}
function changeSource() {
  loaded = false;
  enrichment.value = null;
  categoryFilters.value = []; categories.value = []; rows.value = []; total.value = 0; page.value = 0;
  void load();
}
function filterCategories(values: string[]) { categoryFilters.value = values; void search(); }
async function initialize() {
  error.value = ""; preview.value = undefined;
  try {
    libraries.value = await request("library.list");
    if (props.analysis) libraries.value.unshift({ id: "project", name: "Project resources" });
    if (!libraries.value.some(item => item.id === source.value)) {
      source.value = libraries.value[0]?.id || "";
      changeSource();
    } else if (!loaded && props.mode === "add") await load();
    await nextTick();
    pickerTable.value?.redraw();
  } catch (failure) { error.value = String(failure); }
}
async function review() {
  busy.value = true; error.value = "";
  try { preview.value = await request(props.kind + ".editor.price_preview", { revision: props.revision, ids: props.targetIds, library: source.value }); }
  catch (failure) { error.value = String(failure); }
  finally { busy.value = false; }
}
async function apply(modify = false, ids = selected.value.map(row => row.id)) {
  if (busy.value) return;
  busy.value = true;
  try {
    const params = props.mode === "rates" ? { operation: "price_update", library: source.value, ids: props.targetIds }
      : { operation: "add_from_library", source: source.value === "project" ? "" : source.value, ids, target_ids: props.targetIds, modify };
    if (await props.apply({ revision: props.revision, ...params })) visible.value = false;
  } finally { busy.value = false; }
}
/** GTK SelectScheduleDialog: Enter/double-click is Modify & Add; with Ctrl it adds unmodified. */
function activate(row: { id: string; rowtype?: string }, ctrl: boolean) {
  if (row.rowtype === "Category") return;
  void apply(props.kind === "schedule" && props.mode === "add" && !props.analysis && !ctrl, [row.id]);
}
async function applyRules(params: Record<string, unknown>) {
  const applied = await props.apply({ ...params, operation: "add_from_library" });
  if (applied) visible.value = false;
  return applied;
}
</script>
<template>
  <PersistentDialog v-model:visible="pickerVisible" :header="title" class="database-picker-dialog" :busy="busy" @show="initialize">
    <p class="dialog-intro">{{ mode === 'add' ? 'Select items from an attached database. Add inserts them at the selection in your working project.' : `Match ${targetIds.length} selected project rows by code and preview the database rates before applying.` }}</p>
    <label class="field">Database<select v-model="source" aria-label="Database" :disabled="busy" @change="changeSource"><option v-if="!libraries.length" value="">No attached databases</option><option v-for="library in libraries" :key="library.id" :value="library.id">{{ library.name }}</option></select></label>
    <DatabaseNotes v-if="current?.notes" :source="current.id" :name="current.name" />
    <p v-if="!libraries.length">Attach databases in the Databases tab, then return here.</p>
    <template v-if="mode === 'add' && libraries.length">
      <p v-if="enrichment" role="note"><small class="enrichment-badge">AI-generated</small> {{ enrichment.summary }}</p>
      <div class="project-filter-bar"><form class="search-field" @submit.prevent="search()"><AppIcon name="search" :size="16" /><input data-primary-input autofocus v-model="query" aria-label="Find database items" @keydown.up.down="pickerTable?.step($event)" placeholder="Code, description or category…" /><button class="button small secondary" :disabled="busy">Search</button></form><CategoryFilter :key="source" :model-value="categoryFilters" :categories="categories" :disabled="busy" @update:model-value="filterCategories" /></div>
      <div class="database-picker-grid"><DataTable class="fit-table" type-ahead :active="visible" :key="source" ref="pickerTable" :rows="rows" :columns="columns" :busy="busy" tree drag-select-rows row-only-selection activate-on-double-click :label="kind === 'schedule' ? 'Database schedule items' : 'Database resource rates'" @selection="selected = $event" @activate="(row, keys) => activate(row, keys?.ctrl ?? false)" /></div>
      <div class="pagination"><button class="text-button" :disabled="busy || !page" @click="goToPage(page - 1)">Previous</button><span>{{ total }} items · Page {{ page + 1 }} · {{ selected.length }} selected</span><button class="text-button" :disabled="busy || (page + 1) * 100 >= total" @click="goToPage(page + 1)">Next</button></div>
    </template>
    <template v-if="mode === 'rates'">
      <p class="field-hint">{{ kind === 'schedule' ? 'Loads the stored schedule rate; descriptions and analysis rows stay intact.' : 'Loads base rates, tax, discount and reference, then recalculates affected analyses.' }} The database file remains unchanged; Undo restores the update.</p>
      <button class="button secondary" :disabled="busy || !source || !targetIds.length" @click="review">Preview rate changes</button>
      <p v-if="preview" role="status">{{ preview.changed }} changed · {{ preview.unchanged }} unchanged · {{ preview.unmatched }} unmatched</p>
    </template>
    <p v-if="error || parentError" class="dialog-error" role="alert">{{ error || parentError }}</p>
    <div class="dialog-footer">
      <button class="button secondary" :disabled="busy" @click="visible = false; emit('manage')">Manage databases…</button><span class="spacer" />
      <button class="button secondary" :disabled="busy" @click="visible = false">Cancel</button>
      <template v-if="mode === 'add' && kind === 'schedule'">
        <button class="button secondary" :disabled="busy || !selected.length" title="Use the rate multiplier and analysis-row replacement configured in Program Settings. Enter or double-click on an item does the same; Ctrl+Enter or Ctrl+double-click adds it unmodified." @click="apply(true)">Modify &amp; Add</button>
        <button class="button secondary" :disabled="busy || !selected.length" @click="rulesOpen = true">Modify &amp; Add with rules…</button>
      </template>
      <button class="button primary" :disabled="busy || !source || (mode === 'rates' ? !preview?.changed : !selected.length)" @click="apply()">{{ mode === 'rates' ? 'Apply database rates' : 'Add selected items' }}</button>
    </div>
  </PersistentDialog>
  <AnalysisRulesDialog v-if="rulesOpen" v-model="rulesOpen" :revision="revision" :ids="selectedIds" :library="{ source, targetIds }" :apply="applyRules" :apply-error="parentError" />
</template>
