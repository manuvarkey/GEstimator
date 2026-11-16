import type { TabulatorFull as Tabulator, RowComponent, CellComponent } from "tabulator-tables";

/** Shared pointer-drag selection; import pickers opt into whole rows only. */
export function rowDragSelection(table: Tabulator, host: HTMLElement, options: {
  tree: boolean;
  busy: () => boolean;
  anchor: () => string | undefined;
  cells?: boolean;
  position?: (cell: CellComponent) => void;
}) {
  let drag: { rows: RowComponent[]; start: number; x: number; y: number; base: RowComponent[]; moved: boolean; end: number; column: number; lastColumn: number; header: boolean } | undefined;
  let suppressClick = false;
  let resetClick = 0;
  let scrollFrame = 0;
  let pointer = { x: 0, y: 0 };
  let lastFrame = 0;
  function rowAt(target: EventTarget | null) {
    if (!(target instanceof Element)) return;
    const element = target.closest<HTMLElement>(".tabulator-row");
    // Tabulator's getRow(element) only searches root rows, not tree children.
    return element && host.contains(element) ? (drag?.rows || rows()).find(row => row.getElement() === element) : undefined;
  }
  function rows() {
    const result: RowComponent[] = [];
    const append = (values: RowComponent[]) => { for (const row of values) { result.push(row); if (options.tree) append(row.getTreeChildren() || []); } };
    append(table.getRows());
    return result;
  }
  function selectAt(target: EventTarget | null) {
    if (!drag) return;
    const row = rowAt(target);
    const columns = table.getColumns().filter(column => column.getField());
    const field = target instanceof Element ? target.closest("[tabulator-field]")?.getAttribute("tabulator-field") : undefined;
    const column = columns.findIndex(column => column.getField() === field);
    const index = drag.header ? drag.rows.length - 1 : row ? drag.rows.indexOf(row) : -1;
    if (index < 0 || (drag.moved && index === drag.end && column === drag.lastColumn)) return;
    drag.moved = true; drag.end = index; drag.lastColumn = column;
    host.querySelectorAll(".cell-range-selected").forEach(cell => cell.classList.remove("cell-range-selected"));
    // Crossing a group heading should not import all its off-page children.
    // Clicking a category still provides the explicit whole-category shortcut.
    const range = drag.rows.slice(Math.min(drag.start, index), Math.max(drag.start, index) + 1)
      .filter(row => row.getData().rowtype !== "Category");
    if (options.cells !== false && drag.column >= 0 && column >= 0) for (const selectedRow of range) {
      for (const selectedColumn of columns.slice(Math.min(drag.column, column), Math.max(drag.column, column) + 1)) {
        const cell = selectedRow.getCell(selectedColumn.getField());
        if (cell) cell.getElement()?.classList.add("cell-range-selected");
      }
    }
    table.deselectRow();
    table.selectRow(Array.from(new Set([...drag.base, ...range])));
  }
  function scroll(time: number) {
    if (!drag || options.busy()) { end(); return; }
    const viewport = host.querySelector<HTMLElement>('.tabulator-tableholder');
    if (drag.moved && !drag.header && viewport) {
      const bounds = viewport.getBoundingClientRect();
      const elapsed = Math.min(32, lastFrame ? time - lastFrame : 16.7) / 16.7;
      if (pointer.x >= bounds.left - 24 && pointer.x <= bounds.right + 24) {
        const distance = pointer.y < bounds.top + 28 ? pointer.y - bounds.top - 28
          : pointer.y > bounds.bottom - 28 ? pointer.y - bounds.bottom + 28 : 0;
        const speed = Math.sign(distance) * Math.min(24, Math.abs(distance) * .55);
        if (speed) {
          viewport.scrollTop += speed * elapsed;
          // Hit-test inside the viewport, even when the pointer is above/below it.
          selectAt(document.elementFromPoint(Math.max(bounds.left + 2, Math.min(bounds.right - 2, pointer.x)),
            Math.max(bounds.top + 2, Math.min(bounds.bottom - 2, pointer.y))));
        }
      }
    }
    lastFrame = time;
    scrollFrame = requestAnimationFrame(scroll);
  }
  function move(event: MouseEvent) {
    if (!drag) return;
    if (!(event.buttons & 1) || options.busy()) { end(); return; }
    pointer = { x: event.clientX, y: event.clientY };
    if (!drag.moved && Math.hypot(pointer.x - drag.x, pointer.y - drag.y) < 4) return;
    // Start scrolling even if the initial move goes directly beyond the table.
    drag.moved = true;
    selectAt(event.target);
    event.preventDefault();
  }
  function end() {
    if (drag?.moved) {
      suppressClick = true;
      resetClick = window.setTimeout(() => { suppressClick = false; }, 0);
    }
    drag = undefined;
    cancelAnimationFrame(scrollFrame);
    lastFrame = 0;
    document.removeEventListener("mousemove", move);
    document.removeEventListener("mouseup", end);
    window.removeEventListener("blur", end);
  }
  function start(event: MouseEvent) {
    if (event.button !== 0 || options.busy() || (event.target as Element).closest("input,textarea,select,button,[contenteditable=true]")) return;
    const row = rowAt(event.target);
    const header = (event.target as Element).closest(".tabulator-col");
    if (header && options.cells === false) return;
    if (!row && !header || (event.target as Element).closest(".tabulator-col-resize-handle")) return;
    const values = rows();
    const field = (event.target as Element).closest("[tabulator-field]")?.getAttribute("tabulator-field");
    const column = table.getColumns().filter(column => column.getField()).findIndex(column => column.getField() === field);
    host.querySelectorAll(".cell-range-selected").forEach(cell => cell.classList.remove("cell-range-selected"));
    const anchored = event.shiftKey ? values.findIndex(row => String(row.getData().id) === options.anchor()) : -1;
    if (row && field) options.position?.(row.getCell(field));
    drag = { rows: values, start: header ? 0 : anchored >= 0 ? anchored : values.indexOf(row!), x: event.clientX, y: event.clientY,
      base: event.ctrlKey || event.metaKey ? table.getSelectedRows() : [], moved: false, end: -1, column, lastColumn: column, header: !!header };
    event.preventDefault();
    window.getSelection()?.removeAllRanges();
    host.focus({ preventScroll: true });
    pointer = { x: event.clientX, y: event.clientY };
    document.addEventListener("mousemove", move);
    document.addEventListener("mouseup", end);
    window.addEventListener("blur", end);
    scrollFrame = requestAnimationFrame(scroll);
  }
  function click(event: MouseEvent) {
    if (suppressClick) { event.preventDefault(); event.stopImmediatePropagation(); suppressClick = false; }
  }
  function clearRange(event: KeyboardEvent) {
    if (event.key === "Escape" && !(event.target as Element).closest("input,textarea,[contenteditable=true]"))
      host.querySelectorAll(".cell-range-selected").forEach(cell => cell.classList.remove("cell-range-selected"));
  }
  host.addEventListener("mousedown", start, true);
  host.addEventListener("click", click, true);
  host.addEventListener("keydown", clearRange, true);
  return () => {
    end();
    window.clearTimeout(resetClick);
    host.removeEventListener("mousedown", start, true);
    host.removeEventListener("click", click, true);
    host.removeEventListener("keydown", clearRange, true);
  };
}
