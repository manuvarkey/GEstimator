<script setup lang="ts">
// Keep ribbon groups as siblings so RibbonToolbar can measure their overflow.
import AppIcon from "./AppIcon.vue";
import type { RowKind } from "../backend";

defineProps<{
  canEdit: boolean;
  hasGroups: boolean;
  selectionCount: number;
  hasProject: boolean;
  sidebar: boolean;
  inspector: boolean;
}>();
const emit = defineEmits<{
  command:
    | [operation: "add", params: { kind: RowKind; value: string }]
    | [operation: "move", params: { delta: -1 | 1 }]
    | [operation: "duplicate" | "analysis.insert_template" | "copy" | "paste" | "delete"];
  showResource: [mode: "library" | "custom"];
  showTemplate: [];
  toggleSidebar: [];
  toggleInspector: [];
  exportWorkbook: [];
  showImport: [];
}>();

const rowKinds: {
  kind: RowKind;
  icon: string;
  label: string;
  hint: string;
  value: string;
}[] = [
  {
    kind: "Group",
    icon: "group",
    label: "Resource group",
    hint: "Insert a resource group for materials, labour or equipment at the current selection.",
    value: "",
  },
  {
    kind: "Subtotal",
    icon: "sum",
    label: "Subtotal",
    hint: "Insert a subtotal that captures the cumulative total as the base for later weighted additions.",
    value: "",
  },
  {
    kind: "Weight",
    icon: "percent",
    label: "Weighted addition",
    hint: "Insert a weighted addition calculated as a fraction of the latest group or subtotal base.",
    value: "0.01",
  },
  {
    kind: "Multiply",
    icon: "multiply",
    label: "Multiplier",
    hint: "Insert a multiplier that replaces the total with the last base multiplied by a factor.",
    value: "1",
  },
  {
    kind: "Round",
    icon: "round",
    label: "Round off",
    hint: "Insert a rounding step for the cumulative analysis total using the existing currency rules.",
    value: "2",
  },
];
</script>

<template>
  <div class="ribbon-group">
    <div class="ribbon-actions">
      <button
        class="ribbon-action"
        aria-label="Add resources from database"
        :disabled="!canEdit || !hasGroups"
        @click="emit('showResource', 'library')"
      >
        <AppIcon name="database" /><span class="ribbon-label">From database</span>
      </button>
      <button
        class="ribbon-action"
        aria-label="Add custom resource"
        :disabled="!canEdit || !hasGroups"
        @click="emit('showResource', 'custom')"
      >
        <AppIcon name="resource" /><span class="ribbon-label">Custom resource</span>
      </button>
      <button
        class="ribbon-action"
        aria-label="Duplicate"
        :disabled="!canEdit || !selectionCount"
        @click="emit('command', 'duplicate')"
      >
        <AppIcon name="duplicate" /><span class="ribbon-label">Duplicate</span>
      </button>
    </div>
    <small>RESOURCES</small>
  </div>
  <div class="ribbon-group">
    <div class="ribbon-actions ribbon-actions-wide">
      <button
        v-for="row in rowKinds"
        :key="row.kind"
        class="ribbon-action"
        :aria-label="row.label"
        :title="row.hint"
        :disabled="!canEdit"
        @click="emit('command', 'add', { kind: row.kind, value: row.value })"
      >
        <AppIcon :name="row.icon" /><span class="ribbon-label">{{ row.label }}</span>
      </button>
      <button
        class="ribbon-action"
        aria-label="Default analysis rows"
        title="Insert the default calculation rows configured in Program Settings into this draft. Undo restores the previous draft."
        :disabled="!canEdit"
        @click="emit('command', 'analysis.insert_template')"
      >
        <AppIcon name="file" /><span class="ribbon-label">Default rows</span>
      </button>
      <button
        class="ribbon-action"
        aria-label="Custom analysis template…"
        title="Configure, save and preview reusable calculation rows before inserting them as one undoable batch."
        :disabled="!canEdit"
        @click="emit('showTemplate')"
      >
        <AppIcon name="settings" /><span class="ribbon-label">Custom template</span>
      </button>
    </div>
    <small>INSERT</small>
  </div>
  <div class="ribbon-group">
    <div class="ribbon-actions">
      <button
        class="ribbon-action ribbon-icon"
        aria-label="Copy rows"
        title="Copy selected analysis rows and resource definitions to the system clipboard for use in another GEstimator window (Ctrl+C)."
        :disabled="!canEdit || !selectionCount"
        @click="emit('command', 'copy')"
      >
        <AppIcon name="copy" /><span class="ribbon-label">Copy rows</span>
      </button>
      <button
        class="ribbon-action ribbon-icon"
        aria-label="Paste rows"
        title="Insert analysis rows copied from this or another GEstimator window at the current selection. Existing project resource definitions are reused by code (Ctrl+V)."
        :disabled="!canEdit"
        @click="emit('command', 'paste')"
      >
        <AppIcon name="paste" /><span class="ribbon-label">Paste rows</span>
      </button>

      <button
        class="ribbon-action ribbon-icon danger"
        aria-label="Delete"
        title="Remove the selected rows from this analysis draft. Use Undo to restore them."
        :disabled="!canEdit || !selectionCount"
        @click="emit('command', 'delete')"
      >
        <AppIcon name="trash" /><span class="ribbon-label">Delete</span>
      </button>
    </div>
    <small>EDIT</small>
  </div>
  <div class="ribbon-group">
    <div class="ribbon-actions">
      <button
        class="ribbon-action ribbon-icon"
        aria-label="Move up"
        title="Move the selected analysis row one position earlier in the calculation sequence."
        :disabled="!canEdit || selectionCount !== 1"
        @click="emit('command', 'move', { delta: -1 })"
      >
        <AppIcon name="up" /><span class="ribbon-label">Move up</span></button
      ><button
        class="ribbon-action ribbon-icon"
        aria-label="Move down"
        title="Move the selected analysis row one position later in the calculation sequence."
        :disabled="!canEdit || selectionCount !== 1"
        @click="emit('command', 'move', { delta: 1 })"
      >
        <AppIcon name="down" /><span class="ribbon-label">Move down</span>
      </button>
    </div>
    <small>SEQUENCE</small>
  </div>
  <div class="ribbon-group">
    <div class="ribbon-actions">
      <button
        class="ribbon-action"
        :aria-label="sidebar ? 'Hide explorer' : 'Show explorer'"
        @click="emit('toggleSidebar')"
      >
        <AppIcon name="panel-left" /><span class="ribbon-label">{{ sidebar ? "Hide explorer" : "Show explorer" }}</span>
      </button>
      <button
        class="ribbon-action"
        :aria-label="inspector ? 'Hide analysis inspector' : 'Show analysis inspector'"
        :title="
          inspector
            ? 'Hide the selected-row inspector to give the analysis table more room.'
            : 'Show the inspector to edit the selected analysis row and resource definition.'
        "
        :class="{ pressed: !inspector }"
        :aria-pressed="!inspector"
        @click="emit('toggleInspector')"
      >
        <AppIcon name="panel" />
        <span class="ribbon-label">{{ inspector ? "Hide inspector" : "Show inspector" }}</span>
      </button>
    </div>
    <small>VIEW</small>
  </div>
  <div class="ribbon-group">
    <div class="ribbon-actions">
      <button
        class="ribbon-action"
        aria-label="Export analysis"
        title="Export this analysis, including unapplied draft edits, to an Excel workbook."
        :disabled="!canEdit || !hasProject"
        @click="emit('exportWorkbook')"
      >
        <AppIcon name="export" /><span class="ribbon-label">Export analysis</span>
      </button>
      <button
        class="ribbon-action"
        aria-label="Import analysis"
        title="Preview an Excel worksheet range and insert its calculation rows into this draft. The import can be undone."
        :disabled="!canEdit || !hasProject"
        @click="emit('showImport')"
      >
        <AppIcon name="import" /><span class="ribbon-label">Import analysis</span>
      </button>
    </div>
    <small>PROJECT</small>
  </div>
</template>
