import type { Metadata } from "next";

import { MoneySection } from "@/components/MoneySection";
import { loadTrip, sharedTrip, TripShell } from "@/components/trip/TripShell";

export async function generateMetadata(props: PageProps<"/t/[token]/money">): Promise<Metadata> {
  const { token } = await props.params;
  const data = await sharedTrip(token);
  return { title: data ? `Money: ${data.trip.name}` : "Trip not found" };
}

// The Money tab, at /t/<share_token>/money (design canvas: "Money tab"): settle up for the whole
// group, everyone's budgets, and every expense and payment. Only people on the trip see it.
export default async function MoneyPage(props: PageProps<"/t/[token]/money">) {
  const view = await loadTrip(props);
  return (
    <TripShell view={view} tab="money">
      <div className="px-5 pt-6">
        <MoneySection />
      </div>
    </TripShell>
  );
}
