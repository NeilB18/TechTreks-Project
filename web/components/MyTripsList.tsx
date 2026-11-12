"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { TripArt } from "@/components/TripArt";
import { countdown, formatDayRange, formatMoney } from "@/lib/format";
import type { TripCard } from "@/lib/types";

const STATUS_LABEL = { PLANNING: "Planning", BOOKED: "Booked", ACTIVE: "On the trip", DONE: "Done" } as const;

type State = { step: "loading" } | { step: "signed-out" } | { step: "error" } | { step: "ready"; trips: TripCard[] };

/**
 * My trips: coming up (big cards in each trip's theme) and past (small rows), plus how to add a
 * missing one. Live it asks /api/me/trips; in sample mode `sample` is every fixture.
 */
export function MyTripsList({ sample, today }: { sample: TripCard[] | null; today: string }) {
  const [state, setState] = useState<State>(sample ? { step: "ready", trips: sample } : { step: "loading" });

  useEffect(() => {
    if (sample) return;
    let cancelled = false;
    fetch("/api/me/trips", { cache: "no-store" })
      .then(async (r) => {
        if (cancelled) return;
        if (r.status === 401) return setState({ step: "signed-out" });
        if (!r.ok) throw new Error(String(r.status));
        setState({ step: "ready", trips: ((await r.json()) as { trips: TripCard[] }).trips });
      })
      .catch(() => !cancelled && setState({ step: "error" }));
    return () => {
      cancelled = true;
    };
  }, [sample]);

  if (state.step === "loading") return <p className="px-5 pt-6 text-muted">Loading your trips…</p>;
  if (state.step === "error") return <p className="px-5 pt-6 text-muted">Couldn&rsquo;t load your trips. Try refreshing.</p>;
  if (state.step === "signed-out") {
    return (
      <section className="mx-5 mt-6 flex flex-col gap-2.5 rounded-[26px] bg-paper p-[22px] text-paper-ink">
        <h2 className="display text-2xl">Sign in to see your trips</h2>
        <p className="text-[15px] text-paper-muted">Your trips are the ones you&rsquo;ve linked from their group chats.</p>
        <a href="/accounts/google/login/?next=/trips" className="btn btn-paper mt-1.5 min-h-[50px] text-base">
          Sign in with Google
        </a>
      </section>
    );
  }

  const isPast = (t: TripCard) => t.status === "DONE" || (!!t.end_date && t.end_date < today);
  const soon = state.trips.filter((t) => !isPast(t));
  const past = state.trips.filter(isPast);
  return (
    <>
      <section aria-labelledby="coming-up" className="flex flex-col gap-3.5 px-5 pt-6">
        <h2 id="coming-up" className="label-caps">Coming up</h2>
        {soon.length === 0 && <p className="text-muted">Nothing coming up yet.</p>}
        {soon.map((t) => (
          <Card key={t.share_token} t={t} today={today} />
        ))}
      </section>
      {past.length > 0 && (
        <section aria-labelledby="past" className="flex flex-col gap-2.5 px-5 pt-7">
          <h2 id="past" className="label-caps">Past</h2>
          {past.map((t) => (
            <Link key={t.share_token} href={`/t/${t.share_token}`} className="card flex items-center gap-3.5 p-3 text-ink no-underline">
              <span data-theme={t.theme ?? "sunset"} aria-hidden="true" className="size-[52px] flex-none overflow-hidden rounded-[14px] bg-ground">
                <TripArt theme={t.theme ?? "sunset"} className="block h-full w-full" />
              </span>
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="truncate font-bold">{t.name}</span>
                <span className="text-sm text-muted">{[formatDayRange(t.start_date, t.end_date), money(t)].filter(Boolean).join(" · ")}</span>
              </span>
            </Link>
          ))}
        </section>
      )}
      <section className="mx-5 mt-8 flex flex-col gap-1.5 rounded-[22px] border-2 border-dashed border-outline p-[18px]">
        <h2 className="text-[17px] font-bold">Missing a trip?</h2>
        <p className="text-sm text-muted">Get a code, post it in that trip&rsquo;s group chat, and the trip shows up here.</p>
        <Link href="/link" className="btn btn-outline mt-1.5 self-start">Get a link code</Link>
      </section>
    </>
  );
}

function money(t: TripCard): string {
  if (t.net_cents < 0) return `You owe ${formatMoney(-t.net_cents)}`;
  if (t.net_cents > 0) return `You're owed ${formatMoney(t.net_cents)}`;
  return "All settled";
}

function Card({ t, today }: { t: TripCard; today: string }) {
  const line = [formatDayRange(t.start_date, t.end_date) ?? "Dates not picked yet", `${t.going} going`,
    countdown(t.start_date, t.end_date, today)].filter(Boolean).join(" · ");
  return (
    <Link href={`/t/${t.share_token}`} className="card block overflow-hidden text-ink no-underline">
      <div data-theme={t.theme ?? "sunset"} className="relative h-[92px] overflow-hidden bg-ground">
        <TripArt theme={t.theme ?? "sunset"} className="block h-full w-full" />
        <span className="sticker absolute top-4 left-4 -rotate-6 text-xs">{STATUS_LABEL[t.status]}</span>
      </div>
      <div className="flex flex-col gap-1 p-4">
        <span className="display text-2xl">{t.name}</span>
        <span className="text-sm text-muted">{line}</span>
        <span className="mt-2 self-start rounded-full bg-ground px-3 py-1.5 text-sm font-bold">{money(t)}</span>
      </div>
    </Link>
  );
}
