import { describe, expect, it } from "vitest";

import {
  formatDateRange, formatDay, formatMoney, formatTime, groupByDay, isOutsideTrip, payLink, warningText,
} from "@/lib/format";
import type { Activity } from "@/lib/types";

const activity = (id: string, start: string | null): Activity => ({
  activity_id: id, name: id, location: null, start, end: null, est_cost_cents: null,
  cost_is_per_person: true, est_per_person_cents: null, attendees: [], important: false,
  booking_url: null, expense_id: null,
});

describe("formatMoney", () => {
  it("drops cents on whole amounts and keeps them otherwise", () => {
    expect(formatMoney(5000)).toBe("$50");
    expect(formatMoney(3336)).toBe("$33.36");
    expect(formatMoney(166700)).toBe("$1,667");
    expect(formatMoney(180000, "MXN")).toBe("MX$1,800");
  });
});

describe("dates", () => {
  it("formats ranges without time-zone drift", () => {
    expect(formatDateRange("2027-03-14", "2027-03-18")).toBe("Mar 14–18, 2027");
    expect(formatDateRange("2027-03-30", "2027-04-02")).toBe("Mar 30 – Apr 2, 2027");
    expect(formatDateRange(null, null)).toBeNull();
    expect(formatDay("2027-03-15")).toBe("Mon, Mar 15");
  });

  it("formats times only when there is one", () => {
    expect(formatTime("2027-03-15T14:00")).toBe("2pm");
    expect(formatTime("2027-03-15T09:30")).toBe("9:30am");
    expect(formatTime("2027-03-15")).toBeNull();
  });
});

describe("groupByDay", () => {
  it("groups by date in order, sorts by time, and puts undated last", () => {
    const days = groupByDay([
      activity("dinner", "2027-03-15T19:00"),
      activity("tbd", null),
      activity("beach", "2027-03-14"),
      activity("boat", "2027-03-15T10:00"),
    ]);
    expect(days.map((d) => d.date)).toEqual(["2027-03-14", "2027-03-15", null]);
    expect(days[1].activities.map((a) => a.activity_id)).toEqual(["boat", "dinner"]);
  });

  it("flags activities outside the trip dates", () => {
    expect(isOutsideTrip(activity("x", "2027-03-15T10:00"), "2027-03-16", "2027-03-20")).toBe(true);
    expect(isOutsideTrip(activity("x", "2027-03-17"), "2027-03-16", "2027-03-20")).toBe(false);
  });
});

describe("payLink", () => {
  it("builds a Venmo pay link with the amount for @handles", () => {
    const link = payLink("@aarav-venmo", 30000, "Miami");
    expect(link).toEqual({
      kind: "venmo",
      href: "https://venmo.com/aarav-venmo?txn=pay&amount=300.00&note=Miami",
      label: "Pay on Venmo",
    });
  });

  it("shows other handles (Zelle email/phone) to copy, and nothing without a handle", () => {
    expect(payLink("sam@example.com", 100, "x")).toMatchObject({ kind: "other", handle: "sam@example.com" });
    expect(payLink(null, 100, "x")).toBeNull();
  });
});

describe("warningText", () => {
  it("puts the engine's warnings in plain words", () => {
    expect(warningText("DRINKS under 10% remaining")).toBe("Drinks: under 10% left");
    expect(warningText("FOOD over limit by $12 including planned activities"))
      .toBe("Food: over limit by $12 including planned activities");
  });
  it("accepts objects in case the format changes", () => {
    expect(warningText({ category: "DRINKS", message: "under 10% remaining" })).toBe("Drinks: under 10% left");
    expect(warningText({ text: "Almost out of USD cash" })).toBe("Almost out of USD cash");
  });
});
