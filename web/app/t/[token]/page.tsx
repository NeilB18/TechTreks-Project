import type { Metadata } from "next";

import { Ideas } from "@/components/Ideas";
import { Itinerary } from "@/components/Itinerary";
import { Details } from "@/components/trip/Details";
import { Invite } from "@/components/trip/Invite";
import { Latest } from "@/components/trip/Latest";
import { loadTrip, sharedTrip, TripShell } from "@/components/trip/TripShell";
import { YourMoney } from "@/components/trip/YourMoney";

export async function generateMetadata(props: PageProps<"/t/[token]">): Promise<Metadata> {
  const { token } = await props.params;
  const data = await sharedTrip(token);
  return { title: data ? data.trip.name : "Trip not found" };
}

// The Trip tab, at /t/<share_token>: the link the bot posts (design canvas: Final designs, "Trip
// tab"). The details and the plan render on the server from the shared view, for anyone with the
// link. Your money, Latest and where you're staying load in the browser, only for signed-in
// people on the trip. The Money tab is /t/<share_token>/money.
export default async function TripPage(props: PageProps<"/t/[token]">) {
  const view = await loadTrip(props);
  const { data, pagePath, query } = view;
  return (
    <TripShell view={view} tab="trip">
      <Details data={data} />
      <Invite />
      <YourMoney moneyHref={`${pagePath}/money${query}`} />
      <Latest />
      <section aria-labelledby="plan" className="flex flex-col gap-2.5 px-5 pt-7.5">
        <h2 id="plan" className="wide mb-1 text-xl">The plan</h2>
        <Itinerary activities={data.activities} trip={data.trip} />
        {data.ideas.length > 0 && <Ideas ideas={data.ideas} />}
      </section>
    </TripShell>
  );
}
