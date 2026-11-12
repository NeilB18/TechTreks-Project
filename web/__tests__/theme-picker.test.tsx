import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ThemePicker } from "@/components/ThemePicker";

const router = { push: vi.fn(), refresh: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router }));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  router.push.mockReset();
  router.refresh.mockReset();
});

describe("ThemePicker", () => {
  it("is hidden from people who aren't on the trip", () => {
    render(<ThemePicker tripId="miami" theme="sunset" preview={{ member: false, pagePath: "/t/miami-demo", as: "signed-out" }} />);
    expect(screen.queryByRole("button", { name: "Change theme" })).toBeNull();
  });

  it("in sample mode, previews the picked theme instead of saving", () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    render(<ThemePicker tripId="miami" theme="sunset" preview={{ member: true, pagePath: "/t/miami-demo", as: "mia" }} />);
    fireEvent.click(screen.getByRole("button", { name: "Change theme" }));
    fireEvent.click(screen.getByRole("radio", { name: /Campfire/ }));
    fireEvent.click(screen.getByRole("button", { name: "Use Campfire" }));
    expect(router.push).toHaveBeenCalledWith("/t/miami-demo?as=mia&theme=campfire", { scroll: false });
    expect(fetch).not.toHaveBeenCalled();
  });

  it("live, shows for members and saves with the CSRF token", async () => {
    document.cookie = "csrftoken=tok123";
    const calls: { url: string; init?: RequestInit }[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      if (url === "/api/me/") {
        return new Response(JSON.stringify({ signed_in: true, email: "x", people: [{ trip_id: "miami" }] }));
      }
      return new Response(JSON.stringify({ theme: "night_swim" }));
    }));
    render(<ThemePicker tripId="miami" theme="sunset" preview={null} />);
    fireEvent.click(await screen.findByRole("button", { name: "Change theme" }));
    fireEvent.click(screen.getByRole("radio", { name: /Night Swim/ }));
    fireEvent.click(screen.getByRole("button", { name: "Use Night Swim" }));
    await vi.waitFor(() => expect(router.refresh).toHaveBeenCalled());
    const post = calls.find((c) => c.init?.method === "POST")!;
    expect(post.url).toBe("/api/me/trips/miami/theme");
    expect(JSON.parse(post.init!.body as string)).toEqual({ theme: "night_swim" });
    expect((post.init!.headers as Record<string, string>)["X-CSRFToken"]).toBe("tok123");
  });
});
