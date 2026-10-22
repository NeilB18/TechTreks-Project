"""In-memory data model. Mirrors specs.md; the Django models in Phase 3 copy these fields.

All money is integer cents. Expense/Refund amounts are stored in the trip's base
currency, with the original amount, currency and FX rate kept alongside.
"""

from dataclasses import dataclass, field

CATEGORIES = ["LODGING", "TRANSPORT", "FOOD", "DRINKS", "ACTIVITIES", "OTHER", "SETTLEMENT"]
STATUSES = ["PLANNING", "BOOKED", "ACTIVE", "DONE"]
# Decision types the group can route through the leader at onboarding (no default).
APPROVAL_TYPES = ["trip_changes", "member_changes", "itinerary_saves", "refunds_deletes"]


@dataclass
class Person:
    id: str
    name: str
    chat_user_id: str
    payment_handle: str | None = None
    active: bool = True  # False after remove_member; past splits still count


@dataclass
class Budget:
    owner_id: str
    total_cents: int
    limits: dict[str, int] = field(default_factory=dict)  # Category -> cents


@dataclass
class Expense:
    id: str
    paid_by: str
    amount_cents: int  # base currency
    original_amount: int
    original_currency: str
    fx_rate: float
    description: str
    category: str
    splits: dict[str, int]  # person_id -> base-currency cents, sums to amount_cents
    created_at: str
    source_message: str = ""


@dataclass
class Refund:
    id: str
    expense_id: str
    amount_cents: int  # base currency
    original_amount: int
    currency: str
    note: str
    per_person: dict[str, int]  # same ratio as the expense's splits
    created_at: str


@dataclass
class Activity:
    id: str
    name: str
    location: str | None = None
    start: str | None = None  # ISO date or datetime
    end: str | None = None
    est_cost_cents: int | None = None
    cost_is_per_person: bool = True
    attendees: list[str] = field(default_factory=list)
    important: bool = False
    booking_url: str | None = None
    expense_id: str | None = None


@dataclass
class Poll:
    id: str
    question: str
    options: list[str]
    votes: dict[str, str] = field(default_factory=dict)  # person_id -> option
    closes_at: str | None = None
    is_open: bool = True


@dataclass
class Reminder:
    id: str
    message: str
    due_at: str
    audience: list[str] | str  # list of person_ids, or "all"
    sent: bool = False
    created_by: str = "agent"  # "agent" | "system"


@dataclass
class Trip:
    id: str
    name: str
    status: str = "PLANNING"
    destination: str | None = None
    start_date: str | None = None  # ISO date
    end_date: str | None = None
    target_break: str | None = None
    base_currency: str = "USD"
    group_budget: int | None = None  # per-person cents, the tier the leader locked in
    leader_id: str | None = None
    leader_approval: list[str] = field(default_factory=list)  # subset of APPROVAL_TYPES
    auto_log_mode: str | None = None  # picked at onboarding; no default
    members: dict[str, Person] = field(default_factory=dict)
    budgets: dict[str, Budget] = field(default_factory=dict)  # private
    exclusions: set[tuple[str, str]] = field(default_factory=set)  # (person_id, category)
    expenses: list[Expense] = field(default_factory=list)
    refunds: list[Refund] = field(default_factory=list)
    activities: list[Activity] = field(default_factory=list)
    polls: list[Poll] = field(default_factory=list)
    reminders: list[Reminder] = field(default_factory=list)
    itinerary_drafts: dict[str, list[dict]] = field(default_factory=dict)

    def active_member_ids(self) -> list[str]:
        return [p.id for p in self.members.values() if p.active]
