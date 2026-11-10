import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CopyLinkButton } from "@/components/CopyLinkButton";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.history.replaceState(null, "", "/");
});

describe("CopyLinkButton", () => {
  it("copies the trip page's own address, without query or #hash", async () => {
    const writeText = vi.fn(async () => {});
    vi.stubGlobal("navigator", { ...navigator, clipboard: { writeText } });
    window.history.replaceState(null, "", "/t/k7rm4xq2pa8d?from=chat#money");
    render(<CopyLinkButton />);
    fireEvent.click(screen.getByRole("button", { name: "Copy trip link" }));
    expect(await screen.findByRole("button", { name: "Copied" })).toBeTruthy();
    expect(writeText).toHaveBeenCalledWith(`${window.location.origin}/t/k7rm4xq2pa8d`);
  });
});
