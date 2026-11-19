<script setup lang="ts">
import { computed, ref } from "vue";
import AppIcon from "./AppIcon.vue";
import { activeDocument, documentCode, documentColour, documents, type DocumentTab } from "../documents";

// Vertical document rail, following Open Planner Studio's ProjectRail: one
// tile per open project, a dirty marker, a hover flyout and a dashed add tile.
const props = defineProps<{ busy: boolean }>();
const emit = defineEmits<{ switch: [id: string]; close: [id: string]; add: [] }>();
const hover = ref<{ tab: DocumentTab; top: number }>();
const tabs = computed(() => documents.value.map(tab => {
  const name = tab.open ? tab.title || "Untitled workspace" : "Empty tab";
  return { tab, name, code: tab.open ? documentCode(name) : "–", colour: documentColour(tab.id), active: tab.id === activeDocument.value };
}));
function show(event: Event, tab: DocumentTab) {
  hover.value = { tab, top: (event.currentTarget as HTMLElement).getBoundingClientRect().top };
}
function hide(tab: DocumentTab) {
  if (hover.value?.tab.id === tab.id) hover.value = undefined;
}
function keyboard(event: KeyboardEvent, index: number) {
  const items = Array.from(document.querySelectorAll<HTMLElement>(".document-rail-item"));
  const next = event.key === "ArrowDown" ? (index + 1) % items.length
    : event.key === "ArrowUp" ? (index + items.length - 1) % items.length
    : event.key === "Home" ? 0 : event.key === "End" ? items.length - 1 : -1;
  if (next >= 0) { event.preventDefault(); items[next]?.focus(); }
  else if (event.key === "Delete" && !props.busy) { event.preventDefault(); emit("close", documents.value[index]!.id); }
}
</script>
<template>
  <nav class="document-rail" :class="{ single: documents.length === 1 }" aria-label="Open projects">
    <div class="document-rail-list" role="tablist" aria-orientation="vertical" aria-label="Open projects">
      <div v-for="(item, index) in tabs" :key="item.tab.id" class="document-rail-entry"
        @mouseenter="show($event, item.tab)" @mouseleave="hide(item.tab)">
        <button class="document-rail-item" :class="{ active: item.active }" role="tab"
          :style="{ '--doc-colour': item.colour }"
          :aria-selected="item.active" :aria-label="item.name + (item.tab.dirty ? ' (unsaved changes)' : '')"
          :tabindex="item.active ? 0 : -1" :disabled="busy && !item.active"
          @click="emit('switch', item.tab.id)" @auxclick.prevent="$event.button === 1 && !busy && emit('close', item.tab.id)"
          @keydown="keyboard($event, index)" @focus="show($event, item.tab)" @blur="hide(item.tab)">
          {{ item.code }}
          <span v-if="item.tab.dirty" class="document-rail-dirty" aria-hidden="true" />
        </button>
        <button class="document-rail-close" :aria-label="'Close ' + item.name" title="Close project tab (Ctrl+W)" :disabled="busy"
          @click.stop="emit('close', item.tab.id)"><AppIcon name="close" :size="12" /></button>
      </div>
    </div>
    <button class="document-rail-add" aria-label="New project tab" title="Open a new project tab (Ctrl+T). New and opened projects use a new tab when the current one holds a project." :disabled="busy" @click="emit('add')">
      <AppIcon name="plus" :size="16" />
    </button>
    <div v-if="hover" class="document-rail-flyout" :style="{ top: hover.top + 'px' }" role="tooltip">
      <div class="document-rail-flyout-name"><span class="document-rail-dot" :style="{ '--doc-colour': documentColour(hover.tab.id) }" />{{ hover.tab.open ? hover.tab.title || 'Untitled workspace' : 'Empty tab' }}</div>
      <div v-if="hover.tab.path" class="document-rail-flyout-path">{{ hover.tab.path }}</div>
      <div v-else-if="hover.tab.open" class="document-rail-flyout-path">Not saved to a file yet</div>
      <div v-if="hover.tab.dirty" class="document-rail-flyout-dirty">Unsaved changes</div>
    </div>
  </nav>
</template>
