// Shapes returned by the backend's get_trip and get_balances tools
// (agent/backend/core/engine.py, served by GET /api/trips/<id> and /balances).
// Budgets are never part of these.

export type Member = {
  id: string;
  name: string;
  handle: string | null;
  active: boolean;
  budget_set: boolean;
};

export type TripInfo = {
  id: string;
  name: string;
  status: "PLANNING" | "BOOKED" | "ACTIVE" | "DONE";
  destination: string | null;
  start_date: string | null;
  end_date: string | null;
  target_break: string | null;
  base_currency: string;
  group_budget_cents: number | null;
  leader_id: string | null;
  leader_approval: string[];
  auto_log_mode: string | null;
};

export type Activity = {
  activity_id: string;
  name: string;
  location: string | null;
  start: string | null;
  end: string | null;
  est_cost_cents: number | null;
  cost_is_per_person: boolean;
  est_per_person_cents: number | null;
  attendees: string[];
  important: boolean;
  booking_url: string | null;
  expense_id: string | null;
};

export type Expense = {
  expense_id: string;
  description: string;
  category: string;
  paid_by: string;
  amount_cents: number;
  original_amount: number;
  original_currency: string;
  fx_rate: number;
  // What each person owes for this expense (people with no share are left out).
  shares: Record<string, number>;
  // Net change per person: + is owed, - owes; sums to 0.
  splits: Record<string, number>;
  created_at: string;
  refunded_cents: number;
};

export type TripDetail = {
  trip: TripInfo;
  members: Member[];
  category_opt_outs: [string, string][];
  activities: Activity[];
  expenses: Expense[];
};

// Suggested payments are netted across the group, so someone may pay a person
// other than the one who paid for their stuff.
export type Payment = { from: string; to: string; amount_cents: number; handle: string | null };

export type Balances = {
  net_balances: Record<string, number>;
  suggested_payments: Payment[];
  currency: string;
};

export type TripPageData = { detail: TripDetail; balances: Balances };

// Signed-in API (/api/me/*, proxied to Django). Only ever the caller's own data.
export type Me =
  | { signed_in: false; login_url: string }
  | { signed_in: true; email: string; people: { trip_id: string; trip_name: string; person_id: string; name: string }[] };

export type BudgetStatus = {
  person_id: string;
  budget_set: boolean;
  total_cents?: number;
  spent_cents: number;
  remaining_cents?: number;
  planned_cents: number;
  remaining_after_planned_cents?: number;
  warnings: string[];
};

export type MyBudget = {
  person_id: string;
  name: string;
  budget: BudgetStatus;
  notices: { text: string; created_at: string }[];
};

export type LinkCode = { code: string; expires_at: string; instructions: string };
