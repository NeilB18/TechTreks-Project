import { readFileSync } from "node:fs";
import path from "node:path";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ComponentProps } from "react";

import { MoneySection } from "@/components/MoneySection";
import { MemberDataProvider } from "@/components/trip/MemberData";
import type { TripPageData } from "@/lib/types";

// The Money tab's body, inside the provider that loads the money side for the whole page.
const Money = (p: Omit<ComponentProps<typeof MemberDataProvider>, "children">) => (
  <MemberDataProvider {...p}><MoneySection /></MemberDataProvider>
);

// Each route answers with a body (200) or [status, body].
type Routes = Record<string, unknown>;

function mockFetch(routes: Routes) {
  const calls: { url: string; init?: RequestInit }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    const answer = routes[`${init?.method ?? "GET"} ${url}`];
    if (answer === undefined) return new Response("{}", { status: 404 });
    const [status, body] = Array.isArray(answer) ? answer : [200, answer];
    return new Response(JSON.stringify(body), { status });
  }));
  return calls;
}

const fixture = (name: string): TripPageData =>
  JSON.parse(readFileSync(path.join(__dirname, "..", "fixtures", `${name}.json`), "utf8"));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("MoneySection", () => {
  it("without a backend, previews the fixture as its first payer and calls nothing", () => {
    const calls = mockFetch({});
    render(<Money tripId="miami-demo" pagePath="/t/miami-demo" live={false} sample={fixture("miami-demo")} />);
    expect(screen.getAllByText("You owe Aarav $353.36").length).toBeGreaterThan(0); // Leo
    expect(screen.getByText(/Jake paid, split 5 ways/)).toBeTruthy();
    expect(calls).toEqual([]);
  });

  it("previews as signed out or not on the trip without a backend", () => {
    render(<Money tripId="miami-demo" pagePath="/t/miami-demo" live={false} sample={fixture("miami-demo")} previewAs="signed-out" />);
    // No Google sign-in in sample mode: the button previews as a member instead.
    expect(screen.getByRole("link", { name: "Sign in with Google" }).getAttribute("href")).toBe("/t/miami-demo?as=leo");
    cleanup();
    render(<Money tripId="miami-demo" pagePath="/t/miami-demo" live={false} sample={fixture("miami-demo")} previewAs="not-linked" />);
    expect(screen.getByRole("heading", { name: "You’re not on this trip" })).toBeTruthy();
    // Wrong Google account: sign out and come back to this trip page.
    const other = screen.getByRole("button", { name: "Other Google account" }).closest("form")!;
    expect(other.getAttribute("action")).toBe("/accounts/logout/");
    expect((other.elements.namedItem("next") as HTMLInputElement).value).toBe("/t/miami-demo");
    expect(screen.getByRole("link", { name: "My trips" }).getAttribute("href")).toBe("/trips");
    fireEvent.click(screen.getByRole("button", { name: "Get my link code" }));
    expect(screen.getByText("@tripbot link K7RM4X")).toBeTruthy();
  });

  it("signed out: no money, and Google sign-in that returns to this trip page", async () => {
    mockFetch({ "GET /api/me/trips/miami": [401, { error: "Sign in first" }] });
    render(<Money tripId="miami" pagePath="/t/k7rm4xq2pa8d" live sample={null} />);
    const button = await screen.findByRole("button", { name: "Sign in with Google" });
    const form = button.closest("form")!;
    expect(form.getAttribute("method")).toBe("post");
    expect(form.getAttribute("action")).toBe("/accounts/google/login/?next=%2Ft%2Fk7rm4xq2pa8d");
    expect(screen.queryByRole("heading", { name: "Settle up" })).toBeNull();
  });

  it("not on this trip: gets a link code with the CSRF token", async () => {
    document.cookie = "csrftoken=tok123";
    const calls = mockFetch({
      "GET /api/me/trips/miami": [403, { error: "not linked" }],
      "POST /api/me/link-code": { code: "AB3DE9", expires_at: "x", instructions: "x" },
    });
    render(<Money tripId="miami" pagePath="/t/k7rm4xq2pa8d" live sample={null} />);
    fireEvent.click(await screen.findByRole("button", { name: "Get my link code" }));
    expect(await screen.findByText("@tripbot link AB3DE9")).toBeTruthy();
    const post = calls.find((c) => c.init?.method === "POST")!;
    expect((post.init!.headers as Record<string, string>)["X-CSRFToken"]).toBe("tok123");
  });

  it("says the link code failed when getting a code fails", async () => {
    mockFetch({ "GET /api/me/trips/miami": [403, { error: "not linked" }] });
    render(<Money tripId="miami" pagePath="/t/k7rm4xq2pa8d" live sample={null} />);
    fireEvent.click(await screen.findByRole("button", { name: "Get my link code" }));
    expect(await screen.findByText(/Couldn.t get a link code/)).toBeTruthy();
  });

  it("a linked member sees settle-up, expenses, group budget and their own budget", async () => {
    const { detail, balances } = fixture("miami-demo");
    mockFetch({
      "GET /api/me/trips/miami-demo": {
        person_id: "mia", detail, balances,
        budget: { person_id: "mia", budget_set: true, total_cents: 50000, spent_cents: 30000,
                  remaining_cents: 20000, planned_cents: 21300, remaining_after_planned_cents: -1300,
                  warnings: ["ACTIVITIES over limit by $13 including planned activities"] },
      },
    });
    render(<Money tripId="miami-demo" pagePath="/t/k7rm4xq2pa8d" live sample={null} />);
    expect(await screen.findByRole("heading", { name: "Settle up" })).toBeTruthy();
    expect(screen.getAllByText("You owe Aarav $231.36").length).toBeGreaterThan(0);
    expect(screen.getAllByText("You owe Jake $26").length).toBeGreaterThan(0);
    expect(screen.getByText("The group’s budget is $917 each.")).toBeTruthy();
    expect(screen.getByText("$513 of $500")).toBeTruthy();
    expect(screen.getByText(/\$300 spent and \$213 planned\. \$13 over\./)).toBeTruthy();
    expect(screen.getByText(/Things to do: over limit by \$13|Activities: over limit by \$13/)).toBeTruthy();
  });

  it("shows an error instead of crashing when the API fails", async () => {
    mockFetch({ "GET /api/me/trips/miami": [500, {}] });
    render(<Money tripId="miami" pagePath="/t/k7rm4xq2pa8d" live sample={null} />);
    expect(await screen.findByText(/Couldn.t load the money side/)).toBeTruthy();
  });
});
