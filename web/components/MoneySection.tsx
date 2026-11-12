"use client";

import { useEffect, useState } from "react";

import { Balances } from "@/components/Balances";
import { Expenses } from "@/components/Expenses";
import { formatMoney, warningText } from "@/lib/format";
import type { BudgetStatus, LinkCode, MyTrip, TripPageData } from "@/lib/types";

type State =
  | { step: "loading" }
  | { step: "error"; message: string }
  | { step: "signed-out" }
  | { step: "not-linked"; code: LinkCode | null }
  | { step: "ready"; data: MyTrip };

// Live, per-person data: never serve it from the browser cache.
const NO_STORE: RequestInit = { cache: "no-store" };

function csrfToken(): string {
  return document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)?.[1] ?? "";
}

/**
 * Expenses, settle-up and budgets. Only signed-in members of the trip get them, from
 * /api/me/trips/<id> (proxied to Django with the session cookie): 401 means signed out,
 * 403 means signed in but not linked to anyone on this trip.
 * Without a backend (fixtures), `sample` is shown to everyone: it's sample data.
 */
export function MoneySection({
  tripId,
  pagePath,
  live,
  sample,
}: {
  tripId: string;
  pagePath: string; // where sign-in comes back to: this trip page, /t/<share_token>
  live: boolean;
  sample: TripPageData | null;
}) {
  const [state, setState] = useState<State>(
    live ? { step: "loading" }
      : sample ? { step: "ready", data: { ...sample, person_id: "", budget: null } }
      : { step: "error", message: "No money data here." },
  );

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
    <section aria-labelledby="money" className="rounded-xl border border-dashed border-line p-4">
      <h2 id="money" className="font-semibold">Money and budgets</h2>
      <div className="mt-1 text-sm text-muted">
        {state.step === "loading" && <p>Loading…</p>}
        {state.step === "error" && <p>{state.message}</p>}
        {state.step === "signed-out" && (
          <>
            <p>Only people on this trip can see what&rsquo;s been spent, who owes who, and everyone&rsquo;s budget.</p>
            <a
              href={`/accounts/google/login/?next=${pagePath}`}
              className="mt-3 inline-block rounded-full bg-accent px-3 py-1.5 font-medium text-background hover:opacity-90"
            >
              Sign in with Google
            </a>
          </>
        )}
        {state.step === "not-linked" && (
          <>
            <p>You&rsquo;re signed in, but not linked to anyone on this trip. If you&rsquo;re in the group chat, link yourself so we know which member you are.</p>
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
          </>
        )}
      </div>
    </section>
  );
}

function Money({ data }: { data: MyTrip }) {
  const { detail, balances, budget } = data;
  const { trip, members } = detail;
  const me = members.find((m) => m.id === data.person_id);
  return (
    <>
      {trip.group_budget_cents != null && (
        <p className="mt-8 text-sm text-muted">
          Group budget:{" "}
          <span className="font-semibold text-foreground tabular-nums">
            {formatMoney(trip.group_budget_cents, trip.base_currency)}/person
          </span>
        </p>
      )}
      <section className="mt-8" aria-labelledby="balances">
        <h2 id="balances" className="mb-3 text-lg font-semibold">Settle up</h2>
        <Balances balances={balances} members={members} tripName={trip.name} />
      </section>
      <section className="mt-8" aria-labelledby="expenses">
        <h2 id="expenses" className="mb-3 text-lg font-semibold">Expenses</h2>
        <Expenses expenses={detail.expenses} members={members} currency={trip.base_currency} />
      </section>
      {budget && (
        <section className="mt-8 rounded-xl border border-dashed border-line p-4" aria-labelledby="my-budget">
          <h2 id="my-budget" className="font-medium">My budget{me ? ` (${me.name})` : ""}</h2>
          <div className="mt-1 text-sm">
            <BudgetDetails budget={budget} currency={trip.base_currency} />
          </div>
        </section>
      )}
    </>
  );
}

export function BudgetDetails({ budget: b, currency }: { budget: BudgetStatus; currency: string }) {
  if (!b.budget_set) {
    return <p className="text-muted">No budget set yet. Tell @tripbot in the group chat (e.g. &ldquo;my budget is $800&rdquo;).</p>;
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
          {b.warnings.map((w, i) => (
            <li key={i} className="font-medium text-warn">⚠️ {warningText(w)}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
