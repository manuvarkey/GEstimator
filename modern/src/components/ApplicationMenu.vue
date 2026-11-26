<script setup lang="ts">
import { computed, ref } from "vue";
import Menu from "primevue/menu";
import type { MenuItem } from "primevue/menuitem";
import AppIcon from "./AppIcon.vue";
const props = defineProps<{
  busy: boolean;
  projectOpen: boolean;
  canExport: boolean;
  analysis: boolean;
  reports?: boolean;
}>();
const emit = defineEmits<{ action: [name: string] }>();
const menu = ref<InstanceType<typeof Menu>>();
const visible = ref(false);
function item(label: string, action: string, icon: string, disabled = false): MenuItem {
  return {
    label,
    appIcon: icon,
    disabled,
    command: () => emit("action", action),
  };
}
const items = computed<MenuItem[]>(() => [
  item("New project", "new", "file", props.busy),
  item("Open project…", "open", "folder", props.busy),
  item("Save project", "save", "save", props.busy || !props.projectOpen),
  item("Save project copy…", "save-copy", "save", props.busy || !props.projectOpen),
  item("Close project", "close-project", "close", props.busy || !props.projectOpen),
  item(
    props.reports ? "Export report…" : props.analysis ? "Export analysis…" : "Export workbook…",
    "export",
    "file",
    props.busy || !props.canExport,
  ),
  item("Project settings…", "settings", "settings", props.busy || !props.projectOpen),
  { separator: true },
  item("Program settings…", "program-settings", "settings", props.busy),
  item("Databases…", "libraries", "library", props.busy),
  item("Reconnect engine", "reconnect", "check", props.busy),
  item("Application manual", "manual", "help"),
  item("Keyboard shortcuts", "help", "help"),
  item("About GEstimator", "about", "help"),
  { separator: true },
  item("Close window", "close", "close", props.busy),
]);
</script>
<template>
  <button
    class="application-menu-button brand"
    aria-label="Application menu"
    aria-haspopup="menu"
    :aria-expanded="visible"
    aria-controls="application-menu"
    title="Application menu"
    @click="menu?.toggle($event)"
  >
    <span class="brand-mark">G<span>∑</span></span
    ><span>GEstimator</span><AppIcon name="down" :size="13" />
  </button>
  <Menu
    ref="menu"
    id="application-menu"
    popup
    :model="items"
    class="application-menu"
    @show="visible = true"
    @hide="visible = false"
    ><template #item="{ item, props: slotProps }"
      ><a v-bind="slotProps.action" class="application-menu-item"
        ><AppIcon :name="item.appIcon" :size="17" /><span>{{ item.label }}</span></a
      ></template
    ></Menu
  >
</template>
