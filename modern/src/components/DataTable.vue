<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch } from "vue";
import {
  TabulatorFull as Tabulator,
  type ColumnDefinition,
  type RowComponent,
} from "tabulator-tables";
import "tabulator-tables/dist/css/tabulator.min.css";
import { tableSelection, resetTablePosition } from "../tableSelection";
const props = defineProps<{
  rows: { id: string; [key: string]: any }[];
  columns: ColumnDefinition[];
  busy: boolean;
  tree?: boolean;
  label?: string;
}>();
const emit = defineEmits<{
  selection: [rows: { id: string; [key: string]: any }[]];
  paste: [changes: { id: string; field: string; value: string }[]];
  edit: [row: { id: string; [key: string]: any }, field: string, value: string];
  activate: [row: { id: string; [key: string]: any }];
}>();
const element = ref<HTMLDivElement>();
let table: Tabulator;
let ready: Promise<void>;
let alive = true;
let replacingRows = false;
let anchor: { id: string; field: string } | undefined;
function keyboard(event: KeyboardEvent) {
  if (!table || props.busy || (event.target as HTMLElement).closest("input,textarea,select,[contenteditable=true]")) return;
  if (tableSelection(event, table, props.busy)) return;
  if (event.key === "Enter" && !event.ctrlKey && !event.metaKey && !event.altKey && table.getSelectedRows().length === 1) {
    event.preventDefault();
    event.stopPropagation();
    emit("activate", table.getSelectedData()[0]);
  }
}
function paste(event: ClipboardEvent) {
  if (
    props.busy ||
    !anchor ||
    (event.target as HTMLElement).closest(
      "input,textarea,[contenteditable=true]",
    )
  )
    return;
  const text = event.clipboardData?.getData("text/plain");
  if (text === undefined) return;
  event.preventDefault();
  const rows: any[] = [];
  const flatten = (values: any[]) => {
    for (const row of values) {
      rows.push(row);
      if (row.isTreeExpanded()) flatten(row.getTreeChildren() || []);
    }
  };
  flatten(table.getRows());
  const start = rows.findIndex((row) => row.getData().id === anchor!.id);
  if (start < 0) return;
  const columns = props.columns;
  const columnStart = columns.findIndex(
    (column) => column.field === anchor!.field,
  );
  if (columnStart < 0) return;
  const selection = table.getSelectedData();
  const changes: { id: string; field: string; value: string }[] = [];
  const add = (row: any, field: string, value: string) => {
    const cell = row.getCell(field);
    if (!cell) return;
    const definition = cell.getColumn().getDefinition();
    if (!definition.editor) return;
    const editable = definition.editable;
    if (
      editable === false ||
      (typeof editable === "function" && !editable(cell))
    )
      return;
    changes.push({ id: row.getData().id, field, value });
  };
  const lineFeed = String.fromCharCode(10);
  let normalized = text.split(String.fromCharCode(13)).join("");
  if (normalized.endsWith(lineFeed)) normalized = normalized.slice(0, -1);
  if (selection.length > 1) {
    for (const row of rows)
      if (selection.some((selected) => selected.id === row.getData().id))
        add(row, anchor.field, normalized);
  } else {
    for (const [rowIndex, line] of normalized.split(lineFeed).entries()) {
      const row = rows[start + rowIndex];
      if (!row) break;
      for (const [columnIndex, value] of line
        .split(String.fromCharCode(9))
        .entries()) {
        const field = columns[columnStart + columnIndex]?.field;
        if (field) add(row, field, value);
      }
    }
  }
  if (changes.length) emit("paste", changes);
}

watch(
  () => props.rows,
  async (rows) => {
    await ready;
    if (!alive) return;
    const ids = new Set(table.getSelectedData().map((r) => r.id));
    replacingRows = true;
    try {
      await table.replaceData(rows);
      const restoreSelection = (rows: RowComponent[]) => {
        for (const row of rows) {
          if (!ids.size) break;
          if (ids.delete(row.getData().id)) row.select();
          if (props.tree) restoreSelection(row.getTreeChildren());
        }
      };
      if (alive) restoreSelection(table.getRows());
    } finally {
      replacingRows = false;
    }
    if (alive) emit("selection", table.getSelectedData());
  },
);
watch(
  () => props.columns,
  async (columns, previous) => {
    if (JSON.stringify(columns) === JSON.stringify(previous)) return;
    await ready;
    if (alive) {
      table.setColumns(columns);
      await table.replaceData(props.rows);
    }
  },
);
onMounted(() => {
  table = new Tabulator(element.value!, {
    height: "100%",
    layout: "fitColumns",
    index: "id",
    dataTree: props.tree,
    dataTreeStartExpanded: true,
    dataTreeElementColumn: "description",
    selectableRows: true,
    selectableRowsRangeMode: "click",
    editTriggerEvent: "dblclick",
    clipboard: "copy",
    columnDefaults: {
      headerSort: false,
      resizable: true,
      vertAlign: "middle",
      formatter: "textarea",
      variableHeight: true,
    },
    columns: props.columns,
    placeholder: "No items. Add an item or adjust your search.",
    rowFormatter: (row) => {
      const data = row.getData();
      const element = row.getElement();
      element.dataset.kind = data.rowtype === "Category" ? "Group" : "Resource";
      const colour = data.colour;
      if (data.rowtype === "Schedule" && typeof colour === "string" && /^#[0-9a-f]{6}$/i.test(colour)) {
        const [red, green, blue] = [1, 3, 5].map((offset) => {
          const channel = parseInt(colour.slice(offset, offset + 2), 16) / 255;
          return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
        });
        const luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue;
        element.dataset.scheduleColour = colour;
        element.style.setProperty("--schedule-row-background", colour);
        element.style.setProperty("--schedule-row-text", luminance > 0.179 ? "#000" : "#fff");
      } else {
        delete element.dataset.scheduleColour;
        element.style.removeProperty("--schedule-row-background");
        element.style.removeProperty("--schedule-row-text");
      }
    },
  });
  ready = new Promise<void>((resolve) =>
    table.on("tableBuilt", () => {
      void table.replaceData(props.rows);
      resolve();
    }),
  );
  element.value!.tabIndex = 0;
  element.value!.addEventListener("paste", paste);
  table.on("cellClick", (_event, cell) => {
    anchor = { id: cell.getData().id, field: cell.getField() };
    resetTablePosition(table, cell.getRow());
  });
  table.on("rowSelectionChanged", (rows) => {
    if (!replacingRows) emit("selection", rows);
  });
  table.on("cellEdited", (cell) =>
    emit(
      "edit",
      cell.getData() as { id: string; [key: string]: any },
      cell.getField(),
      String(cell.getValue()),
    ),
  );
});
onBeforeUnmount(() => {
  alive = false;
  element.value?.removeEventListener("paste", paste);
  table?.destroy();
});
</script>
<template>
  <div
    ref="element"
    class="analysis-table tabulator project-grid"
    :class="{ blocked: busy }"
    :aria-busy="busy"
    :aria-label="label || 'Project table'"
    @keydown.capture="keyboard"
  />
</template>
