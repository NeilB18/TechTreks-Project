import Image from "next/image";
import Link from "next/link";

import { Footer } from "@/components/Footer";
import { TopBar } from "@/components/TopBar";
import { PhotoBackdrop, PhotoHeader } from "@/components/TripPhoto";
import { listFixtureTrips, usingFixtures } from "@/lib/api";
import { themeInfo } from "@/lib/themes";

// Made-up trips that show what the themes look like.
const EXAMPLES = [
  { theme: "sunset", name: "Miami Spring Break", line: "Mar 16–20, 5 going" },
  { theme: "night_swim", name: "Chicago Fall Break", line: "Oct 15–18, 4 going" },
  { theme: "campfire", name: "Smokies Cabin Weekend", line: "Apr 9–11, 6 going" },
  { theme: "snow", name: "Tahoe Ski Trip", line: "Jan 8–11, 7 going" },
] as const;

// A real-looking exchange: this is the whole product, so it does the explaining.
const CHAT = [
  { who: "Mia", me: true, text: "@tripbot I paid $120 for dinner, everyone but Leo" },
  { who: "tripbot", me: false, text: "Got it. $24 each for 5 people, and Mia’s owed $96." },
  { who: "Jake", me: true, text: "@tripbot boat tour Wednesday at 10" },
  { who: "tripbot", me: false, text: "Added. Boat tour, Wed Mar 17 at 10am." },
];

// The landing page. Kept short on purpose: what it is, what it looks like, one button.
// In sample mode it also lists the sample trips.
export default async function Home() {
  const samples = await listFixtureTrips();
  const beach = themeInfo("sunset");
  return (
    <div data-theme="sunset" className="relative flex flex-1 flex-col overflow-hidden">
      <PhotoBackdrop theme={beach} height={1000} />
      <main id="main" className="relative mx-auto w-full max-w-2xl">
        <PhotoHeader theme={beach} blur={8} className="h-[420px]">
          <TopBar live={!usingFixtures} className="absolute inset-x-0 top-0" />
          <header className="absolute inset-x-0 top-11 bottom-5 flex flex-col items-center justify-center gap-4 px-6 text-center">
            <h1 className="wide on-photo text-[40px] text-balance">Plan the trip in the group chat.</h1>
            <p className="on-photo max-w-[32ch] text-[17px] leading-[1.45] text-pretty text-[#f0f2f7]">
              Add @tripbot to your GroupMe. It keeps the plan and who owes who.
            </p>
            <Link href="/trips" className="btn btn-white mt-1 min-h-[52px] px-7 text-[17px]">See your trips</Link>
          </header>
        </PhotoHeader>

        <section aria-label="Example trips" className="pt-3">
          <ul className="flex snap-x gap-3.5 overflow-x-auto px-5 pb-1 [scrollbar-width:none]">
            {EXAMPLES.map((e) => {
              const t = themeInfo(e.theme);
              return (
                <li key={e.name} className="relative h-[260px] w-[200px] flex-none snap-start overflow-hidden rounded-[18px]">
                  <Image src={t.photo} alt={t.alt} fill sizes="200px" className="object-cover" />
                  <div aria-hidden="true" className="absolute inset-0 bg-[linear-gradient(180deg,rgb(10_14_26/0)_40%,rgb(10_14_26/0.82)_100%)]" />
                  <span className="absolute inset-x-4 bottom-3.5 flex flex-col gap-1">
                    <span className="text-xl leading-[1.05] font-extrabold [font-stretch:112%]">{e.name}</span>
                    <span className="text-sm text-soft">{e.line}</span>
                  </span>
                </li>
              );
            })}
          </ul>
        </section>

        <section aria-labelledby="chat" className="flex flex-col gap-4 px-5 pt-12">
          <h2 id="chat" className="wide text-[26px]">Just @ it</h2>
          <div className="flex flex-col gap-2.5 rounded-[20px] border border-line bg-surface px-3.5 py-4">
            {CHAT.map((m, i) => (
              <p
                key={i}
                className={`max-w-[82%] px-3.5 py-2.5 text-[15px] leading-snug ${
                  m.me
                    ? "self-end rounded-[18px_18px_6px_18px] bg-white text-ground"
                    : "self-start rounded-[18px_18px_18px_6px] bg-fill"
                }`}
              >
                <b className={m.me ? "" : "text-accent"}>{m.who}</b>
                <br />
                {m.text}
              </p>
            ))}
          </div>
          <p className="text-[15px] leading-[1.45] text-muted">
            Then everyone gets one link with the plan, who owes who, and Venmo buttons. Only people on the trip see
            the money.
          </p>
        </section>

        {usingFixtures && samples.length > 0 && (
          <section aria-labelledby="samples" className="flex flex-col gap-2 px-5 pt-11">
            <h2 id="samples" className="text-[17px] font-bold">Sample trips (no backend connected)</h2>
            <ul className="card divide-y divide-line">
              {samples.map((t) => (
                <li key={t.id}>
                  <Link href={`/t/${t.id}`} className="flex min-h-12 flex-col justify-center px-4 py-3 no-underline">
                    <span className="font-semibold">{t.name}</span>
                    <span className="text-sm text-muted">{t.id}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        )}
      </main>
      <Footer />
    </div>
  );
}
