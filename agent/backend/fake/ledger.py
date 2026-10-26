"""Bridge from the stored trip (models.py) to the money rules in classes/.

The backend keeps its dataclasses as the storage shape (the database mirrors them).
The rules themselves come from classes/: splitting an expense, net balances, the
settle-up plan, paybacks and budget warnings. Category names ("FOOD") become the
Category enum here and nowhere else.

Expense.splits are net changes per person (+ is owed, - owes; they sum to 0).
A person's share of an expense is what they paid minus their net change.
"""

from agent.backend.fake import rules
from agent.backend.fake.models import Expense, Trip
from agent.backend.protocol import ToolError
from classes.budget import Budget as LedgerBudget
from classes.category import Category
from classes.expense import Expense as LedgerExpense
from classes.person import Person as LedgerPerson
from classes.trip import Trip as LedgerTrip


def _person(pid: str, name: str | None = None, chat_user_id: str | None = None,
            payment_handle: str | None = None) -> LedgerPerson:
    return LedgerPerson(pid, name or pid, chat_user_id or pid, payment_handle)


def split(amount_cents: int, paid_by: str, *, people: list[str] | None = None,
          shares: dict[str, int] | None = None, percents: dict[str, float] | None = None) -> dict[str, int]:
    """Net changes for one expense. Pass exactly one of people (equal), shares (exact cents)
    or percents."""
    e = LedgerExpense(None, _person(paid_by), amount_cents, "", None)
    try:
        if people is not None:
            return e.split_equal(people)
        if shares is not None:
            return e.split_custom(shares)
        return e.split_percentage(percents)
    except ValueError as err:
        raise ToolError(str(err)) from err


def shares(e: Expense) -> dict[str, int]:
    """Each person's share of the expense in base cents, before refunds. People with no share are left out."""
    ledger = LedgerExpense(e.id, _person(e.paid_by), e.amount_cents, e.description,
                           Category[e.category], splits=e.splits)
    people = list(e.splits) + ([e.paid_by] if e.paid_by not in e.splits else [])
    return {p: ledger.share_of(p) for p in people if ledger.share_of(p) > 0}


def refunded_by_person(trip: Trip, expense_id: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in trip.refunds:
        if r.expense_id == expense_id:
            for p, c in r.per_person.items():
                out[p] = out.get(p, 0) + c
    return out


def refund_shares(e: Expense, amount_cents: int) -> dict[str, int]:
    """A refund goes back in the same ratio as the original shares."""
    return rules.split_proportional(amount_cents, shares(e))


def _with_refunds(trip: Trip, e: Expense) -> LedgerExpense:
    # A refund lowers what the payer paid by the refund and each person's share by their part of it.
    refunded = refunded_by_person(trip, e.id)
    total = sum(refunded.values())
    splits = dict(e.splits)
    for p, c in refunded.items():
        splits[p] = splits.get(p, 0) + c
    splits[e.paid_by] = splits.get(e.paid_by, 0) - total
    return LedgerExpense(e.id, _person(e.paid_by), e.amount_cents - total, e.description,
                         Category[e.category], splits={p: d for p, d in splits.items() if d})


def ledger_trip(trip: Trip) -> LedgerTrip:
    """The trip as classes/ sees it: every member (removed ones still owe) and every expense,
    refunds applied."""
    lt = LedgerTrip(trip.id, trip.name)
    for p in trip.members.values():
        lt.add_member(_person(p.id, p.name, p.chat_user_id, p.payment_handle))
    for e in trip.expenses:
        lt.add_expense(_with_refunds(trip, e))
    return lt


def net_balances(trip: Trip) -> dict[str, int]:
    return {pid: c for pid, c in ledger_trip(trip).balances().items() if c}


def settle_up(trip: Trip) -> list[tuple[str, str, int]]:
    """Suggested payments (from, to, cents), netted across the group."""
    return ledger_trip(trip).settlement_plan()


def record_payback(trip: Trip, from_person: str, to_person: str, amount_cents: int,
                   payment_id: str) -> LedgerExpense:
    """Validate a real payment and build it as a SETTLEMENT expense (the caller stores it)."""
    try:
        return ledger_trip(trip).record_settlement(from_person, to_person, amount_cents, payment_id)
    except ValueError as err:
        raise ToolError(str(err)) from err


def spent_by_category(trip: Trip, pid: str) -> dict[str, int]:
    """This person's shares by category, refunds applied. Settlements are not spending."""
    expenses = ledger_trip(trip).expenses
    budget = LedgerBudget(pid, 0)
    spent = {c.name: budget.spent(c, expenses) for c in Category if c != Category.SETTLEMENT}
    return {c: v for c, v in spent.items() if v}


def budget_warnings(trip: Trip, pid: str, planned_by_cat: dict[str, int]) -> list[str]:
    """Category limits only: a warning once under 10% of a limit is left, counting planned activities."""
    b = trip.budgets[pid]
    budget = LedgerBudget(pid, b.total_cents, {Category[c]: v for c, v in b.limits.items()})
    expenses = ledger_trip(trip).expenses
    warnings = []
    for cat in sorted(b.limits):
        planned = planned_by_cat.get(cat, 0)
        left = budget.remaining(Category[cat], expenses) - planned
        if left < 0:
            warnings.append(f"{cat} over limit by {rules.fmt_usd(-left)} including planned activities")
        elif budget.warning(Category[cat], expenses, planned):
            warnings.append(f"{cat} under 10% remaining")
    return warnings
