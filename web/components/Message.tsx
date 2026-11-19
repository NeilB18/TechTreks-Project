import type { ReactNode } from "react";

/**
 * A page with one message in the middle: not found, something went wrong (design canvas: Final
 * designs, "Trip not found"). A plain title, a line of help, and up to two buttons.
 */
export function Message({ title, children, actions }: { title: string; children: ReactNode; actions: ReactNode }) {
  return (
    <div className="flex min-h-[70dvh] flex-col justify-center gap-3.5 px-6 pb-20">
      <h1 className="wide text-[32px] leading-[1.05] tracking-[-0.02em] text-balance">{title}</h1>
      <p className="leading-normal text-muted">{children}</p>
      <div className="mt-2 flex gap-2.5">{actions}</div>
    </div>
  );
}
