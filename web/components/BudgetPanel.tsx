"use client";

import { useEffect, useState } from "react";

import { formatMoney } from "@/lib/format";
import type { LinkCode, Me, MyBudget } from "@/lib/types";

type State =
  | { step: "loading" }
  | { step: "error" }
  | { step: "signed-out" }
  | { step: "not-linked"; code: LinkCode | null }
  | { step: "ready"; data: MyBudget };

// Private, per-person data: never serve it from the browser cache.
const NO_STORE: RequestInit = { cache: "no-store" };

function csrfToken(): string {
  return document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)?.[1] ?? "";
}

/**
 * Private budget for the signed-in person only. Data comes from /api/me/*, which
 * Django answers for the caller's own linked trip member and nobody else.
 * Without a backend (fixtures), it just explains where budgets live.
 */
export function BudgetPanel({ tripId, live, currency }: { tripId: string; live: boolean; currency: string }) {
  const [state, setState] = useState<State>({ step: live ? "loading" : "signed-out" });

  useEffect(() => {
    if (!live) return;
    let cancelled = false;
    (async () => {
      try {
        const me = (await (await fetch("/api/me/", NO_STORE)).json()) as Me;
        if (cancelled) return;
        if (!me.signed_in) return setState({ step: "signed-out" });
        if (!me.people.some((p) => p.trip_id === tripId)) return setState({ step: "not-linked", code: null });
        const res = await fetch(`/api/me/trips/${encodeURIComponent(tripId)}/budget`, NO_STORE);
        if (!res.ok) throw new Error(String(res.status));
        const data = (await res.json()) as MyBudget;
        if (!cancelled) setState({ step: "ready", data });
      } catch {
        if (!cancelled) setState({ step: "error" });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [live, tripId]);

  async function getCode() {
    try {
      const res = await fetch("/api/me/link-code", {
        ...NO_STORE, method: "POST", headers: { "X-CSRFToken": csrfToken() },
      });
      if (!res.ok) throw new Error(String(res.status));
      setState({ step: "not-linked", code: (await res.json()) as LinkCode });
    } catch {
      setState({ step: "error" });
    }
  }

  return (
    <div className="rounded-xl border border-dashed border-line p-4">
      <p className="font-medium">🔒 My budget</p>
      <div className="mt-1 text-sm">
        {state.step === "loading" && <p className="text-muted">Loading…</p>}
        {state.step === "error" && <p className="text-muted">Couldn&rsquo;t load your budget. Try refreshing.</p>}
        {state.step === "signed-out" &&
          (live ? (
            <p className="text-muted">
              Your budget is private. Only you can see it.{" "}
              <a href={`/accounts/google/login/?next=/trips/${encodeURIComponent(tripId)}`} className="text-accent underline">
                Sign in with Google
              </a>{" "}
              to see it here.
            </p>
          ) : (
            <p className="text-muted">
              Your budget is private. Only you can see it. Sign-in isn&rsquo;t set up on this page, so DM @tripbot to
              check what you have left.
            </p>
          ))}
        {state.step === "not-linked" && (
          <div className="text-muted">
            <p>You&rsquo;re signed in. Link yourself to this trip so we know which member you are.</p>
            {state.code ? (
              <p className="mt-2">
                Post <code className="rounded bg-line/50 px-1.5 py-0.5 font-mono text-foreground">@tripbot link {state.code.code}</code>{" "}
                in the group chat in the next 15 minutes, then refresh.
              </p>
            ) : (
              <button
                type="button"
                onClick={getCode}
                className="mt-2 rounded-full bg-accent px-3 py-1.5 font-medium text-background hover:opacity-90"
              >
                Get my link code
              </button>
            )}
          </div>
        )}
        {state.step === "ready" && <BudgetDetails data={state.data} currency={currency} />}
      </div>
    </div>
  );
}

export function BudgetDetails({ data, currency }: { data: MyBudget; currency: string }) {
  const b = data.budget;
  if (!b.budget_set) {
    return <p className="text-muted">No budget set yet. DM @tripbot your total (e.g. &ldquo;my budget is $800&rdquo;).</p>;
  }
  const rows: [string, number | undefined][] = [
    ["Total", b.total_cents],
    ["Spent (your share)", b.spent_cents],
    ["Planned activities", b.planned_cents],
    ["Left after plans", b.remaining_after_planned_cents],
  ];
  return (
    <div>
      <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1">
        {rows.map(([label, cents]) => (
          <div key={label} className="contents">
            <dt className="text-muted">{label}</dt>
            <dd className="text-right font-medium tabular-nums">{formatMoney(cents ?? 0, currency)}</dd>
          </div>
        ))}
      </dl>
      {b.warnings.length > 0 && (
        <ul className="mt-3 space-y-1">
          {b.warnings.map((w) => (
            <li key={w} className="font-medium text-warn">⚠️ {w}</li>
          ))}
        </ul>
      )}
      {data.notices.length > 0 && (
        <div className="mt-3">
          <p className="text-muted">Private messages from @tripbot</p>
          <ul className="mt-1 space-y-1">
            {data.notices.map((n) => (
              <li key={n.created_at + n.text} className="rounded-lg bg-line/40 p-2">{n.text}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
