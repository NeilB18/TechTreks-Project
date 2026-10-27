"use client";

import { useState } from "react";

export function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        } catch {
          // Clipboard can be blocked; the handle is still visible in the label.
        }
      }}
      className="mt-2 max-w-full break-all rounded-md border border-line px-3 py-1.5 text-left text-[10px] hover:bg-line/40"
    >
      {copied ? "Copied" : label}
    </button>
  );
}
