<script setup lang="ts">
// Share the schedule-link picker between staged properties and the record editor.
import { ref, type ComputedRef, type Ref } from "vue";
import Dialog from "primevue/dialog";
import AppIcon from "./AppIcon.vue";
import PersistentDialog from "./PersistentDialog.vue";
import { request } from "../backend";
import { vMiddleEllipsis } from "../middleEllipsis";
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
const pickerBusy = ref(false);
const pickerError = ref("");

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

async function searchLinks() {
  pickerBusy.value = true;
  pickerError.value = "";
  try {
    pickerItems.value = await request("schedule.list", { query: pickerQuery.value, offset: pickerPage.value * 100 });
  } catch (reason) {
    pickerError.value = String(reason);
  } finally {
    pickerBusy.value = false;
  }
}

/** Open a fresh schedule search for the chosen link slot. */
async function showLinkPicker(slot: number) {
  pickerSlot.value = slot;
  pickerQuery.value = "";
  pickerPage.value = 0;
  pickerOpen.value = true;
  await searchLinks();
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
    modal
    header="Choose schedule item"
    class="workspace-dialog resource-dialog"
  >
    <form
      class="search-field"
      @submit.prevent="
        pickerPage = 0;
        searchLinks();
      "
    >
      <input
        v-model="pickerQuery"
        data-primary-input
        autofocus
        aria-label="Find linked schedule item"
        placeholder="Code or description…"
      /><button class="button small secondary" :disabled="pickerBusy">Search</button>
    </form>
    <p v-if="pickerError" role="alert" class="dialog-error">{{ pickerError }}</p>
    <div class="library-results">
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
      <button
        class="text-button"
        :disabled="pickerBusy || !pickerPage"
        @click="
          pickerPage--;
          searchLinks();
        "
      >
        Previous</button
      ><span>Page {{ pickerPage + 1 }}</span
      ><button
        class="text-button"
        :disabled="pickerBusy || pickerItems.length < 100"
        @click="
          pickerPage++;
          searchLinks();
        "
      >
        Next
      </button>
    </div>
  </PersistentDialog>
</template>
