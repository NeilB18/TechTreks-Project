import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { readFileSync } from "node:fs";
import path from "node:path";

import { ThemePicker } from "@/components/ThemePicker";
import { MemberDataProvider } from "@/components/trip/MemberData";
import type { TripPageData } from "@/lib/types";

const sample = JSON.parse(readFileSync(path.join(__dirname, "..", "fixtures", "miami-demo.json"), "utf8")) as TripPageData;

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
    render(
      <MemberDataProvider tripId="miami-demo" pagePath="/t/miami-demo" live={false} sample={sample} previewAs="signed-out">
        <ThemePicker theme="sunset" />
      </MemberDataProvider>,
    );
    expect(screen.queryByRole("button", { name: "Change theme" })).toBeNull();
  });

  it("only offers the themes the bot can save, plus the trip's own", () => {
    render(
      <MemberDataProvider tripId="miami-demo" pagePath="/t/miami-demo" live={false} sample={sample} previewAs="mia">
        <ThemePicker theme="snow" />
      </MemberDataProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Change theme" }));
    expect(screen.getAllByRole("radio").map((r) => r.textContent)).toEqual(["Beach", "City nights", "Mountains", "Snow"]);
  });

  it("in sample mode, previews the picked theme instead of saving", () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    render(
      <MemberDataProvider tripId="miami-demo" pagePath="/t/miami-demo" live={false} sample={sample} previewAs="mia">
        <ThemePicker theme="sunset" />
      </MemberDataProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Change theme" }));
    fireEvent.click(screen.getByRole("radio", { name: /Mountains/ }));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(router.push).toHaveBeenCalledWith("/t/miami-demo?as=mia&theme=campfire", { scroll: false });
    expect(fetch).not.toHaveBeenCalled();
  });

  it("live, shows for members and saves with the CSRF token", async () => {
    document.cookie = "csrftoken=tok123";
    const calls: { url: string; init?: RequestInit }[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      if (url === "/api/me/trips/miami") {
        return new Response(JSON.stringify({ ...sample, person_id: "mia", budget: null }));
      }
      return new Response(JSON.stringify({ theme: "night_swim" }));
    }));
    render(
      <MemberDataProvider tripId="miami" pagePath="/t/k7rm4xq2pa8d" live sample={null}>
        <ThemePicker theme="sunset" />
      </MemberDataProvider>,
    );
    fireEvent.click(await screen.findByRole("button", { name: "Change theme" }));
    fireEvent.click(screen.getByRole("radio", { name: /City nights/ }));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await vi.waitFor(() => expect(router.refresh).toHaveBeenCalled());
    const post = calls.find((c) => c.init?.method === "POST")!;
    expect(post.url).toBe("/api/me/trips/miami/theme");
    expect(JSON.parse(post.init!.body as string)).toEqual({ theme: "night_swim" });
    expect((post.init!.headers as Record<string, string>)["X-CSRFToken"]).toBe("tok123");
  });
});
