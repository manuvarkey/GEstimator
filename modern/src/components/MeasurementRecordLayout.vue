<script setup lang="ts">
// Render a measurement record editor's controls around its existing grid and links.
import { computed, ref } from "vue";
import AppIcon from "./AppIcon.vue";
import { vMiddleEllipsis } from "../middleEllipsis";
import type { MeasurementDetail, MeasurementDetailState } from "../projectViewTypes";

const props = defineProps<{
  entryId: string;
  activeMeasurement?: string;
  detail?: MeasurementDetail | null;
  draft?: MeasurementDetailState["measurement_draft"];
  busy: boolean;
  detailBusy: boolean;
}>();
const descriptionDraft = defineModel<string | undefined>("descriptionDraft", { required: true });
const emit = defineEmits<{
  apply: [];
  discard: [];
  editDescription: [];
  finishDescription: [];
  changePage: [delta: -1 | 1];
}>();
defineSlots<{
  links(props: { detail: MeasurementDetail }): unknown;
  default(props: { detail: MeasurementDetail }): unknown;
}>();

const measurementDescription = ref<HTMLTextAreaElement>();
const fullMeasurementTitle = computed(() =>
  props.detail?.id === props.entryId ? props.detail.description || "Measurement entry" : "Measurement entry",
);
const recordDetail = computed(() => (props.detail?.id === props.activeMeasurement ? props.detail : undefined));

/** Focus a newly opened or restored description editor without scrolling the records. */
function focusDescription() {
  measurementDescription.value?.focus({ preventScroll: true });
}

defineExpose({ focusDescription });
</script>

<template>
  <div class="measurement-draft-header draft-headerbar" role="region" aria-label="Measurement records draft">
    <strong :title="detail?.info.note">{{ detail?.id === entryId ? detail.info.label : "Measurement records" }}</strong>
    <button
      class="button small danger"
      aria-label="Discard records"
      title="Discard this draft and return to Measurements."
      :disabled="busy || detailBusy || !draft"
      @click="emit('discard')"
    >
      <AppIcon name="close" /><span>Discard records</span>
    </button>
    <button
      class="button small primary"
      aria-label="Apply records"
      title="Apply records, links and properties to the working project as one undo step (Ctrl+Enter). Return to Measurements after applying. Save the project to retain them on disk."
      :disabled="busy || detailBusy || !draft"
      @click="emit('apply')"
    >
      <AppIcon name="check" /><span>Apply records</span>
    </button>
  </div>
  <div class="measurement-entry-heading">
    <textarea
      v-if="descriptionDraft !== undefined"
      ref="measurementDescription"
      v-model="descriptionDraft"
      class="measurement-entry-title"
      aria-label="Measurement description / remarks"
      rows="1"
      @blur="emit('finishDescription')"
      @keydown.esc.stop.prevent="descriptionDraft = undefined"
    />
    <h2
      v-else
      v-middle-ellipsis="fullMeasurementTitle || 'Measurement entry'"
      class="measurement-entry-title five-line-description"
      :title="fullMeasurementTitle"
      :aria-label="fullMeasurementTitle"
      @dblclick="emit('editDescription')"
    />
    <button
      class="button small secondary"
      aria-label="Edit measurement description / remarks"
      :disabled="busy || detail?.id !== entryId"
      @mousedown.prevent
      @click="descriptionDraft === undefined ? emit('editDescription') : measurementDescription?.focus()"
    >
      <AppIcon name="edit" />Edit description
    </button>

    <span class="draft-badge" :class="{ dirty: draft?.dirty }">{{
      draft?.dirty ? "Unsaved records" : "Up to date"
    }}</span>
  </div>
  <template v-if="recordDetail">
    <slot name="links" :detail="recordDetail" />
    <div class="measurement-record-summary"><strong>Measurement records</strong></div>
    <slot :detail="recordDetail" />
    <div class="measurement-total-row" role="status" aria-label="All measurement records total">
      <span>Total · all records</span
      ><strong
        ><template v-for="(total, index) in recordDetail.totals" :key="index"
          ><span v-if="index"> · </span>{{ recordDetail.links[index]?.label || `Quantity ${Number(index) + 1}` }}:
          {{ total }} {{ recordDetail.links[index]?.unit || "" }}</template
        ></strong
      >
    </div>
    <div class="pagination">
      <button
        class="text-button"
        :disabled="busy || detailBusy || !recordDetail.offset"
        @click="emit('changePage', -1)"
      >
        Previous records
      </button>
      <span>{{ recordDetail.total_records }} records · Page {{ Math.floor(recordDetail.offset / 100) + 1 }}</span>
      <button
        class="text-button"
        :disabled="busy || detailBusy || recordDetail.offset + 100 >= recordDetail.total_records"
        @click="emit('changePage', 1)"
      >
        Next records
      </button>
    </div>
  </template>
</template>
