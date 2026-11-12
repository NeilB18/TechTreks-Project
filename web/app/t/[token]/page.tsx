import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Avatars } from "@/components/Avatars";
import { CopyLinkButton } from "@/components/CopyLinkButton";
import { Ideas } from "@/components/Ideas";
import { Itinerary } from "@/components/Itinerary";
import { MoneySection } from "@/components/MoneySection";
import { PreviewBar } from "@/components/PreviewBar";
import { TripArt } from "@/components/TripArt";
import { getFixtureTrip, getSharedTrip, usingFixtures } from "@/lib/api";
import { countdown, formatDayRange } from "@/lib/format";

export async function generateMetadata(props: PageProps<"/t/[token]">): Promise<Metadata> {
  const { token } = await props.params;
  const data = await getSharedTrip(token);
  return { title: data ? data.trip.name : "Trip not found" };
}

const STATUS_LABEL = { PLANNING: "Planning", BOOKED: "Booked", ACTIVE: "On the trip", DONE: "Done" } as const;

// The trip page, at /t/<share_token>: the link the bot posts. The overview and itinerary render on
// the server from the shared view. The money side (MoneySection) loads in the browser, and only
// for signed-in members of the trip. Look: the "Sunset" artboard on the design canvas.
export default async function TripPage(props: PageProps<"/t/[token]">) {
  const { token } = await props.params;
  const { as } = await props.searchParams;
  const data = await getSharedTrip(token);
  if (!data) notFound();
  const { trip, members } = data;
  const sample = usingFixtures ? await getFixtureTrip(token) : null;
  const active = members.filter((m) => m.active);
  const leader = members.find((m) => m.id === trip.leader_id);
  const dates = formatDayRange(trip.start_date, trip.end_date);
  const soon = countdown(trip.start_date, trip.end_date, new Date().toISOString().slice(0, 10));
  const pagePath = `/t/${encodeURIComponent(token)}`;
  const previewAs = sample && typeof as === "string" ? as : undefined;
  const where = [trip.destination ?? "Destination not picked yet", soon].filter(Boolean).join(" · ");

  return (
    <main className="mx-auto w-full max-w-2xl">
      {sample && <PreviewBar sample={sample} pagePath={pagePath} as={previewAs} />}
      <nav className="flex items-center justify-between px-5 py-3.5">
        <Link href="/" className="display text-xl tracking-tight text-ink no-underline">
          techtreks
        </Link>
      </nav>

      <div className="relative overflow-hidden">
        <TripArt />
        <span className="sticker absolute top-[74px] left-5 -rotate-6">{STATUS_LABEL[trip.status]}</span>
      </div>

      <header className="flex flex-col gap-3.5 px-5 pt-5 pb-2">
        <h1 className="display text-[46px]">{trip.name}</h1>
        <div>
          <p className="text-[17px] font-semibold">{dates ?? "Dates not picked yet"}</p>
          <p className="text-[15px] text-muted">{where}</p>
        </div>
        {active.length > 0 && (
          <div className="mt-1.5 flex items-center gap-3">
            <Avatars names={active.map((m) => m.name)} colorIndexes={active.map((m) => members.indexOf(m))} />
            <p className="flex flex-col">
              <span className="text-[15px] font-bold">{active.length} going</span>
              <span className="text-sm text-muted">{leader ? `${leader.name} is leading` : "No trip lead yet"}</span>
            </p>
          </div>
        )}
        <p className="sr-only">Going: {active.map((m) => m.name).join(", ")}</p>
        <div className="mt-2 flex gap-2.5">
          <CopyLinkButton />
        </div>
      </header>

      <section aria-labelledby="itinerary" className="flex flex-col gap-3.5 px-5 pt-7">
        <h2 id="itinerary" className="display text-[28px]">The plan</h2>
        <Itinerary activities={data.activities} trip={trip} />
      </section>

      {data.ideas.length > 0 && (
        <section aria-labelledby="ideas" className="flex flex-col gap-3 px-5 pt-7">
          <h2 id="ideas" className="display text-[22px]">Ideas, no day yet</h2>
          <Ideas ideas={data.ideas} />
        </section>
      )}

      <div className="px-5 pt-8">
        <MoneySection tripId={trip.id} pagePath={pagePath} live={!usingFixtures} sample={sample} previewAs={previewAs} />
      </div>
    </main>
  );
}
