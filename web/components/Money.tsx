"use client";

import { useState } from "react";

import { Avatar } from "@/components/Avatars";
import { BudgetForm } from "@/components/BudgetForm";
import { CheckIcon, LockIcon, UndoIcon } from "@/components/Icons";
import { useMemberData } from "@/components/trip/MemberData";
import { PayRow } from "@/components/trip/YourMoney";
import { formatMoney, paidLine, timeAgo, warningText } from "@/lib/format";
import { useNow } from "@/lib/now";
import type { BudgetStatus, Member, MyTrip } from "@/lib/types";

// The Money tab for people on the trip (design canvas: Final designs, "Money tab"): settle up for
// the whole group, everyone's budgets, and everything spent, newest first. What you owe is netted
// across every expense, so amounts are never called "your share of" anything; the list only says
// what each expense was for you ("You: $400" or "Not in it").

const CATEGORY: Record<string, string> = {
  LODGING: "Staying", TRANSPORT: "Getting around", FOOD: "Food", DRINKS: "Drinks",
  ACTIVITIES: "Things to do", OTHER: "Other",
};

type Fmt = (cents: number) => string;

export function Money({ data }: { data: MyTrip }) {
  const { detail } = data;
  const { trip, members } = detail;
  const money: Fmt = (c) => formatMoney(c, trip.base_currency);
  const name = (id: string) => members.find((m) => m.id === id)?.name ?? id;
  const index = (id: string) => Math.max(0, members.findIndex((m) => m.id === id));

  return (
    <div className="flex flex-col">
      <p className="mx-5 mt-3.5 flex items-center gap-2 text-[13px] text-muted">
        <LockIcon size={14} stroke={2} />
        Only people on the trip see this tab. Signed in as {name(data.person_id)}.
      </p>
      <SettleUp data={data} money={money} name={name} index={index} />
      <Budgets data={data} money={money} name={name} index={index} />
      <Spent data={data} money={money} name={name} index={index} />
    </div>
  );
}

type Helpers = { data: MyTrip; money: Fmt; name: (id: string) => string; index: (id: string) => number };

function SettleUp({ data, money, name, index }: Helpers) {
  const { detail, balances, person_id: me } = data;
  const payments = balances.suggested_payments;
  const youPay = payments.filter((p) => p.from === me);
  const youGet = payments.filter((p) => p.to === me);
  const others = payments.filter((p) => p.from !== me && p.to !== me);
  const sent = detail.expenses.filter((e) => e.category === "SETTLEMENT");
  const who = (id: string) => (id === me ? "You" : name(id));
  const whom = (id: string) => (id === me ? "you" : name(id));

  return (
    <section id="settle-up" aria-labelledby="settle-up-h" className="flex scroll-mt-4 flex-col gap-2.5 px-3.5 pt-5.5">
      <h2 id="settle-up-h" className="wide mx-1.5 text-xl">Settle up</h2>
      {payments.length === 0 && (
        <div className="card flex items-center gap-3 p-[18px]">
          <span aria-hidden="true" className="avatar size-[42px] bg-[rgb(155_230_170/0.18)] text-[#9be6aa]"><CheckIcon size={20} stroke={2.4} /></span>
          <span className="text-lg font-bold">Everyone&rsquo;s settled up</span>
        </div>
      )}
      {(youPay.length > 0 || youGet.length > 0) && (
        <div className="card overflow-hidden">
          {youPay.map((p, i) => (
            <PayRow key={p.to} p={p} first={i === 0} data={data} money={money} who={name(p.to)} whoIndex={index(p.to)} me={name(me)} />
          ))}
          {youGet.length > 0 && (
            <ul className={`flex flex-col px-[18px] py-2 ${youPay.length ? "border-t border-line" : ""}`}>
              {youGet.map((p) => (
                <li key={p.from} className="flex items-center gap-3 py-2.5">
                  <Avatar name={name(p.from)} index={index(p.from)} size={30} />
                  <span className="flex-1">{name(p.from)} pays you</span>
                  <span className="font-bold tabular-nums">{money(p.amount_cents)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      {(others.length > 0 || sent.length > 0) && (
        <div className="mx-1.5 mt-2 flex flex-col">
          <h3 className="mb-1 font-bold">{youPay.length || youGet.length ? "The rest of the group" : "Who pays who"}</h3>
          <ul>
            {others.map((p) => (
              <li key={`${p.from}-${p.to}`} className="flex items-center gap-3 border-t border-line py-2.5 text-[15px]">
                <Avatar name={name(p.from)} index={index(p.from)} size={30} />
                <span className="flex-1">{name(p.from)} pays {name(p.to)}</span>
                <span className="font-bold tabular-nums">{money(p.amount_cents)}</span>
              </li>
            ))}
            {sent.map((e) => (
              <li key={e.expense_id} className="flex items-center gap-3 border-t border-line py-2.5 text-[15px] text-muted">
                <span aria-hidden="true" className="avatar size-[30px] bg-fill text-ink"><CheckIcon size={15} stroke={2.2} /></span>
                <span className="flex-1">{who(e.paid_by)} sent {Object.keys(e.shares).map(whom).join(", ")}</span>
                <span className="tabular-nums">{money(e.amount_cents)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function Budgets({ data, money, name, index }: Helpers) {
  const { detail, budget: mine, person_id: me } = data;
  const { trip, members } = detail;
  const [editing, setEditing] = useState(false);
  const all = data.budgets ?? {};
  const rest = members.filter((m) => m.active && m.id !== me);
  const mineSet = !!mine?.budget_set && mine.total_cents != null;

  return (
    <section id="budgets" aria-labelledby="budgets-h" className="flex scroll-mt-4 flex-col gap-1.5 px-5 pt-7.5">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id="budgets-h" className="wide text-xl">Budgets</h2>
        {mine && !editing && (
          <button type="button" onClick={() => setEditing(true)} className="btn btn-pill">
            {mineSet ? "Change mine" : "Set mine"}
          </button>
        )}
      </div>
      {editing && <EditMine data={data} onDone={() => setEditing(false)} />}
      {trip.group_budget_cents != null && (
        <p className="text-sm text-muted">The group&rsquo;s budget is {money(trip.group_budget_cents)} each.</p>
      )}
      <ul>
        {mine && <MyBudgetRow b={mine} me={members.find((m) => m.id === me)} money={money} index={index(me)} />}
        {rest.map((m) => (
          <OtherBudgetRow key={m.id} m={m} b={all[m.id]} money={money} name={name} index={index(m.id)} />
        ))}
      </ul>
      <p className="text-[13px] leading-[1.45] text-muted">
        Everyone on the trip can see budgets, and @tripbot posts changes in the group.
      </p>
    </section>
  );
}

function EditMine({ data, onDone }: { data: MyTrip; onDone: () => void }) {
  return (
    <div className="card my-2 p-[18px]">
      <MoneyForm data={data} onDone={onDone} />
    </div>
  );
}

// BudgetForm needs the trip id, sample mode and reload: they come from the page's money data.
function MoneyForm({ data, onDone }: { data: MyTrip; onDone: () => void }) {
  const { tripId, preview, reload } = useMemberData();
  const b = data.budget;
  return (
    <BudgetForm
      tripId={tripId}
      currentCents={b?.budget_set ? b.total_cents ?? null : null}
      preview={preview}
      onSaved={() => { onDone(); reload(); }}
      onCancel={onDone}
    />
  );
}

function Bar({ used, total, mine, label }: { used: number; total: number; mine: boolean; label: string }) {
  const pct = Math.min(100, Math.max(0, (used / Math.max(total, 1)) * 100));
  const over = used > total;
  return (
    <div role="img" aria-label={label} className={`overflow-hidden rounded-full bg-white/14 ${mine ? "h-2" : "h-[5px]"}`}>
      <div
        className={`h-full rounded-full ${over ? "bg-warn" : mine ? "bg-accent" : "bg-white/60"}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

function MyBudgetRow({ b, me, money, index }: { b: BudgetStatus; me?: Member; money: Fmt; index: number }) {
  const set = b.budget_set && b.total_cents != null;
  const total = b.total_cents ?? 0;
  const used = b.spent_cents + b.planned_cents;
  const left = b.remaining_after_planned_cents ?? total - used;
  const paid = paidLine(b, money);
  return (
    <li className="flex flex-col gap-2 py-3">
      <div className="flex items-center gap-3">
        <Avatar name={me?.name ?? "You"} index={index} size={30} />
        <span className="flex-1 font-bold">You</span>
        <span className="text-[15px] font-semibold tabular-nums">{set ? `${money(used)} of ${money(total)}` : "No budget yet"}</span>
      </div>
      {set && (
        <>
          <Bar used={used} total={total} mine label={`${money(used)} of your ${money(total)} budget spent or planned`} />
          <p className="text-sm text-muted tabular-nums">
            {money(b.spent_cents)} spent and {money(b.planned_cents)} planned.{" "}
            {left < 0 ? `${money(-left)} over.` : `${money(left)} left.`}
          </p>
          {paid && <p className="text-sm text-muted tabular-nums">{paid}</p>}
        </>
      )}
      {b.warnings.map((w, i) => (
        <p key={i} className="text-sm font-semibold text-warn">{warningText(w)}</p>
      ))}
    </li>
  );
}

function OtherBudgetRow({ m, b, money, name, index }: {
  m: Member; b?: BudgetStatus; money: Fmt; name: (id: string) => string; index: number;
}) {
  const total = b?.total_cents ?? m.budget_cents ?? null;
  const used = b ? b.spent_cents + b.planned_cents : null;
  return (
    <li className="flex flex-col gap-2 border-t border-line py-3">
      <div className="flex items-center gap-3">
        <Avatar name={name(m.id)} index={index} size={30} />
        <span className="flex-1 text-[15px] font-semibold">{name(m.id)}</span>
        <span className="text-sm text-muted tabular-nums">
          {total == null ? "No budget yet" : used != null ? `${money(used)} of ${money(total)}` : money(total)}
        </span>
      </div>
      {total != null && used != null && (
        <Bar used={used} total={total} mine={false} label={`${name(m.id)}: ${money(used)} of ${money(total)}`} />
      )}
    </li>
  );
}

type Row = {
  key: string;
  at: string;
  order: number;
  icon: { person: string } | "payment" | "refund";
  title: string;
  sub: string;
  amount: string;
  you?: string;
};

function Spent({ data, money, name, index }: Helpers) {
  const { detail, person_id: me } = data;
  const currency = detail.trip.base_currency;
  const now = useNow();
  const when = (iso: string) => (now === null ? "" : timeAgo(iso, now));
  const who = (id: string) => (id === me ? "You" : name(id));
  const whom = (id: string) => (id === me ? "you" : name(id));

  const rows: Row[] = detail.expenses.map((e, i): Row => {
    if (e.category === "SETTLEMENT") {
      return { key: e.expense_id, at: e.created_at, order: i, icon: "payment",
        title: `${who(e.paid_by)} sent ${Object.keys(e.shares).map(whom).join(", ")}`, sub: "Payment", amount: money(e.amount_cents) };
    }
    const people = Object.keys(e.shares).length;
    const sub = [
      CATEGORY[e.category] ?? "Other",
      `${who(e.paid_by)} paid, split ${people === 1 ? "1 way" : `${people} ways`}`,
      e.original_currency !== currency ? `${formatMoney(e.original_amount, e.original_currency)} originally` : null,
      e.refunded_cents > 0 ? `${money(e.refunded_cents)} back` : null,
    ].filter(Boolean).join(". ");
    const mine = e.shares[me];
    return { key: e.expense_id, at: e.created_at, order: i, icon: { person: e.paid_by }, title: e.description, sub,
      amount: money(e.amount_cents), you: mine ? `You: ${money(mine)}` : "Not in it" };
  });
  (detail.refunds ?? []).forEach((r, i) => {
    const expense = detail.expenses.find((e) => e.expense_id === r.expense_id);
    const back = r.per_person[me];
    rows.push({ key: `refund-${r.id}`, at: r.created_at, order: detail.expenses.length + i, icon: "refund",
      title: `Refund: ${expense?.description ?? "an expense"}`,
      sub: [r.note, `Back to ${Object.keys(r.per_person).length} people`].filter(Boolean).join(". "),
      amount: money(r.amount_cents), you: back ? `You: ${money(back)} back` : "Not in it" });
  });
  rows.sort((a, b) => b.at.localeCompare(a.at) || b.order - a.order);

  return (
    <section id="spent" aria-labelledby="spent-h" className="flex scroll-mt-4 flex-col gap-1.5 px-5 pt-7.5">
      <h2 id="spent-h" className="wide text-xl">Everything spent</h2>
      {rows.length === 0 ? (
        <p className="text-[15px] leading-[1.45] text-muted">
          Nothing spent yet. When someone pays, they tell the bot: &ldquo;@tripbot I paid $80 for groceries.&rdquo;
        </p>
      ) : (
        <>
          <p className="mb-1 text-sm text-muted">Every expense and payment from the chat, newest first.</p>
          <ol>
            {rows.map((r) => (
              <li key={r.key} className="flex items-center gap-3 border-t border-line py-3">
                {typeof r.icon === "object" ? (
                  <Avatar name={name(r.icon.person)} index={index(r.icon.person)} size={36} />
                ) : (
                  <span aria-hidden="true" className="avatar size-9 bg-fill text-ink">
                    {r.icon === "payment" ? <CheckIcon size={17} stroke={2.2} /> : <UndoIcon size={17} />}
                  </span>
                )}
                <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <span className="text-[15px] font-semibold">{r.title}</span>
                  <span className="text-[13px] text-muted">
                    {r.sub}
                    {when(r.at) && `, ${when(r.at)}`}
                  </span>
                </span>
                <span className="flex flex-col items-end gap-0.5 text-right">
                  <span className="text-[15px] font-bold tabular-nums">{r.amount}</span>
                  {r.you && <span className="text-[13px] whitespace-nowrap text-muted tabular-nums">{r.you}</span>}
                </span>
              </li>
            ))}
          </ol>
        </>
      )}
    </section>
  );
}
