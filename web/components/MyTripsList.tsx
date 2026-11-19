"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";

import { countdown, formatDateRange, formatMoney, formatShortRange } from "@/lib/format";
import { themeInfo } from "@/lib/themes";
import type { TripCard } from "@/lib/types";

const STATUS_LABEL = { PLANNING: "Planning", BOOKED: "Booked", ACTIVE: "On the trip", DONE: "Done" } as const;

type State = { step: "loading" } | { step: "signed-out" } | { step: "error" } | { step: "ready"; trips: TripCard[] };

/**
 * My trips (design canvas: Final designs, "My trips"): coming up (photo cards in each trip's theme)
 * and past (small rows), plus how to add a
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

  if (state.step === "loading") {
    return (
      <div aria-busy="true" aria-label="Loading your trips" className="flex flex-col gap-3 px-5 pt-6.5">
        <span className="h-[200px] animate-pulse rounded-[20px] bg-surface" />
        <span className="h-[200px] animate-pulse rounded-[20px] bg-surface" />
      </div>
    );
  }
  if (state.step === "error") return <p className="px-5 pt-6 text-muted">Couldn&rsquo;t load your trips. Try refreshing.</p>;
  if (state.step === "signed-out") {
    return (
      <section aria-labelledby="trips-sign-in" className="card mx-3.5 mt-6 flex flex-col gap-3 p-[18px]">
        <h2 id="trips-sign-in" className="text-lg font-bold">Sign in to see your trips</h2>
        <p className="text-[15px] leading-[1.45] text-muted">Your trips are the ones you&rsquo;ve linked from their group chats.</p>
        <a href="/accounts/google/login/?next=/trips" className="btn btn-white">Sign in with Google</a>
      </section>
    );
  }

  const isPast = (t: TripCard) => t.status === "DONE" || (!!t.end_date && t.end_date < today);
  const soon = state.trips.filter((t) => !isPast(t));
  const past = state.trips.filter(isPast);
  return (
    <>
      <section aria-labelledby="coming-up" className="flex flex-col gap-3 px-5 pt-6.5">
        <h2 id="coming-up" className="wide text-xl">Coming up</h2>
        {soon.length === 0 && <p className="text-muted">Nothing coming up yet.</p>}
        <ul className="flex flex-col gap-3">
          {soon.map((t) => (
            <li key={t.share_token}><Card t={t} today={today} /></li>
          ))}
        </ul>
      </section>
      {past.length > 0 && (
        <section aria-labelledby="past" className="flex flex-col gap-1.5 px-5 pt-7.5">
          <h2 id="past" className="wide mb-1 text-xl">Past</h2>
          <ul className="border-b border-line">
            {past.map((t) => (
              <li key={t.share_token} className="border-t border-line">
                <Link href={`/t/${t.share_token}`} className="flex items-center gap-3.5 py-3 no-underline">
                  <Image src={themeInfo(t.theme).photo} alt="" width={56} height={56} className="size-14 flex-none rounded-xl object-cover" />
                  <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                    <span className="truncate font-bold">{t.name}</span>
                    <span className="text-sm text-muted">{formatDateRange(t.start_date, t.end_date) ?? "No dates"}</span>
                  </span>
                  <span className={`text-sm ${t.net_cents ? "font-bold" : "text-muted"}`}>{money(t)}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
      <section aria-labelledby="missing" className="card mx-3.5 mt-7.5 flex flex-col gap-2.5 p-[18px]">
        <h2 id="missing" className="text-[17px] font-bold">Missing a trip?</h2>
        <p className="text-[15px] leading-[1.45] text-muted">Get a code, post it in that trip&rsquo;s group chat, and the trip shows up here.</p>
        <Link href="/link" className="btn btn-line self-start px-5 text-[15px]">Get a link code</Link>
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
  const dates = formatShortRange(t.start_date, t.end_date);
  const when = soonPhrase(countdown(t.start_date, t.end_date, today));
  const line = [dates ?? "Dates not picked yet", when].filter(Boolean).join(", ");
  return (
    <Link href={`/t/${t.share_token}`} className="relative block h-[200px] overflow-hidden rounded-[20px] no-underline">
      <Image src={themeInfo(t.theme).photo} alt="" fill sizes="(max-width: 672px) 100vw, 672px" className="object-cover object-[center_45%]" />
      <span aria-hidden="true" className="absolute inset-0 bg-[linear-gradient(180deg,rgb(10_14_26/0.35)_0%,rgb(10_14_26/0.1)_35%,rgb(10_14_26/0.8)_100%)]" />
      <span className="absolute top-3.5 left-3.5 rounded-lg bg-white/22 px-2.5 py-1 text-xs font-semibold">{STATUS_LABEL[t.status]}</span>
      <span className="absolute inset-x-4 bottom-3.5 flex flex-col gap-1">
        <span className="text-[22px] leading-[1.05] font-extrabold [font-stretch:112%]">{t.name}</span>
        <span className="flex justify-between gap-2.5 text-sm">
          <span className="text-soft">{line}</span>
          <span className="flex-none font-bold">{money(t)}</span>
        </span>
      </span>
    </Link>
  );
}

/** "122 days to go" -> "in 122 days"; "Tomorrow" -> "tomorrow". */
function soonPhrase(c: string | null): string | null {
  if (!c) return null;
  const days = c.match(/^(\d+) days to go$/);
  return days ? `in ${days[1]} days` : c.toLowerCase();
}
