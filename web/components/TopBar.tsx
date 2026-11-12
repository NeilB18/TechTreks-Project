"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

import { csrfToken } from "@/lib/post";
import { useMe } from "@/lib/me";
import type { Me } from "@/lib/types";

/**
 * The bar on every page: the wordmark, and on the right "Sign in", or your initial opening
 * My trips and Sign out. In sample mode (no backend) there's no sign-in, so it links to My trips.
 */
export function TopBar({ live }: { live: boolean }) {
  const me = useMe(live);
  const path = usePathname();
  return (
    <nav className="flex items-center justify-between px-5 py-3.5">
      <Link href="/" className="display text-xl text-ink no-underline">
        techtreks
      </Link>
      {!live ? (
        <Link href="/trips" className="btn btn-outline min-h-11 text-sm">My trips</Link>
      ) : me === undefined ? null : me?.signed_in ? (
        <AccountMenu me={me} />
      ) : (
        <a href={`/accounts/google/login/?next=${path}`} className="btn min-h-11 bg-ink text-sm text-ground">
          Sign in
        </a>
      )}
    </nav>
  );
}

function AccountMenu({ me }: { me: Extract<Me, { signed_in: true }> }) {
  const name = me.people[0]?.name ?? me.email;
  const menu = useRef<HTMLDetailsElement>(null);
  // Close on Escape or a tap anywhere else, like a real menu.
  useEffect(() => {
    const close = (e: Event) => {
      const d = menu.current;
      if (!d?.open) return;
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !d.contains(e.target as Node)) d.open = false;
    };
    document.addEventListener("keydown", close);
    document.addEventListener("click", close);
    return () => {
      document.removeEventListener("keydown", close);
      document.removeEventListener("click", close);
    };
  }, []);
  return (
    <details ref={menu} className="relative">
      <summary
        aria-label={`Account: ${name}`}
        className="flex size-11 cursor-pointer list-none items-center justify-center rounded-full bg-pop font-bold text-ground [&::-webkit-details-marker]:hidden"
      >
        {name.trim()[0]?.toUpperCase()}
      </summary>
      <div className="card absolute right-0 z-20 mt-2 flex w-56 flex-col p-2 shadow-xl">
        <p className="truncate px-3 py-2 text-xs text-muted">{me.email}</p>
        <Link href="/trips" className="rounded-xl px-3 py-3 font-semibold text-ink hover:bg-line">My trips</Link>
        {/* Signing out is a POST with the CSRF token (allauth), then Django sends you back to the site. */}
        <form
          method="post"
          action="/accounts/logout/"
          onSubmit={(e) => {
            (e.currentTarget.elements.namedItem("csrfmiddlewaretoken") as HTMLInputElement).value = csrfToken();
          }}
        >
          <input type="hidden" name="csrfmiddlewaretoken" defaultValue="" />
          <button type="submit" className="w-full rounded-xl px-3 py-3 text-left font-semibold text-ink hover:bg-line">
            Sign out
          </button>
        </form>
      </div>
    </details>
  );
}
