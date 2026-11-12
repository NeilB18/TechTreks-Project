import type { Metadata } from "next";

import { Footer } from "@/components/Footer";
import { LinkFlow } from "@/components/LinkFlow";
import { TopBar } from "@/components/TopBar";
import { usingFixtures } from "@/lib/api";

export const metadata: Metadata = { title: "Link your trip" };

// Link your Google account to your trip member (design canvas: "Signed in, not linked yet").
export default function LinkPage() {
  return (
    <>
      <main id="main" className="mx-auto w-full max-w-2xl">
        <TopBar live={!usingFixtures} />
        <header className="flex flex-col gap-2.5 px-5 pt-6">
          <h1 className="display text-[40px] leading-none">One last step: tell the bot it&rsquo;s you</h1>
          <p className="text-base leading-snug text-muted">
            Post this in your trip&rsquo;s group chat so we know which person on the trip you are.
          </p>
        </header>
        <LinkFlow live={!usingFixtures} />
      </main>
      <Footer />
    </>
  );
}
