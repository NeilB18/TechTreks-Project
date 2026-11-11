"use client";

import { useState } from "react";

// `text` can be a function, for text only known in the browser (like the page's own address).
export function CopyButton({
  text,
  label,
  className = "rounded-full border border-line px-3 py-1.5 text-sm hover:bg-line/40",
}: {
  text: string | (() => string);
  label: string;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
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
      {copied ? "Copied" : label}
    </button>
  );
}
