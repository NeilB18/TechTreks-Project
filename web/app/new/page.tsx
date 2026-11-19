import type { Metadata } from "next";
import { Suspense } from "react";

import { Footer } from "@/components/Footer";
import { NewTripFlow } from "@/components/NewTripFlow";
import { TopBar } from "@/components/TopBar";
import { usingFixtures } from "@/lib/api";

export const metadata: Metadata = { title: "Add a trip" };

// Add a trip: a new GroupMe group with @tripbot in it, and the trip it talks to.
export default function NewTripPage() {
  return (
    <>
      <main id="main" className="mx-auto w-full max-w-2xl">
        <TopBar live={!usingFixtures} />
        <header className="flex flex-col gap-2.5 px-5 pt-4.5">
          <h1 className="wide text-[32px] tracking-[-0.02em]">Add a trip</h1>
          <p className="leading-[1.45] text-muted">
            Name it, and we&rsquo;ll make the GroupMe group with @tripbot already in it.
          </p>
        </header>
        {/* useSearchParams (?error=) needs a Suspense boundary for the static build. */}
        <Suspense>
          <NewTripFlow live={!usingFixtures} />
        </Suspense>
      </main>
      <Footer />
    </>
  );
}
