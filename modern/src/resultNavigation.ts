/** Focus a result button and scroll it into view without centring the list. */
export function focusResultButton(list: HTMLElement | undefined, key: string): boolean {
  const buttons = Array.from(list?.querySelectorAll<HTMLButtonElement>(":scope > button:not(:disabled)") ?? []);
  if (!buttons.length) return false;

  const current = buttons.findIndex((button) => button === document.activeElement);
  const up = key === "ArrowUp";
  const last = buttons.length - 1;
  let index = current + (up ? -1 : 1);
  if (key === "Home") index = 0;
  if (key === "End" || (current < 0 && up)) index = last;
  const button = buttons[Math.max(0, Math.min(last, index))]!;
  button.focus({ preventScroll: true });
  button.scrollIntoView({ block: "nearest", inline: "nearest" });
  return true;
}
