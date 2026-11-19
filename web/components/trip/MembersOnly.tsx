"use client";

import { LockIcon } from "@/components/Icons";
import { csrfToken } from "@/lib/post";

import { useMemberData } from "./MemberData";

/**
 * What someone who can't see the money gets instead: signed out ("On this trip? Sign in") or
 * signed in but not on this trip (get a link code, or switch Google accounts). Also the loading
 * and error states. Renders nothing once the money side has loaded.
 */
export function MembersOnly({ className = "" }: { className?: string }) {
  const { state, preview, pagePath, signInHref, getLinkCode } = useMemberData();
  if (state.step === "ready") return null;

  if (state.step === "loading") {
    return <div aria-busy="true" aria-label="Loading the money side" className={`card h-[180px] animate-pulse ${className}`} />;
  }
  if (state.step === "error") {
    return <p role="alert" className={`card p-[18px] text-[15px] text-muted ${className}`}>{state.message}</p>;
  }

  if (state.step === "signed-out") {
    return (
      <section aria-labelledby="money-locked" className={`card flex flex-col gap-3 p-[18px] ${className}`}>
        <div className="flex items-center gap-3">
          <span aria-hidden="true" className="icon-btn size-[42px]"><LockIcon size={20} /></span>
          <h2 id="money-locked" className="text-lg font-bold">On this trip? Sign in to see the money</h2>
        </div>
        <p className="text-[15px] leading-[1.45] text-muted">
          What you owe, what&rsquo;s been spent, and everyone&rsquo;s budget. Only people on this trip can see it.
        </p>
        <a href={signInHref} className="btn btn-white">Sign in with Google</a>
      </section>
    );
  }

  // Signed in, but not linked to anyone on this trip.
  return (
    <section aria-labelledby="money-not-on" className={`card flex flex-col gap-3 p-[18px] ${className}`}>
      <div className="flex items-center gap-3">
        <span aria-hidden="true" className="icon-btn size-[42px]"><LockIcon size={20} /></span>
        <h2 id="money-not-on" className="text-lg font-bold">You&rsquo;re not on this trip</h2>
      </div>
      <p className="text-[15px] leading-[1.45] text-muted">
        You can see the plan, but the money is only for the people going. If you&rsquo;re in this trip&rsquo;s group chat,
        link yourself and it opens up.
      </p>
      {state.code ? (
        <p className="text-[15px] leading-[1.45]">
          Post <code className="rounded-md bg-white px-2 py-0.5 font-bold text-ground">@tripbot link {state.code.code}</code> in the
          group chat in the next 15 minutes, then refresh.
        </p>
      ) : (
        <button type="button" onClick={getLinkCode} className="btn btn-white">Get my link code</button>
      )}
      <div className="flex gap-2.5">
        {/* Wrong account: sign out (a POST with the CSRF token) and come back here to sign in again. */}
        <form
          method="post"
          action="/accounts/logout/"
          className="flex flex-1"
          onSubmit={(e) => {
            if (preview) return e.preventDefault();
            (e.currentTarget.elements.namedItem("csrfmiddlewaretoken") as HTMLInputElement).value = csrfToken();
          }}
        >
          <input type="hidden" name="csrfmiddlewaretoken" defaultValue="" />
          <input type="hidden" name="next" value={pagePath} />
          <button type="submit" className="btn btn-line flex-1 px-3 text-[15px]">Other Google account</button>
        </form>
        <a href="/trips" className="btn btn-line flex-1 px-3 text-[15px]">My trips</a>
      </div>
    </section>
  );
}
