import { readFileSync } from "node:fs";
import path from "node:path";

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Invite } from "@/components/trip/Invite";
import { MemberDataProvider } from "@/components/trip/MemberData";
import type { TripPageData } from "@/lib/types";

let search = "";
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(search), useRouter: () => ({}) }));

const JOIN = "https://groupme.com/join_group/777/abc";
const sample = (join: string | null) => ({
  ...(JSON.parse(readFileSync(path.join(__dirname, "..", "fixtures", "miami-demo.json"), "utf8")) as TripPageData),
  group_join_url: join,
});

function renderAs(as: string, join: string | null = JOIN) {
  return render(
    <MemberDataProvider tripId="miami-demo" pagePath="/t/miami-demo" live={false} sample={sample(join)} previewAs={as}>
      <Invite />
    </MemberDataProvider>,
  );
}

afterEach(() => {
  cleanup();
  search = "";
});

describe("Invite friends", () => {
  it("gives people on the trip the group chat's link", () => {
    renderAs("mia");
    expect(screen.getByRole("link", { name: "Open the group chat" }).getAttribute("href")).toBe(JOIN);
    expect(screen.getByRole("button", { name: "Copy invite link" })).toBeTruthy();
    expect(screen.queryByText("Your group chat is ready")).toBeNull();
  });

  it("says the group is ready right after Add a trip", () => {
    search = "new=1";
    renderAs("mia");
    expect(screen.getByText("Your group chat is ready")).toBeTruthy();
  });

  it("isn't there when signed out, or for groups without a saved link", () => {
    renderAs("signed-out");
    expect(screen.queryByRole("link", { name: "Open the group chat" })).toBeNull();
    cleanup();
    renderAs("mia", null);
    expect(screen.queryByRole("link", { name: "Open the group chat" })).toBeNull();
  });
});
