import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { Itinerary } from "@/components/Itinerary";
import { MoneySection } from "@/components/MoneySection";
import { getFixtureTrip, getPublicTrip, usingFixtures } from "@/lib/api";
import { formatDateRange } from "@/lib/format";

export async function generateMetadata(props: PageProps<"/trips/[id]">): Promise<Metadata> {
  const { id } = await props.params;
  const data = await getPublicTrip(id);
  return { title: data ? data.trip.name : "Trip not found" };
}

const STATUS_LABEL = { PLANNING: "Planning", BOOKED: "Booked", ACTIVE: "On the trip", DONE: "Done" } as const;

// The overview and itinerary render on the server from the public view. The money side
// (MoneySection) loads in the browser, and only for signed-in members of the trip.
export default async function TripPage(props: PageProps<"/trips/[id]">) {
  const { id } = await props.params;
  const data = await getPublicTrip(id);
  if (!data) notFound();
  const { trip, members } = data;
  const sample = usingFixtures ? await getFixtureTrip(id) : null;
  const active = members.filter((m) => m.active);
  const leader = members.find((m) => m.id === trip.leader_id);
  const dates = formatDateRange(trip.start_date, trip.end_date);

  return (
    <main className="mx-auto w-full max-w-2xl px-4 py-8">
      <header>
        <p className="text-sm font-medium text-accent">{STATUS_LABEL[trip.status]}</p>
        <h1 className="mt-1 text-2xl font-semibold">{trip.name}</h1>
        <p className="mt-1 text-muted">{[trip.destination, dates].filter(Boolean).join(" · ") || "Destination TBD"}</p>
        <dl className="mt-4 grid grid-cols-2 gap-3">
          <div className="rounded-xl border border-line bg-card p-3">
            <dt className="text-xs text-muted">Going</dt>
            <dd className="font-semibold">{active.length} people</dd>
          </div>
          <div className="rounded-xl border border-line bg-card p-3">
            <dt className="text-xs text-muted">Trip lead</dt>
            <dd className="font-semibold">{leader?.name ?? "Not set"}</dd>
          </div>
        </dl>
        <p className="mt-3 text-sm text-muted">{active.map((m) => m.name).join(", ")}</p>
      </header>

      <section className="mt-8" aria-labelledby="itinerary">
        <h2 id="itinerary" className="mb-3 text-lg font-semibold">Itinerary</h2>
        <Itinerary activities={data.activities} trip={trip} />
      </section>

      <div className="mt-8">
        <MoneySection tripId={trip.id} live={!usingFixtures} sample={sample} />
      </div>
    </main>
  );
}
