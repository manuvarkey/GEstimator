import { nextTick } from "vue";
import type { TabulatorFull as Tabulator, CellComponent, RowComponent } from "tabulator-tables";
import { resetTablePosition } from "./tableSelection";

/** Cell coordinates survive authoritative row replacement after a backend edit. */
export function cellNavigation(table: Tabulator, host: HTMLElement, options: {
  busy: () => boolean;
  tree: boolean;
  save: (cell: CellComponent) => Promise<boolean>;
  settled: () => Promise<unknown>;
  position?: (id: string, field: string) => void;
}) {
  let position: { id: string; field: string } | undefined;
  let committed = Promise.resolve(true);
  let navigating = false;
  let alive = true;
  function rows() {
    const values: RowComponent[] = [];
    function flatten(items: RowComponent[]) {
      for (const row of items) {
        values.push(row);
        if (options.tree) flatten(row.getTreeChildren() || []);
      }
    }
    flatten(table.getRows());
    return values;
  }
  function cells() {
    const fields = table.getColumns().filter(column => column.isVisible() && column.getField()).map(column => column.getField());
    return rows().flatMap(row => fields.map(field => row.getCell(field)).filter((cell): cell is CellComponent => !!cell));
  }
  function editable(cell: CellComponent) {
    const definition = cell.getColumn().getDefinition();
    return !!definition.editor && definition.editable !== false && (typeof definition.editable !== "function" || definition.editable(cell));
  }
  function locate(id: string, field: string) {
    return rows().find(row => String(row.getData().id) === id)?.getCell(field) || undefined;
  }
  function mark(cell: CellComponent) {
    host.querySelectorAll(".cell-focused").forEach(element => element.classList.remove("cell-focused"));
    position = { id: String(cell.getData().id), field: cell.getField() };
    options.position?.(position.id, position.field);
    const element = cell.getElement();
    element.tabIndex = -1;
    element.classList.add("cell-focused");
  }
  async function focus(cell: CellComponent, edit = false, raw?: string) {
    await cell.getRow().scrollTo("nearest", false).catch(() => {});
    if (!alive) return;
    const viewport = host.querySelector(".tabulator-tableholder")?.getBoundingClientRect();
    const bounds = cell.getElement().getBoundingClientRect();
    const frozen = host.querySelector(".tabulator-header .tabulator-frozen-right")?.getBoundingClientRect();
    if (viewport && !cell.getColumn().getDefinition().frozen && (bounds.left < viewport.left || bounds.right > Math.min(viewport.right, frozen?.left ?? viewport.right))) {
      // Force scrolling only when needed; Tabulator's already-visible path does
      // not resolve its scroll promise when scrollIfVisible is false.
      await cell.getColumn().scrollTo("middle", true).catch(() => {});
    }
    mark(cell);
    table.deselectRow(); cell.getRow().select();
    resetTablePosition(table, cell.getRow());
    cell.getElement().focus({ preventScroll: true });
    if (edit && editable(cell)) {
      cell.edit();
      const input = cell.getElement().querySelector<HTMLInputElement | HTMLTextAreaElement>("input,textarea");
      if (input) { if (raw !== undefined) input.value = raw; input.focus(); }
    }
  }
  function outside(backward: boolean) {
    const root = host.closest('[role="dialog"]') || document;
    const candidates = Array.from(root.querySelectorAll<HTMLElement>('button,input,textarea,select,a[href],[tabindex="0"]'))
      .filter(element => !host.contains(element) && !element.matches(":disabled") && element.getBoundingClientRect().height > 0);
    const next = backward ? candidates.reverse().find(element => !!(host.compareDocumentPosition(element) & Node.DOCUMENT_POSITION_PRECEDING))
      : candidates.find(element => !!(host.compareDocumentPosition(element) & Node.DOCUMENT_POSITION_FOLLOWING));
    next?.focus();
  }
  async function navigate(event: KeyboardEvent, current: CellComponent, input?: HTMLInputElement | HTMLTextAreaElement) {
    event.preventDefault(); event.stopPropagation();
    const all = cells();
    const direction = event.key === "ArrowLeft" || event.key === "ArrowUp" || (event.key === "Tab" && event.shiftKey) ? -1 : 1;
    const vertical = ["ArrowUp", "ArrowDown", "Enter"].includes(event.key);
    const editing = !!input;
    const currentIndex = all.indexOf(current);
    const candidates = vertical ? all.filter(cell => cell.getField() === current.getField()) : all;
    const start = vertical ? candidates.indexOf(current) : currentIndex;
    let target: CellComponent | undefined;
    for (let index = start + direction; index >= 0 && index < candidates.length; index += direction) {
      const candidate = candidates[index]!;
      if ((editing || event.key === "Tab") && !editable(candidate)) continue;
      target = candidate; break;
    }
    const destination = target && { id: String(target.getData().id), field: target.getField() };
    const original = { id: String(current.getData().id), field: current.getField() };
    const raw = input?.value;
    navigating = true;
    committed = Promise.resolve(true);
    input?.blur(); // Installed Tabulator editor commits through cellEdited.
    const accepted = await committed;
    await nextTick();
    await options.settled();
    if (!alive) return;
    navigating = false;
    if (!accepted) {
      const cell = locate(original.id, original.field);
      if (cell) await focus(cell, true, raw);
      return;
    }
    if (!destination && event.key === "Tab") { outside(event.shiftKey); return; }
    const cell = destination ? locate(destination.id, destination.field) : locate(original.id, original.field);
    if (cell) await focus(cell, editing && !!destination);
  }
  // Tabulator measures a canceled cell before restoring its tree prefix.
  // Measure again after restoration so wrapped parent/leaf text keeps its height.
  table.on("cellEditCancelled", cell => cell.getRow().normalizeHeight());
  table.on("cellEditing", cell => mark(cell));
  table.on("cellEdited", cell => {
    committed = options.save(cell).catch(() => false);
  });
  return {
    clicked: mark,
    replaced(followSelection = false) {
      if (followSelection) {
        const row = table.getSelectedRows()[0];
        const cell = row && (row.getCell("description") || row.getCells().find(editable));
        if (cell) { mark(cell); return; }
      }
      if (position) { const cell = locate(position.id, position.field); if (cell) mark(cell); }
    },
    destroy() { alive = false; },
    keyboard(event: KeyboardEvent) {
      if (event.isComposing || event.altKey || event.ctrlKey || event.metaKey) return false;
      const input = (event.target as HTMLElement).closest<HTMLInputElement | HTMLTextAreaElement>("input,textarea");
      if (input && !input.closest(".tabulator-cell")) return false;
      if (input && event.key.startsWith("Arrow")) {
        // Editing owns caret movement and text selection; the grid owns arrows
        // only after the editor closes. Keep native input behavior intact.
        event.stopPropagation();
        return true;
      }
      if (input && event.key === "Escape") {
        const current = position && locate(position.id, position.field);
        if (!current) return false;
        event.preventDefault(); event.stopPropagation();
        current.cancelEdit();
        mark(current);
        current.getElement().focus({ preventScroll: true });
        return true;
      }
      if (input && event.shiftKey && event.key !== "Tab") return false;
      if (!input && event.shiftKey && event.key !== "Tab") return false;
      if (!["Enter", "F2", "Tab", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) return false;
      if (navigating || options.busy()) { event.preventDefault(); event.stopPropagation(); return true; }
      let current = position && locate(position.id, position.field);
      if (!input && current && !current.getRow().isSelected() && table.getSelectedRows().length) current = undefined;
      if (!current) {
        const selected = table.getSelectedRows()[0];
        current = selected && (selected.getCell("description") || selected.getCells().find(editable));
      }
      if (!current) current = cells().find(editable);
      if (!current) return false;
      if (!input && ["Enter", "F2"].includes(event.key)) {
        const cell = editable(current) ? current : event.key === "F2" ? current.getRow().getCells().find(editable) : undefined;
        if (!cell) {
          if (current.getRow().getCells().some(editable)) { event.preventDefault(); event.stopPropagation(); return true; }
          return false;
        }
        event.preventDefault(); event.stopPropagation(); void focus(cell, true); return true;
      }
      if (event.key === "F2") return false;
      void navigate(event, current, input || undefined);
      return true;
    },
  };
}
