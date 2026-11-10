import type { Activity, PublicTrip, TripDetail } from "./types";

// Mirrors backend/trips/public.py, for fixtures mode (no backend). Fields are listed, not
// removed, so anything new in the full trip stays off the share-link view until added here.
const TRIP_FIELDS = [
  "id", "name", "status", "destination", "start_date", "end_date", "target_break", "base_currency", "leader_id",
] as const;
const ACTIVITY_FIELDS = [
  "activity_id", "name", "location", "start", "end", "est_cost_cents", "cost_is_per_person", "est_per_person_cents",
  "attendees", "important", "booking_url", "lat", "lon", "verified", "maps_url", "kind", "from_idea",
] as const;

function pick<T extends object, K extends keyof T>(obj: T, keys: readonly K[]): Pick<T, K> {
  const out = {} as Pick<T, K>;
  for (const k of keys) if (k in obj) out[k] = obj[k];
  return out;
}

export function toPublicTrip(detail: TripDetail): PublicTrip {
  return {
    trip: pick(detail.trip, TRIP_FIELDS),
    members: detail.members.map((m) => pick(m, ["id", "name", "active"] as const)),
    // expense_id is left out on purpose: whether a stop is paid for is money.
    activities: detail.activities.map((a) => pick(a, ACTIVITY_FIELDS) as Activity),
    ideas: (detail.ideas ?? []).map((i) => pick(i, ["idea_id", "name", "kind", "location"] as const)),
  };
}
