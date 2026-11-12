"use client";

import { useEffect, useState } from "react";

import type { Me } from "./types";

// Who's signed in, asked once per page load and shared by everything that needs it
// (the account menu, the theme button). /api/me/ also sets the CSRF cookie for later POSTs.
let cached: Promise<Me | null> | null = null;

export function fetchMe(): Promise<Me | null> {
  cached ??= fetch("/api/me/", { cache: "no-store" })
    .then((r) => (r.ok ? (r.json() as Promise<Me>) : null))
    .catch(() => null);
  return cached;
}

/** undefined while loading; null if the backend couldn't be reached. Only asks when `live`. */
export function useMe(live: boolean): Me | null | undefined {
  const [me, setMe] = useState<Me | null | undefined>(undefined);
  useEffect(() => {
    if (!live) return;
    let cancelled = false;
    fetchMe().then((m) => !cancelled && setMe(m));
    return () => {
      cancelled = true;
    };
  }, [live]);
  return me;
}
