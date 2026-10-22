"""Business rules that are still placeholders or will move to the real backend.

Each one is a single function so it can be swapped without touching the store.
"""

import random

# --- Budget warnings -------------------------------------------------------
# PLACEHOLDER: specs.md says the real logic is "more complex than < 10% of total".
# Romir to define it; Examples 3 and 8 are blocked on this.
WARN_FRACTION = 0.10


def budget_warnings(total_cents: int, limits: dict[str, int],
                    spent_by_cat: dict[str, int], planned_by_cat: dict[str, int]) -> list[str]:
    warnings = []
    spent = sum(spent_by_cat.values())
    planned = sum(planned_by_cat.values())
    left = total_cents - spent - planned
    if left < 0:
        warnings.append(f"Over total budget by {fmt_usd(-left)} including planned activities")
    elif left < total_cents * WARN_FRACTION:
        warnings.append("Total budget under 10% remaining")
    for cat, limit in sorted(limits.items()):
        cat_left = limit - spent_by_cat.get(cat, 0) - planned_by_cat.get(cat, 0)
        if cat_left < 0:
            warnings.append(f"{cat} over limit by {fmt_usd(-cat_left)} including planned activities")
        elif cat_left < limit * WARN_FRACTION:
            warnings.append(f"{cat} under 10% remaining")
    return warnings


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
