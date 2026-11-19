import type { TripDetail } from "./types";

// "Latest" on the Trip tab: the newest money news, from data the money API already returns.
// For now only money (expenses, refunds, payments marked as sent), so only people on the trip see
// it. Plan news ("Leo added Boat tour") needs the backend to record who added what.

export type LatestItem = {
  key: string;
  who: string; // person id, for their initial and colour
  kind: "paid" | "refund" | "sent";
  cents: number;
  to?: string; // sent: who it went to
  what?: string; // paid / refund: the expense's description
  at: string; // ISO time
  order: number; // tie-break for equal times: later in the list is newer
};

export function latestItems(detail: TripDetail, max = 4): LatestItem[] {
  const items: LatestItem[] = [];
  detail.expenses.forEach((e, i) => {
    if (e.category === "SETTLEMENT") {
      const to = Object.keys(e.shares)[0];
      items.push({ key: e.expense_id, who: e.paid_by, kind: "sent", cents: e.amount_cents, to, at: e.created_at, order: i });
    } else {
      items.push({ key: e.expense_id, who: e.paid_by, kind: "paid", cents: e.amount_cents, what: e.description,
        at: e.created_at, order: i });
    }
  });
  (detail.refunds ?? []).forEach((r, i) => {
    const expense = detail.expenses.find((e) => e.expense_id === r.expense_id);
    if (!expense) return;
    // The refund goes back to the people who shared the expense; it's news for whoever paid it.
    items.push({ key: `refund-${r.id}`, who: expense.paid_by, kind: "refund", cents: r.amount_cents,
      what: expense.description, at: r.created_at, order: detail.expenses.length + i });
  });
  return items.sort((a, b) => b.at.localeCompare(a.at) || b.order - a.order).slice(0, max);
}
