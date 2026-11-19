<script setup lang="ts">
import { onMounted, onBeforeUnmount, nextTick, ref, watch } from "vue";
import { tableTextEditor, tableInputEditor } from "../tableTextEditor";
import { cellNavigation } from "../cellNavigation";
import { rowDragSelection } from "../rowDragSelection";
import {
  TabulatorFull as Tabulator,
  type ColumnDefinition,
  type RowComponent,
} from "tabulator-tables";
import "tabulator-tables/dist/css/tabulator.min.css";
import { tableSelection, resetTablePosition } from "../tableSelection";
import { isRowClipboard } from "../rowClipboard";
import { formatMoney, moneyFormatKey } from "../numberFormatting";
const props = defineProps<{
  rows: { id: string; [key: string]: any }[];
  columns: ColumnDefinition[];
  busy: boolean;
  active?: boolean;
  tree?: boolean;
  dragSelectRows?: boolean;
  rowOnlySelection?: boolean;
  activateOnDoubleClick?: boolean;
  label?: string;
  selectIds?: string[];
  saveCell?: (row: any, field: string, value: string) => Promise<boolean>;
  actions?: { label: string; action: string; itemOnly?: boolean; single?: boolean }[];
}>();
const emit = defineEmits<{
  selection: [rows: { id: string; [key: string]: any }[]];
  paste: [changes: { id: string; field: string; value: string }[]];
  edit: [row: { id: string; [key: string]: any }, field: string, value: string];
  activate: [row: { id: string; [key: string]: any }, modifiers?: { ctrl: boolean }];
  pasteRows: [data: string];
  action: [operation: string];
}>();
const element = ref<HTMLDivElement>();
let table: Tabulator;
let ready: Promise<void>;
let alive = true;
let replacingRows = false;
let anchor: { id: string; field: string } | undefined;
let navigation: ReturnType<typeof cellNavigation>;
let replacement: Promise<unknown> = Promise.resolve();
let savedPosition = { top: 0, left: 0 };
let suspended = false;
let renderPosition: { top: number; left: number } | undefined;
let revealFrame = 0;
function rememberPosition(event: Event) {
  const viewport = event.target as HTMLElement;
  if (!suspended && props.active !== false && viewport.classList.contains("tabulator-tableholder") && viewport.getClientRects().length)
    savedPosition = { top: viewport.scrollTop, left: viewport.scrollLeft };
}
function restorePosition() {
  const viewport = element.value?.querySelector<HTMLElement>(".tabulator-tableholder");
  if (viewport) { viewport.scrollTop = savedPosition.top; viewport.scrollLeft = savedPosition.left; }
}
async function redraw(force = false) {
  await ready;
  await replacement;
  await nextTick();
  if (!alive || props.active === false || !element.value?.clientHeight) return;
  const viewport = element.value?.querySelector<HTMLElement>(".tabulator-tableholder");
  const position = props.active === undefined && viewport ? { top: viewport.scrollTop, left: viewport.scrollLeft } : { ...savedPosition };
  // A hidden virtual table can retain an empty render window at the same size.
  // Force its rows to rebuild after layout, even if no resize was observed.
  table.redraw(force);
  savedPosition = position;
  restorePosition();
  cancelAnimationFrame(revealFrame);
  revealFrame = requestAnimationFrame(() => {
    if (!alive || props.active === false) return;
    if (force && !element.value?.querySelector('.tabulator-editing')) table.redraw(true);
    restorePosition();
    suspended = false;
  });
}
watch(() => props.active, async active => {
  if (active === false) {
    const viewport = element.value?.querySelector<HTMLElement>(".tabulator-tableholder");
    if (viewport?.getClientRects().length) savedPosition = { top: viewport.scrollTop, left: viewport.scrollLeft };
    suspended = true; return;
  }
  await nextTick();
  await redraw(true);
});
let stopDragSelection: (() => void) | undefined;
defineExpose({
  focus: async () => { await ready; await replacement; await nextTick(); element.value?.focus({ preventScroll: true }); },
  patchRows: async (updates: { id: string; [key: string]: any }[]) => {
    await ready;
    const collect = (rows: RowComponent[]): RowComponent[] => rows.flatMap(row => [row, ...collect(row.getTreeChildren() || [])]);
    const rows = collect(table.getRows());
    for (const update of updates) {
      const row = rows.find(row => row.getData().id === update.id);
      if (!row) continue;
      const treeLabelChanged = props.tree && "description" in update &&
        row.getCell("description") && row.getCell("description").getValue() !== update.description;
      await row.update(update);
      // Row.update rewrites the tree cell without running the tree layout pass.
      if (treeLabelChanged) row.reformat();
    }
  },
  redraw,
  clearSelection: async () => { await ready; if (alive) { table.deselectRow(); resetTablePosition(table); } },
});
function editorColumns(columns: ColumnDefinition[]) {
  return columns.map(column => ({ ...column,
    ...(["rate", "effective_rate", "amount"].includes(column.field || "") ? { tooltip: (_event: UIEvent, cell: import("tabulator-tables").CellComponent) => formatMoney(cell.getValue()), formatter: (cell: import("tabulator-tables").CellComponent) => {
      const value = cell.getValue();
      // Preserve the project table's convention for empty/zero schedule rates.
      return column.field === "rate" && cell.getData().rowtype === "Schedule" && Number(value) === 0 ? "" : formatMoney(value);
    } } : {}),
    ...(column.editor === "textarea" ? { editor: tableTextEditor }
      : column.editor === "input" ? { editor: tableInputEditor } : {}),
  }));
}
watch(moneyFormatKey, async () => {
  await ready;
  if (!alive) return;
  const reformat = (rows: RowComponent[]) => rows.forEach(row => { row.reformat(); if (props.tree) reformat(row.getTreeChildren()); });
  reformat(table.getRows());
  await redraw();
});
function keyboard(event: KeyboardEvent) {
  if (!props.rowOnlySelection && navigation?.keyboard(event)) return;
  if (!table || props.busy || (event.target as HTMLElement).closest("input,textarea,select,[contenteditable=true]")) return;
  if (tableSelection(event, table, props.busy, !!props.tree)) return;
  if (event.key === "F2") {
    const anchored = anchor ? table.getRow(anchor.id) : undefined;
    const row = anchored && anchored.isSelected() ? anchored : table.getSelectedRows()[0];
    if (row) {
      const cells = row.getCells();
      const cell = anchor && row.getData().id === anchor.id ? row.getCell(anchor.field) : cells.find(cell => cell.getField() === "description") || cells.find(cell => !!cell.getColumn().getDefinition().editor);
      if (cell) { event.preventDefault(); event.stopPropagation(); cell.edit(); }
    }
    return;
  }
  if (event.key === "Enter" && !event.ctrlKey && !event.metaKey && !event.altKey && table.getSelectedRows().length === 1) {
    event.preventDefault();
    event.stopPropagation();
    emit("activate", table.getSelectedData()[0], { ctrl: event.ctrlKey || event.metaKey });
  }
}
function paste(event: ClipboardEvent) {
  if (
    props.busy ||
    (event.target as HTMLElement).closest(
      "input,textarea,[contenteditable=true]",
    )
  )
    return;
  const text = event.clipboardData?.getData("text/plain");
  if (text === undefined) return;
  if (isRowClipboard(text)) {
    event.preventDefault();
    event.stopPropagation();
    emit("pasteRows", text);
    return;
  }
  if (!anchor) return;
  event.preventDefault();
  const rows: any[] = [];
  const flatten = (values: any[]) => {
    for (const row of values) {
      rows.push(row);
      if (props.tree && row.isTreeExpanded()) flatten(row.getTreeChildren() || []);
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
  [() => props.rows, () => props.columns, () => props.selectIds],
  async ([rows, columns, selectIds], [previousRows, previousColumns, previousIds]) => {
    await ready;
    if (!alive) return;
    const ids = new Set(selectIds !== previousIds ? selectIds : table.getSelectedData().map((r) => r.id));
    replacingRows = true;
    try {
      const columnsChanged = JSON.stringify(columns) !== JSON.stringify(previousColumns);
      if (columnsChanged) table.setColumns(editorColumns(columns));
      if (selectIds !== previousIds) table.deselectRow();
      if (rows !== previousRows || columnsChanged) {
        const viewport = element.value?.querySelector<HTMLElement>(".tabulator-tableholder");
        const top = viewport?.scrollTop || 0, left = viewport?.scrollLeft || 0;
        replacement = table.replaceData(rows);
        await replacement;
        if (viewport && selectIds === previousIds) { viewport.scrollTop = top; viewport.scrollLeft = left; }
      }
      const restoreSelection = (rows: RowComponent[]) => {
        for (const row of rows) {
          if (ids.delete(row.getData().id)) row.select();
          if (props.tree) {
            row.treeExpand();
            restoreSelection(row.getTreeChildren());
          }
        }
      };
      if (alive) restoreSelection(table.getRows());
      if (alive && selectIds !== previousIds) {
        for (const row of table.getSelectedRows()) {
          if (props.tree) { let parent = row.getTreeParent(); while (parent) { parent.treeExpand(); parent = parent.getTreeParent(); } }
        }
        const selected = table.getSelectedRows();
        if (selected.length) void selected[0]!.scrollTo("nearest", false).catch(() => {});
      }
    } finally {
      replacingRows = false;
      navigation?.replaced(selectIds !== previousIds);
    }
    if (alive) emit("selection", table.getSelectedData());
  },
);
onMounted(() => {
  table = new Tabulator(element.value!, {
    height: "100%",
    layout: "fitColumns",
    index: "id",
    dataTree: props.tree,
    dataTreeStartExpanded: true,
    dataTreeChildIndent: 20,
    dataTreeSelectPropagate: false,
    dataTreeExpandElement: '<span class="tree-spacer" aria-hidden="true"></span>',
    dataTreeCollapseElement: '<span class="tree-spacer" aria-hidden="true"></span>',
    dataTreeElementColumn: "description",
    selectableRows: true,
    selectableRowsRangeMode: "click",
    editTriggerEvent: "dblclick",
    clipboard: false,
    rowContextMenu: (_event, row) => {
      if (props.busy || !props.actions?.length) return [];
      if (!row.isSelected()) { table.deselectRow(); row.select(); }
      const selected = table.getSelectedData();
      return props.actions.filter(item => (!item.single || selected.length === 1) && (!item.itemOnly || selected.every(row => row.rowtype !== "Category")))
        .map(item => ({ label: item.label, action: () => emit("action", item.action) }));
    },
    columnDefaults: {
      editorParams: () => ({ enterSubmit: true, shiftEnterNewLine: true, ctrlEnterNewLine: true, metaEnterNewLine: true }),
      headerSort: false,
      resizable: true,
      vertAlign: "middle",
      formatter: "textarea",
      variableHeight: true,
    },
    columns: editorColumns(props.columns),
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
  navigation = cellNavigation(table, element.value!, {
    busy: () => props.busy, tree: !!props.tree, settled: () => replacement,
    position: (id, field) => { anchor = { id, field }; },
    save: async cell => {
      const row = cell.getData(), field = cell.getField(), value = String(cell.getValue());
      if (props.saveCell) return props.saveCell(row, field, value);
      emit("edit", row as any, field, value); return true;
    },
  });
  ready = new Promise<void>((resolve) =>
    table.on("tableBuilt", () => {
      void table.replaceData(props.rows);
      resolve();
    }),
  );
  // Visibility and resize callbacks can redraw after the explicit reveal pass.
  // Preserve pixel position around the renderer itself, independent of observer order.
  table.on("renderStarted", () => {
    const viewport = element.value?.querySelector<HTMLElement>(".tabulator-tableholder");
    renderPosition = !replacingRows && props.active !== false && viewport?.getClientRects().length
      ? { top: viewport.scrollTop, left: viewport.scrollLeft } : undefined;
  });
  table.on("renderComplete", () => {
    const viewport = element.value?.querySelector<HTMLElement>(".tabulator-tableholder");
    if (viewport && renderPosition) { viewport.scrollTop = renderPosition.top; viewport.scrollLeft = renderPosition.left; }
    renderPosition = undefined;
  });
  if (props.dragSelectRows) stopDragSelection = rowDragSelection(table, element.value!, {
    tree: !!props.tree, busy: () => props.busy, anchor: () => anchor?.id,
    cells: !props.rowOnlySelection, position: cell => {
      anchor = { id: String(cell.getData().id), field: cell.getField() };
      if (!props.rowOnlySelection) navigation.clicked(cell);
    },
  });
  element.value!.tabIndex = 0;
  element.value!.addEventListener("paste", paste);
  element.value!.addEventListener("scroll", rememberPosition, true);
  table.on("cellClick", (event, cell) => {
    if (!props.rowOnlySelection) navigation.clicked(cell);
    anchor = { id: cell.getData().id, field: cell.getField() };
    if (!(event as MouseEvent).shiftKey) resetTablePosition(table, cell.getRow());
  });
  table.on("rowSelectionChanged", (rows) => {
    if (!replacingRows) emit("selection", rows);
  });
  table.on("cellDblClick", (event, cell) => {
    const mouse = event as MouseEvent;
    if (props.activateOnDoubleClick && !props.busy) emit("activate", cell.getData() as { id: string; [key: string]: any }, { ctrl: mouse.ctrlKey || mouse.metaKey });
  });
});
onBeforeUnmount(() => {
  alive = false;
  cancelAnimationFrame(revealFrame);
  navigation?.destroy();
  stopDragSelection?.();
  element.value?.removeEventListener("paste", paste);
  element.value?.removeEventListener("scroll", rememberPosition, true);
  table?.destroy();
});
</script>
<template>
  <div
    ref="element"
    class="analysis-table tabulator project-grid"
    :class="{ blocked: busy, 'row-drag-select': dragSelectRows }"
    :aria-busy="busy"
    :aria-label="label || 'Project table'"
    @keydown.capture="keyboard"
  />
</template>
