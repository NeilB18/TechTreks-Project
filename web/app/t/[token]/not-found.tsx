import Link from "next/link";

import { Footer } from "@/components/Footer";
import { Message } from "@/components/Message";
import { TopBar } from "@/components/TopBar";
import { usingFixtures } from "@/lib/api";

// A /t/<token> that matches no trip: a typo, or an old link from before share links.
export default function TripNotFound() {
  return (
    <>
      <main id="main" className="mx-auto w-full max-w-2xl">
        <TopBar live={!usingFixtures} />
        <Message
          title="We can’t find that trip"
          actions={
            <>
              <Link href="/trips" className="btn btn-white min-h-[50px] flex-1">My trips</Link>
              <Link href="/" className="btn btn-line min-h-[50px] flex-1">Home</Link>
            </>
          }
        >
          The link might be old, or the trip was removed. Ask &ldquo;@tripbot what&rsquo;s the trip page?&rdquo; in your
          group chat to get a fresh link.
        </Message>
      </main>
      <Footer />
    </>
  );
}
