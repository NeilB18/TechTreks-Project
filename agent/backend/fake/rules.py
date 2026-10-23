"""Business rules that are still placeholders or will move to the real backend.

Each one is a single function so it can be swapped without touching the store.
"""

import random

# --- Budget warnings -------------------------------------------------------
# Romir's rules (Oct 23, 2026). All private: they only ever go to that person's DM.
# A change (expense, edit, refund, dropout) warns only about lines it newly crosses,
# so nobody gets the same warning twice; get_budget_status shows everything current.
CHECKPOINTS = (0.5, 0.8, 1.0)  # share of the total budget used
CATEGORY_LINES = (0.9, 1.0)  # share of a category limit used (spent + planned)
PACE_MARGIN = 0.20  # warn when % of budget used is this far ahead of % of the trip done
PACE_MIN_USED = 0.20  # ...but not before 20% of the budget is used


def trip_progress(start: str | None, end: str | None, now: str) -> tuple[int, int] | None:
    """(day, days) while the trip is happening, e.g. (2, 5) on its second day; otherwise None."""
    from datetime import date
    if not (start and end):
        return None
    s, e, d = date.fromisoformat(start[:10]), date.fromisoformat(end[:10]), date.fromisoformat(now[:10])
    if not s <= d <= e:
        return None
    return (d - s).days + 1, (e - s).days + 1


def budget_flags(total: int, limits: dict[str, int], spent_by_cat: dict[str, int],
                 planned_by_cat: dict[str, int], progress: tuple[int, int] | None,
                 upcoming: list[tuple[str, int]], currency: str = "USD") -> dict[str, str]:
    """Every warning line this person is currently past, as {flag: DM-ready message}.

    upcoming: (activity name, per-person cents) for their unpaid upcoming activities, priciest
    first; used so over-budget messages can suggest what to cut.
    """
    money = lambda c: fmt_money(c, currency)  # noqa: E731
    spent, planned = sum(spent_by_cat.values()), sum(planned_by_cat.values())
    plans = ", ".join(f"{name} ~{money(c)}" for name, c in upcoming[:3])
    flags: dict[str, str] = {}
    if total > 0:
        used = spent / total
        for line in CHECKPOINTS:
            if used >= line:
                if line == 1.0:
                    msg = (f"You're {money(spent - total)} over your {money(total)} budget ({money(spent)} spent)."
                           if spent > total else f"You've used your whole {money(total)} budget.")
                    if plans:
                        msg += f" Coming up: {plans}."
                else:
                    msg = f"You've used {round(used * 100)}% of your budget ({money(spent)} of {money(total)})."
                flags[f"total_{round(line * 100)}"] = msg
        if planned and spent <= total < spent + planned:
            flags["planned_over"] = (f"Your upcoming plans ({plans}) would put you "
                                     f"{money(spent + planned - total)} over your {money(total)} budget.")
        # Compare whole percentages so 60% used on a 40%-done trip counts as exactly 20 points.
        if progress and used >= PACE_MIN_USED and \
                round(used * 100) - round(progress[0] / progress[1] * 100) >= round(PACE_MARGIN * 100):
            day, days = progress
            left_per_day = max(total - spent, 0) // max(days - day, 1)
            flags["pace"] = (f"You've used {round(used * 100)}% of your budget and it's only day {day} of {days}. "
                             f"That leaves about {money(left_per_day)} a day for the rest of the trip.")
    for cat, limit in sorted(limits.items()):
        if limit <= 0:
            continue
        cat_used = spent_by_cat.get(cat, 0) + planned_by_cat.get(cat, 0)
        name = cat.title()
        if cat_used > limit:
            flags[f"cat_{cat}_100"] = f"{name}: {money(cat_used - limit)} over your {money(limit)} limit (including plans)."
        elif cat_used >= limit * CATEGORY_LINES[0]:
            flags[f"cat_{cat}_90"] = (f"{name}: {money(cat_used)} of your {money(limit)} limit used "
                                      f"(including plans), {money(limit - cat_used)} left.")
    return flags


def newly_crossed(before: dict[str, str], after: dict[str, str]) -> list[str]:
    """Messages for flags that weren't set before. Only the highest new total checkpoint is kept."""
    new = {k: v for k, v in after.items() if k not in before}
    totals = sorted(k for k in new if k.startswith("total_"))
    for k in totals[:-1]:
        del new[k]
    if any(k.endswith("_100") and k.startswith("cat_") for k in new):
        for k in [k for k in new if k.startswith("cat_") and k.endswith("_90")]:
            if k.replace("_90", "_100") in new:
                del new[k]
    return list(new.values())


def current_warnings(flags: dict[str, str]) -> list[str]:
    """What get_budget_status shows: everything current, but only the highest total checkpoint."""
    totals = sorted(k for k in flags if k.startswith("total_"))
    return [v for k, v in flags.items() if not (k in totals[:-1])]


# --- FX ---------------------------------------------------------------------
# PLACEHOLDER: fixed table until the FX provider is chosen (asking mentor).
USD_PER_UNIT = {
    "USD": 1.0,
    "MXN": 0.0556,
    "EUR": 1.08,
    "GBP": 1.27,
    "CAD": 0.73,
}


def fx_rate(from_ccy: str, to_ccy: str) -> float:
    if from_ccy not in USD_PER_UNIT or to_ccy not in USD_PER_UNIT:
        raise ValueError(f"Unsupported currency: {from_ccy if from_ccy not in USD_PER_UNIT else to_ccy}")
    return USD_PER_UNIT[from_ccy] / USD_PER_UNIT[to_ccy]


def convert(amount_cents: int, from_ccy: str, to_ccy: str) -> tuple[int, float]:
    rate = fx_rate(from_ccy, to_ccy)
    return round(amount_cents * rate), rate


# --- Travel-tip tiers ---------------------------------------------------------
PRESET_MULTIPLIERS = [0.5, 0.75, 1, 1.25, 1.5, 2]


def tier_price(average_cents: int, multiplier: float) -> int:
    """Multiplier x group average, rounded to the whole dollar."""
    return round(average_cents * multiplier / 100) * 100


# --- Splitting --------------------------------------------------------------
def split_equal(amount_cents: int, people: list[str], rng: random.Random) -> dict[str, int]:
    """Equal split; leftover cents go to randomly chosen people (one each)."""
    base, leftover = divmod(amount_cents, len(people))
    splits = {p: base for p in people}
    for p in rng.sample(people, leftover):
        splits[p] += 1
    return splits


def split_proportional(amount_cents: int, weights: dict[str, int], rng: random.Random) -> dict[str, int]:
    """Split in the same ratio as `weights` (used for refunds and FX'd exact amounts)."""
    total = sum(weights.values())
    shares = {p: amount_cents * w // total for p, w in weights.items()}
    leftover = amount_cents - sum(shares.values())
    for p in rng.sample([p for p, w in weights.items() if w > 0], leftover):
        shares[p] += 1
    return shares


def fmt_usd(cents: int) -> str:
    return f"${cents / 100:,.2f}".replace(".00", "")


SYMBOLS = {"USD": "$", "MXN": "MX$", "EUR": "€", "GBP": "£", "CAD": "CA$"}


def fmt_money(cents: int, currency: str = "USD") -> str:
    """Chat-ready amount, e.g. 3336 -> "$33.36", 180000 MXN -> "MX$1,800"."""
    text = f"{SYMBOLS.get(currency, currency + ' ')}{abs(cents) / 100:,.2f}".replace(".00", "")
    return "-" + text if cents < 0 else text
