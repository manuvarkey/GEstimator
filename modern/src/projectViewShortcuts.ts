import type { GridRow, View } from "./projectViewTypes";

/** Resolve project editor shortcuts for both grid and workspace key handlers. */
export function projectViewShortcut(
  event: KeyboardEvent,
  context: {
    projectOpen: boolean;
    busy: boolean;
    browsingSource: boolean;
    view: View;
    editingRecords: boolean;
    hasSelectedRecord: boolean;
    selected: readonly GridRow[];
  },
) {
  const { projectOpen, busy, browsingSource, view, editingRecords, hasSelectedRecord, selected } = context;
  if (event.defaultPrevented || !projectOpen || busy || document.querySelector('[role="dialog"]')) return;
  const target = event.target as HTMLElement;
  if (target.closest("input,textarea,select,[contenteditable=true]")) return;

  // Draft finish and history shortcuts are handled before source and grid guards.
  const mod = event.ctrlKey || event.metaKey;
  const key = event.key.toLowerCase();
  if (mod && editingRecords && event.key === "Enter") return "applyRecords";
  if (mod && editingRecords && event.key === "Escape") return "discardRecords";
  if (mod && (key === "z" || key === "y")) return key === "y" || event.shiftKey ? "redo" : "undo";
  if (browsingSource) return;

  // Editor actions can run from outside the table. Selection remains in the editor.
  const one = selected.length === 1 ? selected[0] : undefined;
  if (mod && key === "i") {
    if (editingRecords) return "add";
    return event.shiftKey && view === "schedule" ? "addSubitem" : "add";
  }
  if (mod && key === "e" && one) {
    if (view === "measurement") return "editProperties";
    if (view === "schedule" && one.rowtype === "Schedule") return "editAnalysis";
    if (view === "resources") return one.rowtype === "Category" ? "consume" : "editResource";
  }
  if (mod && key === "l" && view !== "measurement") return "database";
  if (mod && key === "m" && view === "schedule" && selected.some((row) => row.rowtype === "Schedule")) return "colour";

  // Clipboard keys are captured even without a usable selection.
  if (!target.closest(".project-grid")) return;
  const hasSelection = editingRecords ? hasSelectedRecord : selected.length > 0;
  if (mod && key === "x" && view === "resources" && !editingRecords)
    return selected.some((row) => row.rowtype !== "Category") ? "cut" : "consume";
  if (mod && key === "c") return hasSelection ? "copy" : "consume";
  if (!hasSelection) return;

  if (mod && key === "d")
    return editingRecords || view === "measurement" || (one && one.rowtype !== "Category") ? "duplicate" : "consume";
  if (event.key === "Delete") return "delete";
  if (event.altKey && (event.key === "ArrowUp" || event.key === "ArrowDown")) {
    if (!editingRecords && view !== "measurement" && !one) return "consume";
    return event.key === "ArrowUp" ? "moveUp" : "moveDown";
  }
}
