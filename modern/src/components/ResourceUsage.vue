<script setup lang="ts">
import { computed, ref } from "vue";
import Dialog from "primevue/dialog";
import { request } from "../backend";

interface UsageRow {
  code: string;
  description: string;
  category: string;
  unit: string;
  rate: string;
  quantity: string;
  amount: string;
}
interface Analysis {
  code: string;
  description: string;
  indirect: boolean;
}
interface Page<T> {
  rows: T[];
  total: number;
}
const props = defineProps<{ selectedCode?: string }>();
const emit = defineEmits<{ analysis: [code: string] }>();
const visible = defineModel<boolean>({ required: true });
const query = ref("");
const appliedQuery = ref("");
const offset = ref(0);
const resource = ref("");
const usage = ref<Page<UsageRow>>({ rows: [], total: 0 });
const analyses = ref<Page<Analysis>>({ rows: [], total: 0 });
const busy = ref(false);
const error = ref("");
const pageSize = 50;
const total = computed(() => resource.value ? analyses.value.total : usage.value.total);

async function load(nextOffset: number, code: string, search: string) {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    if (code) {
      analyses.value = await request("resources.editor.dependents", {
        code,
        offset: nextOffset,
      });
    } else {
      usage.value = await request("resources.editor.usage", {
        query: search,
        offset: nextOffset,
      });
    }
    appliedQuery.value = search;
    offset.value = nextOffset;
    resource.value = code;
  } catch (reason) {
    error.value = String(reason);
  } finally {
    busy.value = false;
  }
}

function open() {
  query.value = "";
  appliedQuery.value = "";
  resource.value = "";
  offset.value = 0;
  usage.value = { rows: [], total: 0 };
  analyses.value = { rows: [], total: 0 };
  void load(0, props.selectedCode ?? "", "");
}

function openAnalysis(code: string) {
  visible.value = false;
  emit("analysis", code);
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    header="Resource usage"
    class="workspace-dialog"
    style="width: min(94vw, 940px)"
    :closable="!busy"
    :close-on-escape="!busy"
    @show="open"
  >
    <template v-if="resource">
      <button class="button secondary" :disabled="busy" @click="load(0, '', appliedQuery)">
        All resource usage
      </button>
      <h3>Analyses using {{ resource }}</h3>
      <ul v-if="analyses.rows.length" class="resource-dependents">
        <li v-for="item in analyses.rows" :key="item.code">
          <button class="button secondary" :disabled="busy" @click="openAnalysis(item.code)">
            {{ item.code }} {{ item.description }}
          </button>
          <span v-if="item.indirect"> via sub-analysis</span>
        </li>
      </ul>
      <p v-else-if="!busy && !error">No analyses use this resource.</p>
    </template>
    <template v-else>
      <form class="search-field" @submit.prevent="load(0, '', query)">
        <input v-model="query" data-primary-input autofocus aria-label="Search resource usage" placeholder="Search resources…" />
        <button class="button secondary" :disabled="busy">Search</button>
      </form>
      <div v-if="usage.rows.length" class="resource-usage-table">
        <table aria-label="Project resource totals">
          <thead>
            <tr>
              <th scope="col">Code</th>
              <th scope="col">Description</th>
              <th scope="col">Category</th>
              <th scope="col">Unit</th>
              <th scope="col">Rate</th>
              <th scope="col">Quantity</th>
              <th scope="col">Amount</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in usage.rows" :key="row.code">
              <td>
                <button class="button secondary" :disabled="busy" @click="load(0, row.code, appliedQuery)">
                  {{ row.code }}
                </button>
              </td>
              <td>{{ row.description }}</td>
              <td>{{ row.category }}</td>
              <td>{{ row.unit }}</td>
              <td>{{ row.rate }}</td>
              <td>{{ row.quantity }}</td>
              <td>{{ row.amount }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else-if="!busy && !error">No resource usage found.</p>
    </template>
    <div v-if="error" class="dialog-error" role="alert">{{ error }}</div>
    <p v-if="busy" role="status">Loading resource usage…</p>
    <div v-if="total > pageSize" class="dialog-footer">
      <button
        class="button secondary"
        :disabled="busy || offset === 0"
        @click="load(offset - pageSize, resource, appliedQuery)"
      >Previous</button>
      <span>Page {{ offset / pageSize + 1 }} of {{ Math.ceil(total / pageSize) }}</span>
      <button
        class="button secondary"
        :disabled="busy || offset + pageSize >= total"
        @click="load(offset + pageSize, resource, appliedQuery)"
      >Next</button>
    </div>
  </Dialog>
</template>

<style scoped>
.resource-usage-table { overflow: auto; margin-top: 12px; max-height: 54vh; }
table { width: 100%; border-collapse: collapse; }
th, td { border-bottom: 1px solid var(--line); padding: 8px; text-align: left; }
th:nth-last-child(-n + 3), td:nth-last-child(-n + 3) {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.resource-dependents { list-style: none; margin: 0; padding: 0; }
.resource-dependents li + li { margin-top: 6px; }
</style>

<style scoped>
.resource-dependents li { min-width: 0; }
.resource-dependents button { display: block; width: 100%; white-space: normal; overflow-wrap: anywhere; text-align: left; }
.resource-usage-table table { table-layout: fixed; }
.resource-usage-table td { overflow-wrap: anywhere; white-space: normal; }
</style>
