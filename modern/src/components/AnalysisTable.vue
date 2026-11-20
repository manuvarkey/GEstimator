<script setup lang="ts">
import { onMounted, onBeforeUnmount, nextTick, watch, ref } from "vue";
import {
  TabulatorFull as Tabulator,
  type CellComponent,
  type RowComponent,
} from "tabulator-tables";
import "tabulator-tables/dist/css/tabulator.min.css";
import type { AnalysisRow } from "../backend";
import { tableTextEditor, tableInputEditor } from "../tableTextEditor";
import { rowDragSelection } from "../rowDragSelection";
import { tableSelection, resetTablePosition } from "../tableSelection";
import { cellNavigation } from "../cellNavigation";
import { moneyCell, moneyFormatKey } from "../numberFormatting";
import { overflowTooltip } from "../cellTooltip";
const props = defineProps<{
  rows: AnalysisRow[];
  busy: boolean;
  active: boolean;
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
let stopDragSelection: (() => void) | undefined;
let anchorId: string | undefined;
let fitFrame = 0;
const scrollable = ref(false);
let resizeObserver: ResizeObserver;
async function fitVisibleTable(force = false) {
  await built;
  await nextTick();
  if (!active || !props.active) return;
  cancelAnimationFrame(fitFrame);
  fitFrame = requestAnimationFrame(() => {
    if (active && props.active && element.value?.clientWidth) {
      // Keep every column accessible at small sizes; normal desktop panes fit.
      scrollable.value = element.value.clientWidth < 500;
      // Remarks need room beside the fixed numeric columns; hide them in a
      // narrow pane that must fit, show them again when it scrolls or widens.
      const remarks = table.getColumn("remarks");
      const showRemarks = scrollable.value || element.value.clientWidth >= 720;
      if (remarks && remarks.isVisible() !== showRemarks) showRemarks ? remarks.show() : remarks.hide();
      table.redraw(force && !element.value.querySelector('.tabulator-editing'));
    }
  });
}
watch(() => props.active, () => fitVisibleTable(true), { flush: "post" });
watch(moneyFormatKey, async () => {
  await built;
  if (!active) return;
  for (const row of table.getRows()) { row.reformat(); for (const child of row.getTreeChildren() || []) child.reformat(); }
  void fitVisibleTable();
});
const isResource = (cell: CellComponent) => cell.getData().kind === "Resource";
const isTotal = (cell: CellComponent) => cell.getData().kind === "GroupTotal";
/** A group's total is shown on a "TOTAL of …" line after its resources, not on the heading. */
function displayRows(rows: AnalysisRow[]): AnalysisRow[] {
  return rows.map(row => row.kind !== "Group" ? row : {
    ...row,
    _children: [...(row._children || []), {
      id: row.id + ":total", kind: "GroupTotal", description: "TOTAL of " + (row.code || row.description || "group"),
      value: "", amount: row.amount, _displayOnly: true,
    } as AnalysisRow],
  });
}
function amountCell(cell: CellComponent) {
  return cell.getData().kind === "Group" ? "" : moneyCell(cell);
}
function kindBadge(cell: CellComponent) {
  const row = cell.getData() as AnalysisRow;
  const label = document.createElement("span");
  label.className = `row-badge kind-${row.kind.toLowerCase()}`;
  label.textContent =
    row.kind === "Resource" ? row.code || "Resource" : row.kind === "GroupTotal" ? "Total" : row.kind;
  label.title = row.kind === "Resource" ? `Resource ${row.code}` : row.kind === "GroupTotal" ? "Group total" : row.kind;
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
    replacement = table.replaceData(displayRows(rows));
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
    void fitVisibleTable();
  },
);
onMounted(() => {
  table = new Tabulator(element.value!, {
    height: "100%",
    layout: "fitColumns",
    layoutColumnsOnNewData: true,
    data: displayRows(props.rows),
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
    selectableRowsCheck: row => !row.getData()._displayOnly,
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
        width: 34,
        resizable: false,
        cellClick: (_e, cell) => cell.getRow().toggleSelect(),
      },
      { title: "TYPE / CODE", field: "kind", formatter: kindBadge, width: 118, minWidth: 64, widthShrink: 1 },
      {
        title: "DESCRIPTION",
        field: "description",
        editor: tableTextEditor,
        editorParams: () => ({ grow: false }),
        editable: cell => !isResource(cell) && !isTotal(cell),
        formatter: "textarea",
        variableHeight: true,
        minWidth: 80,
      },
      {
        // Notes on a resource line, e.g. what a substituted resource stands for.
        title: "REMARKS",
        field: "remarks",
        cssClass: "analysis-line-remarks",
        editor: tableTextEditor,
        editorParams: () => ({ grow: false }),
        editable: cell => isResource(cell),
        formatter: "textarea",
        variableHeight: true,
        // Shares the free width with the description, so narrow panes still fit.
        widthGrow: 0.5,
        minWidth: 60,
      },
      {
        title: "UNIT",
        field: "unit",
        width: 56,
        minWidth: 32,
        widthShrink: 1,
        tooltip: overflowTooltip(),
      },
      {
        title: "QTY / FACTOR",
        field: "value",
        editor: tableInputEditor,
        hozAlign: "right",
        width: 87,
        minWidth: 56,
        widthShrink: 1,
        tooltip: overflowTooltip(),
        editable: (cell) =>
          !["Group", "Subtotal", "GroupTotal"].includes(cell.getData().kind),
      },
      { title: "RATE", field: "effective_rate", formatter: moneyCell, hozAlign: "right", width: 110, minWidth: 56, widthShrink: 1, tooltip: overflowTooltip(moneyCell) },
      {
        title: "AMOUNT",
        field: "amount",
        formatter: amountCell,
        hozAlign: "right",
        width: 114,
        minWidth: 60,
        widthShrink: 1,
        tooltip: overflowTooltip(amountCell),
        frozen: true,
      },
    ],
  });
  navigation = cellNavigation(table, element.value!, {
    busy: () => props.busy, tree: true, settled: () => replacement,
    position: id => { anchorId = id; },
    save: cell => props.saveCell(cell.getData() as AnalysisRow, cell.getField(), String(cell.getValue())),
  });
  stopDragSelection = rowDragSelection(table, element.value!, {
    tree: true, busy: () => props.busy, anchor: () => anchorId,
    position: cell => navigation.clicked(cell),
  });
  built = new Promise<void>((resolve) => table.on("tableBuilt", resolve));
  resizeObserver = new ResizeObserver(() => void fitVisibleTable());
  resizeObserver.observe(element.value!);
  table.on("rowContext", (_event, row) => {
    if (!row.isSelected()) {
      table.deselectRow();
      row.select();
    }
  });
  table.on("rowSelectionChanged", (data) =>
    emit("selection", data as AnalysisRow[]),
  );
  table.on("cellClick", (event, cell) => { if (isTotal(cell)) return; navigation.clicked(cell); if (!(event as MouseEvent).shiftKey) resetTablePosition(table, cell.getRow()); });
  void fitVisibleTable();
});
defineExpose({
  prepare: async () => {
    await built;
    await replacement;
    cancelAnimationFrame(fitFrame);
    table.redraw(true);
  },
  focus: async () => { await built; await replacement; element.value?.focus({ preventScroll: true }); },
  clearSelection: () => table?.deselectRow(),
});
onBeforeUnmount(() => {
  active = false;
  cancelAnimationFrame(fitFrame);
  resizeObserver?.disconnect();
  navigation?.destroy();
  stopDragSelection?.();
  table?.destroy();
});
</script>
<template>
  <div
    ref="element"
    class="analysis-table tabulator compact fit-table"
    :class="{ blocked: busy, 'analysis-scrollable': scrollable }"
    :aria-busy="busy"
    aria-label="Rate analysis table"
    tabindex="0"
    @keydown.capture="keyboard"
  />
</template>
