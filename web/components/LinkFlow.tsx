"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { CopyButton } from "@/components/CopyButton";
import { CheckIcon, CopyIcon } from "@/components/Icons";
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

  if (state.step === "loading") return <p role="status" className="px-5 pt-6 text-muted">Getting your code…</p>;
  if (state.step === "error") return <p className="px-5 pt-6 text-muted">Couldn&rsquo;t get a code. Refresh and try again.</p>;
  if (state.step === "signed-out") {
    return (
      <section aria-labelledby="link-sign-in" className="card mx-3.5 mt-6 flex flex-col gap-3 p-[18px]">
        <h2 id="link-sign-in" className="text-lg font-bold">Sign in first</h2>
        <p className="text-[15px] leading-[1.45] text-muted">Then you&rsquo;ll get a code to post in your trip&rsquo;s group chat.</p>
        <a href="/accounts/google/login/?next=/link" className="btn btn-white">Sign in with Google</a>
      </section>
    );
  }

  const message = `@tripbot link ${state.code.code}`;
  const name = state.me.people[0]?.name;
  return (
    <>
      <p className="mx-5 mt-5 flex items-center gap-2.5 text-[15px]">
        <span aria-hidden="true" className="avatar size-[26px] bg-[rgb(155_230_170/0.18)] text-[#9be6aa]"><CheckIcon size={15} stroke={2.6} /></span>
        Signed in with Google as {name ?? state.me.email}
      </p>

      <section aria-labelledby="link-code" className="card mx-3.5 mt-4.5 flex flex-col gap-3.5 px-[18px] py-5">
        <div className="flex items-baseline justify-between gap-3">
          <h2 id="link-code" className="font-bold">Post this in the group</h2>
          <span className="text-sm text-muted">{state.expired ? "Expired" : "Expires in 15 min"}</span>
        </div>
        <p className="rounded-[14px] bg-black/25 p-4 text-[17px] leading-[1.4]">
          @tripbot link <span className="font-extrabold tracking-[0.02em] [font-stretch:125%]">{state.code.code}</span>
        </p>
        <div className="flex gap-2.5">
          <CopyButton
            text={message}
            label={<><CopyIcon size={18} />Copy message</>}
            copiedLabel={<><CheckIcon size={18} />Copied</>}
            className="btn btn-white min-h-[50px] flex-1 px-3"
          />
          <a href="https://web.groupme.com/chats" target="_blank" rel="noreferrer" className="btn btn-line min-h-[50px] flex-1 px-3">
            Open GroupMe
          </a>
        </div>
        <p className="text-[13px] text-muted">{state.expired ? "This code expired." : "Only works once."}</p>
      </section>

      <section aria-live="polite" className="mx-3.5 mt-3.5 flex items-start gap-3 rounded-[18px] border border-dashed border-white/25 px-[18px] py-4">
        <span aria-hidden="true" className={`mt-1.5 size-2.5 flex-none rounded-full ${state.expired ? "bg-warn" : "bg-[#ffd08a]"} ${waiting ? "animate-pulse" : ""}`} />
        <span className="flex flex-col gap-0.5">
          <span className="font-bold">{!live ? "Preview only" : state.expired ? "Code expired" : "Waiting for your message"}</span>
          <span className="text-sm leading-[1.45] text-muted">
            {!live
              ? "With the bot connected, this page opens your trip once the bot sees the code."
              : "This page opens your trip once the bot sees the code. You can leave it open."}
          </span>
        </span>
      </section>

      {live && (
        <p className="mx-5 mt-4.5 text-sm leading-[1.45] text-muted">
          {state.expired ? "Code expired?" : "Need another one?"}{" "}
          <button type="button" onClick={start} className="font-semibold text-ink underline underline-offset-4">Get a new code</button>
        </p>
      )}
    </>
  );
}
