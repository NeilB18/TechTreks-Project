import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SignInButton } from "@/components/SignInButton";

// Sign in is a POST with the CSRF token, so allauth goes straight to Google instead of showing
// its "Sign In Via Google / Continue" page.
describe("SignInButton", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    document.cookie = "csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
  });

  it("posts to Google sign-in with the CSRF token and where to come back to", () => {
    document.cookie = "csrftoken=tok123";
    render(<SignInButton next="/t/abc">Sign in</SignInButton>);
    const form = screen.getByRole("button", { name: "Sign in" }).closest("form")!;
    let sent: string | null = null;
    // On document, so it runs after React's handler has filled in the token.
    const read = (e: Event) => {
      sent = (form.elements.namedItem("csrfmiddlewaretoken") as HTMLInputElement).value;
      e.preventDefault(); // jsdom can't navigate
    };
    document.addEventListener("submit", read);
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    document.removeEventListener("submit", read);
    expect(form.getAttribute("method")).toBe("post");
    expect(form.getAttribute("action")).toBe("/accounts/google/login/?next=%2Ft%2Fabc");
    expect(sent).toBe("tok123");
  });

  it("without the cookie yet, waits for /api/me/ to set it, then sends", async () => {
    const submit = vi.spyOn(HTMLFormElement.prototype, "submit").mockImplementation(() => {});
    vi.stubGlobal("fetch", vi.fn(async () => {
      document.cookie = "csrftoken=late456";
      return new Response(JSON.stringify({ signed_in: false }), { status: 200 });
    }));
    render(<SignInButton next="/trips">Sign in</SignInButton>);
    const form = screen.getByRole("button", { name: "Sign in" }).closest("form")!;
    fireEvent.submit(form);
    await waitFor(() => expect(submit).toHaveBeenCalled());
    expect((form.elements.namedItem("csrfmiddlewaretoken") as HTMLInputElement).value).toBe("late456");
    vi.unstubAllGlobals();
  });
});
