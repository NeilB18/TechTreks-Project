"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { CopyButton } from "@/components/CopyButton";
import { postJson } from "@/lib/post";
import type { LinkCode, Me } from "@/lib/types";

// How often to check whether the bot has seen the code.
const POLL_MS = 4000;

type State =
  | { step: "loading" }
  | { step: "signed-out" }
  | { step: "error" }
  | { step: "code"; me: Extract<Me, { signed_in: true }>; code: LinkCode; expired: boolean };

async function getMe(): Promise<Me> {
  const res = await fetch("/api/me/", { cache: "no-store" });
  if (!res.ok) throw new Error(String(res.status));
  return (await res.json()) as Me;
}

/**
 * Link your Google account to your trip member: post "@tripbot link CODE" in the group, and this
 * page opens the trip once the bot has seen it (it checks every few seconds until the code expires).
 * Sample mode shows a made-up code and doesn't wait.
 */
export function LinkFlow({ live }: { live: boolean }) {
  const router = useRouter();
  const [state, setState] = useState<State>(
    live ? { step: "loading" }
      : { step: "code", me: { signed_in: true, email: "you@example.com", people: [] },
          code: { code: "K7RM4X", expires_at: "", instructions: "" }, expired: false },
  );
  const known = useRef<Set<string>>(new Set());

  const start = useCallback(async () => {
    try {
      const me = await getMe();
      if (!me.signed_in) return setState({ step: "signed-out" });
      known.current = new Set(me.people.map((p) => p.trip_id));
      const code = await postJson<LinkCode>("/api/me/link-code", {});
      setState({ step: "code", me, code, expired: false });
    } catch {
      setState({ step: "error" });
    }
  }, []);

  useEffect(() => {
    if (!live) return;
    void (async () => {
      await start();
    })();
  }, [live, start]);

  // Waiting for the bot: a new trip in /api/me/ means the code worked.
  const waiting = live && state.step === "code" && !state.expired;
  const expiresAt = state.step === "code" ? Date.parse(state.code.expires_at) : NaN;
  useEffect(() => {
    if (!waiting) return;
    const timer = setInterval(async () => {
      if (Date.now() > expiresAt) {
        setState((s) => (s.step === "code" ? { ...s, expired: true } : s));
        return;
      }
      try {
        const me = await getMe();
        const linked = me.signed_in && me.people.find((p) => !known.current.has(p.trip_id));
        if (linked) router.push(`/t/${linked.share_token}`);
      } catch {
        // Try again on the next tick.
      }
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [waiting, expiresAt, router]);

  if (state.step === "loading") return <p className="px-5 pt-6 text-muted">Getting your code…</p>;
  if (state.step === "error") return <p className="px-5 pt-6 text-muted">Couldn&rsquo;t get a code. Refresh and try again.</p>;
  if (state.step === "signed-out") {
    return (
      <section className="mx-5 mt-6 flex flex-col gap-2.5 rounded-[26px] bg-paper p-[22px] text-paper-ink">
        <h2 className="display text-2xl">Sign in first</h2>
        <p className="text-[15px] text-paper-muted">Then you&rsquo;ll get a code to post in your trip&rsquo;s group chat.</p>
        <a href="/accounts/google/login/?next=/link" className="btn btn-paper mt-1.5 min-h-[50px] text-base">Sign in with Google</a>
      </section>
    );
  }

  const message = `@tripbot link ${state.code.code}`;
  const name = state.me.people[0]?.name;
  return (
    <ol className="mx-5 mt-7 flex list-none flex-col gap-3.5 p-0">
      <li className="card flex items-center gap-3 px-4 py-3.5">
        <span aria-hidden="true" className="inline-flex size-8 flex-none items-center justify-center rounded-full bg-good text-ground">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12l4 4 10-10" /></svg>
        </span>
        <span className="flex flex-col">
          <span className="font-bold">Signed in with Google</span>
          <span className="text-sm text-muted">{name ?? state.me.email}</span>
        </span>
      </li>

      <li className="relative flex flex-col gap-3.5 rounded-[22px] bg-paper p-4 pt-[18px] text-paper-ink">
        <span className="sticker absolute -top-3 right-4 rotate-6 text-xs">15 min</span>
        <span className="label-caps text-paper-hot">Post this in the group</span>
        <p className="rounded-2xl bg-paper-ink p-4 text-xl font-semibold text-paper">
          @tripbot link <span className="display tracking-[0.12em] text-pop">{state.code.code}</span>
        </p>
        <div className="flex gap-2">
          <CopyButton text={message} label="Copy message" className="btn btn-paper min-h-12 flex-1" />
          <a href="https://web.groupme.com/chats" target="_blank" rel="noreferrer" className="btn min-h-12 flex-1 border-2 border-paper-ink text-paper-ink">
            Open GroupMe
          </a>
        </div>
        <p className="text-sm text-paper-muted">
          {state.expired ? "This code expired. " : "Only works once. "}
          {live && (
            <button type="button" onClick={start} className="font-bold text-paper-hot underline">Get a new code</button>
          )}
        </p>
      </li>

      <li className="flex items-center gap-3 rounded-[22px] border-2 border-dashed border-outline px-4 py-3.5" aria-live="polite">
        <span aria-hidden="true" className={`size-8 flex-none rounded-full border-[3px] border-line border-t-pop ${waiting ? "animate-spin" : ""}`} />
        <span className="flex flex-col">
          <span className="font-bold">{!live ? "Preview only" : state.expired ? "Code expired" : "Waiting for your message"}</span>
          <span className="text-sm text-muted">
            {!live ? "With the bot connected, this page opens your trip once the bot sees the code." : "This page opens your trip once the bot sees it."}
          </span>
        </span>
      </li>
    </ol>
  );
}
