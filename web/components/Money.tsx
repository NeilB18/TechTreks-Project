import { Avatars } from "@/components/Avatars";
import { CopyButton } from "@/components/CopyButton";
import { formatMoney, handleKind, listNames, payLink, warningText } from "@/lib/format";
import type { BudgetStatus, Expense, Member, MyTrip, Payment } from "@/lib/types";

// The money side of the trip page for a signed-in member, in style D from the design canvas:
// the same cards and caps labels as the itinerary, a big "You owe" headline on top.

const GROUPS: { label: string; categories: string[] }[] = [
  { label: "Staying", categories: ["LODGING"] },
  { label: "Getting around", categories: ["TRANSPORT"] },
  { label: "Food and drinks", categories: ["FOOD", "DRINKS"] },
  { label: "Things to do", categories: ["ACTIVITIES"] },
  { label: "Other", categories: ["OTHER"] },
];

export function Money({ data }: { data: MyTrip }) {
  const { detail, balances } = data;
  const { trip, members } = detail;
  const currency = trip.base_currency;
  const me = data.person_id;
  const money = (cents: number) => formatMoney(cents, currency);
  const name = (id: string) => members.find((m) => m.id === id)?.name ?? id;
  const colorOf = (id: string) => Math.max(0, members.findIndex((m) => m.id === id));

  const payments = balances.suggested_payments;
  const youPay = payments.filter((p) => p.from === me);
  const youGet = payments.filter((p) => p.to === me);
  const others = payments.filter((p) => p.from !== me && p.to !== me);
  const sent = detail.expenses.filter((e) => e.category === "SETTLEMENT");

  return (
    <div className="flex flex-col">
      <Headline youPay={youPay} youGet={youGet} money={money} name={name} colorOf={colorOf} />

      <section aria-labelledby="settle-up" className="flex scroll-mt-4 flex-col gap-3.5 pt-7">
        <h2 id="settle-up" className="display text-[28px]">Settle up</h2>
        {payments.length === 0 && sent.length === 0 && (
          <p className="card px-[18px] py-4 text-muted">Everyone&rsquo;s settled up.</p>
        )}
        {youPay.length > 0 && (
          <article className="card px-[18px] pt-[18px] pb-1.5">
            <span className="label-caps">You pay</span>
            <ul>
              {youPay.map((p) => (
                <PayRow key={p.to} p={p} who={name(p.to)} money={money} tripName={trip.name} />
              ))}
            </ul>
          </article>
        )}
        {youGet.length > 0 && (
          <article className="card px-[18px] pt-[18px] pb-1.5">
            <span className="label-caps">You get</span>
            <ul className="mt-2">
              {youGet.map((p) => (
                <li key={p.from} className="flex justify-between gap-3 border-t border-line py-3">
                  <span>{name(p.from)} pays you</span>
                  <span className="font-semibold tabular-nums">{money(p.amount_cents)}</span>
                </li>
              ))}
            </ul>
          </article>
        )}
        {(others.length > 0 || sent.length > 0) && (
          <article className="card px-[18px] pt-[18px] pb-1.5">
            <span className="label-caps">{me ? "The rest of the group" : "Who pays who"}</span>
            <ul className="mt-2">
              {others.map((p) => (
                <li key={`${p.from}-${p.to}`} className="flex justify-between gap-3 border-t border-line py-3">
                  <span>{name(p.from)} pays {name(p.to)}</span>
                  <span className="font-semibold tabular-nums">{money(p.amount_cents)}</span>
                </li>
              ))}
              {sent.map((e) => (
                <li key={e.expense_id} className="flex justify-between gap-3 border-t border-line py-3 text-muted">
                  <span>
                    {e.paid_by === me ? "You" : name(e.paid_by)} sent {Object.keys(e.shares).map((id) => (id === me ? "you" : name(id))).join(", ")}
                  </span>
                  <span className="tabular-nums">{money(e.amount_cents)}</span>
                </li>
              ))}
            </ul>
          </article>
        )}
      </section>

      <section aria-labelledby="budgets" className="flex scroll-mt-4 flex-col gap-3.5 pt-7">
        <h2 id="budgets" className="display text-[28px]">Budgets</h2>
        <Budgets data={data} money={money} name={name} />
      </section>

      <section aria-labelledby="spent" className="flex scroll-mt-4 flex-col gap-3.5 pt-7">
        <h2 id="spent" className="display text-[28px]">Spent</h2>
        <Spent expenses={detail.expenses} me={me} money={money} name={name} currency={currency} />
      </section>

      {trip.lodging && (
        <section aria-labelledby="staying" className="flex flex-col gap-3.5 pt-7">
          <h2 id="staying" className="display text-[28px]">Where you&rsquo;re staying</h2>
          <article className="card flex items-center justify-between gap-3 p-[18px]">
            <div className="min-w-0">
              <p className="font-bold">{trip.lodging.name}</p>
              <p className="text-sm text-muted">{trip.lodging.address}</p>
            </div>
            <a href={trip.lodging.maps_url} target="_blank" rel="noreferrer" className="btn btn-outline shrink-0">
              Maps
            </a>
          </article>
        </section>
      )}
    </div>
  );
}

type Fmt = (cents: number) => string;

function Headline({ youPay, youGet, money, name, colorOf }: {
  youPay: Payment[]; youGet: Payment[]; money: Fmt; name: (id: string) => string; colorOf: (id: string) => number;
}) {
  const sum = (ps: Payment[]) => ps.reduce((s, p) => s + p.amount_cents, 0);
  const owe = youPay.length > 0;
  const people = owe ? youPay.map((p) => p.to) : youGet.map((p) => p.from);
  return (
    <header className="flex flex-col gap-3">
      <h2 className="display text-[44px]">
        {owe ? "You owe " : youGet.length ? "You’re owed " : "All settled"}
        {people.length > 0 && (
          <span className={`${owe ? "text-hot" : "text-good"} tabular-nums`}>{money(sum(owe ? youPay : youGet))}</span>
        )}
      </h2>
      {people.length > 0 && (
        <div className="flex items-center gap-2.5">
          <Avatars names={people.map(name)} colorIndexes={people.map(colorOf)} />
          <span className="text-[15px] text-muted">{owe ? "to" : "from"} {listNames(people.map(name))}</span>
        </div>
      )}
      <nav aria-label="Money sections" className="mt-1.5 flex flex-wrap gap-2">
        {[["#settle-up", "Settle up"], ["#budgets", "Budgets"], ["#spent", "Spent"]].map(([href, label]) => (
          <a key={href} href={href} className="btn min-h-11 bg-surface px-3.5 text-sm text-ink">
            {label}
          </a>
        ))}
      </nav>
    </header>
  );
}

function PayRow({ p, who, money, tripName }: { p: Payment; who: string; money: Fmt; tripName: string }) {
  const link = payLink(p.handle, p.amount_cents, tripName);
  return (
    <li className="flex flex-col gap-2.5 border-t border-line py-3 first:mt-2">
      <div className="flex items-baseline justify-between gap-3">
        <div className="min-w-0">
          <p className="text-base font-bold">{who}</p>
          {p.handle && <p className="truncate text-sm text-muted">{p.handle}</p>}
        </div>
        <span className="text-lg font-bold tabular-nums">{money(p.amount_cents)}</span>
      </div>
      <div className="flex gap-2">
        {link?.kind === "venmo" && (
          <a href={link.href} target="_blank" rel="noreferrer" className="btn btn-pop flex-1">
            Pay on Venmo
          </a>
        )}
        {link?.kind === "other" && (
          <CopyButton text={link.handle} label={`Copy ${handleKind(link.handle)}`} className="btn btn-pop flex-1" />
        )}
        {!link && <p className="text-sm text-muted">No payment handle yet. {who} can tell @tripbot theirs.</p>}
      </div>
    </li>
  );
}

function Budgets({ data, money, name }: { data: MyTrip; money: Fmt; name: (id: string) => string }) {
  const { detail, budget: mine } = data;
  const { trip, members } = detail;
  const all = data.budgets ?? {};
  const rest = members.filter((m) => m.active && m.id !== data.person_id);
  return (
    <article className="card p-[18px]">
      {trip.group_budget_cents != null && (
        <p className="mb-3 text-sm text-muted">
          Group budget: <span className="font-bold text-ink tabular-nums">{money(trip.group_budget_cents)} each</span>
        </p>
      )}
      {mine && <MyBudget b={mine} money={money} />}
      <ul className={mine ? "mt-3.5" : ""}>
        {rest.map((m) => (
          <OtherBudget key={m.id} m={m} b={all[m.id]} money={money} name={name} />
        ))}
      </ul>
    </article>
  );
}

function MyBudget({ b, money }: { b: BudgetStatus; money: Fmt }) {
  if (!b.budget_set || b.total_cents == null) {
    return (
      <div>
        <span className="label-caps">You</span>
        <p className="mt-1.5 font-bold">You haven&rsquo;t set a budget</p>
        <p className="text-sm text-muted">Tell @tripbot in the group chat, like &ldquo;my budget is $800&rdquo;.</p>
      </div>
    );
  }
  const total = b.total_cents;
  const left = b.remaining_after_planned_cents ?? total - b.spent_cents - b.planned_cents;
  const pct = (c: number) => `${Math.min(100, Math.max(0, (c / Math.max(total, 1)) * 100))}%`;
  return (
    <div>
      <span className="label-caps">You</span>
      <p className="mt-2 flex items-baseline gap-2">
        <span className="display text-[34px] tabular-nums">{money(Math.abs(left))}</span>
        <span className="text-muted">{left < 0 ? "over" : "left"} of {money(total)}</span>
      </p>
      <div className="mt-2.5 flex h-3 overflow-hidden rounded-full bg-ground" aria-hidden="true">
        <span className="bg-hot" style={{ width: pct(b.spent_cents) }} />
        <span className="bg-pop" style={{ width: pct(b.planned_cents) }} />
      </div>
      <p className="mt-2 flex gap-4 text-sm text-muted tabular-nums">
        <span>{money(b.spent_cents)} spent</span>
        <span>{money(b.planned_cents)} planned</span>
      </p>
      {b.warnings.length > 0 && (
        <ul className="mt-2.5 flex flex-col gap-1">
          {b.warnings.map((w, i) => (
            <li key={i} className="text-sm font-semibold text-warn">{warningText(w)}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function OtherBudget({ m, b, money, name }: { m: Member; b?: BudgetStatus; money: Fmt; name: (id: string) => string }) {
  const total = b?.total_cents ?? m.budget_cents ?? null;
  return (
    <li className="flex justify-between gap-3 border-t border-line py-2.5 first:border-t-0 first:pt-0">
      <span>{name(m.id)}</span>
      <span className="text-muted tabular-nums">
        {total == null ? "not set" : b ? `${money(b.spent_cents)} of ${money(total)}` : money(total)}
      </span>
    </li>
  );
}

function Spent({ expenses, me, money, name, currency }: {
  expenses: Expense[]; me: string; money: Fmt; name: (id: string) => string; currency: string;
}) {
  const spending = expenses.filter((e) => e.category !== "SETTLEMENT");
  if (spending.length === 0) {
    return (
      <p className="card px-[18px] py-4 text-muted">
        Nothing spent yet. When someone pays, they tell the bot: &ldquo;@tripbot I paid $80 for groceries.&rdquo;
      </p>
    );
  }
  const known = new Set(GROUPS.flatMap((g) => g.categories));
  const groups = GROUPS.map((g) => ({
    label: g.label,
    items: spending.filter((e) => g.categories.includes(e.category) || (g.label === "Other" && !known.has(e.category))),
  })).filter((g) => g.items.length);
  return (
    <>
      {groups.map((g) => (
        <article key={g.label} className="card px-[18px] pt-[18px] pb-1.5">
          <div className="flex items-baseline justify-between">
            <span className="label-caps">{g.label}</span>
            {me && <span className="text-sm text-muted">your share</span>}
          </div>
          <ul className="mt-2">
            {[...g.items].reverse().map((e) => {
              const people = Object.keys(e.shares).length;
              const share = e.shares[me];
              const bits = [
                `${e.paid_by === me ? "You" : name(e.paid_by)} paid ${money(e.amount_cents)}`,
                e.original_currency !== currency ? formatMoney(e.original_amount, e.original_currency) : null,
                `${people} ${people === 1 ? "person" : "people"}`,
                e.refunded_cents > 0 ? `${money(e.refunded_cents)} back` : null,
              ].filter(Boolean);
              return (
                <li key={e.expense_id} className="flex justify-between gap-3 border-t border-line py-3">
                  <div className="min-w-0">
                    <p className="font-bold">{e.description}</p>
                    <p className="text-sm text-muted">{bits.join(" · ")}</p>
                  </div>
                  {me ? (
                    share ? (
                      <span className="font-bold tabular-nums">{money(share)}</span>
                    ) : (
                      <span className="text-sm text-muted">not in it</span>
                    )
                  ) : (
                    <span className="font-bold tabular-nums">{money(e.amount_cents)}</span>
                  )}
                </li>
              );
            })}
          </ul>
        </article>
      ))}
    </>
  );
}
