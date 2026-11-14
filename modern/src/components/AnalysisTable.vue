<script setup lang="ts">
import { onMounted, onBeforeUnmount, watch, ref } from "vue";
import {
  TabulatorFull as Tabulator,
  type CellComponent,
  type RowComponent,
} from "tabulator-tables";
import "tabulator-tables/dist/css/tabulator.min.css";
import type { AnalysisRow } from "../backend";
import { tableSelection, resetTablePosition } from "../tableSelection";
import { cellNavigation } from "../cellNavigation";
const props = defineProps<{
  rows: AnalysisRow[];
  busy: boolean;
  compact: boolean;
  saveCell: (row: AnalysisRow, field: string, value: string) => Promise<boolean>;
}>();
const emit = defineEmits<{
  selection: [rows: AnalysisRow[]];
  edit: [row: AnalysisRow, field: string, value: string];
  action: [method: string];
}>();
const element = ref<HTMLDivElement>();
let table: Tabulator;
let built: Promise<void>;
let active = true;
let navigation: ReturnType<typeof cellNavigation>;
let replacement: Promise<unknown> = Promise.resolve();
const isResource = (cell: CellComponent) => cell.getData().kind === "Resource";
function kindBadge(cell: CellComponent) {
  const row = cell.getData() as AnalysisRow;
  const label = document.createElement("span");
  label.className = `row-badge kind-${row.kind.toLowerCase()}`;
  label.textContent =
    row.kind === "Resource" ? row.code || "Resource" : row.kind;
  label.title = row.kind === "Resource" ? `Resource ${row.code}` : row.kind;
  return label;
}
function keyboard(event: KeyboardEvent) {
  if (navigation?.keyboard(event)) return;
  if (!table || props.busy || (event.target as HTMLElement).closest("input,textarea,select,[contenteditable=true]")) return;
  if (tableSelection(event, table, props.busy)) return;
  if (event.key === "F2" && table.getSelectedRows().length === 1) {
    event.preventDefault(); event.stopPropagation();
    table.getSelectedRows()[0]!.getCell("description").edit();
  }
}
watch(
  () => props.rows,
  async (rows) => {
    await built;
    if (!active) return;
    const selected = table.getSelectedData().map((r) => r.id);
    replacement = table.replaceData(rows);
    await replacement;
    table.selectRow(selected.filter((id) => rows.some((r) => r.id === id)));
    // Resource rows are children; select them using their row components.
    for (const row of table.getRows())
      for (const child of row.getTreeChildren() || [])
        if (selected.includes(child.getData().id)) child.select();
    for (const row of table.getRows()) {
      row.treeExpand();
    }
    navigation?.replaced();
  },
);
watch(
  () => props.compact,
  () => requestAnimationFrame(() => table?.redraw(true)),
);
onMounted(() => {
  table = new Tabulator(element.value!, {
    height: "100%",
    layout: "fitColumns",
    index: "id",
    editTriggerEvent: "dblclick",
    dataTree: true,
    dataTreeStartExpanded: true,
    dataTreeExpandElement: '<span class="tree-spacer" aria-hidden="true"></span>',
    dataTreeCollapseElement: '<span class="tree-spacer" aria-hidden="true"></span>',
    dataTreeElementColumn: "kind",
    dataTreeSelectPropagate: false,
    selectableRows: true,
    selectableRowsRangeMode: "click",
    clipboard: false,
    placeholder: "Add a resource group to begin your analysis.",
    columnDefaults: { headerSort: false, resizable: true, vertAlign: "middle", editorParams: () => ({ enterSubmit: true, shiftEnterNewLine: true, ctrlEnterNewLine: true, metaEnterNewLine: true }) },
    rowFormatter: (row) => {
      row.getElement().dataset.kind = row.getData().kind;
    },
    rowContextMenu: [
      { label: "Copy selected rows", action: () => emit("action", "copy") },
      {
        label: "Duplicate selected rows",
        action: () => emit("action", "duplicate"),
      },
      { label: "Paste into group", action: () => emit("action", "paste") },
      { separator: true },
      { label: "Delete selected rows", action: () => emit("action", "delete") },
    ],
    columns: [
      {
        title: "",
        formatter: "rowSelection",
        titleFormatter: "rowSelection",
        headerSort: false,
        hozAlign: "center",
        width: 38,
        resizable: false,
        cellClick: (_e, cell) => cell.getRow().toggleSelect(),
      },
      { title: "TYPE / CODE", field: "kind", formatter: kindBadge, width: 128 },
      {
        title: "DESCRIPTION",
        field: "description",
        editor: "textarea",
        formatter: "textarea",
        variableHeight: true,
        minWidth: 235,
        widthGrow: 3,
      },
      {
        title: "UNIT",
        field: "unit",
        editor: "input",
        editable: isResource,
        width: 60,
      },
      {
        title: "QTY / FACTOR",
        field: "value",
        editor: "input",
        hozAlign: "right",
        width: 102,
        editable: (cell) =>
          !["Group", "Subtotal"].includes(cell.getData().kind),
      },
      {
        title: "BASE RATE",
        field: "rate",
        editor: "input",
        editable: isResource,
        hozAlign: "right",
        width: 90,
      },
      {
        title: "VAT %",
        field: "vat",
        editor: "input",
        editable: isResource,
        hozAlign: "right",
        width: 65,
      },
      {
        title: "DISC. %",
        field: "discount",
        editor: "input",
        editable: isResource,
        hozAlign: "right",
        width: 65,
      },
      {
        title: "AMOUNT",
        field: "amount",
        hozAlign: "right",
        width: 110,
        frozen: true,
      },
    ],
  });
  navigation = cellNavigation(table, element.value!, {
    busy: () => props.busy, tree: true, settled: () => replacement,
    save: cell => props.saveCell(cell.getData() as AnalysisRow, cell.getField(), String(cell.getValue())),
  });
  built = new Promise<void>((resolve) => table.on("tableBuilt", resolve));
  table.on("rowContext", (_event, row) => {
    if (!row.isSelected()) {
      table.deselectRow();
      row.select();
    }
  });
  table.on("rowSelectionChanged", (data) =>
    emit("selection", data as AnalysisRow[]),
  );
  table.on("cellClick", (event, cell) => { navigation.clicked(cell); if (!(event as MouseEvent).shiftKey) resetTablePosition(table, cell.getRow()); });
  table.on("tableBuilt", () => {
    void table.replaceData(props.rows);
  });
});
defineExpose({ clearSelection: () => table?.deselectRow() });
onBeforeUnmount(() => {
  active = false;
  navigation?.destroy();
  table?.destroy();
});
</script>
<template>
  <div
    ref="element"
    class="analysis-table tabulator"
    :class="{ blocked: busy, compact }"
    :aria-busy="busy"
    aria-label="Rate analysis table"
    tabindex="0"
    @keydown.capture="keyboard"
  />
</template>
