/**
 * Accessibility helpers for dialog/modal focus management.
 */

/**
 * Move keyboard focus off the currently focused element (typically the button
 * or menu item that just triggered an action).
 *
 * MUI's `Dialog`/`Modal` marks the rest of the app (the `#root` container) as
 * hidden from assistive technology while it is open. If the element that opened
 * the dialog keeps focus, Chromium logs:
 *   "Blocked aria-hidden on an element because its descendant retained focus."
 * Calling this right before opening a dialog releases that focus so the dialog's
 * own focus trap can take over cleanly without leaving a focused node inside the
 * hidden subtree.
 */
export const blurActiveElement = (): void => {
  const active = document.activeElement;
  if (active instanceof HTMLElement) {
    active.blur();
  }
};
