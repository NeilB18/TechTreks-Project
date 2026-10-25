"""Business rules that are still placeholders or will move to the real backend.

Each one is a single function so it can be swapped without touching the store.
Money rules (splits, balances, settling up, budget warnings) come from classes/
through ledger.py.
"""

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
# Equal, exact and percentage splits live in classes/expense.py (see ledger.py).
def split_proportional(amount_cents: int, weights: dict[str, int]) -> dict[str, int]:
    """Split in the same ratio as `weights` (used for refunds and FX'd exact amounts).
    Leftover cents go to the largest remainders, ties in id order, so the same input
    always splits the same way."""
    total = sum(weights.values())
    shares = {p: amount_cents * w // total for p, w in weights.items()}
    leftover = amount_cents - sum(shares.values())
    by_remainder = sorted(sorted(p for p, w in weights.items() if w > 0),
                          key=lambda p: amount_cents * weights[p] % total, reverse=True)
    for p in by_remainder[:leftover]:
        shares[p] += 1
    return shares


def fmt_usd(cents: int) -> str:
    return f"${cents / 100:,.2f}".replace(".00", "")
