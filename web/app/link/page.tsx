import type { Metadata } from "next";

import { Footer } from "@/components/Footer";
import { LinkFlow } from "@/components/LinkFlow";
import { TopBar } from "@/components/TopBar";
import { usingFixtures } from "@/lib/api";

export const metadata: Metadata = { title: "Link a trip" };

// Link your Google account to your trip member (design canvas: Final designs, "Link a trip").
export default function LinkPage() {
  return (
    <>
      <main id="main" className="mx-auto w-full max-w-2xl">
        <TopBar live={!usingFixtures} />
        <header className="flex flex-col gap-2.5 px-5 pt-4.5">
          <h1 className="wide text-[32px] tracking-[-0.02em]">Link a trip</h1>
          <p className="leading-[1.45] text-muted">
            Post this message in your trip&rsquo;s group chat. When @tripbot sees it, the trip shows up in My trips.
          </p>
        </header>
        <LinkFlow live={!usingFixtures} />
      </main>
      <Footer />
    </>
  );
}
