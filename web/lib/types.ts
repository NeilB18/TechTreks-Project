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
  planning_notes?: string | null; // interests and pace, for itinerary drafts
  page_url?: string | null; // the trip page, <TRIP_PAGE_URL>/t/<share_token> (full trip only)
  lodging?: Lodging | null; // not shown on the page yet: an address belongs behind sign-in
  home_city?: string | null; // where the group flies from
};

export type Lodging = { name: string; address: string; lat: number; lon: number; maps_url: string };

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
  lat?: number | null;
  lon?: number | null;
  verified?: boolean | null; // null: never checked on the map (added by hand)
  maps_url?: string; // only in the full trip, for stops from an itinerary draft
  kind?: "food" | "activity" | "night" | null; // null: not a place (a flight, check-in...)
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

export type TripDetail = {
  trip: TripInfo;
  members: Member[];
  category_opt_outs: [string, string][];
  activities: Activity[];
  expenses: Expense[];
  ideas?: Idea[];
};

// Places the group wants to do but hasn't put on a day (up to 20), checked on the map when saved.
export type Idea = {
  idea_id: string;
  name: string;
  kind: "food" | "activity" | "night";
  location?: string | null;
  verified?: boolean | null;
  maps_url?: string;
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

export type TripPageData = { detail: TripDetail; balances: Balances };

// What anyone with the trip's link sees (GET /api/share/<share_token>, backend/trips/public.py):
// the overview and itinerary. No expenses, balances, budgets, group budget, handles or lodging.
export type PublicTrip = {
  trip: Pick<TripInfo, "id" | "name" | "status" | "destination" | "start_date" | "end_date" | "target_break" | "base_currency" | "leader_id">;
  members: Pick<Member, "id" | "name" | "active">[];
  activities: Activity[];
  ideas: Pick<Idea, "idea_id" | "name" | "kind" | "location">[];
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
