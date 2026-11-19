"use client";

import { useSyncExternalStore } from "react";

const noop = () => () => {};
const thisMinute = () => Math.floor(Date.now() / 60_000) * 60_000;

/**
 * The time, to the minute, for "3h ago" labels. null on the server and while hydrating, so the
 * server's HTML never disagrees with the browser's clock.
 */
export function useNow(): number | null {
  return useSyncExternalStore(noop, thisMinute, () => null);
}
