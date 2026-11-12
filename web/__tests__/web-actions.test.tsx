import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BudgetForm } from "@/components/BudgetForm";
import { MarkSent } from "@/components/MarkSent";
import { parseDollars } from "@/lib/post";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function mockPost(status = 200, body: unknown = {}) {
  const calls: { url: string; init: RequestInit }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init: RequestInit) => {
    calls.push({ url, init });
    return new Response(JSON.stringify(body), { status });
  }));
  return calls;
}

describe("parseDollars", () => {
  it("reads plain amounts and refuses anything else", () => {
    expect(parseDollars("231.36")).toBe(23136);
    expect(parseDollars("$1,200")).toBe(120000);
    expect(parseDollars("25.5")).toBe(2550);
    expect(parseDollars("12.345")).toBeNull();
    expect(parseDollars("ten")).toBeNull();
    expect(parseDollars("")).toBeNull();
  });
});

describe("MarkSent", () => {
  const props = { tripId: "miami", to: "aarav", who: "Aarav", owedCents: 23136, currency: "USD" };

  it("fills in what you owe, allows less, and saves once per opening", async () => {
    document.cookie = "csrftoken=tok123";
    const calls = mockPost();
    const onSaved = vi.fn();
    render(<MarkSent {...props} preview={false} onSaved={onSaved} />);
    fireEvent.click(screen.getByRole("button", { name: "Mark as sent" }));
    const input = screen.getByLabelText("Amount you sent") as HTMLInputElement;
    expect(input.value).toBe("231.36");
    fireEvent.change(input, { target: { value: "100" } });
    fireEvent.click(screen.getByRole("button", { name: "Yes, I sent it" }));
    await vi.waitFor(() => expect(onSaved).toHaveBeenCalled());
    const body = JSON.parse(calls[0].init.body as string);
    expect(calls[0].url).toBe("/api/me/trips/miami/payments");
    expect(body).toMatchObject({ to: "aarav", amount_cents: 10000 });
    expect(body.request_id).toMatch(/\w{8}-/);
    expect((calls[0].init.headers as Record<string, string>)["X-CSRFToken"]).toBe("tok123");
  });

  it("won't send more than you owe, and saves nothing in sample mode", () => {
    const calls = mockPost();
    render(<MarkSent {...props} preview onSaved={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "Mark as sent" }));
    fireEvent.change(screen.getByLabelText("Amount you sent"), { target: { value: "500" } });
    fireEvent.click(screen.getByRole("button", { name: "Yes, I sent it" }));
    expect(screen.getByRole("alert").textContent).toContain("You owe Aarav $231.36");
    fireEvent.change(screen.getByLabelText("Amount you sent"), { target: { value: "231.36" } });
    fireEvent.click(screen.getByRole("button", { name: "Yes, I sent it" }));
    expect(screen.getByRole("alert").textContent).toBe("Preview only: nothing was saved.");
    expect(calls).toEqual([]);
  });

  it("shows Django's reason when it refuses", async () => {
    mockPost(400, { error: "You owe Aarav $50 right now" });
    render(<MarkSent {...props} preview={false} onSaved={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "Mark as sent" }));
    fireEvent.click(screen.getByRole("button", { name: "Yes, I sent it" }));
    expect((await screen.findByRole("alert")).textContent).toBe("You owe Aarav $50 right now");
  });
});

describe("BudgetForm", () => {
  it("saves your new total in cents", async () => {
    const calls = mockPost();
    const onSaved = vi.fn();
    render(<BudgetForm tripId="miami" currentCents={91700} preview={false} onSaved={onSaved} />);
    const input = screen.getByLabelText("Most I want to spend on this trip") as HTMLInputElement;
    expect(input.value).toBe("917");
    fireEvent.change(input, { target: { value: "900" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await vi.waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(calls[0].url).toBe("/api/me/trips/miami/budget");
    expect(JSON.parse(calls[0].init.body as string)).toEqual({ total_cents: 90000 });
  });
});
