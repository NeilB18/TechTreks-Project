"use client";

import { type ReactNode, type RefObject, useRef } from "react";

/**
 * A bottom sheet: a native <dialog> that comes up from the bottom of the screen (design canvas:
 * "Mark as sent", "Change theme"). The browser handles focus, Escape and the backdrop.
 * useSheet() gives the ref plus open/close (destructure them); jsdom (tests) has no showModal, so it falls back to
 * the open attribute.
 */
export function useSheet(): { ref: RefObject<HTMLDialogElement | null>; open: () => void; close: () => void } {
  const ref = useRef<HTMLDialogElement>(null);
  return {
    ref,
    open: () => {
      const d = ref.current;
      if (d?.showModal) d.showModal();
      else d?.setAttribute("open", "");
      // Start focus on the sheet itself, not its first button, so nothing looks pre-picked.
      d?.focus();
    },
    close: () => {
      const d = ref.current;
      if (d?.close) d.close();
      else d?.removeAttribute("open");
    },
  };
}

export function Sheet({
  dialogRef,
  onClose,
  labelledBy,
  children,
}: {
  dialogRef: RefObject<HTMLDialogElement | null>;
  onClose: () => void;
  labelledBy: string;
  children: ReactNode;
}) {
  return (
    <dialog
      ref={dialogRef}
      aria-labelledby={labelledBy}
      tabIndex={-1}
      className="sheet outline-none"
      // A tap on the dimmed backdrop (outside the sheet's box) closes it.
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          const r = e.currentTarget.getBoundingClientRect();
          if (e.clientY < r.top || e.clientY > r.bottom || e.clientX < r.left || e.clientX > r.right) onClose();
        }
      }}
    >
      <span aria-hidden="true" className="mx-auto mb-4 block h-[5px] w-10 rounded-full bg-white/25" />
      <div className="flex flex-col gap-3.5">{children}</div>
    </dialog>
  );
}
