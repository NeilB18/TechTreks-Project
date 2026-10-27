import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BudgetPanel } from "@/components/BudgetPanel";

type Route = Record<string, unknown>;

function mockFetch(routes: Route) {
  const calls: { url: string; init?: RequestInit }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    const body = routes[`${init?.method ?? "GET"} ${url}`];
    if (body === undefined) return new Response("{}", { status: 404 });
    return new Response(JSON.stringify(body), { status: 200 });
  }));
  return calls;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const ME_LINKED = {
  signed_in: true, email: "mia@nyu.edu",
  people: [{ trip_id: "miami", trip_name: "Miami", person_id: "mia", name: "Mia" }],
};

describe("BudgetPanel", () => {
  it("without a backend, explains budgets are private and calls nothing", () => {
    const calls = mockFetch({});
    render(<BudgetPanel tripId="miami" live={false} currency="USD" />);
    expect(screen.getByText(/DM @tripbot/)).toBeTruthy();
    expect(calls).toEqual([]);
  });

  it("offers Google sign-in that returns to this trip", async () => {
    mockFetch({ "GET /api/me/": { signed_in: false, login_url: "/accounts/google/login/" } });
    render(<BudgetPanel tripId="miami" live currency="USD" />);
    const link = await screen.findByRole("link", { name: "Sign in with Google" });
    expect(link.getAttribute("href")).toBe("/accounts/google/login/?next=/trips/miami");
  });

  it("gets a link code with the CSRF token when signed in but not linked", async () => {
    document.cookie = "csrftoken=tok123";
    const calls = mockFetch({
      "GET /api/me/": { signed_in: true, email: "mia@nyu.edu", people: [] },
      "POST /api/me/link-code": { code: "AB3DE9", expires_at: "x", instructions: "x" },
    });
    render(<BudgetPanel tripId="miami" live currency="USD" />);
    fireEvent.click(await screen.findByRole("button", { name: "Get my link code" }));
    expect(await screen.findByText("@tripbot link AB3DE9")).toBeTruthy();
    const post = calls.find((c) => c.init?.method === "POST")!;
    expect((post.init!.headers as Record<string, string>)["X-CSRFToken"]).toBe("tok123");
  });

  it("says the link code failed, not the budget, when getting a code fails", async () => {
    mockFetch({ "GET /api/me/": { signed_in: true, email: "mia@nyu.edu", people: [] } });
    render(<BudgetPanel tripId="miami" live currency="USD" />);
    fireEvent.click(await screen.findByRole("button", { name: "Get my link code" }));
    expect(await screen.findByText(/Couldn.t get a link code/)).toBeTruthy();
  });

  it("shows your own budget, warnings and private messages once linked", async () => {
    mockFetch({
      "GET /api/me/": ME_LINKED,
      "GET /api/me/trips/miami/budget": {
        person_id: "mia", name: "Mia",
        budget: { person_id: "mia", budget_set: true, total_cents: 50000, spent_cents: 30000,
                  remaining_cents: 20000, planned_cents: 21300, remaining_after_planned_cents: -1300,
                  warnings: ["ACTIVITIES over limit by $13 including planned activities"] },
        notices: [{ text: "Heads up: club night puts you over.", created_at: "2027-03-01T12:00:00" }],
      },
    });
    render(<BudgetPanel tripId="miami" live currency="USD" />);
    expect(await screen.findByText("$500")).toBeTruthy();
    expect(screen.getByText("-$13")).toBeTruthy();
    expect(screen.getByText(/Activities: over limit by \$13/)).toBeTruthy();
    expect(screen.getByText("Heads up: club night puts you over.")).toBeTruthy();
  });

  it("shows an error instead of crashing when the API fails", async () => {
    mockFetch({ "GET /api/me/": ME_LINKED });
    render(<BudgetPanel tripId="miami" live currency="USD" />);
    expect(await screen.findByText(/Couldn.t load your budget/)).toBeTruthy();
  });
});
