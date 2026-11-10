import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { toPublicTrip } from "@/lib/public";
import type { TripPageData } from "@/lib/types";

const fixture = (name: string): TripPageData =>
  JSON.parse(readFileSync(path.join(__dirname, "..", "fixtures", `${name}.json`), "utf8"));

describe("toPublicTrip", () => {
  it("keeps the plan and drops everything about money", () => {
    const { detail } = fixture("miami-demo");
    const pub = toPublicTrip(detail);
    expect(Object.keys(pub).sort()).toEqual(["activities", "ideas", "members", "trip"]);
    expect(pub.trip.name).toBe("Miami Spring Break");
    expect(pub.activities).toHaveLength(detail.activities.length);
    expect(pub.activities[0].est_per_person_cents).toBe(detail.activities[0].est_per_person_cents);
    expect(pub.members[0]).toEqual({ id: "aarav", name: "Aarav", active: true });

    const text = JSON.stringify(pub);
    for (const key of ["group_budget_cents", "lodging", "handle", "budget", "expense", "venmo"]) {
      expect(text).not.toContain(key);
    }
  });
});
