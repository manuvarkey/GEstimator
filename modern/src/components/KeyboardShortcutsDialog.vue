<script setup lang="ts">
import Dialog from "primevue/dialog";

const visible = defineModel<boolean>({ required: true });
const shortcutGroups = [
  {
    title: "Project and search",
    items: [
      ["Open project", "Ctrl / ⌘ + O"],
      ["Save project", "Ctrl / ⌘ + S"],
      ["Save project copy", "Ctrl / ⌘ + Shift + S"],
      ["Focus search in current view or selection dialog", "Ctrl / ⌘ + F"],
      ["New project tab / Close project tab", "Ctrl / ⌘ + T / W"],
      ["Next / previous project tab", "Ctrl / ⌘ + Tab / Shift + Tab"],
    ],
  },
  {
    title: "Rows and clipboard",
    items: [
      ["Undo / Redo", "Ctrl / ⌘ + Z / Y"],
      ["Copy / Paste rows", "Ctrl / ⌘ + C / V"],
      ["Cut resources (Paste moves them)", "Ctrl / ⌘ + X"],
      ["Repair stored item order", "Ctrl / ⌘ + Shift + R"],
      ["Add item / measurement record / analysis resource", "Ctrl / ⌘ + I"],
      ["Add schedule subitem / custom analysis resource", "Ctrl / ⌘ + Shift + I"],
      ["Duplicate selected rows", "Ctrl / ⌘ + D"],
      ["Delete selected rows", "Delete"],
      ["Move project item or measurement record", "Alt + Up / Down"],
    ],
  },
  {
    title: "Cell editing and selection",
    items: [
      ["Edit focused cell", "Enter / F2"],
      ["Cancel cell edit and retain focus", "Escape"],
      ["Accept and edit next / previous cell", "Tab / Shift + Tab"],
      ["Move caret / select text while editing", "Arrow keys / Shift + arrows"],
      ["Navigate cells outside editing", "Arrow keys"],
      ["New line while editing text", "Shift / Ctrl + Enter"],
      ["Navigate editable cells", "Tab / Shift + Tab"],
      ["Select table rows", "Up / Down / Home / End"],
      ["Extend table selection", "Shift + Up / Down / Home / End"],
      ["Select current table page / Clear selection", "Ctrl / ⌘ + A / Escape"],
    ],
  },
  {
    title: "Editor actions",
    items: [
      ["Open selected schedule analysis", "Ctrl / ⌘ + E"],
      ["Colour selected schedule items", "Ctrl / ⌘ + M"],
      ["Edit resource / Measurement properties", "Ctrl / ⌘ + E"],
      ["Browse attached schedule / resource library", "Ctrl / ⌘ + L"],
      ["Apply analysis or records / Confirm draft discard", "Ctrl / ⌘ + Enter / Escape"],
    ],
  },
  {
    title: "Ribbon navigation",
    items: [
      ["Focus ribbon tabs", "Left / Right / Home / End"],
      ["Activate focused ribbon tab", "Enter / Space"],
    ],
  },
];
</script>

<template>
  <Dialog v-model:visible="visible" modal header="Keyboard shortcuts" class="workspace-dialog shortcuts-dialog"
    ><div class="shortcut-groups">
      <section v-for="group in shortcutGroups" :key="group.title" class="shortcut-group" :aria-label="group.title">
        <h3>{{ group.title }}</h3>
        <div class="shortcut-list">
          <div v-for="[label, key] in group.items" :key="label">
            <span>{{ label }}</span
            ><kbd>{{ key }}</kbd>
          </div>
        </div>
      </section>
    </div>
    <p class="field-hint">
      Text fields keep their normal editing shortcuts. Copied rows can be pasted in the same editor in another
      GEstimator window. Measurement records require the same template; whole-item schedule links match codes in the
      destination. Analysis resource paste uses the selected resource group. In project tables, Ctrl+D duplicates and
      Delete removes selected items; these shortcuts apply to records when the measurement record table has focus.
      Spreadsheet cell paste keeps its normal Ctrl+V behavior.
    </p></Dialog
  >
</template>

<style scoped>
.shortcut-group + .shortcut-group {
  margin-top: 20px;
}
.shortcut-group h3 {
  margin: 0;
  padding-bottom: 6px;
  color: var(--accent);
  font-size: var(--text-size-ui);
  border-bottom: 1px solid var(--line);
}
/* One row per shortcut: the label takes the free width, the keys never break. */
:global(.workspace-dialog.shortcuts-dialog) {
  width: min(94vw, 760px);
}
.shortcut-list > div {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 15px;
  padding: 11px 0;
  border-bottom: 1px solid var(--line-soft);
  font-size: var(--text-size-ui);
  color: var(--muted);
}
.shortcut-list kbd {
  white-space: nowrap;
}
</style>
