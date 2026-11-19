"use client"; // error pages must run in the browser

import Link from "next/link";
import { useEffect } from "react";

import { Message } from "@/components/Message";
import { SITE_NAME } from "@/lib/site";

// Something broke while showing a page (the backend is down, a bug). Offer a retry and a way home.
// It replaces the page, top bar included, so it brings its own name link.
export default function ErrorPage({ error, retry }: { error: unknown; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);
  return (
    <main id="main" className="mx-auto flex w-full max-w-2xl flex-1 flex-col">
      <nav className="px-5 py-1.5">
        <Link href="/" className="wide inline-flex min-h-11 items-center text-lg no-underline">{SITE_NAME.toLowerCase()}</Link>
      </nav>
      <Message
        title="Something went wrong"
        actions={
          <>
            <button type="button" onClick={() => retry()} className="btn btn-white min-h-[50px] flex-1">Try again</button>
            <Link href="/" className="btn btn-line min-h-[50px] flex-1">Home</Link>
          </>
        }
      >
        The page couldn&rsquo;t load. It&rsquo;s probably on our end, so try again in a moment.
      </Message>
    </main>
  );
}
