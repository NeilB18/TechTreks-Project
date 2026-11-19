import { readFileSync } from "node:fs";
import path from "node:path";

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Itinerary } from "@/components/Itinerary";
import { MoneySection } from "@/components/MoneySection";
import { MemberDataProvider } from "@/components/trip/MemberData";
import type { TripPageData } from "@/lib/types";

const fixture = (name: string): TripPageData =>
  JSON.parse(readFileSync(path.join(__dirname, "..", "fixtures", `${name}.json`), "utf8"));

afterEach(cleanup);

describe("Money tab", () => {
  // Sample mode: the fixture, previewed as `me` (the money data comes from the page's provider).
  const view = (name: string, me: string) => (
    <MemberDataProvider tripId={name} pagePath={`/t/${name}`} live={false} sample={fixture(name)} previewAs={me}>
      <MoneySection />
    </MemberDataProvider>
  );

  it("shows Example 9's netted settle-up after the refund, with a Venmo link for the payer", () => {
    render(view("ex9-refund", "mia"));
    expect(screen.getAllByText("You owe Jake $50").length).toBeGreaterThan(0);
    const pay = screen.getByRole("link", { name: "Pay on Venmo" });
    expect(pay.getAttribute("href")).toContain("venmo.com/jake-venmo?txn=pay&amount=50.00");
  });

  it("offers copy for Zelle-style handles, lists the rest of the group, and payments as sent", () => {
    render(view("miami-demo", "mia"));
    expect(screen.getByRole("button", { name: "Copy Jake's email" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "The rest of the group" })).toBeTruthy();
    expect(screen.getByText("Leo pays Aarav")).toBeTruthy();
    expect(screen.getAllByText("Priya sent Aarav")).toHaveLength(2); // settle-up and the list
  });

  it("lists everything spent, newest first, with what it was for you", () => {
    render(view("miami-demo", "mia"));
    const rows = screen.getByRole("heading", { name: "Everything spent" }).parentElement!.querySelectorAll("ol > li");
    expect(rows[0].textContent).toContain("Refund: Concert tickets");
    // Jake paid the bar tab but opted out of drinks: 5 people share it, not 6.
    expect(screen.getByText(/Drinks\. Jake paid, split 5 ways/)).toBeTruthy();
    expect(screen.getByText(/MX\$1,800 originally/)).toBeTruthy();
    expect(screen.getByText(/\$150 back/)).toBeTruthy();
    expect(screen.getAllByText("Not split with you").length).toBeGreaterThan(0); // Mia isn't in the concert tickets
    expect(screen.queryByText("Not in it")).toBeNull();
    expect(screen.getByText("You: $250")).toBeTruthy(); // the Airbnb
    expect(screen.queryByText(/share of/i)).toBeNull();
  });

  it("lists everyone's budget, yours first", () => {
    render(view("ex1-dropout", "mia"));
    const rows = screen.getByRole("heading", { name: "Budgets" }).closest("section")!.querySelectorAll("li");
    expect(rows[0].textContent).toContain("You");
    expect(screen.getByText(/of \$1,500/)).toBeTruthy(); // Aarav
    expect(screen.getByText(/of \$1,100/)).toBeTruthy(); // Jake
    expect(screen.getByRole("button", { name: "Change mine" })).toBeTruthy();
  });

  it("says when everyone's settled and nothing's been spent", () => {
    const data = fixture("miami-demo");
    const empty = { ...data, balances: { ...data.balances, suggested_payments: [] },
      detail: { ...data.detail, expenses: [], refunds: [] } };
    render(
      <MemberDataProvider tripId="x" pagePath="/t/x" live={false} sample={empty} previewAs="mia">
        <MoneySection />
      </MemberDataProvider>,
    );
    expect(screen.getByText("Everyone’s settled up")).toBeTruthy();
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
  it("ex1-dropout", () => {
    const { members } = fixture("ex1-dropout").detail;
    expect(Object.fromEntries(members.map((m) => [m.id, m.budget_cents]))).toEqual(
      { aarav: 150000, priya: null, jake: 110000, mia: 95000 });
  });
});

describe("Itinerary folding", () => {
  it("opens the first two days and folds the rest, with their stops listed", () => {
    const { detail } = fixture("miami-demo");
    const { container } = render(<Itinerary activities={detail.activities} trip={detail.trip} />);
    const days = [...container.querySelectorAll("details")];
    expect(days.map((d) => d.open)).toEqual([true, true, false, false, false]);
    expect(screen.getByText("Day 3")).toBeTruthy();
    expect(screen.getByText("Vizcaya Museum and Gardens, La Mar by Gastón Acurio")).toBeTruthy();
    expect(screen.getAllByRole("link", { name: /on Google Maps/ })).toHaveLength(detail.activities.length);
    expect(screen.getByText("Must do")).toBeTruthy();
  });

  it("shows a slot by name, a clock time as a time, and just-a-day plans first as any time", () => {
    const { detail } = fixture("miami-demo");
    const { container } = render(<Itinerary activities={detail.activities} trip={detail.trip} />);
    const sunday = [...container.querySelectorAll("details")[0].querySelectorAll("li")].map((li) => li.textContent);
    expect(sunday.map((t) => t?.match(/^(Any time|\d+(:\d\d)?[ap]m|Morning|Lunch|Afternoon|Dinner|Night)/)?.[0]))
      .toEqual(["Any time", "3pm", "Dinner"]); // South Pointe Park, check-in, Joe's
  });

  it("says nothing's planned and how to ask, when there are no stops", () => {
    render(<Itinerary activities={[]} trip={fixture("miami-demo").detail.trip} />);
    expect(screen.getByRole("heading", { name: "Nothing planned yet" })).toBeTruthy();
  });
});
