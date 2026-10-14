/** Small DOM helpers shared by the shell: focus handling, focus trap, native modal dialogs. */
import { useCallback, useEffect, useLayoutEffect, useRef, type MouseEvent, type KeyboardEvent, type SyntheticEvent } from "react";

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), summary, [tabindex]:not([tabindex="-1"])';
const NATURALLY_FOCUSABLE = 'a[href], button, input, select, textarea, summary, [tabindex]';

/** True when typing would go into the target (so single-key shortcuts must stay out of the way). */
export function isEditable(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLElement &&
    (target.isContentEditable ||
      target.matches('input, textarea, select, [role="textbox"], [role="combobox"], [role="searchbox"]'))
  );
}

/**
 * Focus an element by id once it exists (children may mount a frame later),
 * then scroll it into view without moving ancestor scrollers more than needed.
 * If it never appears, focus `fallbackId` so keyboard focus is not left on <body>.
 * Returns a cancel function.
 */
export function focusWhenReady(id: string, block: ScrollLogicalPosition = "nearest", fallbackId = "main-content", tries = 40): () => void {
  let frame = 0;
  let cancelled = false;
  const focus = (el: HTMLElement) => {
    if (!el.matches(NATURALLY_FOCUSABLE)) el.setAttribute("tabindex", "-1");
    el.focus({ preventScroll: true });
    el.scrollIntoView({ block, inline: "nearest", behavior: "auto" });
  };
  const attempt = (left: number) => {
    if (cancelled) return;
    const el = document.getElementById(id);
    if (el) return focus(el);
    if (left > 0) frame = requestAnimationFrame(() => attempt(left - 1));
    else {
      const fallback = document.getElementById(fallbackId);
      if (fallback) focus(fallback);
    }
  };
  attempt(tries);
  return () => {
    cancelled = true;
    cancelAnimationFrame(frame);
  };
}

/** Keep Tab / Shift+Tab inside `event.currentTarget`. Attach to the modal's onKeyDown. */
export function trapTab(event: KeyboardEvent<HTMLElement>) {
  if (event.key !== "Tab") return;
  const root = event.currentTarget;
  const items = Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
    (el) => el.getClientRects().length > 0,
  );
  if (!items.length) {
    event.preventDefault();
    return;
  }
  const first = items[0];
  const last = items[items.length - 1];
  const active = document.activeElement;
  if (event.shiftKey && (active === first || active === root)) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && active === last) {
    event.preventDefault();
    first.focus();
  }
}

/**
 * Native <dialog> opened modally while mounted. Mounting opens it, unmounting closes it.
 * Escape and backdrop clicks call `onClose` (React state stays authoritative);
 * Tab is trapped; the opener is refocused by the owner when the dialog unmounts.
 */
export function useModalDialog(onClose: () => void) {
  const ref = useRef<HTMLDialogElement>(null);
  const close = useRef(onClose);
  const pressedOnBackdrop = useRef(false);
  useEffect(() => {
    close.current = onClose;
  });
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (!dialog.open) dialog.showModal();
    return () => {
      if (dialog.open) dialog.close();
    };
  }, []);
  return {
    ref,
    onCancel: (event: SyntheticEvent) => {
      event.preventDefault();
      close.current();
    },
    onKeyDown: trapTab,
    onMouseDown: (event: MouseEvent<HTMLDialogElement>) => {
      pressedOnBackdrop.current = event.target === event.currentTarget;
    },
    onClick: (event: MouseEvent<HTMLDialogElement>) => {
      if (pressedOnBackdrop.current && event.target === event.currentTarget) close.current();
      pressedOnBackdrop.current = false;
    },
  };
}

/** A callback with a constant identity that always calls the latest closure (safe to hand to map code). */
export function useStableCallback<A extends unknown[], R>(fn: (...args: A) => R): (...args: A) => R {
  const latest = useRef(fn);
  useLayoutEffect(() => {
    latest.current = fn;
  });
  return useCallback((...args: A) => latest.current(...args), []);
}
