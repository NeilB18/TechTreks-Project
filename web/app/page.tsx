import Link from "next/link";

import { listFixtureTrips, usingFixtures } from "@/lib/api";

export default async function Home() {
  const trips = await listFixtureTrips();
  return (
    <main className="mx-auto w-full max-w-2xl px-4 py-10">
      <h1 className="text-2xl font-semibold">Trip pages</h1>
      {usingFixtures ? (
        <>
          <p className="mt-2 text-sm text-muted">
            Sample trips generated from examples.md. Set TRIP_API_URL to read real trips from the backend.
          </p>
          <ul className="mt-6 divide-y divide-line rounded-xl border border-line bg-card">
            {trips.map((t) => (
              <li key={t.id}>
                <Link href={`/trips/${t.id}`} className="flex justify-between gap-3 p-3 hover:bg-line/30">
                  <span className="font-medium">{t.name}</span>
                  <span className="text-sm text-muted">{t.id}</span>
                </Link>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="mt-2 text-sm text-muted">Open the link @tripbot posted in your group chat.</p>
      )}
    </main>
  );
}
