// Shapes returned by the backend's get_trip and get_balances tools
// (agent/backend/core/engine.py, served by GET /api/trips/<id> and /balances).
// Budgets are shared with everyone on the trip, so members carry their total.

export type Member = {
  id: string;
  name: string;
  handle: string | null;
  active: boolean;
  budget_set: boolean;
  budget_cents?: number | null;
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
  theme?: Theme | null; // the trip page's look; null: Sunset
  page_url?: string | null; // the trip page, <TRIP_PAGE_URL>/t/<share_token> (full trip only)
  lodging?: string | null; // where the group is staying, as they wrote it; members only (an address)
};

// snow and desert: the website can show them; the bot saves them once the bot-themes PR merges.
export type Theme = "sunset" | "night_swim" | "campfire" | "snow" | "desert";

// Parts of the day a plan can be in (trip_model/activity.py SLOTS). A plan in a slot has no clock time.
export type Slot = "morning" | "lunch" | "afternoon" | "dinner" | "night";

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
  // start is just the day ("2027-03-15") unless the group gave a clock time; slot is set when they named one.
  slot?: Slot | null;
  from_idea?: boolean; // came off the ideas list
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

// Money paid back to the people who shared an expense (a cancelled concert, a deposit returned).
export type Refund = {
  id: string;
  expense_id: string;
  amount_cents: number;
  note?: string | null;
  per_person: Record<string, number>;
  created_at: string;
};

export type TripDetail = {
  trip: TripInfo;
  members: Member[];
  category_opt_outs: [string, string][];
  activities: Activity[];
  expenses: Expense[];
  refunds?: Refund[];
  ideas?: Idea[];
};

// Things the group wants to do but hasn't put on a day (up to 20).
export type Idea = {
  idea_id: string;
  name: string;
  est_cost_cents?: number | null;
  suggested_by?: string | null;
};

// Suggested payments are netted across the group, so someone may pay a person
// other than the one who paid for their stuff.
export type Payment = { from: string; to: string; amount_cents: number; handle: string | null };

export type Balances = {
  net_balances: Record<string, number>;
  suggested_payments: Payment[];
  currency: string;
};

// budgets: everyone's budget status by person id (active members), for the Budgets card.
export type TripPageData = { detail: TripDetail; balances: Balances; budgets?: Record<string, BudgetStatus> };

// What anyone with the trip's link sees (GET /api/share/<share_token>, backend/trips/public.py):
// the overview and itinerary. No expenses, balances, budgets, group budget, handles or lodging.
export type PublicTrip = {
  trip: Pick<TripInfo, "id" | "name" | "status" | "destination" | "start_date" | "end_date" | "target_break" | "base_currency" | "leader_id" | "theme">;
  members: Pick<Member, "id" | "name" | "active">[];
  activities: Activity[];
  ideas: Pick<Idea, "idea_id" | "name" | "est_cost_cents">[];
};

// The money side, for a signed-in member of the trip (GET /api/me/trips/<id>).
export type MyTrip = TripPageData & { person_id: string; budget: BudgetStatus | null };

// Signed-in API (/api/me/*, proxied to Django). The caller's own linked trip member.
export type Me =
  | { signed_in: false; login_url: string }
  | {
      signed_in: true;
      email: string;
      // share_token: the trip page is /t/<share_token>.
      people: { trip_id: string; trip_name: string; share_token: string; person_id: string; name: string }[];
    };

export type BudgetStatus = {
  person_id: string;
  budget_set: boolean;
  total_cents?: number;
  spent_cents: number;
  remaining_cents?: number;
  planned_cents: number;
  remaining_after_planned_cents?: number;
  // Roger's engine sends strings ("DRINKS under 10% remaining"); objects are accepted too in case that changes.
  warnings: BudgetWarning[];
};

export type BudgetWarning = string | { category?: string; message?: string; text?: string };

export type MyBudget = {
  person_id: string;
  name: string;
  budget: BudgetStatus;
};

export type LinkCode = { code: string; expires_at: string; instructions: string };

// One row of My trips (GET /api/me/trips). net_cents: + you're owed, - you owe.
export type TripCard = {
  trip_id: string;
  name: string;
  share_token: string;
  status: TripInfo["status"];
  destination: string | null;
  start_date: string | null;
  end_date: string | null;
  theme: Theme | null;
  going: number;
  net_cents: number;
};
