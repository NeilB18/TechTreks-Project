import Link from "next/link";
import type { ReactNode } from "react";

import { Footer } from "@/components/Footer";
import { TopBar } from "@/components/TopBar";
import { TripArt } from "@/components/TripArt";
import { listFixtureTrips, usingFixtures } from "@/lib/api";
import type { Theme } from "@/lib/types";

// The landing page (design canvas: "Landing page"). Everyone sees this at "/"; signed-in people
// get to their trips from the button or the account menu. In sample mode it also lists the samples.
export default async function Home() {
  const samples = await listFixtureTrips();
  return (
    <>
      <main id="main" className="mx-auto w-full max-w-2xl overflow-hidden">
        <TopBar live={!usingFixtures} />

        <header className="flex flex-col gap-4 px-5 pt-9">
          <h1 className="display text-[54px] leading-[0.95]">
            Plan the trip <span className="text-pop">in the group chat.</span>
          </h1>
          <p className="text-lg leading-snug text-muted">
            @tripbot lives in your GroupMe. It plans the days, splits what everyone spends, and keeps each
            person&rsquo;s budget honest.
          </p>
          <div className="mt-1 flex gap-2.5">
            <Link href="/trips" className="btn btn-pop min-h-[50px] flex-1 text-base">See your trips</Link>
            <a href="#how" className="btn btn-outline min-h-[50px] flex-1 text-base">How it works</a>
          </div>
        </header>

        <div aria-hidden="true" className="relative mx-auto mt-10 h-[300px] max-w-[390px]">
          <Postcard theme="night_swim" status="Done" name="Chicago Fall Break" className="top-10 -left-5 -rotate-[8deg]" />
          <Postcard theme="campfire" status="Planning" name="Smokies Cabin Weekend" className="top-0 -right-6 rotate-[7deg]" />
          <Postcard theme="sunset" status="Booked" name="Miami Spring Break" className="top-14 left-[95px] -rotate-2 border-[3px] border-ground" />
        </div>

        <section id="how" aria-labelledby="how-h" className="flex scroll-mt-4 flex-col gap-4 px-5 pt-10">
          <h2 id="how-h" className="display text-[32px]">How it works</h2>
          <article className="card flex flex-col gap-3 p-[18px]">
            <span className="label-caps">1 · Just @ it</span>
            <h3 className="text-xl font-bold">Ask in the chat you already use</h3>
            <p className="max-w-[80%] self-end rounded-[18px_18px_4px_18px] bg-paper px-3.5 py-2.5 text-sm text-paper-ink">
              <span className="font-bold">Mia</span>
              <br />
              @tripbot I paid $120 for dinner, everyone but Leo
            </p>
            <p className="max-w-[80%] self-start rounded-[18px_18px_18px_4px] bg-ground px-3.5 py-2.5 text-sm">
              <span className="font-bold text-pop">tripbot</span>
              <br />
              Got it. $24 each for 5 people, and Mia&rsquo;s owed $96.
            </p>
          </article>
          <Step n={2} label="The plan" title="It plans the days you ask for">
            Suggests places that fit the group&rsquo;s budget, lays them out day by day, and changes one stop at a
            time when someone has a better idea.
          </Step>
          <Step n={3} label="The money" title="Nobody has to be the spreadsheet friend">
            Splits, refunds and budgets are worked out for you. At the end, everyone gets the fewest payments to
            settle up, with Venmo links.
          </Step>
          <article className="flex flex-col gap-2 rounded-[22px] bg-paper p-[18px] text-paper-ink">
            <span className="label-caps text-paper-hot">4 · The page</span>
            <h3 className="text-xl font-bold">One link for the whole trip</h3>
            <p className="text-[15px] leading-snug text-paper-muted">
              Ask @tripbot for the trip page. Anyone with the link sees the plan; sign in to see the money side.
              Only people on the trip can.
            </p>
          </article>
        </section>

        {usingFixtures && samples.length > 0 && (
          <section aria-labelledby="samples" className="flex flex-col gap-3 px-5 pt-10">
            <h2 id="samples" className="label-caps">Sample trips (no backend connected)</h2>
            <ul className="card divide-y divide-line">
              {samples.map((t) => (
                <li key={t.id}>
                  <Link href={`/t/${t.id}`} className="flex justify-between gap-3 px-4 py-3 text-ink no-underline">
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
    </>
  );
}

function Step({ n, label, title, children }: { n: number; label: string; title: string; children: ReactNode }) {
  return (
    <article className="card flex flex-col gap-2 p-[18px]">
      <span className="label-caps">{n} · {label}</span>
      <h3 className="text-xl font-bold">{title}</h3>
      <p className="text-[15px] leading-snug text-muted">{children}</p>
    </article>
  );
}

function Postcard({ theme, status, name, className }: { theme: Theme; status: string; name: string; className: string }) {
  return (
    <div data-theme={theme} className={`absolute flex h-[230px] w-[200px] flex-col justify-end gap-1 overflow-hidden rounded-[22px] bg-ground p-[18px] ${className}`}>
      <TripArt theme={theme} className="absolute inset-x-0 top-0 block h-[120px] w-full" />
      <span className="sticker relative self-start text-[11px]">{status}</span>
      <span className="display relative text-[22px] leading-none text-ink">{name}</span>
    </div>
  );
}
