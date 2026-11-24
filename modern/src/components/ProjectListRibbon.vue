<script setup lang="ts">
// Keep ribbon groups as siblings so RibbonToolbar can measure their overflow.
import { computed } from "vue";
import AppIcon from "./AppIcon.vue";
import { quantityRoundingOptions } from "../quantityRounding";
import type { GridRow, View } from "../projectViewTypes";

const props = defineProps<{
  view: View;
  busy: boolean;
  browsingSource: boolean;
  hasRows: boolean;
  selected: readonly GridRow[];
}>();
const quantityRounding = defineModel<string>("quantityRounding", { required: true });
const emit = defineEmits<{
  showDatabase: [];
  showPriceUpdate: [];
  addItem: [];
  addSubitem: [];
  addCategory: [];
  duplicate: [];
  cut: [];
  copy: [];
  paste: [];
  deleteSelection: [];
  editResource: [];
  moveResources: [];
  move: [delta: -1 | 1];
  editAnalysis: [];
  importAnalyses: [];
  showDiscrepancies: [];
  editAnalysisRules: [];
  renumberSchedule: [];
  showScheduleColour: [];
  refreshScheduleRates: [];
  updateSelectedQuantities: [];
  showResourceUsage: [];
  findAnalyses: [];
  refreshDependentRates: [];
  renumberResources: [];
  syncScheduleRates: [];
  editRecords: [];
  showMeasurementProperties: [];
  updateQuantities: [];
  importWorkbook: [];
  exportWorkbook: [];
}>();

const isMeasurement = computed(() => props.view === "measurement");
const one = computed(() => (props.selected.length === 1 ? props.selected[0] : undefined));
const selectedSchedule = computed(() => (one.value?.rowtype === "Schedule" ? one.value : undefined));
const hasScheduleSelection = computed(() => props.selected.some((row) => row.rowtype === "Schedule"));
</script>

<template>
  <div v-if="!isMeasurement" class="ribbon-group">
    <div class="ribbon-actions">
      <button
        class="ribbon-action"
        :aria-label="view === 'schedule' ? 'Add item from database' : 'Add resources from database'"
        title="Select items from attached databases in a separate dialog. The working table and its insertion selection remain in place (Ctrl+L)."
        :disabled="busy"
        @click="emit('showDatabase')"
      >
        <AppIcon name="database" /><span class="ribbon-label">Add from database</span>
      </button>
      <button
        v-if="view === 'resources'"
        class="ribbon-action"
        aria-label="Refresh selected rates from database"
        title="Choose an attached database, preview rates matching selected project codes, and apply as one undoable update."
        :disabled="busy || !selected.length"
        @click="emit('showPriceUpdate')"
      >
        <AppIcon name="refresh" /><span class="ribbon-label">Database rates</span>
      </button>
    </div>
    <small>DATABASE</small>
  </div>
  <template v-if="!browsingSource">
    <div class="ribbon-group">
      <div class="ribbon-actions">
        <button
          class="ribbon-action"
          :aria-label="isMeasurement ? 'Add measurement' : 'Add item'"
          :title="
            isMeasurement
              ? 'Add a measurement using a shipped template in the selected category (Ctrl+I).'
              : 'Create an item in the selected category with its code, description and numeric fields (Ctrl+I).'
          "
          :disabled="busy"
          @click="emit('addItem')"
        >
          <AppIcon name="plus" :size="15" /><span class="ribbon-label">Add item</span>
        </button>
        <button
          v-if="view === 'schedule'"
          class="ribbon-action"
          aria-label="Add subitem"
          title="Create a subitem of the selected item; with a subitem selected, add another subitem under the same item. Its category follows the parent; the parent code is filled in for you (Ctrl+Shift+I)."
          :disabled="busy || !one || one.rowtype === 'Category'"
          @click="emit('addSubitem')"
        >
          <AppIcon name="child" /><span class="ribbon-label">Add subitem</span>
        </button>
        <button
          class="ribbon-action"
          aria-label="Add category"
          title="Add a category after the selected group, or at the start with no selection."
          :disabled="busy"
          @click="emit('addCategory')"
        >
          <AppIcon name="category" /><span class="ribbon-label">Add category</span>
        </button>
        <button
          class="ribbon-action"
          aria-label="Duplicate"
          title="Create a separate copy of the selected item. Measurement selections are duplicated in their current order."
          :disabled="busy || (isMeasurement ? !selected.length : !one || one.rowtype === 'Category')"
          @click="emit('duplicate')"
        >
          <AppIcon name="duplicate" /><span class="ribbon-label">Duplicate</span>
        </button>
      </div>
      <small>CREATE</small>
    </div>
    <div class="ribbon-group">
      <div class="ribbon-actions">
        <button
          v-if="view === 'resources'"
          class="ribbon-action ribbon-icon"
          aria-label="Cut"
          title="Cut the selected resources. Paste after a resource or on a category moves them there, keeping their codes and analysis links. Works within this project only (Ctrl+X)."
          :disabled="busy || !selected.some((row) => row.rowtype !== 'Category')"
          @click="emit('cut')"
        >
          <AppIcon name="cut" /><span class="ribbon-label">Cut</span></button
        ><button
          class="ribbon-action ribbon-icon"
          aria-label="Copy"
          title="Copy selected items or categories, including off-page contents, to the system clipboard for use in this or another GEstimator window (Ctrl+C)."
          :disabled="busy || !selected.length"
          @click="emit('copy')"
        >
          <AppIcon name="copy" /><span class="ribbon-label">Copy</span></button
        ><button
          class="ribbon-action ribbon-icon"
          aria-label="Paste"
          title="Paste items below the selection or first in a selected category. Paste copied categories as separate groups after the selected group, or at the start with no selection. Cut resources move (Ctrl+V)."
          :disabled="busy"
          @click="emit('paste')"
        >
          <AppIcon name="paste" /><span class="ribbon-label">Paste</span>
        </button>
        <button
          class="ribbon-action ribbon-icon danger"
          aria-label="Delete"
          title="Preview deletion of selected items and category contents before confirming. Project Undo restores the operation."
          :disabled="busy || !selected.length"
          @click="emit('deleteSelection')"
        >
          <AppIcon name="trash" /><span class="ribbon-label">Delete</span>
        </button>
        <template v-if="view === 'resources'">
          <button
            class="ribbon-action ribbon-icon"
            aria-label="Edit resource"
            title="Edit all fields of the selected resource together. Only changed fields are saved, as one undoable operation (Ctrl+E). Enter edits the focused cell."
            :disabled="busy || !one || one.rowtype === 'Category'"
            @click="emit('editResource')"
          >
            <AppIcon name="edit" /><span class="ribbon-label">Edit resource</span>
          </button>
          <button
            class="ribbon-action ribbon-icon"
            aria-label="Move resources…"
            title="Move selected definitions to another category without making copies or breaking analysis links. Undo restores their previous categories."
            :disabled="busy || !selected.length || selected.some((row) => row.rowtype === 'Category')"
            @click="emit('moveResources')"
          >
            <AppIcon name="category" /><span class="ribbon-label">Move resources</span>
          </button>
        </template>
      </div>
      <small>EDIT</small>
    </div>
    <div class="ribbon-group">
      <div class="ribbon-actions">
        <button
          class="ribbon-action ribbon-icon"
          :disabled="busy || (isMeasurement ? !selected.length || one?.id === 'measurement:uncategorised' : !one)"
          aria-label="Move item up"
          title="Move the selected item or category earlier among its siblings while preserving its contents and links."
          @click="emit('move', -1)"
        >
          <AppIcon name="up" /><span class="ribbon-label">Move up</span></button
        ><button
          class="ribbon-action ribbon-icon"
          :disabled="busy || (isMeasurement ? !selected.length || one?.id === 'measurement:uncategorised' : !one)"
          aria-label="Move item down"
          title="Move the selected item or category later among its siblings while preserving its contents and links."
          @click="emit('move', 1)"
        >
          <AppIcon name="down" /><span class="ribbon-label">Move down</span>
        </button>
      </div>
      <small>ARRANGE</small>
    </div>
    <div v-if="view === 'schedule'" class="ribbon-group">
      <div class="ribbon-actions ribbon-actions-wide">
        <button
          class="ribbon-action"
          aria-label="Edit analysis"
          :title="
            selectedSchedule?.has_children
              ? 'Items with subitems are priced through their subitems; select a subitem to edit its analysis.'
              : 'Open the selected schedule item in the Analysis editor to inspect and edit its rate calculation.'
          "
          :disabled="busy || !selectedSchedule || selectedSchedule.has_children"
          @click="emit('editAnalysis')"
        >
          <AppIcon name="edit" /><span class="ribbon-label">Edit analysis</span>
        </button>
        <button
          class="ribbon-action"
          aria-label="Import multiple analyses"
          :disabled="busy"
          @click="emit('importAnalyses')"
        >
          <AppIcon name="import" /><span class="ribbon-label">Import analyses</span>
        </button>
        <button
          class="ribbon-action"
          aria-label="Show rate discrepancies"
          :disabled="busy"
          @click="emit('showDiscrepancies')"
        >
          <AppIcon name="search" /><span class="ribbon-label">Rate discrepancies</span>
        </button>
        <button
          class="ribbon-action"
          aria-label="Bulk edit analysis…"
          title="Match and modify analysis rows across selected schedule items/categories or the whole schedule. Preview ordered rules and rate changes before applying as one project undo step."
          :disabled="busy"
          @click="emit('editAnalysisRules')"
        >
          <AppIcon name="filter" /><span class="ribbon-label">Bulk edit analysis</span>
        </button>
        <button
          class="ribbon-action"
          aria-label="Renumber schedule…"
          title="Choose numbering options for the schedule hierarchy. Item links are preserved and the operation can be undone."
          :disabled="busy || !hasRows"
          @click="emit('renumberSchedule')"
        >
          <AppIcon name="calculate" /><span class="ribbon-label">Renumber schedule…</span>
        </button>
        <button
          class="ribbon-action"
          aria-label="Row colour…"
          title="Apply or clear a saved background colour for selected schedule items. Categories and unselected descendants are excluded."
          :disabled="busy || !hasScheduleSelection"
          @click="emit('showScheduleColour')"
        >
          <AppIcon name="colour" /><span class="ribbon-label">Row colour…</span>
        </button>
        <button
          class="ribbon-action"
          aria-label="Refresh selected rates"
          title="Recalculate the selected schedule analyses and dependent rates using the current project resources."
          :disabled="busy || !hasScheduleSelection"
          @click="emit('refreshScheduleRates')"
        >
          <AppIcon name="refresh" /><span class="ribbon-label">Refresh rates</span>
        </button>
        <button
          class="ribbon-action"
          aria-label="Quantities from measurements…"
          title="Choose a rounding rule and update only the selected schedule items from their linked measurement totals."
          :disabled="busy || !hasScheduleSelection"
          @click="emit('updateSelectedQuantities')"
        >
          <AppIcon name="ruler" /><span class="ribbon-label">Measured quantities</span>
        </button>
        <button
          class="ribbon-action"
          aria-label="Resource usage"
          title="View aggregate project resource quantities and amounts, search totals, and navigate to referencing analyses."
          :disabled="busy"
          @click="emit('showResourceUsage')"
        >
          <AppIcon name="chart" /><span class="ribbon-label">Resource usage</span>
        </button>
      </div>
      <small>SCHEDULE</small>
    </div>
    <div v-if="view === 'resources'" class="ribbon-group">
      <div class="ribbon-actions ribbon-actions-wide">
        <button
          class="ribbon-action"
          aria-label="Resource usage"
          title="View aggregate project resource quantities and amounts, search totals, and navigate to referencing analyses."
          :disabled="busy"
          @click="emit('showResourceUsage')"
        >
          <AppIcon name="chart" /><span class="ribbon-label">Resource usage</span>
        </button>
        <button
          class="ribbon-action"
          aria-label="Find analyses"
          title="Find schedule analyses that use the selected resource directly or through nested sub-analyses."
          :disabled="busy || !one || one.rowtype === 'Category'"
          @click="emit('findAnalyses')"
        >
          <AppIcon name="link" /><span class="ribbon-label">Find analyses</span>
        </button>
        <button
          class="ribbon-action"
          aria-label="Update dependent rates"
          title="Recalculate schedule rates affected by the current resource definitions in the project working copy."
          :disabled="busy"
          @click="emit('refreshDependentRates')"
        >
          <AppIcon name="refresh" /><span class="ribbon-label">Refresh rates</span>
        </button>
        <button class="ribbon-action" :disabled="busy" @click="emit('renumberResources')">
          <AppIcon name="edit" /><span class="ribbon-label">Renumber resources</span>
        </button>
        <button class="ribbon-action" :disabled="busy || !selected.length" @click="emit('syncScheduleRates')">
          <AppIcon name="refresh" /><span class="ribbon-label">Rates from schedule</span>
        </button>
      </div>
      <small>RESOURCES</small>
    </div>
    <div v-if="isMeasurement" class="ribbon-group">
      <div class="ribbon-actions">
        <button
          class="ribbon-action"
          data-ribbon-keep-label
          aria-label="Edit records"
          :disabled="busy || !one || one.rowtype === 'Category'"
          @click="emit('editRecords')"
        >
          <AppIcon name="edit" /><span class="ribbon-label">Edit records</span>
        </button>
        <button
          class="ribbon-action"
          data-ribbon-keep-label
          aria-label="Properties…"
          :disabled="busy || !one || one.id === 'measurement:uncategorised'"
          @click="emit('showMeasurementProperties')"
        >
          <AppIcon name="settings" /><span class="ribbon-label">Properties</span>
        </button>
      </div>
      <small>MEASUREMENT</small>
    </div>
    <div v-if="isMeasurement" class="ribbon-group">
      <div class="ribbon-actions ribbon-measure-actions">
        <select v-model="quantityRounding" aria-label="Quantity rounding">
          <option v-for="option in quantityRoundingOptions" :key="option">
            {{ option }}
          </option>
        </select>
        <button
          class="ribbon-action"
          aria-label="Update schedule quantities"
          title="Update schedule quantities from linked measurement totals using the selected rounding rule. Project Undo restores the previous quantities."
          :disabled="busy"
          @click="emit('updateQuantities')"
        >
          <AppIcon name="calculate" /><span class="ribbon-label">Update quantities</span>
        </button>
      </div>
      <small>QUANTITIES</small>
    </div>
    <div class="ribbon-group">
      <div class="ribbon-actions">
        <button
          v-if="!isMeasurement"
          class="ribbon-action"
          aria-label="Import workbook"
          title="Preview a schedule or resource worksheet, map columns and choose how duplicate codes are handled before importing."
          :disabled="busy"
          @click="emit('importWorkbook')"
        >
          <AppIcon name="import" /><span class="ribbon-label">Import workbook</span>
        </button>
        <button
          class="ribbon-action"
          aria-label="Export workbook"
          title="Export the project to an Excel workbook containing Schedule, Resources, Measurements, Resource Usage and Analysis sheets."
          :disabled="busy"
          @click="emit('exportWorkbook')"
        >
          <AppIcon name="export" /><span class="ribbon-label">Export workbook</span>
        </button>
      </div>
      <small>WORKBOOK</small>
    </div>
  </template>
</template>
