"use client";

import { CopyButton } from "@/components/CopyButton";

/** Copies this page's own address (no query or #hash): the trip's share link. */
export function CopyLinkButton() {
  return (
    <CopyButton
      label="Copy trip link"
      text={() => `${window.location.origin}${window.location.pathname}`}
      className="btn btn-pop min-h-12 flex-1 sm:flex-none"
    />
  );
}
