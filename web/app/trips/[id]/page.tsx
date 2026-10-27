import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Image from "next/image";
import { AppShell } from "@/components/AppShell";
import { Icon } from "@/components/Icon";
import { Balances } from "@/components/Balances";
import { BudgetPanel } from "@/components/BudgetPanel";
import { Expenses } from "@/components/Expenses";
import { Itinerary } from "@/components/Itinerary";
import { getTripPage, usingFixtures } from "@/lib/api";
import { formatDateRange, formatMoney } from "@/lib/format";

export async function generateMetadata(props: PageProps<"/trips/[id]">): Promise<Metadata> {
  const { id } = await props.params;
  const data = await getTripPage(id);
  return { title: data ? `${data.detail.trip.name} · TechTreks` : "Trip not found" };
}
const STATUS_LABEL = { PLANNING: "In the making", BOOKED: "Booked & ready", ACTIVE: "On the trip", DONE: "In the memory books" } as const;

export default async function TripPage(props: PageProps<"/trips/[id]">) {
  const { id } = await props.params;
  const data = await getTripPage(id);
  if (!data) notFound();
  const { detail, balances } = data;
  const { trip, members } = detail;
  const active = members.filter((m) => m.active);
  const dates = formatDateRange(trip.start_date, trip.end_date);
  const spent = detail.expenses.filter((e) => e.category !== "SETTLEMENT").reduce((sum, e) => sum + e.amount_cents - e.refunded_cents, 0);
  const tripDays = trip.start_date && trip.end_date ? Math.round((Date.parse(trip.end_date) - Date.parse(trip.start_date)) / 86400000) + 1 : null;
  return <AppShell tripName={trip.name} demo={usingFixtures}>
    <main id="main-content" className="workspace-content">
      <div id="overview" className="mb-6 flex items-end justify-between gap-3"><div><p className="eyebrow text-muted">The group chat, organized.</p><h1 className="mt-2 text-[27px] font-semibold tracking-[-1px]">Your trip at a glance</h1></div><a className="section-link mb-1" href="#itinerary">See the plan <Icon name="arrow" size={15} /></a></div>
      <section className="trip-hero" aria-label="Trip overview">
        <Image src="/coast.svg" alt="" width={1000} height={400} className="hero-landscape" priority />
        <div className="hero-copy"><span className="status-pill"><span className="status-dot" />{STATUS_LABEL[trip.status]}</span><h2 className="display-heading mt-4 text-[38px] sm:text-[48px]">{trip.name}</h2><p className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-[#596f5e]"><span className="flex items-center gap-1.5"><Icon name="pin" size={14} />{trip.destination || "Destination to be decided"}</span><span className="flex items-center gap-1.5"><Icon name="calendar" size={14} />{dates || "Dates to be decided"}</span></p><div className="mt-5 flex items-center gap-3"><div className="avatar-stack">{active.slice(0, 6).map((m) => <span key={m.id} className="avatar" title={m.name}>{m.name.slice(0, 1)}</span>)}</div><span className="text-[11px] text-[#596f5e]">{active.length} people. One great trip.</span></div></div>
      </section>
      <dl className="stat-grid">
        <div className="stat-card"><div><dt className="text-[11px] text-muted">Group spending</dt><dd className="stat-value mt-2 text-[27px] font-semibold tracking-[-1px] tabular-nums">{formatMoney(spent, trip.base_currency)}</dd><p className="mt-1 text-[10px] text-muted">Across {detail.expenses.filter((e) => e.category !== "SETTLEMENT").length} shared expenses</p></div><span className="stat-icon"><Icon name="wallet" /></span></div>
        <div className="stat-card"><div><dt className="text-[11px] text-muted">Group budget / person</dt><dd className="stat-value mt-2 text-[27px] font-semibold tracking-[-1px] tabular-nums">{trip.group_budget_cents != null ? formatMoney(trip.group_budget_cents, trip.base_currency) : "To decide"}</dd><p className="mt-1 text-[10px] text-muted">The group’s agreed target</p></div><span className="stat-icon"><Icon name="leaf" /></span></div>
        <div className="stat-card"><div><dt className="text-[11px] text-muted">On the itinerary</dt><dd className="stat-value mt-2 text-[27px] font-semibold tracking-[-1px]">{detail.activities.length}<span className="ml-1.5 text-xs font-normal tracking-normal text-muted">plans</span></dd><p className="mt-1 text-[10px] text-muted">{tripDays && tripDays > 0 ? `${tripDays} days of making memories` : "Room for a little adventure"}</p></div><span className="stat-icon"><Icon name="calendar" /></span></div>
      </dl>
      <div className="dashboard-grid"><div className="min-w-0 space-y-6">
        <section className="panel" aria-labelledby="itinerary"><div className="panel-header"><div><h2 id="itinerary" className="panel-title">The plan</h2><p className="panel-subtitle">A little structure. Plenty of room for spontaneity.</p></div><Icon name="calendar" size={19} /></div><div className="panel-body"><Itinerary activities={detail.activities} trip={trip} /></div><div className="border-t border-line bg-[#fbfcf8] px-6 py-3.5 text-[11px] text-muted">Plans change. Ask <span className="font-medium text-accent">@tripbot</span> to update your itinerary.</div></section>
        <section className="panel" aria-labelledby="expenses"><div className="panel-header"><div><h2 id="expenses" className="panel-title">Shared expenses</h2><p className="panel-subtitle">Less mental math. More enjoying the moment.</p></div><span className="rounded-md bg-background px-2.5 py-1 text-[10px] text-muted">{detail.expenses.length} logged</span></div><Expenses expenses={detail.expenses} members={members} currency={trip.base_currency} /></section>
      </div><aside className="dashboard-aside space-y-6" aria-label="Trip finances and members">
        <section className="panel" aria-labelledby="balances"><div className="panel-header"><div><h2 id="balances" className="panel-title">Square things up</h2><p className="panel-subtitle">A few payments. A clean slate.</p></div><Icon name="wallet" size={19} /></div><div className="panel-body"><Balances balances={balances} members={members} tripName={trip.name} /></div><p className="border-t border-line px-6 py-3 text-[10px] leading-relaxed text-muted">Suggested payments simplify what the group owes. Record a payment with @tripbot once it’s sent.</p></section>
        <section id="budget"><BudgetPanel tripId={trip.id} live={!usingFixtures} currency={trip.base_currency} /></section>
        <section className="panel" aria-labelledby="crew"><div className="panel-header"><div><h2 id="crew" className="panel-title">Your travel people</h2><p className="panel-subtitle">The crew that makes the trip.</p></div><span className="text-xs text-muted">{active.length}</span></div><ul className="space-y-4 p-5">{members.map((m) => <li key={m.id} className="flex items-center gap-3"><span className="avatar" aria-hidden="true">{m.name.slice(0, 1)}</span><span className="flex-1 text-xs font-medium">{m.name}</span><span className="text-[10px] text-muted">{!m.active ? "Not joining" : m.id === trip.leader_id ? "Trip lead" : "Coming along"}</span></li>)}</ul></section>
      </aside></div>
      <footer className="mt-9 flex items-center justify-between gap-3 border-t border-line pt-5 text-[10px] text-muted"><span>Made for the memories, not the spreadsheets.</span><span className="flex items-center gap-1.5"><Icon name="compass" size={13} />TechTreks</span></footer>
    </main>
  </AppShell>;
}
