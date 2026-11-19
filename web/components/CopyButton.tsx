"use client";

import { type ReactNode, useState } from "react";

/**
 * Copies text to the clipboard and says "Copied" for a moment. `text` can be a function, for text
 * only known in the browser (like the page's own address). An icon-only button passes `ariaLabel`
 * (its name) and icons as `label` / `copiedLabel`.
 */
export function CopyButton({
  text,
  label,
  copiedLabel = "Copied",
  ariaLabel,
  className = "btn btn-line",
}: {
  text: string | (() => string);
  label: ReactNode;
  copiedLabel?: ReactNode;
  ariaLabel?: string;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      aria-label={ariaLabel && (copied ? "Copied" : ariaLabel)}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(typeof text === "function" ? text() : text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        } catch {
          // Clipboard can be blocked; the handle (or the address bar) still shows the text.
        }
      }}
      className={className}
    >
      {copied ? copiedLabel : label}
    </button>
  );
}
