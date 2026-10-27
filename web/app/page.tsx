import Link from "next/link";
import Image from "next/image";
import { AppShell } from "@/components/AppShell";
import { Icon } from "@/components/Icon";
import { listFixtureTrips, usingFixtures } from "@/lib/api";

export default async function Home() {
  const trips = (await listFixtureTrips()).sort((a, b) => Number(b.id === "miami-demo") - Number(a.id === "miami-demo"));
  return <AppShell demo={usingFixtures}><main id="main-content" className="workspace-content">
    <div className="mb-7"><p className="eyebrow text-muted">Less logistics. More living.</p><h1 className="display-heading mt-3 text-[42px] sm:text-[52px]">Somewhere good, together.</h1><p className="mt-4 max-w-lg text-sm leading-7 text-muted">All the plans, shared expenses, and people that turn a getaway into a great story.</p></div>
    {usingFixtures ? <><Link href="/trips/miami-demo" className="trip-hero mb-10"><Image src="/coast.svg" width={1000} height={400} alt="" priority className="hero-landscape" /><div className="hero-copy"><p className="eyebrow text-accent">Take a look around</p><h2 className="display-heading mt-3 text-[38px]">A little sunshine awaits.</h2><p className="mt-3 text-xs text-[#596f5e]">Explore the Miami Spring Break demo.</p><span className="mt-6 inline-flex items-center gap-3 rounded-lg bg-accent px-4 py-2.5 text-xs font-medium text-white">Open trip <Icon name="arrow" size={15} /></span></div></Link><div className="mb-5 flex items-center justify-between"><h2 className="panel-title">Explore sample trips</h2><span className="text-[11px] text-muted">{trips.length} trips</span></div><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{trips.map((t) => <Link key={t.id} href={`/trips/${t.id}`} className="trip-card"><span className="stat-icon mb-5"><Icon name="compass" /></span><h3 className="font-semibold">{t.name}</h3><p className="mt-2 text-xs text-muted">Plans, expenses & the whole crew</p><span className="section-link mt-6">Explore trip <Icon name="arrow" size={14} /></span></Link>)}</div></> : <div className="panel max-w-xl p-8"><span className="stat-icon mb-5"><Icon name="compass" /></span><h2 className="panel-title">Your next adventure is in the chat.</h2><p className="mt-3 text-sm leading-7 text-muted">Open the trip link @tripbot shared in your GroupMe chat to find your plans, expenses, and crew.</p></div>}
  </main></AppShell>;
}
