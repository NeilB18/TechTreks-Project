import type { Metadata } from "next";
import { connection } from "next/server";

import { Footer } from "@/components/Footer";
import { MyTripsList } from "@/components/MyTripsList";
import { TopBar } from "@/components/TopBar";
import { listFixtureCards, usingFixtures } from "@/lib/api";

export const metadata: Metadata = { title: "Your trips" };

// My trips (design canvas: "My trips"). Live, the list loads in the browser for the signed-in
// account; in sample mode it shows every fixture.
export default async function MyTripsPage() {
  await connection(); // per request: "today" decides what's past and the countdowns
  const sample = usingFixtures ? await listFixtureCards() : null;
  return (
    <>
      <main id="main" className="mx-auto w-full max-w-2xl">
        <TopBar live={!usingFixtures} />
        <h1 className="display px-5 pt-6 text-[46px]">Your trips</h1>
        <MyTripsList sample={sample} today={new Date().toISOString().slice(0, 10)} />
      </main>
      <Footer />
    </>
  );
}
