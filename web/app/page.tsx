import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";

import { Footer } from "@/components/Footer";
import { CalendarIcon, GaugeIcon, LinkIcon, MoneyIcon } from "@/components/Icons";
import { TopBar } from "@/components/TopBar";
import { PhotoBackdrop, PhotoHeader } from "@/components/TripPhoto";
import { listFixtureTrips, usingFixtures } from "@/lib/api";
import { themeInfo } from "@/lib/themes";

// Three made-up trips that show what the themes look like.
const EXAMPLES = [
  { theme: "sunset", name: "Miami Spring Break", line: "Mar 16–20, 5 going" },
  { theme: "night_swim", name: "Chicago Fall Break", line: "Oct 15–18, 4 going" },
  { theme: "campfire", name: "Smokies Cabin Weekend", line: "Apr 9–11, 6 going" },
] as const;

// The landing page (design canvas: Final designs, "Landing page"). Everyone sees this at "/";
// signed-in people get to their trips from the button or the account menu. In sample mode it
// also lists the samples.
export default async function Home() {
  const samples = await listFixtureTrips();
  const beach = themeInfo("sunset");
  return (
    <div data-theme="sunset" className="relative flex flex-1 flex-col overflow-hidden">
      <PhotoBackdrop theme={beach} height={1000} />
      <main id="main" className="relative mx-auto w-full max-w-2xl">
        <PhotoHeader theme={beach} blur={8} className="h-[440px]">
          <TopBar live={!usingFixtures} className="absolute inset-x-0 top-0" />
          <header className="absolute inset-x-0 top-11 bottom-5 flex flex-col items-center justify-center gap-4 px-6 text-center">
            <h1 className="wide on-photo text-[40px] text-balance">Plan the trip in the group chat.</h1>
            <p className="on-photo text-[17px] leading-[1.45] text-pretty text-[#f0f2f7]">
              @tripbot lives in your GroupMe. It keeps the plan, splits what everyone spends, and keeps each
              person&rsquo;s budget honest.
            </p>
            <Link href="/trips" className="btn btn-white mt-1 min-h-[52px] px-7 text-[17px]">See your trips</Link>
          </header>
        </PhotoHeader>

        <section aria-label="Example trips" className="pt-3">
          <ul className="flex snap-x gap-3.5 overflow-x-auto px-5 pb-1 [scrollbar-width:none]">
            {EXAMPLES.map((e) => {
              const t = themeInfo(e.theme);
              return (
                <li key={e.name} className="relative h-[280px] w-[220px] flex-none snap-start overflow-hidden rounded-[18px]">
                  <Image src={t.photo} alt={t.alt} fill sizes="220px" className="object-cover" />
                  <div aria-hidden="true" className="absolute inset-0 bg-[linear-gradient(180deg,rgb(10_14_26/0)_40%,rgb(10_14_26/0.82)_100%)]" />
                  <span className="absolute inset-x-4 bottom-3.5 flex flex-col gap-1">
                    <span className="text-xl leading-[1.05] font-extrabold [font-stretch:112%]">{e.name}</span>
                    <span className="text-sm text-soft">{e.line}</span>
                  </span>
                </li>
              );
            })}
          </ul>
          <p className="mx-5 mt-3.5 text-sm leading-[1.45] text-muted">
            Every trip gets a theme that looks like where you&rsquo;re going. @tripbot picks it, and anyone on the
            trip can switch to another.
          </p>
        </section>

        <section aria-labelledby="chat" className="flex flex-col gap-4 px-5 pt-13">
          <h2 id="chat" className="wide text-[26px]">Just @ it in the chat</h2>
          <div className="flex flex-col gap-2.5 rounded-[20px] border border-line bg-surface px-3.5 py-4">
            <p className="max-w-[82%] self-end rounded-[18px_18px_6px_18px] bg-white px-3.5 py-2.5 text-[15px] leading-snug text-ground">
              <b>Mia</b>
              <br />
              @tripbot I paid $120 for dinner, everyone but Leo
            </p>
            <p className="max-w-[82%] self-start rounded-[18px_18px_18px_6px] bg-fill px-3.5 py-2.5 text-[15px] leading-snug">
              <b className="text-accent">tripbot</b>
              <br />
              Got it. $24 each for 5 people, and Mia&rsquo;s owed $96.
            </p>
          </div>
        </section>

        <section aria-label="What it does" className="flex flex-col gap-5.5 px-5 pt-8">
          <Feature icon={<CalendarIcon size={20} />} title="Keeps the plan">
            Say &ldquo;boat tour Wednesday at 10&rdquo; and it&rsquo;s on the calendar, with the cost per person.
          </Feature>
          <Feature icon={<MoneyIcon size={20} />} title="Splits every bill">
            Nobody has to be the spreadsheet friend. At the end, everyone gets the fewest payments to settle up, with
            Venmo links.
          </Feature>
          <Feature icon={<GaugeIcon size={20} />} title="Watches your budget">
            Tell it the most you want to spend. It warns you in the chat before you go over.
          </Feature>
          <Feature icon={<LinkIcon size={20} />} title="One link for the whole trip">
            Anyone with the link sees the plan. Only people on the trip see the money.
          </Feature>
        </section>

        <section className="flex flex-col items-center gap-3.5 px-5 pt-11 text-center">
          <p className="text-lg font-bold">Already in a trip chat with @tripbot?</p>
          <Link href="/trips" className="btn btn-white min-h-[52px] px-7 text-[17px]">See your trips</Link>
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

function Feature({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <div className="flex gap-3.5">
      <span aria-hidden="true" className="inline-flex size-[42px] flex-none items-center justify-center rounded-xl border border-white/16">
        {icon}
      </span>
      <span className="flex flex-col gap-0.5">
        <span className="text-[17px] font-bold">{title}</span>
        <span className="text-[15px] leading-[1.45] text-muted">{children}</span>
      </span>
    </div>
  );
}
