import type { CellComponent } from "tabulator-tables";

/**
 * True when the cell's content is wider than the cell. Right-aligned cells
 * are flex boxes that overflow to the left, which `scrollWidth` does not
 * report, so the content is measured directly.
 */
function clipped(element: HTMLElement) {
  if (element.scrollWidth > element.clientWidth + 1) return true;
  const style = getComputedStyle(element);
  const available = element.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
  const range = document.createRange();
  range.selectNodeContents(element);
  return range.getBoundingClientRect().width > available + 1;
}

/**
 * Tabulator `tooltip` option that shows the cell's full text only when the
 * cell is too narrow to show it. `text` gives the tooltip text; by default
 * the cell's own displayed text.
 */
export function overflowTooltip(text?: (cell: CellComponent) => string) {
  return (_event: UIEvent, cell: CellComponent) => {
    const element = cell.getElement();
    if (!clipped(element)) return "";
    const value = text ? text(cell) : element.textContent?.trim() ?? "";
    if (!value) return "";
    // Escape: Tabulator assigns string tooltips as innerHTML.
    const div = document.createElement("div");
    div.textContent = value;
    return div;
  };
}
