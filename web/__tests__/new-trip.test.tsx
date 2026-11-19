import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Add a trip (/new): name it, then the backend sends you to GroupMe to make the group.
let search = "";
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(search),
  usePathname: () => "/new",
}));

function routes(map: Record<string, [number, unknown]>) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const answer = map[`${init?.method ?? "GET"} ${url}`];
    if (!answer) return new Response("{}", { status: 404 });
    return new Response(JSON.stringify(answer[1]), { status: answer[0] });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

// lib/me caches who's signed in for the page, so each test loads the components fresh.
async function load() {
  vi.resetModules();
  return (await import("@/components/NewTripFlow")).NewTripFlow;
}

const SIGNED_IN = { signed_in: true, email: "romir@example.com", people: [] };

beforeEach(() => {
  search = "";
  document.cookie = "csrftoken=tok123";
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Add a trip", () => {
  it("sends the name to the backend, then goes to GroupMe", async () => {
    const fetchMock = routes({
      "GET /api/me/": [200, SIGNED_IN],
      "POST /api/me/new-trip": [200, { authorize_url: "https://oauth.groupme.com/oauth/authorize?client_id=abc" }],
    });
    const assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign });
    const NewTripFlow = await load();
    render(<NewTripFlow live />);
    fireEvent.change(await screen.findByLabelText("Trip name"), { target: { value: "  Cabo   Spring Break " } });
    fireEvent.click(screen.getByRole("button", { name: "Make the group on GroupMe" }));
    await waitFor(() => expect(assign).toHaveBeenCalledWith("https://oauth.groupme.com/oauth/authorize?client_id=abc"));
    const post = fetchMock.mock.calls.find(([url]) => url === "/api/me/new-trip")!;
    expect(JSON.parse(post[1]!.body as string)).toEqual({ name: "Cabo Spring Break" });
    expect((post[1]!.headers as Record<string, string>)["X-CSRFToken"]).toBe("tok123");
  });

  it("asks for a name, and shows the backend's error", async () => {
    routes({ "GET /api/me/": [200, SIGNED_IN], "POST /api/me/new-trip": [503, { error: "Adding trips from the site isn't set up yet" }] });
    const NewTripFlow = await load();
    render(<NewTripFlow live />);
    fireEvent.click(await screen.findByRole("button", { name: "Make the group on GroupMe" }));
    expect((await screen.findByRole("alert")).textContent).toBe("Give the trip a name.");
    fireEvent.change(screen.getByLabelText("Trip name"), { target: { value: "Cabo" } });
    fireEvent.click(screen.getByRole("button", { name: "Make the group on GroupMe" }));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toBe("Adding trips from the site isn't set up yet"));
  });

  it("explains why it came back from GroupMe", async () => {
    search = "error=groupme";
    routes({ "GET /api/me/": [200, SIGNED_IN] });
    const NewTripFlow = await load();
    render(<NewTripFlow live />);
    expect((await screen.findByRole("alert")).textContent).toContain("GroupMe couldn't make the group");
  });

  it("asks you to sign in first, and comes back here", async () => {
    routes({ "GET /api/me/": [200, { signed_in: false, login_url: "/accounts/google/login/" }] });
    const NewTripFlow = await load();
    render(<NewTripFlow live />);
    const button = await screen.findByRole("button", { name: "Sign in with Google" });
    expect(button.closest("form")!.getAttribute("action")).toBe("/accounts/google/login/?next=%2Fnew");
  });
});
