import type { TabulatorFull as Tabulator, RowComponent } from "tabulator-tables";
import { ref } from "vue";
import { resetTablePosition } from "./tableSelection";
import { revealRow } from "./virtualRows";

const idle = 5000;

/**
 * Loads the page that holds the next match outside the rows on screen and
 * selects it. `from` is the id of the last (or, going back, first) row on
 * screen. Resolves true when a match was found.
 */
export type TypeAheadFind = (text: string, from: string | undefined, direction: 1 | -1) => Promise<boolean>;

/**
 * GTK3 TreeView interactive search: typing on a focused table opens a find
 * popup, selects the first matching row and leaves the rows unfiltered and
 * unranked. Up/Down jump to the previous/next match, Escape or Enter closes.
 * A row matches when every word occurs in its code, description or unit.
 * With `find`, the search continues on the other pages of a paged table.
 */
export function useTypeAhead(table: () => Tabulator | undefined, fields: () => string[], tree: () => boolean, find: () => TypeAheadFind | undefined) {
  const text = ref("");
  const missing = ref(false);
  const searching = ref(false);
  let timer: ReturnType<typeof setTimeout> | undefined;
  let sequence = 0;
  const close = () => { sequence++; text.value = ""; missing.value = false; searching.value = false; if (timer) clearTimeout(timer); timer = undefined; };
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
  function choose(t: Tabulator, row: RowComponent) {
    let parent = tree() ? row.getTreeParent() : false;
    while (parent) { if (!parent.isTreeExpanded()) parent.treeExpand(); parent = parent.getTreeParent(); }
    t.deselectRow();
    row.select();
    resetTablePosition(t, row);
    void revealRow(row);
    missing.value = false;
  }
  async function jump(direction: 1 | -1 | 0) {
    const t = table();
    if (!t) return;
    const all = rows();
    const remote = find();
    const current = t.getSelectedRows()[0];
    const index = current ? all.findIndex(row => row === current || row.getData().id === current.getData().id) : -1;
    const step = direction === -1 ? -1 : 1;
    // Typing keeps the current row when it still matches; Up/Down move past it.
    let start = direction === 0 ? Math.max(index, 0) : index + step;
    if (direction === -1 && index < 0) start = all.length - 1;
    for (let i = start; i >= 0 && i < all.length; i += step) {
      if (matches(all[i]!)) { choose(t, all[i]!); return; }
    }
    if (!remote) {
      // A single page wraps around, like GTK.
      const count = all.length;
      for (let n = 1; n <= count; n++) {
        const row = all[((start - step + step * n) % count + count) % count]!;
        if (matches(row)) { choose(t, row); return; }
      }
      missing.value = true;
      return;
    }
    // Category rows have no database id; anchor on the outermost item row.
    const items = all.filter(row => /^\d+$/.test(String(row.getData().id)));
    const anchor = step === 1 ? items[items.length - 1] : items[0];
    const token = ++sequence;
    searching.value = true;
    const found = await remote(text.value, anchor ? String(anchor.getData().id) : undefined, step).catch(() => false);
    if (token !== sequence) return;
    searching.value = false;
    missing.value = !found;
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
    if (open && (event.key === "ArrowUp" || event.key === "ArrowDown")) { stop(); touch(); void jump(event.key === "ArrowDown" ? 1 : -1); return true; }
    if (open && event.key === "Backspace") { stop(); text.value = text.value.slice(0, -1); touch(); if (text.value) void jump(0); else close(); return true; }
    if (event.key.length === 1 && !(event.key === " " && !open)) {
      stop(); text.value += event.key; touch(); void jump(0); return true;
    }
    return false;
  }
  return { text, missing, searching, key, close };
}
