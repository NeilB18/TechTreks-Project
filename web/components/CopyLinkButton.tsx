"use client";

import type { ReactNode } from "react";

import { CopyButton } from "@/components/CopyButton";

/** The trip's share link: this page's address without the Money tab, query or #hash. */
export function tripLink(): string {
  return `${window.location.origin}${window.location.pathname.replace(/\/money\/?$/, "")}`;
}

/** Copies the trip's share link. */
export function CopyLinkButton({
  label = "Copy trip link",
  copiedLabel = "Copied",
  className = "btn btn-line",
}: {
  label?: ReactNode;
  copiedLabel?: ReactNode;
  className?: string;
}) {
  return <CopyButton label={label} copiedLabel={copiedLabel} text={tripLink} className={className} />;
}
