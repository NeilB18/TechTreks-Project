"use client";

import type { ReactNode } from "react";

import { Avatars } from "@/components/Avatars";
import { CalendarIcon, HomeIcon, PeopleIcon, PinIcon, PlusIcon } from "@/components/Icons";
import { formatDayRange, listNames, mapsSearchUrl, tripLength } from "@/lib/format";
import { tripCalendar } from "@/lib/ics";
import type { PublicTrip } from "@/lib/types";

import { useMemberData } from "./MemberData";

/**
 * The trip's details under the tabs: dates (with Add to calendar), the place, where you're
 * staying (people on the trip only: an address belongs behind sign-in), and who's going.
 */
export function Details({ data }: { data: PublicTrip }) {
  const { trip, members } = data;
  const active = members.filter((m) => m.active);
  const dates = formatDayRange(trip.start_date, trip.end_date);
  return (
    <section aria-label="Details" className="flex flex-col px-5 pt-3">
      <Row icon={<CalendarIcon />} title={dates ?? "Dates not picked yet"}
        sub={dates ? tripLength(trip.start_date, trip.end_date) : "Ask @tripbot to start a poll in the chat"}>
        {trip.start_date && <AddToCalendar data={data} />}
      </Row>
      <Row icon={<PinIcon />} title={trip.destination ?? "Destination not picked yet"}
        sub={trip.destination ? null : "The theme changes once you pick one"} />
      <Stay destination={trip.destination} />
      <Row icon={<PeopleIcon />} title={`${active.length} going`} sub={listNames(active.map((m) => m.name)) || null}>
        {active.length > 0 && (
          <Avatars names={active.map((m) => m.name)} colorIndexes={active.map((m) => members.indexOf(m))} max={5} />
        )}
      </Row>
    </section>
  );
}

function Row({ icon, title, sub, children }: { icon: ReactNode; title: string; sub?: string | null; children?: ReactNode }) {
  return (
    <div className="flex items-center gap-3.5 py-2.5">
      <span className="flex-none text-soft">{icon}</span>
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="font-bold">{title}</span>
        {sub && <span className="text-sm text-muted">{sub}</span>}
      </span>
      {children}
    </div>
  );
}

function Stay({ destination }: { destination: string | null }) {
  const { state } = useMemberData();
  // Where the group is staying, as they told the bot ("Freehand Miami, 2727 Indian Creek Dr").
  const lodging = state.step === "ready" ? state.data.detail.trip.lodging : null;
  if (!lodging) return null;
  return (
    <Row icon={<HomeIcon />} title={lodging} sub="Only people on the trip see this">
      <a
        href={mapsSearchUrl(lodging, destination)}
        target="_blank"
        rel="noreferrer"
        aria-label={`${lodging} on Google Maps`}
        className="btn btn-pill flex-none"
      >
        Maps
      </a>
    </Row>
  );
}

function AddToCalendar({ data }: { data: PublicTrip }) {
  const { trip } = data;
  return (
    <button
      type="button"
      aria-label="Add to calendar"
      className="icon-btn border-[1.5px] border-edge bg-transparent"
      onClick={() => {
        const ics = tripCalendar({
          id: trip.id, name: trip.name, destination: trip.destination, start_date: trip.start_date!,
          end_date: trip.end_date, url: `${window.location.origin}${window.location.pathname}`, activities: data.activities,
        });
        const url = URL.createObjectURL(new Blob([ics], { type: "text/calendar" }));
        const a = document.createElement("a");
        a.href = url;
        a.download = `${trip.name.replace(/[^\w -]+/g, "").trim() || "trip"}.ics`;
        a.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      }}
    >
      <PlusIcon size={18} />
    </button>
  );
}
