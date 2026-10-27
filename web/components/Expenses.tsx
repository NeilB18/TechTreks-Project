import { formatMoney } from "@/lib/format";
import type { Expense, Member } from "@/lib/types";
import { Icon, type IconName } from "./Icon";

const CATEGORY_ICON: Record<string, IconName> = { LODGING: "home", TRANSPORT: "car", FOOD: "food", DRINKS: "food", ACTIVITIES: "compass", SETTLEMENT: "wallet" };

const CATEGORY_LABEL: Record<string, string> = {
  LODGING: "Lodging",
  TRANSPORT: "Transport",
  FOOD: "Food",
  DRINKS: "Drinks",
  ACTIVITIES: "Activities",
  OTHER: "Other",
  SETTLEMENT: "Payback",
};

export function Expenses({ expenses, members, currency }: { expenses: Expense[]; members: Member[]; currency: string }) {
  const name = (id: string) => members.find((m) => m.id === id)?.name ?? id;
  if (expenses.length === 0) {
    return <p className="empty-state m-5">No expenses logged yet.</p>;
  }
  return (
    <ul className="divide-y divide-line">
      {[...expenses].reverse().map((e) => {
        const people = Object.keys(e.shares);
        const foreign = e.original_currency !== currency;
        return (
          <li key={e.expense_id} className="flex items-start gap-3 px-5 py-4">
            <span className="expense-icon"><Icon name={CATEGORY_ICON[e.category] ?? "receipt"} size={16} /></span>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold">{e.description}</p>
              <p className="mt-1 text-[10px] leading-relaxed text-muted">
                {CATEGORY_LABEL[e.category] ?? e.category} · paid by {name(e.paid_by)}
                {e.category === "SETTLEMENT"
                  ? ` to ${people.map(name).join(", ")}`
                  : ` · split ${people.length === 1 ? `with ${name(people[0])}` : `${people.length} ways`}`}
              </p>
              {e.refunded_cents > 0 && (
                <p className="mt-1 text-[10px] text-good">{formatMoney(e.refunded_cents, currency)} refunded</p>
              )}
            </div>
            <div className="shrink-0 text-right">
              <p className="text-xs font-semibold tabular-nums">{formatMoney(e.amount_cents, currency)}</p>
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
