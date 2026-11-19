"use client";

import type { ReactNode } from "react";

import { Avatar, Avatars } from "@/components/Avatars";
import { CalendarIcon, ChevronIcon, HomeIcon, PeopleIcon, PinIcon, PlusIcon } from "@/components/Icons";
import { Sheet, useSheet } from "@/components/Sheet";
import { formatDayRange, listNames, mapsSearchUrl, tripLength } from "@/lib/format";
import { tripCalendar } from "@/lib/ics";
import type { PublicTrip } from "@/lib/types";

import { useMemberData } from "./MemberData";

/**
 * The trip's details under the tabs: dates (with Add to calendar), the place, where you're
 * staying (people on the trip only: an address belongs behind sign-in), and who's going (tap it for
 * everyone on the trip).
 */
export function Details({ data }: { data: PublicTrip }) {
  const { trip, members } = data;
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
      <Going members={members} leaderId={trip.leader_id} />
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

/**
 * "4 going" with everyone's initials. Tapping it opens a sheet listing everyone on the trip: the
 * leader, you (when you're signed in and on the trip), and anyone who has left. Names only: it's on
 * the public page, so no handles or money.
 */
function Going({ members, leaderId }: { members: PublicTrip["members"]; leaderId: string | null }) {
  const { ref, open, close } = useSheet();
  const { state } = useMemberData();
  const me = state.step === "ready" ? state.data.person_id : null;
  const active = members.filter((m) => m.active);
  const gone = members.filter((m) => !m.active);
  const names = listNames(active.map((m) => m.name)) || null;
  const person = (m: PublicTrip["members"][number]) => (
    <li key={m.id} className={`flex items-center gap-3 py-2.5 ${m.active ? "" : "opacity-60"}`}>
      <Avatar name={m.name} index={members.indexOf(m)} size={36} />
      <span className="min-w-0 flex-1 truncate font-semibold">{m.name}</span>
      {m.id === me && <span className="rounded-lg bg-fill px-2 py-0.5 text-[13px] font-semibold">You</span>}
      {m.id === leaderId && <span className="rounded-lg bg-accent px-2 py-0.5 text-[13px] font-bold text-accent-ink">Leader</span>}
    </li>
  );
  return (
    <>
      <button
        type="button"
        onClick={open}
        aria-haspopup="dialog"
        disabled={members.length === 0}
        className="flex w-full cursor-pointer items-center gap-3.5 py-2.5 text-left disabled:cursor-default"
      >
        <span className="flex-none text-soft"><PeopleIcon /></span>
        <span className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="font-bold">{active.length} going</span>
          {names && <span className="text-sm text-muted">{names}</span>}
        </span>
        {active.length > 0 && (
          <Avatars names={active.map((m) => m.name)} colorIndexes={active.map((m) => members.indexOf(m))} max={5} />
        )}
        {members.length > 0 && <span aria-hidden="true" className="flex-none -rotate-90 text-soft"><ChevronIcon size={18} /></span>}
      </button>
      <Sheet dialogRef={ref} onClose={close} labelledBy="going-title">
        <span className="flex flex-col gap-px">
          <h2 id="going-title" className="wide text-[22px]">Who&rsquo;s going</h2>
          <span className="text-[15px] text-muted">
            {active.length === 1 ? "1 person" : `${active.length} people`} on this trip
          </span>
        </span>
        <ul className="flex max-h-[50vh] flex-col divide-y divide-line overflow-y-auto">{active.map(person)}</ul>
        {gone.length > 0 && (
          <>
            <h3 className="pt-1 text-sm font-bold text-muted">No longer going</h3>
            <ul className="flex flex-col divide-y divide-line">{gone.map(person)}</ul>
          </>
        )}
        <p className="text-[13px] leading-[1.45] text-muted">
          Someone missing? They&rsquo;re added the first time they @tripbot in the group chat.
        </p>
        <button type="button" onClick={close} className="btn btn-line">Done</button>
      </Sheet>
    </>
  );
}
