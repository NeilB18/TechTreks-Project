import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LinkFlow } from "@/components/LinkFlow";
import { MyTripsList } from "@/components/MyTripsList";
import { TopBar } from "@/components/TopBar";
import type { TripCard } from "@/lib/types";

const router = { push: vi.fn(), refresh: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router, usePathname: () => "/t/k7rm4xq2pa8d" }));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
  router.push.mockReset();
});

function routes(map: Record<string, unknown>) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const answer = map[`${init?.method ?? "GET"} ${url}`];
    if (answer === undefined) return new Response("{}", { status: 404 });
    const [status, body] = Array.isArray(answer) ? answer : [200, answer];
    return new Response(JSON.stringify(typeof body === "function" ? body() : body), { status });
  }));
}

const card = (over: Partial<TripCard>): TripCard => ({
  trip_id: "miami", name: "Miami Spring Break", share_token: "k7rm4xq2pa8d", status: "BOOKED",
  destination: "Miami", start_date: "2027-03-14", end_date: "2027-03-18", theme: null, going: 6,
  net_cents: -25736, ...over,
});

describe("MyTripsList", () => {
  it("splits coming up from past, with what you owe, and links to each trip page", () => {
    render(<MyTripsList today="2026-11-12" sample={[
      card({}),
      card({ trip_id: "chi", name: "Chicago Fall Break", share_token: "chi", status: "DONE", net_cents: 0,
             start_date: "2026-10-09", end_date: "2026-10-12", theme: "night_swim" }),
    ]} />);
    const miami = screen.getByRole("link", { name: /Miami Spring Break/ });
    expect(miami.getAttribute("href")).toBe("/t/k7rm4xq2pa8d");
    expect(miami.textContent).toContain("You owe $257.36");
    expect(miami.textContent).toContain("6 going · 122 days to go");
    expect(screen.getByRole("link", { name: /Chicago Fall Break/ }).textContent).toContain("All settled");
    expect(screen.getByRole("heading", { name: "Past" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Get a link code" }).getAttribute("href")).toBe("/link");
  });

  it("asks you to sign in when you aren't", async () => {
    routes({ "GET /api/me/trips": [401, {}] });
    render(<MyTripsList today="2026-11-12" sample={null} />);
    const link = await screen.findByRole("link", { name: "Sign in with Google" });
    expect(link.getAttribute("href")).toBe("/accounts/google/login/?next=/trips");
  });
});

describe("TopBar", () => {
  it("in sample mode, links to My trips without asking anyone", () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    render(<TopBar live={false} />);
    expect(screen.getByRole("link", { name: "My trips" }).getAttribute("href")).toBe("/trips");
    expect(fetch).not.toHaveBeenCalled();
  });
});

describe("LinkFlow", () => {
  it("gets a code, then opens the trip once the bot has linked you", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let linked = false;
    routes({
      "GET /api/me/": () => ({ signed_in: true, email: "mia@x.edu",
        people: linked ? [{ trip_id: "miami", trip_name: "Miami", share_token: "k7rm4xq2pa8d", person_id: "mia", name: "Mia" }] : [] }),
      "POST /api/me/link-code": { code: "AB3DE9", expires_at: new Date(Date.now() + 900_000).toISOString(), instructions: "" },
    });
    render(<LinkFlow live />);
    expect((await screen.findByText("AB3DE9")).textContent).toBe("AB3DE9");
    expect(screen.getByRole("button", { name: "Copy message" })).toBeTruthy();
    expect(screen.getByText("Waiting for your message")).toBeTruthy();

    linked = true; // the bot saw "@tripbot link AB3DE9" in the group
    await act(async () => {
      await vi.advanceTimersByTimeAsync(4100);
    });
    expect(router.push).toHaveBeenCalledWith("/t/k7rm4xq2pa8d");
  });

  it("in sample mode, shows a made-up code and doesn't wait", () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    render(<LinkFlow live={false} />);
    expect(screen.getByText("K7RM4X")).toBeTruthy();
    expect(screen.getByText("Preview only")).toBeTruthy();
    expect(fetch).not.toHaveBeenCalled();
  });
});
