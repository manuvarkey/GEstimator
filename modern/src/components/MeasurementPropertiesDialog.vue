<script setup lang="ts">
// Share the schedule-link picker between staged properties and the record editor.
import { nextTick, ref, watch, type ComputedRef, type Ref } from "vue";
import Dialog from "primevue/dialog";
import AppIcon from "./AppIcon.vue";
import PersistentDialog from "./PersistentDialog.vue";
import { request } from "../backend";
import { useLiveSearch } from "../liveSearch";
import { vMiddleEllipsis } from "../middleEllipsis";
import { focusResultButton } from "../resultNavigation";
import type { GridRow, GridState, MeasurementDetail, ViewCommand } from "../projectViewTypes";

interface PropertiesContext {
  state: Ref<GridState | undefined>;
  one: ComputedRef<GridRow | undefined>;
  error: Ref<string>;
  activeMeasurement: Ref<string | undefined>;
  command: ViewCommand;
  loadDetail: () => Promise<void>;
}

const props = defineProps<{ busy: boolean; context: PropertiesContext }>();
const { state, one, error, activeMeasurement, command, loadDetail } = props.context;
const propertiesOpen = ref(false);
const propertiesCategory = ref(false);
const propertiesDetail = ref<MeasurementDetail | null>();
const properties = ref<{
  description: string;
  links: { code: string; remark: string; label: string }[];
  user_data: string[];
}>({ description: "", links: [], user_data: [] });
const propertiesRevision = ref(0);
const pickerOpen = ref(false);
const pickerSlot = ref(0);
const pickerQuery = ref("");
const pickerPage = ref(0);
const pickerItems = ref<{ code: string; description: string; unit: string | null }[]>([]);
const pickerResults = ref<HTMLElement>();
const pickerBusy = ref(false);
const pickerError = ref("");
let pendingNavigation: { key: string; from: EventTarget | null } | undefined;
let searchedQuery = "";
const liveSearch = useLiveSearch(
  pickerQuery,
  () => searchedQuery,
  async () => {
    if (pickerOpen.value) return searchLinks();
  },
);
watch(pickerOpen, (opened) => {
  if (!opened) liveSearch.cancel();
});

/** Open a form snapshot for the selected measurement or category. */
async function showProperties() {
  // Step 1: load the selected item's detail; selection may change while it is in flight.
  if (!one.value || !state.value || one.value.id === "measurement:uncategorised") return;
  const identity = one.value.id;
  if (one.value.type !== "Heading" && one.value.rowtype !== "Category" && state.value.detail?.id !== identity)
    await loadDetail();
  if (one.value?.id !== identity) return;
  // Step 2: stage a separate form snapshot and retain the revision for stale-write checks.
  const detail = one.value.rowtype === "Category" ? undefined : state.value.detail;
  propertiesCategory.value = one.value.rowtype === "Category";
  propertiesDetail.value = detail;
  properties.value = {
    description: one.value.description,
    links: detail?.links.map((link) => ({ code: link.code, remark: link.remark, label: link.label })) || [],
    user_data: detail?.user_data.map((field) => field.value) || [],
  };
  propertiesRevision.value = state.value.revision;
  error.value = "";
  propertiesOpen.value = true;
}

async function saveProperties() {
  if (await command("properties", { id: one.value?.id, revision: propertiesRevision.value, ...properties.value }))
    propertiesOpen.value = false;
}

async function searchLinks(page = 0) {
  if (pickerBusy.value) return false;
  liveSearch.cancel();
  searchedQuery = pickerQuery.value;
  pickerBusy.value = true;
  pickerError.value = "";
  pickerPage.value = page;
  // Reset at the start, so the response cannot pull the viewport away from a user scroll.
  pickerItems.value = [];
  pickerResults.value?.scrollTo(0, 0);
  try {
    pickerItems.value = await request("schedule.list", { query: searchedQuery, offset: page * 100 });
  } catch (reason) {
    pickerError.value = String(reason);
  } finally {
    pickerBusy.value = false;
  }
  await nextTick();
  const pending = pendingNavigation;
  pendingNavigation = undefined;
  if (pending && pickerOpen.value && document.activeElement === pending.from)
    focusResultButton(pickerResults.value, pending.key);
}

/** Open a fresh schedule search for the chosen link slot. */
async function showLinkPicker(slot: number) {
  pickerSlot.value = slot;
  pickerQuery.value = "";
  pickerOpen.value = true;
  await searchLinks();
}

function navigateLinks(event: KeyboardEvent) {
  if (event.isComposing || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
  if (pickerBusy.value) {
    pendingNavigation = { key: event.key, from: event.target };
    event.preventDefault();
  } else if (focusResultButton(pickerResults.value, event.key)) {
    event.preventDefault();
  }
}

async function chooseLink(code: string) {
  if (propertiesOpen.value) properties.value.links[pickerSlot.value]!.code = code;
  else if (
    !(await command("link", {
      id: activeMeasurement.value,
      slot: pickerSlot.value,
      code,
      remark: state.value?.detail!.links[pickerSlot.value].remark || "",
    }))
  )
    return;
  pickerOpen.value = false;
}

defineExpose({ showProperties, showLinkPicker });
</script>

<template>
  <Dialog
    v-model:visible="propertiesOpen"
    modal
    :header="propertiesCategory ? 'Edit measurement category' : 'Measurement properties'"
    class="workspace-dialog measurement-properties-dialog"
    :closable="!busy"
    :close-on-escape="!busy"
    :pt="{ root: { inert: pickerOpen || undefined } }"
  >
    <form @submit.prevent="saveProperties">
      <p v-if="propertiesDetail" class="dialog-intro">{{ propertiesDetail.info.note }}</p>
      <label class="field"
        >{{ propertiesCategory ? "Category name" : "Description / remarks"
        }}<textarea
          v-model="properties.description"
          data-primary-input
          autofocus
          :disabled="busy"
          :rows="propertiesCategory ? 1 : 3"
        />
      </label>
      <div class="measurement-properties-fields">
        <label v-for="(link, index) in properties.links" :key="index" class="field"
          >{{ link.label }} · Schedule code {{ index + 1 }}
          <div class="file-input">
            <input v-model="link.code" :aria-label="'Property schedule code ' + (index + 1)" :disabled="busy" />
            <button
              type="button"
              class="icon-button"
              :aria-label="'Choose property schedule item ' + (index + 1)"
              @click="showLinkPicker(index)"
            >
              <AppIcon name="search" />
            </button>
            <button
              type="button"
              class="icon-button"
              :aria-label="'Clear property schedule link ' + (index + 1)"
              @click="link.code = ''"
            >
              <AppIcon name="close" />
            </button>
          </div>
          <input
            v-model="link.remark"
            :aria-label="'Property item remark ' + (index + 1)"
            placeholder="Item remark / column label"
            :disabled="busy"
          />
        </label>
      </div>
      <p v-if="propertiesDetail?.property_groups.length" class="field-hint">
        Numeric constants accept arithmetic; saving stores the evaluated number.
      </p>
      <div class="measurement-property-groups">
        <fieldset v-for="group in propertiesDetail?.property_groups || []" :key="group.label">
          <legend>{{ group.label }}</legend>
          <label v-for="field in group.fields" :key="field.index" class="field"
            >{{ field.label
            }}<input
              v-model="properties.user_data[Number(field.index)]"
              :aria-label="field.caption"
              :inputmode="field.numeric ? 'decimal' : 'text'"
              :disabled="busy"
          /></label>
        </fieldset>
      </div>
      <p v-if="error" role="alert" class="dialog-error">{{ error }}</p>
      <div class="dialog-footer">
        <button type="button" class="button secondary" :disabled="busy" @click="propertiesOpen = false">Cancel</button
        ><button class="button primary" :disabled="busy">Save properties</button>
      </div>
    </form>
  </Dialog>
  <PersistentDialog
    :busy="pickerBusy"
    v-model:visible="pickerOpen"
    header="Choose schedule item"
    class="resource-dialog measurement-link-picker"
  >
    <form class="search-field" @submit.prevent="searchLinks()">
      <input
        v-model="pickerQuery"
        data-primary-input
        autofocus
        aria-label="Find linked schedule item"
        placeholder="Code or description…"
        @keydown.up.down="navigateLinks"
      /><button class="button small secondary" :disabled="pickerBusy">Search</button>
    </form>
    <p v-if="pickerError" role="alert" class="dialog-error">{{ pickerError }}</p>
    <div ref="pickerResults" class="library-results" @keydown.up.down.home.end="navigateLinks">
      <button
        v-for="item in pickerItems"
        :key="item.code"
        class="library-item"
        :disabled="pickerBusy"
        :title="item.description"
        @click="chooseLink(item.code)"
      >
        <span
          ><b>{{ item.code }}</b
          ><small v-middle-ellipsis="item.description" class="five-line-description" /></span
        ><span>{{ item.unit }}</span>
      </button>
      <p v-if="!pickerBusy && !pickerItems.length">No schedule items match this search.</p>
    </div>
    <div class="pagination">
      <button class="text-button" :disabled="pickerBusy || !pickerPage" @click="searchLinks(pickerPage - 1)">
        Previous</button
      ><span>Page {{ pickerPage + 1 }}</span
      ><button
        class="text-button"
        :disabled="pickerBusy || pickerItems.length < 100"
        @click="searchLinks(pickerPage + 1)"
      >
        Next
      </button>
    </div>
  </PersistentDialog>
</template>
