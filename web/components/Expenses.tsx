import { formatMoney } from "@/lib/format";
import type { Expense, Member } from "@/lib/types";

const CATEGORY_LABEL: Record<string, string> = {
  LODGING: "🏠 Lodging",
  TRANSPORT: "🚗 Transport",
  FOOD: "🍽️ Food",
  DRINKS: "🍹 Drinks",
  ACTIVITIES: "🎟️ Activities",
  OTHER: "Other",
  SETTLEMENT: "💸 Payback",
};

export function Expenses({ expenses, members, currency }: { expenses: Expense[]; members: Member[]; currency: string }) {
  const name = (id: string) => members.find((m) => m.id === id)?.name ?? id;
  if (expenses.length === 0) {
    return <p className="text-sm text-muted">No expenses logged yet.</p>;
  }
  return (
    <ul className="divide-y divide-line rounded-xl border border-line bg-card">
      {[...expenses].reverse().map((e) => {
        const people = Object.keys(e.splits);
        const foreign = e.original_currency !== currency;
        return (
          <li key={e.expense_id} className="flex items-start justify-between gap-3 p-3">
            <div className="min-w-0">
              <p className="font-medium">{e.description}</p>
              <p className="text-sm text-muted">
                {CATEGORY_LABEL[e.category] ?? e.category} · paid by {name(e.paid_by)}
                {e.category === "SETTLEMENT"
                  ? ` to ${people.map(name).join(", ")}`
                  : ` · split ${people.length === 1 ? `with ${name(people[0])}` : `${people.length} ways`}`}
              </p>
              {e.refunded_cents > 0 && (
                <p className="text-sm text-good">{formatMoney(e.refunded_cents, currency)} refunded</p>
              )}
            </div>
            <div className="shrink-0 text-right">
              <p className="font-semibold tabular-nums">{formatMoney(e.amount_cents, currency)}</p>
              {foreign && (
                <p className="text-xs text-muted tabular-nums">
                  {formatMoney(e.original_amount, e.original_currency)}
                </p>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
