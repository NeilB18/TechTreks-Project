import { readFileSync } from "node:fs";
import path from "node:path";

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Itinerary } from "@/components/Itinerary";
import { Money } from "@/components/Money";
import type { TripPageData } from "@/lib/types";

const fixture = (name: string): TripPageData =>
  JSON.parse(readFileSync(path.join(__dirname, "..", "fixtures", `${name}.json`), "utf8"));

afterEach(cleanup);

describe("Money (style D)", () => {
  const view = (name: string, me: string) => {
    const data = fixture(name);
    return { ...data, person_id: me, budget: data.budgets?.[me] ?? null };
  };

  it("shows Example 9's netted settle-up after the refund, with a Venmo link for the payer", () => {
    render(<Money data={view("ex9-refund", "mia")} />);
    expect(screen.getByRole("heading", { name: /^You owe/ }).textContent).toBe("You owe $50");
    const pay = screen.getByRole("link", { name: "Pay on Venmo" });
    expect(pay.getAttribute("href")).toContain("venmo.com/jake-venmo?txn=pay&amount=50.00");
  });

  it("offers copy for Zelle-style handles, lists the rest of the group, and paybacks as sent", () => {
    render(<Money data={view("miami-demo", "mia")} />);
    expect(screen.getByRole("button", { name: "Copy email" })).toBeTruthy();
    expect(screen.getByText("Leo pays Aarav")).toBeTruthy();
    expect(screen.getByText("Priya sent Aarav")).toBeTruthy();
  });

  it("groups spending, with each person's share, foreign originals and refunds", () => {
    render(<Money data={view("miami-demo", "mia")} />);
    for (const label of ["Staying", "Food and drinks", "Things to do"]) expect(screen.getByText(label)).toBeTruthy();
    // Jake paid the bar tab but opted out of drinks: 5 people share it, not 6.
    expect(screen.getByText("Jake paid $350 · 5 people")).toBeTruthy();
    expect(screen.getByText(/MX\$1,800/)).toBeTruthy();
    expect(screen.getByText(/\$150 back/)).toBeTruthy();
    expect(screen.getAllByText("not in it").length).toBeGreaterThan(0); // Mia isn't in the concert tickets
  });

  it("lists everyone's budget, yours first", () => {
    render(<Money data={view("ex5-travel-tips", "mia")} />);
    expect(screen.getByText("You")).toBeTruthy();
    expect(screen.getByText(/of \$1,200/)).toBeTruthy(); // Aarav
    expect(screen.getByText(/of \$800/)).toBeTruthy(); // Jake
  });

  it("says when everyone's settled", () => {
    const data = view("miami-demo", "mia");
    render(<Money data={{ ...data, balances: { ...data.balances, suggested_payments: [] },
      detail: { ...data.detail, expenses: [] } }} />);
    expect(screen.getByRole("heading", { name: "All settled" })).toBeTruthy();
    expect(screen.getByText(/Nothing spent yet/)).toBeTruthy();
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

describe("fixtures carry everyone's budget (budgets are shared with the trip)", () => {
  it("ex5-travel-tips", () => {
    const { members } = fixture("ex5-travel-tips").detail;
    expect(Object.fromEntries(members.map((m) => [m.id, m.budget_cents]))).toEqual(
      { aarav: 120000, jake: 80000, mia: 50000 });
  });
});

describe("Itinerary folding", () => {
  it("opens the first two days and folds the rest, with their stops listed", () => {
    const { detail } = fixture("miami-demo");
    const { container } = render(<Itinerary activities={detail.activities} trip={detail.trip} />);
    const days = [...container.querySelectorAll("details")];
    expect(days.map((d) => d.open)).toEqual([true, true, false, false, false]);
    expect(screen.getByText("Day 3")).toBeTruthy();
    expect(screen.getByText("South Pointe Park, La Mar by Gastón Acurio")).toBeTruthy();
    expect(screen.getAllByRole("link", { name: /on Google Maps/ })).toHaveLength(detail.activities.length);
    expect(screen.getByText("Must do")).toBeTruthy();
  });

  it("says nothing's planned and how to ask, when there are no stops", () => {
    render(<Itinerary activities={[]} trip={fixture("miami-demo").detail.trip} />);
    expect(screen.getByRole("heading", { name: "Nothing planned yet" })).toBeTruthy();
  });
});
