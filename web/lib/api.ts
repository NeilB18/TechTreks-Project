import "server-only";

import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

import { previewMember } from "./preview";
import { toPublicTrip } from "./public";
import type { PublicTrip, TripCard, TripPageData } from "./types";

// With TRIP_API_URL set, the page's public part (overview and itinerary) comes from the
// Django API (server-side only, so the token never reaches the browser), and the money
// side is fetched in the browser by signed-in members (components/MoneySection.tsx).
// Without it, the page reads JSON fixtures that scripts/export_fixtures.py generates
// from the backend's TripEngine, and shows their sample money to everyone.
const API_URL = process.env.TRIP_API_URL;
const API_TOKEN = process.env.TRIP_API_TOKEN;
const FIXTURE_DIR = path.join(process.cwd(), "fixtures");

async function fromApi<T>(route: string): Promise<T | null> {
  const res = await fetch(`${API_URL}${route}`, {
    headers: { Authorization: `Bearer ${API_TOKEN}`, "ngrok-skip-browser-warning": "1" },
    cache: "no-store",
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`Trip API ${route} failed: ${res.status}`);
  return (await res.json()) as T;
}

/** What anyone with the trip's link (/t/<share_token>) sees. In fixtures mode the token is the fixture's name. */
export async function getSharedTrip(token: string): Promise<PublicTrip | null> {
  if (API_URL) return fromApi<PublicTrip>(`/api/share/${encodeURIComponent(token)}`);
  const data = await getFixtureTrip(token);
  return data && toPublicTrip(data.detail);
}

/** A fixture's full trip, money included. Fixtures mode only (sample data, no sign-in). */
export async function getFixtureTrip(name: string): Promise<TripPageData | null> {
  if (API_URL || !/^[\w-]+$/.test(name)) return null;
  try {
    return JSON.parse(await readFile(path.join(FIXTURE_DIR, `${name}.json`), "utf8")) as TripPageData;
  } catch {
    return null;
  }
}

/** Fixture trips for the index page; empty when reading from the API. */
export async function listFixtureTrips(): Promise<{ id: string; name: string }[]> {
  if (API_URL) return [];
  const files = (await readdir(FIXTURE_DIR)).filter((f) => f.endsWith(".json")).sort();
  return Promise.all(
    files.map(async (f) => {
      const data = JSON.parse(await readFile(path.join(FIXTURE_DIR, f), "utf8")) as TripPageData;
      return { id: f.replace(/\.json$/, ""), name: data.detail.trip.name };
    }),
  );
}

/** Sample mode's My trips: every fixture, as seen by the person the trip page previews by default. */
export async function listFixtureCards(): Promise<TripCard[]> {
  if (API_URL) return [];
  const files = (await readdir(FIXTURE_DIR)).filter((f) => f.endsWith(".json")).sort();
  return Promise.all(
    files.map(async (f) => {
      const data = JSON.parse(await readFile(path.join(FIXTURE_DIR, f), "utf8")) as TripPageData;
      const t = data.detail.trip;
      const me = previewMember(data);
      return {
        trip_id: t.id, name: t.name, share_token: f.replace(/\.json$/, ""), status: t.status,
        destination: t.destination, start_date: t.start_date, end_date: t.end_date, theme: t.theme ?? null,
        going: data.detail.members.filter((m) => m.active).length, net_cents: data.balances.net_balances[me] ?? 0,
      };
    }),
  );
}

export const usingFixtures = !API_URL;
