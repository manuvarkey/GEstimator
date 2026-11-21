import type { TabulatorFull as Tabulator, RowComponent } from "tabulator-tables";
import { ref } from "vue";
import { resetTablePosition } from "./tableSelection";
import { revealRow } from "./virtualRows";

const idle = 5000;

/**
 * GTK3 TreeView interactive search: typing on a focused table opens a find
 * popup, selects the first matching row and leaves the rows unfiltered and
 * unranked. Up/Down jump to the previous/next match, Escape or Enter closes.
 * A row matches when every word occurs in its code, description or unit.
 */
export function useTypeAhead(table: () => Tabulator | undefined, fields: () => string[], tree: () => boolean) {
  const text = ref("");
  const missing = ref(false);
  let timer: ReturnType<typeof setTimeout> | undefined;
  const close = () => { text.value = ""; missing.value = false; if (timer) clearTimeout(timer); timer = undefined; };
  const touch = () => { if (timer) clearTimeout(timer); timer = setTimeout(close, idle); };
  function rows() {
    const out: RowComponent[] = [];
    const visit = (list: RowComponent[]) => {
      for (const row of list) {
        if (!row.getData()._displayOnly) out.push(row);
        if (tree()) visit(row.getTreeChildren() || []);
      }
    };
    visit(table()?.getRows() || []);
    return out;
  }
  function matches(row: RowComponent) {
    const data = row.getData();
    const haystack = fields().map(field => String(data[field] ?? "")).join(" ").toLowerCase();
    return text.value.toLowerCase().split(/\s+/).filter(Boolean).every(word => haystack.includes(word));
  }
  function jump(direction: 1 | -1 | 0) {
    const t = table();
    const all = rows();
    if (!t || !all.length) return;
    const current = t.getSelectedRows()[0];
    let start = current ? all.findIndex(row => row === current || row.getData().id === current.getData().id) : -1;
    if (direction === 0) start = start < 0 ? -1 : start - 1;
    const count = all.length;
    for (let step = 1; step <= count; step++) {
      const index = ((start + (direction === -1 ? -step : step)) % count + count) % count;
      const row = all[index]!;
      if (!matches(row)) continue;
      let parent = tree() ? row.getTreeParent() : false;
      while (parent) { if (!parent.isTreeExpanded()) parent.treeExpand(); parent = parent.getTreeParent(); }
      t.deselectRow();
      row.select();
      resetTablePosition(t, row);
      void revealRow(row);
      missing.value = false;
      return;
    }
    missing.value = true;
  }
  /** Returns true when the key was consumed. */
  function key(event: KeyboardEvent) {
    if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey) return false;
    if ((event.target as HTMLElement).closest("input,textarea,select,[contenteditable=true]")) return false;
    const open = text.value !== "";
    const stop = () => { event.preventDefault(); event.stopPropagation(); };
    if (open && (event.key === "Escape" || event.key === "Enter")) {
      // Enter closes the popup and still activates the selected row.
      if (event.key === "Escape") { stop(); close(); return true; }
      close(); return false;
    }
    if (open && (event.key === "ArrowUp" || event.key === "ArrowDown")) { stop(); touch(); jump(event.key === "ArrowDown" ? 1 : -1); return true; }
    if (open && event.key === "Backspace") { stop(); text.value = text.value.slice(0, -1); touch(); if (text.value) jump(0); else close(); return true; }
    if (event.key.length === 1 && !(event.key === " " && !open)) {
      stop(); text.value += event.key; touch(); jump(0); return true;
    }
    return false;
  }
  return { text, missing, key, close };
}
