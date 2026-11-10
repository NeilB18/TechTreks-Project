import "server-only";

import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

import { toPublicTrip } from "./public";
import type { PublicTrip, TripPageData } from "./types";

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

/** What anyone with the trip's link sees. */
export async function getPublicTrip(tripId: string): Promise<PublicTrip | null> {
  if (API_URL) return fromApi<PublicTrip>(`/api/trips/${encodeURIComponent(tripId)}/public`);
  const data = await getFixtureTrip(tripId);
  return data && toPublicTrip(data.detail);
}

/** A fixture's full trip, money included. Fixtures mode only (sample data, no sign-in). */
export async function getFixtureTrip(tripId: string): Promise<TripPageData | null> {
  if (API_URL || !/^[\w-]+$/.test(tripId)) return null;
  try {
    return JSON.parse(await readFile(path.join(FIXTURE_DIR, `${tripId}.json`), "utf8")) as TripPageData;
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

export const usingFixtures = !API_URL;
