import Link from "next/link";
import type { ReactNode } from "react";
import { Icon, type IconName } from "./Icon";

export function AppShell({ children, tripName, demo = false }: { children: ReactNode; tripName?: string; demo?: boolean }) {
  const links: { label: string; href: string; icon: IconName }[] = tripName
    ? [{ label: "Overview", href: "#overview", icon: "grid" }, { label: "Itinerary", href: "#itinerary", icon: "calendar" }, { label: "Expenses", href: "#expenses", icon: "receipt" }, { label: "Settle up", href: "#balances", icon: "wallet" }, { label: "The crew", href: "#crew", icon: "people" }]
    : [{ label: "My trips", href: "/", icon: "compass" }];
  return <div className="app-shell">
    <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:bg-white focus:p-3">Skip to content</a>
    <aside className="sidebar">
      <Link href="/" className="brand" aria-label="TechTreks home"><span className="brand-mark"><Icon name="compass" size={23} /></span>techtreks<span className="text-[#c6d69a]">.</span></Link>
      <p className="sidebar-caption">Your next adventure</p>
      <nav aria-label="Main navigation">{links.map((link, i) => <Link key={link.label} href={link.href} className={`side-link ${i === 0 ? "active" : ""}`}><Icon name={link.icon} />{link.label}</Link>)}{tripName && <Link href="/" className="side-link"><Icon name="compass" />All trips</Link>}</nav>
      <div className="sidebar-footer"><div className="bot-note"><div className="flex items-center gap-2 text-xs font-semibold"><Icon name="spark" size={16} />A little less planning.</div><p>A lot more being there. Ask @tripbot in your group chat to handle the details.</p></div><p className="mt-6 flex items-center gap-2 text-[10px] text-[#b3c5b8]"><Icon name="leaf" size={13} />Good trips start together.</p></div>
    </aside>
    <div className="workspace"><header className="topbar"><div className="flex min-w-0 items-center gap-3"><Link href="/" className="topbar-label shrink-0">My trips</Link>{tripName && <><span className="text-line">/</span><span className="truncate text-xs font-medium">{tripName}</span></>}</div><span className="shrink-0 rounded-full border border-line px-3 py-1.5 text-[10px] text-muted">{demo ? "Demo trip" : "Your trip, together"}</span></header>{children}</div>
  </div>;
}
