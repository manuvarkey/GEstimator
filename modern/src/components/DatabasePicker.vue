<script setup lang="ts">
import { computed, ref } from "vue";
import Dialog from "primevue/dialog";
import DataTable from "./DataTable.vue";
import AppIcon from "./AppIcon.vue";
import type { ColumnDefinition } from "tabulator-tables";
import { request } from "../backend";
const visible = defineModel<boolean>({ required: true });
const props = defineProps<{
  kind: "schedule" | "resources";
  mode: "add" | "rates";
  revision: number;
  targetIds: string[];
  apply: (params: Record<string, unknown>) => Promise<boolean>;
  parentError: string;
}>();
const emit = defineEmits<{ manage: [] }>();
const libraries = ref<{ id: string; name: string }[]>([]);
const source = ref("");
const query = ref("");
const page = ref(0);
const rows = ref<{ id: string; [key: string]: any }[]>([]);
const total = ref(0);
const selected = ref<{ id: string; [key: string]: any }[]>([]);
const busy = ref(false);
const error = ref("");
const preview = ref<{ changed: number; unchanged: number; unmatched: number }>();
const title = computed(() => props.mode === "rates" ? "Refresh selected rates from database" : props.kind === "schedule" ? "Add item from database" : "Add resources from database");
const columns: ColumnDefinition[] = [
  { title: "CODE", field: "code", width: 150 },
  { title: "DESCRIPTION", field: "description", minWidth: 300, widthGrow: 3, formatter: "textarea" },
  { title: "UNIT", field: "unit", width: 90 },
  { title: "RATE", field: "rate", width: 120, hozAlign: "right" as const },
];
async function load() {
  preview.value = undefined;
  selected.value = [];
  if (!source.value || props.mode === "rates") return;
  busy.value = true; error.value = "";
  try {
    const result = await request<{ rows: typeof rows.value; total: number }>(props.kind + ".editor.state", { source: source.value, query: query.value, offset: page.value * 100 });
    rows.value = result.rows; total.value = result.total;
  } catch (failure) { error.value = String(failure); }
  finally { busy.value = false; }
}
async function initialize() {
  error.value = ""; preview.value = undefined; page.value = 0; query.value = "";
  try {
    libraries.value = await request("library.list");
    if (!libraries.value.some(item => item.id === source.value)) source.value = libraries.value[0]?.id || "";
    await load();
  } catch (failure) { error.value = String(failure); }
}
async function review() {
  busy.value = true; error.value = "";
  try { preview.value = await request(props.kind + ".editor.price_preview", { revision: props.revision, ids: props.targetIds, library: source.value }); }
  catch (failure) { error.value = String(failure); }
  finally { busy.value = false; }
}
async function apply(modify = false) {
  if (busy.value) return;
  busy.value = true;
  try {
    const params = props.mode === "rates" ? { operation: "price_update", library: source.value, ids: props.targetIds }
      : { operation: "add_from_library", source: source.value, ids: selected.value.map(row => row.id), target_ids: props.targetIds, modify };
    if (await props.apply({ revision: props.revision, ...params })) visible.value = false;
  } finally { busy.value = false; }
}
</script>
<template>
  <Dialog v-model:visible="visible" modal :header="title" class="workspace-dialog database-picker-dialog" :closable="!busy" :close-on-escape="!busy" @show="initialize">
    <p class="dialog-intro">{{ mode === 'add' ? 'Select items from an attached database. Add inserts them at the selection in your working project.' : `Match ${targetIds.length} selected project rows by code and preview the database rates before applying.` }}</p>
    <label class="field">Database<select v-model="source" aria-label="Database" :disabled="busy" @change="page = 0; load()"><option v-if="!libraries.length" value="">No attached databases</option><option v-for="library in libraries" :key="library.id" :value="library.id">{{ library.name }}</option></select></label>
    <p v-if="!libraries.length">Attach databases in the Databases tab, then return here.</p>
    <template v-if="mode === 'add' && libraries.length">
      <form class="search-field" @submit.prevent="page = 0; load()"><AppIcon name="search" :size="16" /><input v-model="query" aria-label="Find database items" placeholder="Code, description or category…" /><button class="button small secondary" :disabled="busy">Search</button></form>
      <div class="database-picker-grid"><DataTable :rows="rows" :columns="columns" :busy="busy" tree :label="kind === 'schedule' ? 'Database schedule items' : 'Database resource rates'" @selection="selected = $event" @activate="row => { if (row.rowtype !== 'Category') apply(); }" /></div>
      <div class="pagination"><button class="text-button" :disabled="busy || !page" @click="page--; load()">Previous</button><span>{{ total }} items · Page {{ page + 1 }} · {{ selected.length }} selected</span><button class="text-button" :disabled="busy || (page + 1) * 100 >= total" @click="page++; load()">Next</button></div>
    </template>
    <template v-if="mode === 'rates'">
      <p class="field-hint">{{ kind === 'schedule' ? 'Loads the stored schedule rate; descriptions and analysis rows stay intact.' : 'Loads base rates, VAT, discount and reference, then recalculates affected analyses.' }} The database file remains unchanged; Undo restores the update.</p>
      <button class="button secondary" :disabled="busy || !source || !targetIds.length" @click="review">Preview rate changes</button>
      <p v-if="preview" role="status">{{ preview.changed }} changed · {{ preview.unchanged }} unchanged · {{ preview.unmatched }} unmatched</p>
    </template>
    <p v-if="error || parentError" class="dialog-error" role="alert">{{ error || parentError }}</p>
    <div class="dialog-footer"><button class="button secondary" :disabled="busy" @click="visible = false; emit('manage')">Manage databases…</button><span class="spacer" /><button class="button secondary" :disabled="busy" @click="visible = false">Cancel</button><button v-if="mode === 'add' && kind === 'schedule'" class="button secondary" :disabled="busy || !selected.length" title="Use the rate multiplier and analysis-row replacement configured together in Program Settings → Library Modify & Add." @click="apply(true)">Modify &amp; Add</button><button class="button primary" :disabled="busy || !source || (mode === 'rates' ? !preview?.changed : !selected.length)" @click="apply()">{{ mode === 'rates' ? 'Apply database rates' : 'Add selected items' }}</button></div>
  </Dialog>
</template>
