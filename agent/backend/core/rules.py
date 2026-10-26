"""Business rules that are still placeholders or will move to the real backend.

Each one is a single function so it can be swapped without touching the store.
Money rules (splits, balances, settling up, budget warnings) live in trip_model/.
Multi-currency is post-MVP (the MVP is USD-only); the FX table stays so it keeps working.
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


def fmt_usd(cents: int) -> str:
    return f"${cents / 100:,.2f}".replace(".00", "")
