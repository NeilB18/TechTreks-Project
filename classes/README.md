# Trip Bot — Data Models and Ledger Pseudocode

All money is stored as **integer cents**. Person IDs are dictionary keys. Pseudocode describes behavior, not executable Python. All methods accept structured parameters and do not parse natural language.

## Models

```text
enum Category:
    LODGING, TRANSPORT, FOOD, DRINKS, ACTIVITIES, OTHER, SETTLEMENT

enum TripStatus:
    PLANNING, BOOKED, ACTIVE, DONE

class Person:
    id; name; chat_user_id; payment_handle
    budget: Budget | None                # private to this person
    trips: list[Trip]

class Budget:
    owner_id; total_cents
    limits: dict[Category, int]          # e.g. {DRINKS: 8000}

    remaining(category, expenses) -> int:
        spent = sum of this owner's assigned expense shares in category
        return limits[category] - spent  # if category has a limit

    warning(category, expenses, planned_cents=0) -> bool:
        # planned_cents = this owner's share of planned, unpaid activities
        # only category limits warn; the total is informational
        return remaining(category, expenses) - planned_cents < 0.10 * limits[category]

class Expense:
    id; paid_by: Person; amount_cents; description; category
    splits: dict[person_id, int]         # NET balance DELTAS, not amounts owed
    created_at; source_message

    # Positive: this person is owed money. Negative: this person owes money.
    # Must satisfy sum(splits.values()) == 0.

    split_equal(participant_ids: list[person_id]) -> dict[person_id, int]
    split_custom(shares_cents: dict[person_id, int]) -> dict[person_id, int]
    split_percentage(percents: dict[person_id, number]) -> dict[person_id, int]
    _calculate_net_splits(shares_cents: dict[person_id, int]) -> dict[person_id, int]

class Activity:
    id; name; location; start: datetime; end: datetime
    est_cost_cents; cost_is_per_person: bool
    attendees: list[Person]; important: bool; booking_url
    expense_id | None                   # links plan to real cost once paid

class Poll:
    id; question; options: list[str]
    votes: dict[person_id, str]; closes_at; is_open
    vote(person, option); results() -> dict; winner()

class Reminder:
    message; due_at; audience: list[Person] | "all"
    sent: bool; created_by: "agent" | "system"

class Trip:
    id; name; status: TripStatus
    destination | None; start_date | None; end_date | None
    target_break | None                 # e.g. "spring break", "fall break"
    members: list[Person]
    activities: list[Activity]
    expenses: list[Expense]
    polls: list[Poll]
    reminders: list[Reminder]

    add_member(); add_expense(); add_activity(); add_poll()
    itinerary_by_day() -> dict[date, list[Activity]]
    spent_by_category(person=None) -> dict[Category, int]
    balances() -> dict[person_id, int]
    settlement_plan() -> list[tuple[from_person_id, to_person_id, amount_cents]]
    _greedy_settlements(balances) -> list[tuple[from_person_id, to_person_id, amount_cents]]
    record_settlement(from_person_id, to_person_id, amount_cents, payment_id)
```

## Splitting an expense

**Rule:** A person's net balance change is `amount_paid - share_owed`. The payer does **not** need to be a participant.

```text
Expense._calculate_net_splits(shares_cents):
    require amount_cents >= 0
    require payer ID and all participant IDs are valid
    require all shares >= 0
    require sum(shares_cents.values()) == amount_cents

    deltas = {person_id: -share for each entry in shares_cents}
    deltas[paid_by.id] += amount_cents  # use 0 if payer absent
    remove zero entries (optional)
    require sum(deltas.values()) == 0
    self.splits = deltas
    return deltas

Expense.split_equal(participant_ids):
    require nonempty participant_ids and no duplicate person IDs
    base = amount_cents // count(participant_ids)
    remainder = amount_cents % count(participant_ids)
    assign base cents to each participant ID
    assign 1 extra cent to the first `remainder` IDs in stable ID order
    return _calculate_net_splits(assigned_shares)

Expense.split_custom(shares_cents):
    # Explicit allocation of the *entire* bill, including payer's share if any.
    return _calculate_net_splits(shares_cents)

Expense.split_percentage(percents):
    require all percentages >= 0 and sum to 100%
    compute each exact share = amount_cents * percentage / 100
    floor each share to whole cents
    distribute leftover cents to largest fractional remainders
      (stable ID order to break ties)
    return _calculate_net_splits(whole_cent_shares)
```

Examples (all dollar amounts below; stored values are cents):

| Scenario | X (payer) | Y | Z |
|---|---:|---:|---:|
| X pays $90, X/Y/Z share equally | +$60 | −$30 | −$30 |
| X pays $90, only Y/Z share | +$90 | −$45 | −$45 |
| X pays $17; shares X=$8, Y=$6, Z=$3 | +$9 | −$6 | −$3 |

`split_custom` requires amounts covering the entire expense. If only some shares are specified, the caller must supply the missing allocation before invoking it.

## Balances and recorded payments

There is no bank integration. `settlement_plan()` only recommends payments. After a real-world payment has been confirmed, `record_settlement()` saves it as a `SETTLEMENT` expense. Prefer calculating balances from saved expense deltas rather than updating a separate mutable balance dictionary.

```text
Trip.add_expense(expense):
    validate expense and its zero-sum splits
    save expense once (unique expense ID)
    # SETTLEMENT expenses reduce debt, not trip spending or budget usage.

Trip.balances():
    balance = {member.id: 0 for member in members}
    for expense in expenses:
        for person_id, delta in expense.splits:
            balance[person_id] += delta
    require sum(balance.values()) == 0
    return balance

Trip.record_settlement(from_person_id, to_person_id, amount_cents, payment_id):
    # Call only after an actual off-app payment is confirmed.
    require both IDs belong to trip, are different, and amount_cents > 0
    require payment_id has not already been recorded (idempotency)
    create an Expense with:
        id = payment_id
        paid_by = sender (from_person_id)
        amount_cents = amount_cents
        category = SETTLEMENT
        description = "Payment from sender to recipient"
        splits = {from_person_id: +amount_cents, to_person_id: -amount_cents}
    add_expense(settlement_expense)
    # Balance rises for the sender and falls for the recipient.
    # Do not also add a separate balance adjustment or count it as trip spending.
```

For edits/deletes, recalculate from current saved expenses; do not apply a second delta on top of an old one. Exclude `SETTLEMENT` expenses from `spent_by_category()` and budget calculations.

## Settlement plan (greedy, no overpayments)

**Objective:** Suggest few payments, with every payment going directly from someone who owes to someone who is owed. Nobody pays more than they owe or receives more than they're owed. Balances are netted across the group, so a person may be told to pay someone other than the one who paid for their stuff. This is the approach most expense-splitting apps use: at most `n - 1` payments for `n` people with nonzero balances, not always the fewest possible, and fast for any group size.

```text
Trip.settlement_plan():
    b = balances()
    remove entries with zero balance
    if b is empty: return []
    return self._greedy_settlements(b)

Trip._greedy_settlements(b):
    require sum(b.values()) == 0
    payments = []

    # 1. Exact opposites pay each other directly (one payment clears both).
    for person in stable id order:
        if someone unmatched has exactly -b[person]:
            the one who owes pays the other abs(b[person])
        else:
            mark person unmatched

    # 2. Everyone left: the biggest debtor pays the biggest creditor.
    debtors = max-heap of unmatched people who owe (ties: smaller id first)
    creditors = max-heap of unmatched people who are owed
    while debtors and creditors:
        d = biggest debtor, c = biggest creditor
        amount = min(debt[d], credit[c])
        append (d, c, amount) to payments
        whoever still has money left goes back on their heap

    require each person paid exactly what they owe / received exactly what they're owed
    return payments
```

The settlement plan is **only a suggestion**: do not modify recorded balances when showing it. Call `record_settlement()` only after confirming an off-app payment, then regenerate the plan from updated balances.
