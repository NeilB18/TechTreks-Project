"use client";

import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { SignInButton } from "@/components/SignInButton";
import { useMe } from "@/lib/me";
import { postJson } from "@/lib/post";

const MAX_NAME = 60; // backend/accounts/new_trip.py

// Why the last try came back here (Django's groupme_connected redirects to /new?error=...).
const ERRORS: Record<string, string> = {
  signin: "Sign in first, then try again.",
  expired: "That took a while, so nothing was made. Try again.",
  cancelled: "No group was made: GroupMe wasn't allowed to make it. Try again if you meant to.",
  groupme: "GroupMe couldn't make the group just now. Nothing was saved. Try again in a minute.",
};

/**
 * Add a trip: name it, then GroupMe asks you to let TravelBot make the group. You come back to the
 * new trip page, with @tripbot already in the group and you as the trip's leader. The backend does
 * the GroupMe part (backend/accounts/new_trip.py); this page only asks for the name.
 * Sample mode (no backend) can't make groups, so it just says so.
 */
export function NewTripFlow({ live }: { live: boolean }) {
  const me = useMe(live);
  const params = useSearchParams();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(ERRORS[params.get("error") ?? ""] ?? null);

  if (!live) {
    return (
      <section className="card mx-3.5 mt-6 flex flex-col gap-2.5 p-[18px]">
        <h2 className="text-lg font-bold">Sample mode</h2>
        <p className="text-[15px] leading-[1.45] text-muted">Adding a trip needs the live site: it makes a real GroupMe group.</p>
      </section>
    );
  }
  if (me === undefined) return <p role="status" className="px-5 pt-6 text-muted">Loading…</p>;
  if (me === null) return <p className="px-5 pt-6 text-muted">Couldn&rsquo;t reach TravelBot. Refresh and try again.</p>;
  if (!me.signed_in) {
    return (
      <section aria-labelledby="new-sign-in" className="card mx-3.5 mt-6 flex flex-col gap-3 p-[18px]">
        <h2 id="new-sign-in" className="text-lg font-bold">Sign in first</h2>
        <p className="text-[15px] leading-[1.45] text-muted">The new trip is linked to you, so you can see its money side.</p>
        <SignInButton next="/new" className="btn btn-white">Sign in with Google</SignInButton>
      </section>
    );
  }

  async function start() {
    const clean = name.trim().replace(/\s+/g, " ");
    if (!clean) return setMessage("Give the trip a name.");
    setBusy(true);
    setMessage(null);
    try {
      const { authorize_url } = await postJson<{ authorize_url: string }>("/api/me/new-trip", { name: clean });
      window.location.assign(authorize_url); // GroupMe's own page; it sends you back here when it's done
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Couldn’t start. Try again.");
      setBusy(false);
    }
  }

  return (
    <form
      className="flex flex-col gap-4 px-5 pt-6"
      onSubmit={(e) => {
        e.preventDefault();
        void start();
      }}
    >
      <div className="flex flex-col gap-2">
        <label htmlFor="trip-name" className="font-bold">Trip name</label>
        <span className="field">
          <input
            id="trip-name"
            value={name}
            maxLength={MAX_NAME}
            autoComplete="off"
            placeholder="Cabo Spring Break"
            onChange={(e) => setName(e.target.value)}
            className="min-w-0 flex-1 bg-transparent text-lg outline-none placeholder:text-muted/70"
          />
        </span>
        <p className="text-sm text-muted">It&rsquo;s also the group chat&rsquo;s name. You can change it in GroupMe later.</p>
      </div>
      {message && <p role="alert" className="text-sm font-semibold text-warn">{message}</p>}
      <button type="submit" disabled={busy} className="btn btn-white min-h-[52px] disabled:opacity-60">
        {busy ? "Opening GroupMe…" : "Make the group on GroupMe"}
      </button>
      <ol className="card flex flex-col gap-3 p-[18px] text-[15px] leading-[1.45] text-muted">
        <li><span className="font-bold text-ink">1.</span> GroupMe asks you to let TravelBot make a group for you, once.</li>
        <li><span className="font-bold text-ink">2.</span> We make the group with @tripbot in it, and you&rsquo;re the trip&rsquo;s leader.</li>
        <li><span className="font-bold text-ink">3.</span> Invite your friends with the group&rsquo;s link. They&rsquo;re on the trip the first time they @tripbot.</li>
      </ol>
      <p className="text-[13px] leading-[1.45] text-muted">
        TravelBot uses GroupMe&rsquo;s permission only to make the group and add the bot, and doesn&rsquo;t keep it.
      </p>
    </form>
  );
}
