import { readFileSync } from "node:fs";
import path from "node:path";

import { cleanup, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it } from "vitest";

import { FloatingBar } from "@/components/trip/FloatingBar";
import { Latest } from "@/components/trip/Latest";
import { MemberDataProvider } from "@/components/trip/MemberData";
import { YourMoney } from "@/components/trip/YourMoney";
import { openDaysLine, timeAgo, tripLength } from "@/lib/format";
import { tripCalendar } from "@/lib/ics";
import { latestItems } from "@/lib/latest";
import type { TripPageData } from "@/lib/types";

const fixture = (name: string): TripPageData =>
  JSON.parse(readFileSync(path.join(__dirname, "..", "fixtures", `${name}.json`), "utf8"));

// Sample mode: the fixture, previewed as `as`.
function As({ name = "miami-demo", as, children }: { name?: string; as: string; children: ReactNode }) {
  return (
    <MemberDataProvider tripId={name} pagePath={`/t/${name}`} live={false} sample={fixture(name)} previewAs={as}>
      {children}
    </MemberDataProvider>
  );
}

afterEach(cleanup);

describe("Your money (Trip tab)", () => {
  it("lists each person you owe, with Pay on Venmo only for Venmo handles", () => {
    render(<As as="mia"><YourMoney moneyHref="/t/miami-demo/money" /></As>);
    // Each also appears in its (closed) Mark as sent sheet.
    expect(screen.getAllByText("You owe Aarav $231.36")).toHaveLength(2);
    expect(screen.getAllByText("You owe Jake $26")).toHaveLength(2);
    expect(screen.getAllByRole("link", { name: "Pay on Venmo" })).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: "Mark as sent" })).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Copy Jake's email" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Set budget" })).toBeTruthy();
    expect(screen.queryByText(/share of/i)).toBeNull();
  });

  it("says what you're owed and from whom", () => {
    render(<As as="aarav"><YourMoney moneyHref="/t/miami-demo/money" /></As>);
    expect(screen.getByText("You’re owed $1,156")).toBeTruthy();
    expect(screen.getByText("From Leo, Priya, Sam and Mia")).toBeTruthy();
    expect(screen.getByRole("link", { name: "See who owes what" }).getAttribute("href")).toBe("/t/miami-demo/money");
  });

  it("shows your budget with what's left and Change", () => {
    render(<As name="ex1-dropout" as="mia"><YourMoney moneyHref="/t/x/money" /></As>);
    expect(screen.getByText("Your budget")).toBeTruthy();
    expect(screen.getByText(/left of \$950|over \$950/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Change" })).toBeTruthy();
  });

  it("signed out: the sign-in card instead, and no Latest", () => {
    render(<As as="signed-out"><YourMoney moneyHref="/t/miami-demo/money" /><Latest /></As>);
    expect(screen.getByRole("heading", { name: "On this trip? Sign in to see the money" })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Latest" })).toBeNull();
  });
});

describe("Latest", () => {
  it("shows the newest money news first, for people on the trip", () => {
    render(<As as="mia"><Latest /></As>);
    const rows = screen.getAllByRole("listitem").map((li) => li.textContent);
    expect(rows[0]).toContain("Aarav logged a $150 refund");
    expect(rows[1]).toContain("Priya marked $100 to Aarav as sent");
    expect(rows).toHaveLength(4);
  });

  it("puts refunds after the expenses they belong to, and says who sent what", () => {
    const items = latestItems(fixture("miami-demo").detail, 10);
    expect(items.map((i) => i.kind)).toEqual(["refund", "sent", "paid", "paid", "paid", "paid", "paid"]);
    expect(items[1]).toMatchObject({ who: "priya", to: "aarav", cents: 10000 });
  });
});

describe("FloatingBar", () => {
  it("one person to pay: Pay Aarav, straight to Venmo", () => {
    render(<As as="leo"><FloatingBar moneyHref="/t/miami-demo/money" /></As>);
    expect(screen.getByRole("link", { name: /Pay Aarav \$353.36/ }).getAttribute("href")).toContain("venmo.com/aarav-venmo");
    expect(screen.getByRole("button", { name: /Copy link/ })).toBeTruthy();
  });

  it("more than one: the total, to the Money tab's settle-up", () => {
    render(<As as="mia"><FloatingBar moneyHref="/t/miami-demo/money" /></As>);
    expect(screen.getByRole("link", { name: /Pay \$257.36/ }).getAttribute("href")).toBe("/t/miami-demo/money#settle-up");
  });

  it("signed out: Sign in; owed money: just Copy link", () => {
    render(<As as="signed-out"><FloatingBar moneyHref="/t/miami-demo/money" /></As>);
    expect(screen.getByRole("link", { name: "Sign in" })).toBeTruthy();
    cleanup();
    render(<As as="aarav"><FloatingBar moneyHref="/t/miami-demo/money" /></As>);
    expect(screen.queryByRole("link")).toBeNull();
  });
});

describe("Trip tab helpers", () => {
  it("counts the trip's days and names the open ones", () => {
    const { detail } = fixture("miami-demo");
    expect(tripLength("2027-03-14", "2027-03-18")).toBe("5 days");
    expect(openDaysLine(detail.activities, "2027-03-14", "2027-03-20")).toBe("Friday and Saturday are open.");
    expect(openDaysLine(detail.activities, "2027-03-14", "2027-03-18")).toBeNull();
  });

  it("says how long ago, or the date once it's over a week (or in the future)", () => {
    const now = Date.parse("2027-03-10T12:00:00Z");
    expect(timeAgo("2027-03-10T11:00", now)).toBe("1h");
    expect(timeAgo("2027-03-08T12:00", now)).toBe("2d");
    expect(timeAgo("2027-02-20T12:00", now)).toBe("Feb 20");
    expect(timeAgo("2027-03-11T12:00", now)).toBe("Mar 11");
  });

  it("makes a calendar file with the trip and each dated stop", () => {
    const { detail } = fixture("miami-demo");
    const ics = tripCalendar({ ...detail.trip, start_date: "2027-03-14", url: "https://x/t/abc", activities: detail.activities });
    expect(ics).toContain("DTSTART;VALUE=DATE:20270314");
    expect(ics).toContain("DTEND;VALUE=DATE:20270319"); // all-day end is the day after
    expect(ics.match(/BEGIN:VEVENT/g)).toHaveLength(1 + detail.activities.filter((a) => a.start).length);
    expect(ics).toContain("SUMMARY:Miami Spring Break");
  });
});
