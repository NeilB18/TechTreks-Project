import Link from "next/link";

import { Footer } from "@/components/Footer";
import { Message } from "@/components/Message";
import { TopBar } from "@/components/TopBar";
import { usingFixtures } from "@/lib/api";

export default function NotFound() {
  return (
    <>
      <main id="main" className="mx-auto w-full max-w-2xl">
        <TopBar live={!usingFixtures} />
        <Message title="Nothing here" actions={<Link href="/" className="btn btn-white min-h-[50px] flex-1">Home</Link>}>
          That page doesn&rsquo;t exist. Check the link, or head home.
        </Message>
      </main>
      <Footer />
    </>
  );
}
