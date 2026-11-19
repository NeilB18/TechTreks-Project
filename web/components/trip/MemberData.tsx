"use client";

import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { csrfToken } from "@/lib/post";
import { previewMember, previewState, type State } from "@/lib/preview";
import type { LinkCode, MyTrip, TripPageData } from "@/lib/types";

// Live, per-person data: never serve it from the browser cache.
const NO_STORE: RequestInit = { cache: "no-store" };

type MemberData = {
  state: State;
  tripId: string;
  pagePath: string; // the trip page, /t/<share_token>: where sign-in comes back to
  tabPath: string; // the tab you're on (the Trip tab is pagePath, Money is pagePath/money)
  preview: boolean; // sample mode: nothing is saved
  previewAs?: string;
  signInHref: string;
  reload: () => void; // after a save (a payment marked as sent, a new budget)
  getLinkCode: () => Promise<void>;
};

const Ctx = createContext<MemberData | null>(null);

/**
 * The money side of one trip, loaded once for the whole page. Only signed-in members of the trip
 * get it, from /api/me/trips/<id> (proxied to Django with the session cookie): 401 means signed
 * out, 403 means signed in but not linked to anyone on this trip. The Trip tab's money card,
 * Latest, where you're staying, Change theme and the floating bar all read it from here.
 * Without a backend (sample mode), `sample` is the fixture and `previewAs` picks who's looking
 * (the "Preview as" bar): "signed-out", "not-linked", or a member's id.
 */
export function MemberDataProvider({
  tripId,
  pagePath,
  tabPath,
  live,
  sample,
  previewAs,
  children,
}: {
  tripId: string;
  pagePath: string;
  tabPath?: string;
  live: boolean;
  sample: TripPageData | null;
  previewAs?: string;
  children: ReactNode;
}) {
  const [state, setState] = useState<State>(live ? { step: "loading" } : previewState(sample, previewAs));
  const [version, setVersion] = useState(0);
  const preview = !live;
  const here = tabPath ?? pagePath;

  useEffect(() => {
    if (!live) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`/api/me/trips/${encodeURIComponent(tripId)}`, NO_STORE);
        if (cancelled) return;
        if (res.status === 401) return setState({ step: "signed-out" });
        if (res.status === 403) return setState({ step: "not-linked", code: null });
        if (!res.ok) throw new Error(String(res.status));
        const data = (await res.json()) as MyTrip;
        if (!cancelled) setState({ step: "ready", data });
      } catch {
        if (!cancelled) setState({ step: "error", message: "Couldn’t load the money side. Try refreshing." });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [live, tripId, version]);

  const getLinkCode = useCallback(async () => {
    if (preview) {
      setState({ step: "not-linked", code: { code: "K7RM4X", expires_at: "", instructions: "" } });
      return;
    }
    try {
      const res = await fetch("/api/me/link-code", { ...NO_STORE, method: "POST", headers: { "X-CSRFToken": csrfToken() } });
      if (!res.ok) throw new Error(String(res.status));
      setState({ step: "not-linked", code: (await res.json()) as LinkCode });
    } catch {
      setState({ step: "error", message: "Couldn’t get a link code. Refresh and try again." });
    }
  }, [preview]);

  const value = useMemo<MemberData>(
    () => ({
      state,
      tripId,
      pagePath,
      tabPath: here,
      preview,
      previewAs,
      // In sample mode there's no Google sign-in: signing in previews the page as a member instead.
      signInHref: preview ? `${here}?as=${previewMember(sample)}` : `/accounts/google/login/?next=${here}`,
      reload: () => setVersion((v) => v + 1),
      getLinkCode,
    }),
    [state, tripId, pagePath, here, preview, previewAs, sample, getLinkCode],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useMemberData(): MemberData {
  const v = useContext(Ctx);
  if (!v) throw new Error("useMemberData needs a MemberDataProvider around it");
  return v;
}
