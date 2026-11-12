"use client"; // error pages must run in the browser

import Link from "next/link";
import { useEffect } from "react";

// Something broke while showing a page (the backend is down, a bug). Offer a retry and a way home.
export default function ErrorPage({ error, retry }: { error: unknown; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);
  return (
    <main id="main" className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-3 px-5 py-16">
      <span className="sticker self-start -rotate-6">Oops</span>
      <h1 className="display text-[40px]">Something went wrong</h1>
      <p className="text-muted">The page couldn&rsquo;t load. It&rsquo;s probably on our end, so try again in a moment.</p>
      <div className="mt-3 flex gap-2.5">
        <button type="button" onClick={() => retry()} className="btn btn-pop">Try again</button>
        <Link href="/" className="btn btn-outline">Home</Link>
      </div>
    </main>
  );
}
