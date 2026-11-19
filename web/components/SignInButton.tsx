"use client";

import type { ReactNode } from "react";

import { fetchMe } from "@/lib/me";
import { csrfToken } from "@/lib/post";

/**
 * "Sign in with Google", straight to Google. allauth only skips its own "Sign In Via Google /
 * Continue" page for a POST with the CSRF token, so this is a small form, like Sign out.
 * /api/me/ sets the CSRF cookie; if it hasn't answered yet, wait for it before sending. If there's
 * still no token (the backend is down), fall back to the GET link, which shows allauth's page.
 * `next` is where Google sends you back to on this site, like /t/<share_token>.
 */
export function SignInButton({ next, className, children }: { next: string; className?: string; children: ReactNode }) {
  const action = `/accounts/google/login/?${new URLSearchParams({ next })}`;
  return (
    <form
      method="post"
      action={action}
      className="contents"
      onSubmit={async (e) => {
        const form = e.currentTarget;
        const field = form.elements.namedItem("csrfmiddlewaretoken") as HTMLInputElement;
        field.value = csrfToken();
        if (field.value) return;
        e.preventDefault();
        await fetchMe();
        field.value = csrfToken();
        if (field.value) form.submit();
        // /accounts/* is Django behind proxy.ts, not a Next page, so a full page load is right.
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination
        else window.location.href = action;
      }}
    >
      <input type="hidden" name="csrfmiddlewaretoken" defaultValue="" />
      <button type="submit" className={className}>{children}</button>
    </form>
  );
}
