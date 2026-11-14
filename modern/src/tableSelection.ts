import type { TabulatorFull as Tabulator, RowComponent } from "tabulator-tables";

const positions = new WeakMap<Tabulator, { anchor: string; focus: string }>();
const id = (row: RowComponent) => String(row.getData().id);
export function resetTablePosition(table: Tabulator, row?: RowComponent) {
  if (row) positions.set(table, { anchor: id(row), focus: id(row) });
  else positions.delete(table);
}
export function tableSelection(event: KeyboardEvent, table: Tabulator, busy: boolean) {
  if (busy || event.defaultPrevented || (event.target as HTMLElement).closest("input,textarea,select,[contenteditable=true]")) return false;
  const selectAll = (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "a";
  if (!selectAll && !["Escape", "ArrowUp", "ArrowDown", "Home", "End"].includes(event.key)) return false;
  if (event.altKey || (!selectAll && (event.ctrlKey || event.metaKey))) return false;
  event.preventDefault();
  event.stopPropagation();
  const rows: RowComponent[] = [];
  function flatten(values: RowComponent[]) {
    for (const row of values) {
      rows.push(row);
      if (row.isTreeExpanded()) flatten(row.getTreeChildren() || []);
    }
  }
  flatten(table.getRows());
  if (event.key === "Escape") { table.deselectRow(); resetTablePosition(table); return true; }
  if (selectAll) { table.selectRow(rows); resetTablePosition(table); return true; }
  if (!rows.length) return true;
  const selected = table.getSelectedRows();
  const previous = positions.get(table);
  const currentId = previous?.focus || (selected.length ? id(selected[selected.length - 1]!) : "");
  const index = rows.findIndex(row => id(row) === currentId);
  const next = event.key === "Home" ? 0 : event.key === "End" ? rows.length - 1
    : index < 0 ? (event.key === "ArrowUp" ? rows.length - 1 : 0)
    : Math.max(0, Math.min(rows.length - 1, index + (event.key === "ArrowUp" ? -1 : 1)));
  const target = rows[next]!;
  const anchorId = event.shiftKey ? previous?.anchor || currentId || id(target) : id(target);
  const anchor = rows.findIndex(row => id(row) === anchorId);
  table.deselectRow();
  table.selectRow(event.shiftKey && anchor >= 0 ? rows.slice(Math.min(anchor, next), Math.max(anchor, next) + 1) : [target]);
  positions.set(table, { anchor: anchorId, focus: id(target) });
  void target.scrollTo("nearest", false).catch(() => {});
  return true;
}
