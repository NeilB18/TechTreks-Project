import { readFileSync } from "node:fs";
import path from "node:path";

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Balances } from "@/components/Balances";
import { Expenses } from "@/components/Expenses";
import { Itinerary } from "@/components/Itinerary";
import type { TripPageData } from "@/lib/types";

const fixture = (name: string): TripPageData =>
  JSON.parse(readFileSync(path.join(__dirname, "..", "fixtures", `${name}.json`), "utf8"));

afterEach(cleanup);

describe("Balances", () => {
  it("shows Example 9's netted settle-up after the refund", () => {
    const { detail, balances } = fixture("ex9-refund");
    render(<Balances balances={balances} members={detail.members} tripName={detail.trip.name} />);
    const items = screen.getAllByRole("listitem").map((li) => li.textContent);
    expect(items).toEqual([expect.stringContaining("Mia pays Jake $50")]);
    const pay = screen.getAllByRole("link", { name: "Pay on Venmo" });
    expect(pay[0].getAttribute("href")).toContain("venmo.com/jake-venmo?txn=pay&amount=50.00");
  });

  it("offers copy for Zelle-style handles and says when everyone is settled", () => {
    const { detail, balances } = fixture("miami-demo");
    render(<Balances balances={balances} members={detail.members} tripName="Miami" />);
    expect(screen.getAllByRole("button", { name: /sam@example.com/ }).length).toBeGreaterThan(0);
    cleanup();
    render(<Balances balances={{ net_balances: {}, suggested_payments: [], currency: "USD" }} members={[]} tripName="x" />);
    expect(screen.getByText(/settled up/)).toBeTruthy();
  });
});

describe("Expenses", () => {
  it("shows foreign-currency originals and refunds", () => {
    const { detail } = fixture("miami-demo");
    render(<Expenses expenses={detail.expenses} members={detail.members} currency="USD" />);
    // Jake paid the bar tab but opted out of drinks: 5 people share it, not 6.
    expect(screen.getByText(/paid by Jake · split 5 ways/)).toBeTruthy();
    expect(screen.getByText("MX$1,800")).toBeTruthy();
    expect(screen.getByText("$150 refunded")).toBeTruthy();
    expect(screen.getByText(/Payback · paid by Priya to Aarav/)).toBeTruthy();
  });
});

describe("Itinerary", () => {
  it("flags Example 2a's boat tour as outside the new dates", () => {
    const { detail } = fixture("ex2a-date-change");
    render(<Itinerary activities={detail.activities} trip={detail.trip} />);
    expect(screen.getByText("Outside the trip dates")).toBeTruthy();
    expect(screen.getByText("Mon, Mar 15")).toBeTruthy();
  });
});

describe("fixtures never contain budgets", () => {
  it.each(["miami-demo", "ex5-travel-tips", "ex2b-budget-change"])("%s", (name) => {
    const text = JSON.stringify(fixture(name));
    expect(text).not.toContain("total_cents");
    expect(text).not.toContain("budgets");
  });
});
