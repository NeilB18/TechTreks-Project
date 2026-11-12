"use client";

import { useEffect, useState } from "react";

import { Money } from "@/components/Money";
import { previewMember, previewState, type State } from "@/lib/preview";
import type { LinkCode, MyTrip, TripPageData } from "@/lib/types";

// Live, per-person data: never serve it from the browser cache.
const NO_STORE: RequestInit = { cache: "no-store" };

function csrfToken(): string {
  return document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)?.[1] ?? "";
}

/**
 * Expenses, settle-up and budgets. Only signed-in members of the trip get them, from
 * /api/me/trips/<id> (proxied to Django with the session cookie): 401 means signed out,
 * 403 means signed in but not linked to anyone on this trip.
 * Without a backend (sample mode), `sample` is the fixture and `previewAs` picks what to show
 * (the "Preview as" bar): "signed-out", "not-linked", or a member's id.
 */
export function MoneySection({
  tripId,
  pagePath,
  live,
  sample,
  previewAs,
}: {
  tripId: string;
  pagePath: string; // where sign-in comes back to: this trip page, /t/<share_token>
  live: boolean;
  sample: TripPageData | null;
  previewAs?: string;
}) {
  const [state, setState] = useState<State>(live ? { step: "loading" } : previewState(sample, previewAs));
  const preview = !live;

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
  }, [live, tripId]);

  async function getCode() {
    if (preview) {
      setState({ step: "not-linked", code: { code: "K7RM4X", expires_at: "", instructions: "" } });
      return;
    }
    try {
      const res = await fetch("/api/me/link-code", {
        ...NO_STORE, method: "POST", headers: { "X-CSRFToken": csrfToken() },
      });
      if (!res.ok) throw new Error(String(res.status));
      setState({ step: "not-linked", code: (await res.json()) as LinkCode });
    } catch {
      setState({ step: "error", message: "Couldn’t get a link code. Refresh and try again." });
    }
  }

  if (state.step === "ready") return <Money data={state.data} />;

  return (
    // The "members only" card from the design canvas: cream paper with a sticker.
    <section aria-labelledby="money" className="relative mt-3.5 flex flex-col gap-2.5 rounded-[26px] bg-paper p-[22px] text-paper-ink">
      <span className="sticker absolute -top-3.5 right-[18px] rotate-[8deg] text-[13px]">Members only</span>
      <h2 id="money" className="display text-2xl leading-tight">Money and budgets</h2>
      <div className="flex flex-col gap-2.5 text-[15px] leading-snug text-paper-muted">
        {state.step === "loading" && <p>Loading…</p>}
        {state.step === "error" && <p>{state.message}</p>}
        {state.step === "signed-out" && (
          <>
            <p>Sign in to see what&rsquo;s been spent, who owes who, and everyone&rsquo;s budget. Only people on this trip can see it.</p>
            {/* In sample mode there's no Google sign-in: the button previews the page as a member instead. */}
            <a
              href={preview ? `${pagePath}?as=${previewMember(sample)}` : `/accounts/google/login/?next=${pagePath}`}
              className="btn btn-paper mt-1.5 min-h-[50px] text-base"
            >
              Sign in with Google
            </a>
          </>
        )}
        {state.step === "not-linked" && (
          <>
            <p>You&rsquo;re signed in, but not linked to anyone on this trip. If you&rsquo;re in the group chat, link yourself so we know which member you are.</p>
            {state.code ? (
              <p>
                Post{" "}
                <code className="rounded-md bg-paper-ink px-2 py-1 font-bold text-paper">@tripbot link {state.code.code}</code>{" "}
                in the group chat in the next 15 minutes, then refresh.
              </p>
            ) : (
              <button type="button" onClick={getCode} className="btn btn-paper mt-1.5 min-h-[50px] text-base">
                Get my link code
              </button>
            )}
          </>
        )}
      </div>
    </section>
  );
}
