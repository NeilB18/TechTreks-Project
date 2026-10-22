import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { Balances } from "@/components/Balances";
import { BudgetPanel } from "@/components/BudgetPanel";
import { Expenses } from "@/components/Expenses";
import { Itinerary } from "@/components/Itinerary";
import { getTripPage } from "@/lib/api";
import { formatDateRange, formatMoney } from "@/lib/format";

export async function generateMetadata(props: PageProps<"/trips/[id]">): Promise<Metadata> {
  const { id } = await props.params;
  const data = await getTripPage(id);
  return { title: data ? data.detail.trip.name : "Trip not found" };
}

const STATUS_LABEL = { PLANNING: "Planning", BOOKED: "Booked", ACTIVE: "On the trip", DONE: "Done" } as const;

export default async function TripPage(props: PageProps<"/trips/[id]">) {
  const { id } = await props.params;
  const data = await getTripPage(id);
  if (!data) notFound();
  const { detail, balances } = data;
  const { trip, members } = detail;
  const active = members.filter((m) => m.active);
  const leader = members.find((m) => m.id === trip.leader_id);
  const dates = formatDateRange(trip.start_date, trip.end_date);

  return (
    <main className="mx-auto w-full max-w-2xl px-4 py-8">
      <header>
        <p className="text-sm font-medium text-accent">{STATUS_LABEL[trip.status]}</p>
        <h1 className="mt-1 text-2xl font-semibold">{trip.name}</h1>
        <p className="mt-1 text-muted">{[trip.destination, dates].filter(Boolean).join(" · ") || "Destination TBD"}</p>
        <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
          <div className="rounded-xl border border-line bg-card p-3">
            <dt className="text-xs text-muted">Group budget</dt>
            <dd className="font-semibold tabular-nums">
              {trip.group_budget_cents != null
                ? `${formatMoney(trip.group_budget_cents, trip.base_currency)}/person`
                : "Not picked yet"}
            </dd>
          </div>
          <div className="rounded-xl border border-line bg-card p-3">
            <dt className="text-xs text-muted">Going</dt>
            <dd className="font-semibold">{active.length} people</dd>
          </div>
          <div className="col-span-2 rounded-xl border border-line bg-card p-3 sm:col-span-1">
            <dt className="text-xs text-muted">Trip lead</dt>
            <dd className="font-semibold">{leader?.name ?? "Not set"}</dd>
          </div>
        </dl>
        <p className="mt-3 text-sm text-muted">{active.map((m) => m.name).join(", ")}</p>
      </header>

      <section className="mt-8" aria-labelledby="itinerary">
        <h2 id="itinerary" className="mb-3 text-lg font-semibold">Itinerary</h2>
        <Itinerary activities={detail.activities} trip={trip} />
      </section>

      <section className="mt-8" aria-labelledby="balances">
        <h2 id="balances" className="mb-3 text-lg font-semibold">Who owes whom</h2>
        <Balances balances={balances} members={members} tripName={trip.name} />
      </section>

      <section className="mt-8" aria-labelledby="expenses">
        <h2 id="expenses" className="mb-3 text-lg font-semibold">Expenses</h2>
        <Expenses expenses={detail.expenses} members={members} currency={trip.base_currency} />
      </section>

      <section className="mt-8">
        <BudgetPanel />
      </section>
    </main>
  );
}
