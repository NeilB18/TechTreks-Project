"use client";

import Link from "next/link";
import { useState } from "react";

import { Avatar, Avatars } from "@/components/Avatars";
import { BudgetForm } from "@/components/BudgetForm";
import { CopyButton } from "@/components/CopyButton";
import { CheckIcon, CopyIcon, LockIcon } from "@/components/Icons";
import { MarkSent } from "@/components/MarkSent";
import { formatMoney, handleKind, listNames, payLink, warningText } from "@/lib/format";
import type { BudgetStatus, MyTrip, Payment } from "@/lib/types";

import { useMemberData } from "./MemberData";
import { MembersOnly } from "./MembersOnly";

/**
 * "Your money" on the Trip tab (design canvas: "Trip tab" and "Your money card: other states"):
 * who you pay (each with Pay on Venmo, Mark as sent and copy the handle), or what you're owed,
 * or all settled; then your budget with Change. What you owe is netted across every expense by
 * the settle-up math, so it's never tied to one expense. Everyone else gets the sign-in or
 * not-on-this-trip card instead.
 */
export function YourMoney({ moneyHref }: { moneyHref: string }) {
  const { state } = useMemberData();
  return (
    <section aria-labelledby="your-money" className="flex flex-col gap-2.5 px-3.5 pt-6.5">
      <div className="mx-1.5 flex items-baseline justify-between gap-3">
        <h2 id="your-money" className="wide text-xl">Your money</h2>
        {state.step === "ready" && (
          <Link href={moneyHref} className="inline-flex min-h-11 items-center text-[15px] font-semibold underline">See all</Link>
        )}
      </div>
      {state.step === "ready" ? <MoneyCard data={state.data} moneyHref={moneyHref} /> : <MembersOnly />}
    </section>
  );
}

function MoneyCard({ data, moneyHref }: { data: MyTrip; moneyHref: string }) {
  const { detail, balances } = data;
  const { trip, members } = detail;
  const me = data.person_id;
  const money = (c: number) => formatMoney(c, trip.base_currency);
  const name = (id: string) => members.find((m) => m.id === id)?.name ?? id;
  const index = (id: string) => Math.max(0, members.findIndex((m) => m.id === id));
  const youPay = balances.suggested_payments.filter((p) => p.from === me);
  const youGet = balances.suggested_payments.filter((p) => p.to === me);
  const nothingSpent = detail.expenses.length === 0;

  return (
    <div className="card overflow-hidden">
      {youPay.map((p, i) => (
        <PayRow key={p.to} p={p} first={i === 0} data={data} money={money} who={name(p.to)} whoIndex={index(p.to)} me={name(me)} />
      ))}
      {youGet.length > 0 && (
        <div className={`flex flex-col gap-3.5 p-[18px] ${youPay.length ? "border-t border-line" : ""}`}>
          <div className="flex items-center gap-3">
            <Avatars names={youGet.map((p) => name(p.from))} colorIndexes={youGet.map((p) => index(p.from))} max={3} />
            <span className="flex min-w-0 flex-1 flex-col gap-px">
              <span className="text-lg font-bold">You&rsquo;re owed {money(youGet.reduce((s, p) => s + p.amount_cents, 0))}</span>
              <span className="text-sm text-muted">From {listNames(youGet.map((p) => name(p.from)))}</span>
            </span>
          </div>
          {youPay.length === 0 && <Link href={moneyHref} className="btn btn-line">See who owes what</Link>}
        </div>
      )}
      {youPay.length === 0 && youGet.length === 0 && (
        nothingSpent ? (
          <p className="p-[18px] text-[15px] leading-[1.45] text-muted">
            Nothing spent yet. When someone tells @tripbot they paid, it&rsquo;s split here.
          </p>
        ) : (
          <div className="flex items-center gap-3 p-[18px]">
            <span aria-hidden="true" className="avatar size-[42px] bg-[rgb(155_230_170/0.18)] text-[#9be6aa]"><CheckIcon size={20} stroke={2.4} /></span>
            <span className="flex flex-1 flex-col gap-px">
              <span className="text-lg font-bold">You&rsquo;re all settled</span>
              <span className="text-sm text-muted">You don&rsquo;t owe anyone, and nobody owes you.</span>
            </span>
          </div>
        )
      )}
      <YourBudget budget={data.budget} money={money} />
      <p className="flex items-center gap-2 border-t border-line px-[18px] py-2.5 text-[13px] text-muted">
        <LockIcon size={14} stroke={2} />
        Only people on the trip see this. Signed in as {name(me)}.
      </p>
    </div>
  );
}

function PayRow({ p, first, data, money, who, whoIndex, me }: {
  p: Payment; first: boolean; data: MyTrip; money: (c: number) => string; who: string; whoIndex: number; me: string;
}) {
  const { tripId, preview, reload } = useMemberData();
  const trip = data.detail.trip;
  const link = payLink(p.handle, p.amount_cents, trip.name);
  return (
    <div className={`flex flex-col gap-3.5 p-[18px] ${first ? "" : "border-t border-line"}`}>
      <div className="flex items-center gap-3">
        <Avatar name={who} index={whoIndex} />
        <span className="flex min-w-0 flex-1 flex-col gap-px">
          <span className="text-lg font-bold">You owe {who} {money(p.amount_cents)}</span>
          <span className="truncate text-sm text-muted">
            {p.handle ? `${link?.kind === "venmo" ? "Venmo" : "Zelle or other"} ${p.handle}` : `No payment handle yet. ${who} can tell @tripbot.`}
          </span>
        </span>
        {p.handle && (
          <CopyButton
            text={p.handle}
            label={<CopyIcon size={18} />}
            copiedLabel={<CheckIcon size={18} />}
            ariaLabel={`Copy ${who}'s ${link?.kind === "venmo" ? "Venmo" : handleKind(p.handle)}`}
            className="icon-btn"
          />
        )}
      </div>
      <div className="flex gap-2.5">
        {link?.kind === "venmo" && (
          <a href={link.href} target="_blank" rel="noreferrer" className="btn btn-white flex-1 px-3">Pay on Venmo</a>
        )}
        <MarkSent tripId={tripId} to={p.to} who={who} whoIndex={whoIndex} owedCents={p.amount_cents}
          currency={trip.base_currency} preview={preview} onSaved={reload} me={me} />
      </div>
    </div>
  );
}

/** Your budget: what's left (spent and planned both count), Change, and the bar. Also used on the Money tab. */
export function YourBudget({ budget, money, className = "border-t border-line" }: {
  budget: BudgetStatus | null; money: (c: number) => string; className?: string;
}) {
  const { tripId, preview, reload } = useMemberData();
  const [editing, setEditing] = useState(false);
  if (!budget) return null;
  const set = budget.budget_set && budget.total_cents != null;

  if (editing) {
    return (
      <div className={`p-[18px] ${className}`}>
        <BudgetForm tripId={tripId} currentCents={set ? budget.total_cents! : null} preview={preview}
          onSaved={() => { setEditing(false); reload(); }} onCancel={() => setEditing(false)} />
      </div>
    );
  }
  if (!set) {
    return (
      <div className={`flex items-center justify-between gap-3 px-[18px] pt-3.5 pb-4 ${className}`}>
        <span className="flex flex-col gap-px">
          <span className="font-bold">No budget yet</span>
          <span className="text-sm text-muted">@tripbot warns you before you go over</span>
        </span>
        <button type="button" onClick={() => setEditing(true)} className="btn btn-white btn-pill flex-none border-0">Set budget</button>
      </div>
    );
  }
  const total = budget.total_cents!;
  const used = budget.spent_cents + budget.planned_cents;
  const left = budget.remaining_after_planned_cents ?? total - used;
  const pct = Math.min(100, Math.max(0, (used / Math.max(total, 1)) * 100));
  return (
    <div className={`flex flex-col gap-2.5 px-[18px] pt-3.5 pb-4 ${className}`}>
      <div className="flex items-center justify-between gap-3">
        <span className="flex flex-col gap-px">
          <span className="font-bold">Your budget</span>
          <span className="text-sm text-muted tabular-nums">
            {left < 0 ? `${money(-left)} over ${money(total)}` : `${money(left)} left of ${money(total)}`}
          </span>
        </span>
        <button type="button" onClick={() => setEditing(true)} className="btn btn-pill flex-none">Change</button>
      </div>
      <div
        role="img"
        aria-label={`${money(used)} of your ${money(total)} budget spent or planned`}
        className="h-2 overflow-hidden rounded-full bg-white/14"
      >
        <div className={`h-full rounded-full ${left < 0 ? "bg-warn" : "bg-accent"}`} style={{ width: `${pct}%` }} />
      </div>
      {budget.warnings.length > 0 && (
        <ul className="flex flex-col gap-0.5">
          {budget.warnings.map((w, i) => (
            <li key={i} className="text-sm font-semibold text-warn">{warningText(w)}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
