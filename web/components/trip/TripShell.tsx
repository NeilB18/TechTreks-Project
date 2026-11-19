import { notFound } from "next/navigation";
import type { ReactNode } from "react";
import { cache } from "react";

import { Avatar } from "@/components/Avatars";
import { Footer } from "@/components/Footer";
import { PreviewBar } from "@/components/PreviewBar";
import { ThemePicker } from "@/components/ThemePicker";
import { TopBar } from "@/components/TopBar";
import { PhotoBackdrop, PhotoHeader } from "@/components/TripPhoto";
import { getFixtureTrip, getSharedTrip, usingFixtures } from "@/lib/api";
import { countdown } from "@/lib/format";
import { THEMES, themeInfo } from "@/lib/themes";
import type { PublicTrip, Theme, TripPageData } from "@/lib/types";

import { FloatingBar } from "./FloatingBar";
import { MemberDataProvider } from "./MemberData";
import { TabSwitch } from "./TabSwitch";

const STATUS_LABEL = { PLANNING: "Planning", BOOKED: "Booked", ACTIVE: "On the trip", DONE: "Done" } as const;

export type TripView = {
  token: string;
  data: PublicTrip;
  sample: TripPageData | null;
  theme: Theme;
  pagePath: string; // /t/<share_token>
  previewAs?: string;
  previewTheme?: Theme;
  query: string; // sample mode's ?as=&theme=, kept when switching tabs
};

/** Asked once per request, even though the page and its title both need it. */
export const sharedTrip = cache(getSharedTrip);

/** Everything both tabs need, from the URL. 404s for a token that matches no trip. */
type TripProps = {
  params: Promise<{ token: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export async function loadTrip(props: TripProps): Promise<TripView> {
  const { token } = await props.params;
  const { as, theme: themeParam } = await props.searchParams;
  const data = await sharedTrip(token);
  if (!data) notFound();
  const sample = usingFixtures ? await getFixtureTrip(token) : null;
  const previewAs = sample && typeof as === "string" ? as : undefined;
  // Sample mode can preview a theme with ?theme= (the picker does that instead of saving).
  const previewTheme = sample ? THEMES.find((t) => t.id === themeParam)?.id : undefined;
  const q = new URLSearchParams({ ...(previewAs ? { as: previewAs } : {}), ...(previewTheme ? { theme: previewTheme } : {}) });
  return {
    token, data, sample, previewAs, previewTheme,
    theme: previewTheme ?? themeInfo(data.trip.theme).id,
    pagePath: `/t/${encodeURIComponent(token)}`,
    query: q.size ? `?${q}` : "",
  };
}

/**
 * The frame both tabs share (design canvas: "Trip tab", "Money tab"): the photo with the
 * trip's name on it, Trip | Money, the footer and the floating bar. The money side loads once,
 * in MemberDataProvider, for everything inside.
 */
export function TripShell({ view, tab, children }: { view: TripView; tab: "trip" | "money"; children: ReactNode }) {
  const { data, sample, theme, pagePath, previewAs, previewTheme, query } = view;
  const { trip, members } = data;
  const leader = members.find((m) => m.id === trip.leader_id);
  const soon = countdown(trip.start_date, trip.end_date, new Date().toISOString().slice(0, 10));
  const tabPath = tab === "trip" ? pagePath : `${pagePath}/money`;
  const photo = themeInfo(theme);

  return (
    <MemberDataProvider tripId={trip.id} pagePath={pagePath} tabPath={tabPath} live={!usingFixtures} sample={sample} previewAs={previewAs}>
      <div data-theme={theme} className="relative flex flex-1 flex-col overflow-hidden pb-24">
        <PhotoBackdrop theme={photo} />
        <main id="main" className="relative mx-auto w-full max-w-2xl">
          {sample && <PreviewBar sample={sample} tabPath={tabPath} as={previewAs} theme={previewTheme} />}
          <PhotoHeader theme={photo}>
            <TopBar live={!usingFixtures} className="absolute inset-x-0 top-0" />
            <header className="absolute inset-x-0 top-11 bottom-7.5 flex flex-col items-center justify-center gap-2.5 px-5.5 text-center">
              <div className="flex items-center gap-2.5">
                <span className="rounded-lg bg-white/22 px-2.5 py-1 text-[13px] font-semibold">{STATUS_LABEL[trip.status]}</span>
                {soon && <span className="on-photo text-sm font-medium">{soon}</span>}
              </div>
              <h1 className="wide on-photo text-[38px] tracking-[-0.02em] text-balance">{trip.name}</h1>
              <p className="on-photo flex items-center gap-2 text-[15px] font-medium">
                {leader && <Avatar name={leader.name} index={members.indexOf(leader)} size={24} />}
                {leader ? `Led by ${leader.name}` : "No trip lead yet"}
              </p>
            </header>
            <ThemePicker theme={theme} />
          </PhotoHeader>
          <TabSwitch current={tab} query={query} />
          {children}
        </main>
        <Footer />
      </div>
      <FloatingBar moneyHref={`${pagePath}/money${query}`} />
    </MemberDataProvider>
  );
}
