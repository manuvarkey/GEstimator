import type { TabulatorFull as Tabulator, RowComponent } from "tabulator-tables";

/** Plain pointer-drag selection for read-only item pickers, using public table APIs. */
export function rowDragSelection(table: Tabulator, host: HTMLElement, options: {
  tree: boolean;
  busy: () => boolean;
  anchor: () => string | undefined;
}) {
  let drag: { rows: RowComponent[]; start: number; x: number; y: number; base: RowComponent[]; moved: boolean; end: number } | undefined;
  let suppressClick = false;
  let resetClick = 0;
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
  function move(event: MouseEvent) {
    if (!drag) return;
    if (!(event.buttons & 1) || options.busy()) { end(); return; }
    if (!drag.moved && Math.hypot(event.clientX - drag.x, event.clientY - drag.y) < 4) return;
    const row = rowAt(event.target);
    const index = row ? drag.rows.indexOf(row) : -1;
    if (index < 0 || (drag.moved && index === drag.end)) return;
    drag.moved = true; drag.end = index;
    // Crossing a group heading should not import all its off-page children.
    // Clicking a category still provides the explicit whole-category shortcut.
    const range = drag.rows.slice(Math.min(drag.start, index), Math.max(drag.start, index) + 1)
      .filter(row => row.getData().rowtype !== "Category");
    table.deselectRow();
    table.selectRow(Array.from(new Set([...drag.base, ...range])));
    event.preventDefault();
  }
  function end() {
    if (drag?.moved) {
      suppressClick = true;
      resetClick = window.setTimeout(() => { suppressClick = false; }, 0);
    }
    drag = undefined;
    document.removeEventListener("mousemove", move);
    document.removeEventListener("mouseup", end);
  }
  function start(event: MouseEvent) {
    if (event.button !== 0 || options.busy()) return;
    const row = rowAt(event.target);
    if (!row) return;
    const values = rows();
    const anchored = event.shiftKey ? values.findIndex(row => String(row.getData().id) === options.anchor()) : -1;
    drag = { rows: values, start: anchored >= 0 ? anchored : values.indexOf(row), x: event.clientX, y: event.clientY,
      base: event.ctrlKey || event.metaKey ? table.getSelectedRows() : [], moved: false, end: -1 };
    event.preventDefault();
    window.getSelection()?.removeAllRanges();
    host.focus({ preventScroll: true });
    document.addEventListener("mousemove", move);
    document.addEventListener("mouseup", end);
  }
  function click(event: MouseEvent) {
    if (suppressClick) { event.preventDefault(); event.stopImmediatePropagation(); suppressClick = false; }
  }
  host.addEventListener("mousedown", start, true);
  host.addEventListener("click", click, true);
  return () => {
    end();
    window.clearTimeout(resetClick);
    host.removeEventListener("mousedown", start, true);
    host.removeEventListener("click", click, true);
  };
}
