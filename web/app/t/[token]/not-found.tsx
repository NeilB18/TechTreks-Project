import Link from "next/link";

import { Footer } from "@/components/Footer";
import { TopBar } from "@/components/TopBar";
import { usingFixtures } from "@/lib/api";

// A /t/<token> that matches no trip: a typo, or an old link from before share links.
export default function TripNotFound() {
  return (
    <>
      <main id="main" className="mx-auto w-full max-w-2xl">
        <TopBar live={!usingFixtures} />
        <div className="flex flex-col gap-3 px-5 py-14">
          <span className="sticker self-start -rotate-6">Hmm</span>
          <h1 className="display text-[40px]">Trip not found</h1>
          <p className="text-muted">
            Check the link, or ask &ldquo;@tripbot what&rsquo;s the trip page?&rdquo; in your group chat for the current one.
          </p>
          <div className="mt-3 flex gap-2.5">
            <Link href="/trips" className="btn btn-pop">My trips</Link>
            <Link href="/" className="btn btn-outline">Home</Link>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}
