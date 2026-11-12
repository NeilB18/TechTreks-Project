import Link from "next/link";

import { Footer } from "@/components/Footer";
import { TopBar } from "@/components/TopBar";
import { usingFixtures } from "@/lib/api";

export default function NotFound() {
  return (
    <>
      <main id="main" className="mx-auto w-full max-w-2xl">
        <TopBar live={!usingFixtures} />
        <div className="flex flex-col gap-3 px-5 py-14">
          <span className="sticker self-start -rotate-6">404</span>
          <h1 className="display text-[40px]">Nothing here</h1>
          <p className="text-muted">That page doesn&rsquo;t exist. Check the link, or head home.</p>
          <Link href="/" className="btn btn-pop mt-3 self-start">Home</Link>
        </div>
      </main>
      <Footer />
    </>
  );
}
