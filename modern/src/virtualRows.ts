import type { TabulatorFull as Tabulator, RowComponent } from "tabulator-tables";

/**
 * Tabulator 6.7 virtual renderer fix for variable-height rows.
 *
 * After a large scroll near the top, `_virtualRenderFill` sets the top padding
 * to `scrollTop - (height of the buffer rows)`. Rows taller than the average
 * make this negative; the browser ignores a negative `padding-top`, so the old
 * padding stays and the viewport shows no rows until the next scroll.
 * When that happens, render the rows above, drop the padding and keep the
 * intended view by moving `scrollTop` by the same amount.
 */
export function guardVirtualRenderer(table: Tabulator) {
  const renderer = (table as any).rowManager?.renderer;
  if (!renderer || typeof renderer._virtualRenderFill !== "function" || renderer.guardedFill) return;
  renderer.guardedFill = true;
  const fill = renderer._virtualRenderFill.bind(renderer);
  renderer._virtualRenderFill = (...args: unknown[]) => {
    fill(...args);
    const padding: number = renderer.vDomTopPad;
    if (!(padding < 0)) return;
    const holder: HTMLElement = renderer.elementVertical;
    const body: HTMLElement = renderer.tableElement;
    const first = body.firstElementChild as HTMLElement | null;
    const intended: number = renderer.scrollTop;
    renderer.vDomTopPad = 0;
    body.style.paddingTop = "0px";
    if (renderer.vDomTop > 0) renderer._addTopRow(renderer.rows(), Number.MAX_SAFE_INTEGER);
    // The first rendered row was meant to start `padding` px above the content
    // top; it now starts `above` px below it.
    const above = first ? first.getBoundingClientRect().top - body.getBoundingClientRect().top : 0;
    holder.scrollTop = Math.max(0, intended + above - padding);
    renderer.scrollTop = renderer.vDomScrollPosTop = renderer.vDomScrollPosBottom = holder.scrollTop;
  };
}

/**
 * Bring a row fully into view with the least scrolling. A rendered row only
 * moves the scroll position; Tabulator's own scrollTo re-renders the whole
 * window starting at the row whenever the row is not fully visible.
 */
export async function revealRow(row: RowComponent) {
  const element = row.getElement();
  const holder = element?.isConnected ? element.closest<HTMLElement>(".tabulator-tableholder") : null;
  if (!holder || !element.getClientRects().length) {
    await row.scrollTo("nearest", false).catch(() => {});
    return;
  }
  const view = holder.getBoundingClientRect();
  // clientHeight excludes a horizontal scrollbar.
  const bottom = view.top + holder.clientTop + holder.clientHeight;
  const top = view.top + holder.clientTop;
  const bounds = element.getBoundingClientRect();
  if (bounds.top < top) holder.scrollTop -= top - bounds.top;
  else if (bounds.bottom > bottom) holder.scrollTop += Math.min(bounds.bottom - bottom, bounds.top - top);
}
