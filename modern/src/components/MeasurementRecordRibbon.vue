<script setup lang="ts">
// Keep ribbon groups as siblings so RibbonToolbar can measure their overflow.
import AppIcon from "./AppIcon.vue";

defineProps<{ busy: boolean; detailBusy: boolean; hasSelection: boolean }>();
const emit = defineEmits<{
  action: [operation: "add" | "duplicate" | "copy" | "paste" | "delete"] | [operation: "move", delta: -1 | 1];
  insertMultiple: [];
  importRecords: [];
  showProperties: [];
}>();
</script>

<template>
  <div class="ribbon-group">
    <div class="ribbon-actions">
      <button
        class="ribbon-action"
        aria-label="Add record"
        :disabled="busy || detailBusy"
        @click="emit('action', 'add')"
      >
        <AppIcon name="plus" /><span class="ribbon-label">Add record</span>
      </button>
      <button
        class="ribbon-action"
        aria-label="Add multiple records"
        :disabled="busy || detailBusy"
        @click="emit('insertMultiple')"
      >
        <AppIcon name="rows" /><span class="ribbon-label">Add multiple records</span>
      </button>
      <button
        class="ribbon-action"
        aria-label="Duplicate record"
        :disabled="busy || !hasSelection"
        @click="emit('action', 'duplicate')"
      >
        <AppIcon name="duplicate" /><span class="ribbon-label">Duplicate record</span>
      </button>
    </div>
    <small>CREATE</small>
  </div>
  <div class="ribbon-group">
    <div class="ribbon-actions">
      <button
        class="ribbon-action ribbon-icon"
        aria-label="Copy record"
        :disabled="busy || !hasSelection"
        @click="emit('action', 'copy')"
      >
        <AppIcon name="copy" /><span class="ribbon-label">Copy record</span>
      </button>
      <button
        class="ribbon-action ribbon-icon"
        aria-label="Paste record"
        :disabled="busy"
        @click="emit('action', 'paste')"
      >
        <AppIcon name="paste" /><span class="ribbon-label">Paste record</span>
      </button>
      <button
        class="ribbon-action ribbon-icon danger"
        aria-label="Delete record"
        :disabled="busy || !hasSelection"
        @click="emit('action', 'delete')"
      >
        <AppIcon name="trash" /><span class="ribbon-label">Delete record</span>
      </button>
    </div>
    <small>EDIT</small>
  </div>
  <div class="ribbon-group">
    <div class="ribbon-actions">
      <button
        class="ribbon-action ribbon-icon"
        aria-label="Move record up"
        :disabled="busy || !hasSelection"
        @click="emit('action', 'move', -1)"
      >
        <AppIcon name="up" /><span class="ribbon-label">Move up</span>
      </button>
      <button
        class="ribbon-action ribbon-icon"
        aria-label="Move record down"
        :disabled="busy || !hasSelection"
        @click="emit('action', 'move', 1)"
      >
        <AppIcon name="down" /><span class="ribbon-label">Move down</span>
      </button>
    </div>
    <small>ARRANGE</small>
  </div>
  <div class="ribbon-group">
    <div class="ribbon-actions">
      <button
        class="ribbon-action"
        aria-label="Import records…"
        :disabled="busy || detailBusy"
        @click="emit('importRecords')"
      >
        <AppIcon name="import" /><span class="ribbon-label">Import records</span>
      </button>
      <button
        class="ribbon-action"
        aria-label="Properties…"
        :disabled="busy || detailBusy"
        @click="emit('showProperties')"
      >
        <AppIcon name="settings" /><span class="ribbon-label">Properties</span>
      </button>
    </div>
    <small>MEASUREMENT</small>
  </div>
</template>
